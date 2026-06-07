#!/usr/bin/env python3
"""Pull NWS gridpoint forecasts for active airports and cache raw data locally.

Source:  https://api.weather.gov/points/{lat},{lon}  → then forecast URL
Auth:    None (public), but NWS requires a descriptive User-Agent per their policy.
         NWS_USER_AGENT must come from environment / .env — NOT hardcoded.
Writes:  data/raw/nws_forecasts.json  (per-airport forecast summary)
         data/raw/nws_gridpoints.json (cached gridpoint URLs — reused across runs)
         feed_runs (source_system_id='nws_api')
Doctrine: NWS = Forecast Weather Impact proxy — NOT an official FAA delay forecast.
          Never label NWS output as official FAA delays.

Usage:
  python pull_nws_forecasts.py [--dry-run] [--limit N] [--clear-gridpoint-cache]
"""
from __future__ import annotations
import argparse, os, sys, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from lib_pull import (
    load_env, get_supabase_creds, get_active_airports,
    write_feed_run, http_get_json, save_raw, load_raw, nws_impact, log,
)

NWS_POINTS_URL   = 'https://api.weather.gov/points/{lat},{lon}'
SOURCE_ID        = 'nws_api'
GRIDPOINTS_CACHE = 'nws_gridpoints'
FORECASTS_CACHE  = 'nws_forecasts'
REQUEST_DELAY_S  = 0.5  # Polite delay between NWS calls


def nws_headers(user_agent: str) -> dict:
    return {
        'User-Agent': user_agent,
        'Accept': 'application/geo+json',
    }


def fetch_gridpoint(lat: float, lon: float, user_agent: str) -> str | None:
    """Call the NWS points API and return the forecast URL for this lat/lon."""
    url = NWS_POINTS_URL.format(lat=round(lat, 4), lon=round(lon, 4))
    try:
        data = http_get_json(url, headers=nws_headers(user_agent))
        return data.get('properties', {}).get('forecast')
    except Exception as e:
        log('nws_points_error', {'url': url, 'error': str(e)})
        return None


def fetch_forecast(forecast_url: str, user_agent: str) -> list[dict]:
    """Fetch forecast periods from a NWS gridpoint forecast URL."""
    data = http_get_json(forecast_url, headers=nws_headers(user_agent))
    return data.get('properties', {}).get('periods', [])


