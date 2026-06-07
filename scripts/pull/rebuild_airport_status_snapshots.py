#!/usr/bin/env python3
"""Build comprehensive airport_status_snapshots rows combining all source caches.

This is the primary snapshot builder. Run after the individual pull scripts
have cached their raw data, or use --fetch-all to pull all sources inline.

Pipeline:
  1. Load active airports from Supabase
  2. Load cached raw data (faa_nas_status, metar_parsed, taf_parsed, nws_forecasts)
  3. Combine into one comprehensive snapshot row per airport
  4. Insert into airport_status_snapshots (snapshot_source='live')
  5. Write feed_runs for each source used

Doctrine labels (do not alter):
  - Current Operational Impact — FAA NAS Status
  - Aviation Weather Truth — AviationWeather.gov
  - Forecast Weather Impact — NWS forecast proxy (NOT an official FAA delay forecast)

Usage:
  python rebuild_airport_status_snapshots.py [--dry-run] [--limit N] [--fetch-all]
"""
from __future__ import annotations
import argparse, subprocess, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from lib_pull import (
    load_env, get_supabase_creds, get_active_airports,
    insert_snapshots, write_feed_run, load_raw, utc_now, log,
)
from pull_faa_nas_status import parse_faa_event

SOURCE_IDS = {
    'faa': 'faa_nas_status',
    'metar': 'aviationweather_api',
    'nws': 'nws_api',
}


def build_snapshot(airport: dict, faa: dict | None, metar: dict | None,
                   taf: dict | None, nws: dict | None) -> dict:
    """Combine data from all sources into one airport_status_snapshots row."""
    aid = airport['airport_id']

    snap: dict = {
        'airport_id': aid,
        'snapshot_source': 'live',
        'generated_at': utc_now(),
        'freshness_status': 'fresh',
    }

    # ── FAA NAS operational fields (Current Operational Impact — FAA NAS Status) ──
    if faa:
        snap.update({
            'current_delay_type': faa.get('current_delay_type', 'None'),
            'current_status_code': faa.get('current_status_code', 'NORMAL'),
            'current_reason': faa.get('current_reason'),
            'avg_delay_minutes': faa.get('avg_delay_minutes'),
            'max_delay_minutes': faa.get('max_delay_minutes'),
            'delay_summary': faa.get('delay_summary'),
            'current_impact_color': faa.get('current_impact_color'),
        })
    else:
        snap.update({
            'current_delay_type': 'None',
            'current_status_code': 'NORMAL',
            'current_impact_color': None,
        })

    # ── METAR (Aviation Weather Truth — AviationWeather.gov) ──────────
    if metar:
        snap.update({
            'metar_condition': metar.get('metar_condition'),
            'flight_category': metar.get('flight_category'),
            'metar_wind': metar.get('metar_wind'),
            'metar_visibility': metar.get('metar_visibility'),
            'metar_observed_at': metar.get('metar_observed_at'),
        })

    # ── TAF ───────────────────────────────────────────────────────────
    if taf:
        snap.update({
            'taf_trend': taf.get('taf_trend'),
            'taf_next_risk_window': taf.get('taf_next_risk_window'),
        })

    # ── NWS forecast (Forecast Weather Impact — NWS forecast proxy) ───
    if nws:
        snap.update({
            'sky_condition': nws.get('sky_condition'),
            'high_temperature_f': nws.get('high_temperature_f'),
            'low_temperature_f': nws.get('low_temperature_f'),
            'forecast_impact_color': nws.get('forecast_impact_color'),
            'forecast_impact_label': nws.get('forecast_impact_label'),
            'forecast_impact_reasons': nws.get('forecast_impact_reasons'),
        })

    # ── Composite source_summary ───────────────────────────────────────
    sources_used = []
    if faa:
        sources_used.append('Current Operational Impact — FAA NAS Status')
    if metar:
        sources_used.append('Aviation Weather Truth — AviationWeather.gov')
    if nws:
        sources_used.append('Forecast Weather Impact — NWS forecast proxy')
    snap['source_summary'] = ' | '.join(sources_used) if sources_used else 'No live sources'

    return snap


def run_pull_script(script_name: str, extra_args: list[str]) -> bool:
    """Run a sibling pull script via subprocess. Returns True if exit code 0."""
    script_path = Path(__file__).parent / script_name
    cmd = [sys.executable, str(script_path)] + extra_args
    log('running_script', {'cmd': ' '.join(cmd)})
    result = subprocess.run(cmd, capture_output=False)
    ok = result.returncode == 0
    log('script_complete', {'script': script_name, 'ok': ok})
    return ok


