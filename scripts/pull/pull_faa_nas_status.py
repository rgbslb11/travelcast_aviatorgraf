#!/usr/bin/env python3
"""Pull FAA NAS airport status and write airport_status_snapshots rows.

Source:  https://soa.smext.faa.gov/asws/api/airport/status/{IATA}
Auth:    None (public API, no key required)
Writes:  airport_status_snapshots (snapshot_source='live')
         feed_runs (source_system_id='faa_nas_status')
Doctrine: FAA NAS Status = Current Operational Impact (operational truth)

Usage:
  python pull_faa_nas_status.py [--dry-run] [--limit N]
"""
from __future__ import annotations
import argparse, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from lib_pull import (
    load_env, get_supabase_creds, get_active_airports,
    insert_snapshots, write_feed_run, http_get_json, save_raw, utc_now, log,
)

FAA_STATUS_BASE = 'https://soa.smext.faa.gov/asws/api/airport/status/{iata}'
SOURCE_ID = 'faa_nas_status'


def parse_faa_status(raw: dict, airport: dict) -> dict:
    """Map FAA airport status API response to airport_status_snapshots fields."""
    has_delay = raw.get('Delay', False)
    status_list = raw.get('Status', [])

    current_delay_type = 'None'
    current_status_code = 'NORMAL'
    current_reason = None
    avg_delay: int | None = None
    max_delay: int | None = None
    current_impact_color: str | None = None

    if has_delay and status_list:
        s = status_list[0]
        raw_type = (s.get('Type') or '').strip()
        raw_reason = (s.get('Reason') or '').strip()
        current_delay_type = raw_type or 'Delay'
        current_reason = raw_reason or None

        lo = raw_type.lower()
        if 'ground delay' in lo:
            current_status_code = 'GROUND_DELAY_PROGRAM'
            current_impact_color = 'Red'
        elif 'ground stop' in lo:
            current_status_code = 'GROUND_STOP'
            current_impact_color = 'Red'
        elif 'closure' in lo:
            current_status_code = 'CLOSURE'
            current_impact_color = 'Red'
        elif 'departure' in lo or 'arrival' in lo:
            current_status_code = 'DELAY'
            current_impact_color = 'Amber'
        else:
            current_status_code = 'DELAY'
            current_impact_color = 'Amber'

        for field, dest in (('AvgDelay', 'avg'), ('MaxDelay', 'max')):
            try:
                v = int(s.get(field) or 0)
                if v > 0:
                    if field == 'AvgDelay':
                        avg_delay = v
                    else:
                        max_delay = v
            except (ValueError, TypeError):
                pass

    delay_parts = []
    if current_status_code != 'NORMAL':
        delay_parts.append(f'{current_delay_type} active')
        if avg_delay:
            delay_parts.append(f'avg {avg_delay} min')
        if max_delay:
            delay_parts.append(f'max {max_delay} min')
        if current_reason:
            delay_parts.append(f'({current_reason})')
    delay_summary = '. '.join(delay_parts) + '.' if delay_parts else None

    return {
        'airport_id': airport['airport_id'],
        'snapshot_source': 'live',
        'generated_at': utc_now(),
        'freshness_status': 'fresh',
        'current_delay_type': current_delay_type,
        'current_status_code': current_status_code,
        'current_reason': current_reason,
        'avg_delay_minutes': avg_delay,
        'max_delay_minutes': max_delay,
        'delay_summary': delay_summary,
        'current_impact_color': current_impact_color,
        'source_summary': 'Current Operational Impact — FAA NAS Status',
    }


def main() -> None:
    parser = argparse.ArgumentParser(description='Pull FAA NAS airport status')
    parser.add_argument('--dry-run', action='store_true',
                        help='Fetch data but do not write to Supabase')
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

    # Load airports from Supabase
    airports: list[dict] = []
    if sb_url and sb_key:
        try:
            airports = get_active_airports(sb_url, sb_key, limit=args.limit)
            log('airports_loaded', {'count': len(airports), 'source': 'supabase'})
        except Exception as e:
            log('airports_load_error', str(e))

    if not airports:
        log('no_airports', 'No airports to process — exiting')
        write_feed_run(sb_url, sb_key, SOURCE_ID, False, 0,
                       'No airports loaded from Supabase', dry_run=args.dry_run)
        return

    snapshots: list[dict] = []
    raw_all: dict = {}
    fetch_errors: list[dict] = []

    for apt in airports:
        iata = (apt.get('iata') or '').strip().upper()
        if not iata:
            continue
        url = FAA_STATUS_BASE.format(iata=iata)
        try:
            raw = http_get_json(url)
            raw_all[iata] = raw
            snap = parse_faa_status(raw, apt)
            snapshots.append(snap)
            log('faa_fetched', {
                'airport': iata,
                'delay_type': snap['current_delay_type'],
                'status_code': snap['current_status_code'],
                'impact': snap['current_impact_color'],
            })
        except Exception as e:
            fetch_errors.append({'airport': iata, 'error': str(e)})
            log('faa_fetch_error', {'airport': iata, 'error': str(e)})

    # Save raw cache regardless of dry-run
    if raw_all:
        save_raw('faa_nas_status', raw_all)
        log('raw_saved', {'file': 'data/raw/faa_nas_status.json', 'airports': len(raw_all)})

    log('pull_summary', {
        'snapshots_built': len(snapshots),
        'fetch_errors': len(fetch_errors),
        'dry_run': args.dry_run,
    })

    # Write to Supabase (or dry-run print)
    success = False
    write_error: str | None = None
    try:
        insert_snapshots(sb_url, sb_key, snapshots, dry_run=args.dry_run)
        success = True
    except Exception as e:
        write_error = str(e)
        log('snapshot_write_error', write_error)

    write_feed_run(
        sb_url, sb_key, SOURCE_ID,
        success=success,
        records=len(snapshots),
        error=write_error,
        dry_run=args.dry_run,
    )


if __name__ == '__main__':
    main()