def summarise_forecast(periods: list[dict]) -> dict:
    """Derive forecast_impact fields from NWS forecast periods.

    NWS output is a proxy — not an official FAA delay forecast.
    Labels must follow source doctrine.
    """
    if not periods:
        return {}

    daytime = [p for p in periods if p.get('isDaytime', True)]
    nighttime = [p for p in periods if not p.get('isDaytime', False)]

    today = daytime[0] if daytime else periods[0]
    tonight = nighttime[0] if nighttime else (periods[1] if len(periods) > 1 else {})

    high_f = today.get('temperature') if today.get('temperatureUnit') == 'F' else None
    low_f  = tonight.get('temperature') if tonight.get('temperatureUnit') == 'F' else None

    short = today.get('shortForecast', '')
    detailed = today.get('detailedForecast', '')

    impact_color, impact_label = nws_impact(short)

    reasons_parts = [short]
    if today.get('windSpeed'):
        reasons_parts.append(f"Wind: {today['windSpeed']} {today.get('windDirection','')}")
    if high_f is not None:
        reasons_parts.append(f'High: {high_f}°F')

    sky = short.split(',')[0].strip() if short else 'Unknown'

    return {
        'sky_condition': sky,
        'high_temperature_f': high_f,
        'low_temperature_f': low_f,
        'forecast_impact_color': impact_color,
        'forecast_impact_label': impact_label,
        'forecast_impact_reasons': '. '.join(reasons_parts),
        'nws_short_forecast': short,
        'nws_detailed_first': detailed[:200] if detailed else None,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description='Pull NWS forecasts for active airports')
    parser.add_argument('--dry-run', action='store_true',
                        help='Fetch and cache locally but do not write feed_runs to Supabase')
    parser.add_argument('--limit', type=int, default=None,
                        help='Limit number of airports processed')
    parser.add_argument('--clear-gridpoint-cache', action='store_true',
                        help='Force re-fetch of NWS gridpoint URLs (re-hits the points API)')
    args = parser.parse_args()

    load_env()

    nws_ua = os.environ.get('NWS_USER_AGENT', '').strip()
    if not nws_ua:
        log('nws_user_agent_missing',
            'NWS_USER_AGENT not set — NWS requires a contact User-Agent. '
            'Set it in .env: NWS_USER_AGENT="TravelCast/wxSense (your@email.com)"')
        if not args.dry_run:
            sys.exit(1)
        nws_ua = 'TravelCast-AviatorGraf/1.0 (no-contact-configured)'

    sb_url: str | None = None
    sb_key: str | None = None
    try:
        sb_url, sb_key = get_supabase_creds()
    except RuntimeError as e:
        log('supabase_config_error', str(e))
        if not args.dry_run:
            sys.exit(1)

    airports: list[dict] = []
    if sb_url and sb_key:
        try:
            airports = get_active_airports(sb_url, sb_key, limit=args.limit)
            log('airports_loaded', {'count': len(airports)})
        except Exception as e:
            log('airports_load_error', str(e))

    if not airports:
        log('no_airports', 'No airports to process — exiting')
        write_feed_run(sb_url, sb_key, SOURCE_ID, False, 0,
                       'No airports loaded', dry_run=args.dry_run)
        return

    # ── Load / initialise gridpoint cache ─────────────────────────────
    gridpoints: dict = {} if args.clear_gridpoint_cache else (load_raw(GRIDPOINTS_CACHE) or {})

    # ── Fetch gridpoints for airports not yet cached ──────────────────
    for apt in airports:
        aid = apt['airport_id']
        if aid in gridpoints:
            continue
        lat = apt.get('latitude')
        lon = apt.get('longitude')
        if lat is None or lon is None:
            log('skip_no_coords', aid)
            continue
        forecast_url = fetch_gridpoint(float(lat), float(lon), nws_ua)
        if forecast_url:
            gridpoints[aid] = forecast_url
            log('gridpoint_cached', {'airport': aid, 'url': forecast_url})
        time.sleep(REQUEST_DELAY_S)

    save_raw(GRIDPOINTS_CACHE, gridpoints)

    # ── Fetch forecasts ───────────────────────────────────────────────
    forecasts: dict = {}
    fetch_errors: list[str] = []

    for apt in airports:
        aid = apt['airport_id']
        iata = apt.get('iata', aid)
        forecast_url = gridpoints.get(aid)
        if not forecast_url:
            log('no_gridpoint', {'airport': iata})
            continue
        try:
            periods = fetch_forecast(forecast_url, nws_ua)
            summary = summarise_forecast(periods)
            summary['airport_id'] = aid
            summary['iata'] = iata
            forecasts[aid] = summary
            log('nws_fetched', {
                'airport': iata,
                'impact': summary.get('forecast_impact_color'),
                'sky': summary.get('sky_condition'),
            })
            time.sleep(REQUEST_DELAY_S)
        except Exception as e:
            fetch_errors.append(f'{iata}: {e}')
            log('nws_forecast_error', {'airport': iata, 'error': str(e)})

    save_raw(FORECASTS_CACHE, forecasts)
    log('pull_summary', {
        'airports': len(airports),
        'forecasts_cached': len(forecasts),
        'errors': len(fetch_errors),
        'dry_run': args.dry_run,
    })

    write_feed_run(
        sb_url, sb_key, SOURCE_ID,
        success=len(fetch_errors) == 0 and len(forecasts) > 0,
        records=len(forecasts),
        error='; '.join(fetch_errors[:3]) if fetch_errors else None,
        dry_run=args.dry_run,
    )


if __name__ == '__main__':
    main()
