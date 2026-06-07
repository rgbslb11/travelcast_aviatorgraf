#!/usr/bin/env python3
"""Pull METAR and TAF from AviationWeather.gov and cache raw data locally.

Source:  https://aviationweather.gov/api/data/metar?ids={ICAO_LIST}&format=json
         https://aviationweather.gov/api/data/taf?ids={ICAO_LIST}&format=json
Auth:    None (public API, no key required)
Writes:  data/raw/metar_raw.json, data/raw/taf_raw.json (local cache)
         feed_runs (source_system_id='aviationweather_api')
         Does NOT write airport_status_snapshots directly —
         rebuild_airport_status_snapshots.py merges this cache into snapshots.
Doctrine: AviationWeather.gov = Aviation Weather Truth — METAR/TAF

Usage:
  python pull_aviationweather_metar_taf.py [--dry-run] [--limit N]
"""
from __future__ import annotations
import argparse, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from lib_pull import (
    load_env, get_supabase_creds, get_active_airports,
    write_feed_run, http_get_json, save_raw, log,
)

METAR_URL = 'https://aviationweather.gov/api/data/metar?ids={ids}&format=json&taf=false'
TAF_URL   = 'https://aviationweather.gov/api/data/taf?ids={ids}&format=json'
SOURCE_ID = 'aviationweather_api'
BATCH_SIZE = 30  # AviationWeather recommends no more than 50 IDs per request


def parse_metar(obj: dict) -> dict:
    """Extract METAR snapshot fields from an AviationWeather.gov METAR JSON object."""
    wdir = obj.get('wdir', '')
    wspd = obj.get('wspd', '')
    wgst = obj.get('wgst', '')

    wind_dir = 'VRB' if not wdir else f'{int(wdir):03d}'
    wind_str = f'{wind_dir}{str(int(wspd or 0)).zfill(2)}'
    if wgst:
        wind_str += f'G{int(wgst):02d}'
    wind_str += 'KT'

    vis = obj.get('visib', '')
    vis_str = f'{vis}SM' if vis not in ('', None) else ''

    obs_at: str | None = None
    obs_time = obj.get('obsTime') or obj.get('timeObs')
    if obs_time:
        from datetime import datetime, timezone
        try:
            obs_at = datetime.fromtimestamp(int(obs_time), tz=timezone.utc).isoformat()
        except (ValueError, TypeError, OSError):
            obs_at = None

    wx = obj.get('wxString', '') or ''

    return {
        'icao': obj.get('icaoId', '').upper(),
        'metar_condition': wx or (obj.get('skyCover') or ''),
        'flight_category': (obj.get('fltcat') or 'VFR').upper(),
        'metar_wind': wind_str,
        'metar_visibility': vis_str,
        'metar_observed_at': obs_at,
        'raw_ob': obj.get('rawOb', ''),
    }


def parse_taf(obj: dict) -> dict:
    """Extract TAF trend fields from an AviationWeather.gov TAF JSON object."""
    fcsts = obj.get('fcsts', [])
    trend_parts = []
    for f in fcsts[:3]:
        change = f.get('changeIndicator', '')
        wx = f.get('wxString', '') or ''
        sky = f.get('skyCover', '') or ''
        desc = ' '.join(filter(None, [change, wx, sky])).strip()
        if desc:
            trend_parts.append(desc)

    next_risk: str | None = None
    risk_kw = ('TS', 'SN', 'FG', 'GR', 'FZRA', 'TSRA')
    for f in fcsts:
        wx_up = (f.get('wxString') or '').upper()
        if any(k in wx_up for k in risk_kw):
            from_t = f.get('timeFrom', '')
            next_risk = f'Risk window from {from_t}' if from_t else 'Risk present in TAF'
            break

    return {
        'icao': obj.get('icaoId', '').upper(),
        'taf_trend': ' | '.join(trend_parts) if trend_parts else None,
        'taf_next_risk_window': next_risk,
    }


def batched(lst: list, size: int):
    for i in range(0, len(lst), size):
        yield lst[i:i + size]


def main() -> None:
    parser = argparse.ArgumentParser(description='Pull METAR and TAF from AviationWeather.gov')
    parser.add_argument('--dry-run', action='store_true',
                        help='Fetch and cache locally but do not write feed_runs to Supabase')
    parser.add_argument('--limit', type=int, default=None,
                        help='Limit number of airports processed')
    args = parser.parse_args()

    load_env()

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

    icao_list = [a['icao'] for a in airports if a.get('icao')]
    if args.limit:
        icao_list = icao_list[:args.limit]

    # ── Fetch METARs ──────────────────────────────────────────────────
    metar_raw: list[dict] = []
    metar_errors: list[str] = []
    for batch in batched(icao_list, BATCH_SIZE):
        ids = ','.join(batch)
        try:
            data = http_get_json(METAR_URL.format(ids=ids))
            if isinstance(data, list):
                metar_raw.extend(data)
            log('metar_batch_ok', {'batch_size': len(batch), 'returned': len(data) if isinstance(data, list) else 0})
        except Exception as e:
            metar_errors.append(str(e))
            log('metar_batch_error', str(e))

    metar_parsed = {m['icao']: m for m in (parse_metar(r) for r in metar_raw)}

    # ── Fetch TAFs ────────────────────────────────────────────────────
    taf_raw: list[dict] = []
    taf_errors: list[str] = []
    for batch in batched(icao_list, BATCH_SIZE):
        ids = ','.join(batch)
        try:
            data = http_get_json(TAF_URL.format(ids=ids))
            if isinstance(data, list):
                taf_raw.extend(data)
            log('taf_batch_ok', {'batch_size': len(batch), 'returned': len(data) if isinstance(data, list) else 0})
        except Exception as e:
            taf_errors.append(str(e))
            log('taf_batch_error', str(e))

    taf_parsed = {t['icao']: t for t in (parse_taf(r) for r in taf_raw)}

    # ── Save raw caches ───────────────────────────────────────────────
    save_raw('metar_raw', metar_raw)
    save_raw('taf_raw', taf_raw)
    save_raw('metar_parsed', metar_parsed)
    save_raw('taf_parsed', taf_parsed)
    log('raw_saved', {'metar': len(metar_raw), 'taf': len(taf_raw)})

    all_errors = metar_errors + taf_errors
    log('pull_summary', {
        'metar_fetched': len(metar_raw),
        'taf_fetched': len(taf_raw),
        'errors': len(all_errors),
        'dry_run': args.dry_run,
    })

    write_feed_run(
        sb_url, sb_key, SOURCE_ID,
        success=len(all_errors) == 0,
        records=len(metar_raw),
        error='; '.join(all_errors[:3]) if all_errors else None,
        dry_run=args.dry_run,
    )


if __name__ == '__main__':
    main()