def main() -> None:
    parser = argparse.ArgumentParser(
        description='Rebuild airport_status_snapshots from all source caches'
    )
    parser.add_argument('--dry-run', action='store_true',
                        help='Build snapshots but do not write to Supabase')
    parser.add_argument('--limit', type=int, default=None,
                        help='Limit number of airports processed')
    parser.add_argument('--fetch-all', action='store_true',
                        help='Run all individual pull scripts first to refresh caches')
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

    # ── Optionally refresh all caches first ───────────────────────────
    if args.fetch_all:
        log('fetch_all_start', 'Running individual pull scripts to refresh caches')
        extra = ['--dry-run'] if args.dry_run else []
        if args.limit:
            extra += ['--limit', str(args.limit)]
        run_pull_script('pull_faa_nas_status.py', extra)
        run_pull_script('pull_aviationweather_metar_taf.py', extra)
        run_pull_script('pull_nws_forecasts.py', extra)
        run_pull_script('pull_atcscc_ops_plan.py', ['--dry-run'] if args.dry_run else [])
        log('fetch_all_done', 'All pull scripts completed — loading caches')

    # ── Load airports ─────────────────────────────────────────────────
    airports: list[dict] = []
    if sb_url and sb_key:
        try:
            airports = get_active_airports(sb_url, sb_key, limit=args.limit)
            log('airports_loaded', {'count': len(airports)})
        except Exception as e:
            log('airports_load_error', str(e))

    if not airports:
        log('no_airports', 'No airports to process — exiting')
        return

    # ── Load caches ───────────────────────────────────────────────────
    # faa_nas_status.json is the raw list from nasstatus.faa.gov/api/airport-events.
    # Index it by airportId for O(1) lookup per tracked airport.
    _faa_raw = load_raw('faa_nas_status') or []
    faa_events_by_iata: dict[str, dict] = {}
    if isinstance(_faa_raw, list):
        for ev in _faa_raw:
            aid = (ev.get('airportId') or ev.get('airport') or '').strip().upper()
            if aid:
                faa_events_by_iata[aid] = ev
    elif isinstance(_faa_raw, dict):
        # Older cache format: {IATA: event_dict} — still usable
        faa_events_by_iata = {k.upper(): v for k, v in _faa_raw.items()}

    metar_cache: dict = load_raw('metar_parsed') or {}   # {ICAO: parsed METAR dict}
    taf_cache: dict   = load_raw('taf_parsed') or {}     # {ICAO: parsed TAF dict}
    nws_cache: dict   = load_raw('nws_forecasts') or {}  # {airport_id: NWS summary}

    log('caches_loaded', {
        'faa_events': len(faa_events_by_iata),
        'metar': len(metar_cache),
        'taf': len(taf_cache),
        'nws': len(nws_cache),
    })

    # ── Build comprehensive snapshot for each airport ──────────────────
    snapshots: list[dict] = []

    for apt in airports:
        aid = apt['airport_id']
        iata = (apt.get('iata') or '').upper()
        icao = (apt.get('icao') or '').upper()

        # Look up the FAA event for this airport (None = no active program → NORMAL)
        faa_event = faa_events_by_iata.get(iata)
        faa_fields: dict | None = parse_faa_event(faa_event, apt) if faa_events_by_iata else None

        metar_data = metar_cache.get(icao)
        taf_data   = taf_cache.get(icao)
        nws_data   = nws_cache.get(aid)

        snap = build_snapshot(apt, faa_fields, metar_data, taf_data, nws_data)
        snapshots.append(snap)

        log('snapshot_built', {
            'airport': iata,
            'status': snap.get('current_status_code', 'NORMAL'),
            'flt_cat': snap.get('flight_category'),
            'op_impact': snap.get('current_impact_color'),
            'fcst_impact': snap.get('forecast_impact_color'),
        })

    log('rebuild_summary', {
        'snapshots_built': len(snapshots),
        'dry_run': args.dry_run,
    })

    # ── Write to Supabase ─────────────────────────────────────────────
    write_ok = False
    write_err: str | None = None
    try:
        insert_snapshots(sb_url, sb_key, snapshots, dry_run=args.dry_run)
        write_ok = True
    except Exception as e:
        write_err = str(e)
        log('snapshot_write_error', write_err)

    # Write a feed_run for each source that contributed data
    if faa_events_by_iata:
        write_feed_run(sb_url, sb_key, SOURCE_IDS['faa'],
                       write_ok, len(snapshots), write_err, dry_run=args.dry_run)
    if metar_cache:
        write_feed_run(sb_url, sb_key, SOURCE_IDS['metar'],
                       write_ok, len(metar_cache), write_err, dry_run=args.dry_run)
    if nws_cache:
        write_feed_run(sb_url, sb_key, SOURCE_IDS['nws'],
                       write_ok, len(nws_cache), write_err, dry_run=args.dry_run)


if __name__ == '__main__':
    main()
