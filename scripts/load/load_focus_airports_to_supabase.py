#!/usr/bin/env python3
"""Load TravelCast focus airports from CSV into Supabase airports table.

Reads data/reference/travelcast_focus_airports.csv (71 airports) and
upserts each active row into the Supabase airports table keyed on airport_id
(= ICAO code).  Existing rows are updated; new rows are inserted.

Auth:    SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY from .env or environment.
         Never use service-role key in browser code.
Writes:  airports table (upsert on airport_id)

Usage:
  python load_focus_airports_to_supabase.py [--dry-run] [--csv PATH] [--limit N]
"""
from __future__ import annotations
import argparse, csv, json, sys, urllib.request, urllib.error, urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'pull'))
from lib_pull import load_env, get_supabase_creds, log, utc_now, ROOT, _sb_headers

CSV_DEFAULT = 'data/reference/travelcast_focus_airports.csv'

REQUIRED_COLS = {'region', 'city_name', 'display_name', 'iata', 'icao',
                 'active', 'sort_order', 'latitude', 'longitude'}


def parse_bool(v: str) -> bool:
    return v.strip().lower() in {'true', '1', 'yes', 'y'}


def row_to_airport(row: dict) -> dict | None:
    """Map a focus-airports CSV row to an airports table dict.

    Returns None if the row is missing required identity fields.
    """
    icao = row.get('icao', '').strip().upper()
    iata = row.get('iata', '').strip().upper()
    if not icao or not iata:
        return None
    lat_s = row.get('latitude', '').strip()
    lon_s = row.get('longitude', '').strip()
    if not lat_s or not lon_s:
        return None
    try:
        lat = float(lat_s)
        lon = float(lon_s)
    except ValueError:
        return None

    return {
        'airport_id':   icao,
        'iata':         iata,
        'icao':         icao,
        'faa_lid':      iata,
        'display_name': row.get('display_name', '').strip() or None,
        'city':         row.get('city_name', '').strip() or None,
        'region':       row.get('region', '').strip() or None,
        'country':      'US',
        'latitude':     lat,
        'longitude':    lon,
        'active':       parse_bool(row.get('active', 'true')),
    }


def upsert_airports(sb_url: str, sb_key: str, rows: list[dict],
                    dry_run: bool = False) -> tuple[int, int]:
    """Upsert rows to Supabase airports table.

    Returns (upserted_count, error_count).
    Sends in one POST with on_conflict=airport_id and merge-duplicates.
    """
    if dry_run:
        log('upsert_dry_run', {'count': len(rows)})
        for r in rows:
            log('would_upsert', {
                'airport_id': r['airport_id'],
                'iata': r['iata'],
                'region': r['region'],
                'lat': r['latitude'],
                'lon': r['longitude'],
            })
        return len(rows), 0

    path = f"{sb_url}/rest/v1/airports?on_conflict=airport_id"
    body = json.dumps(rows).encode('utf-8')
    headers = _sb_headers(sb_key, {
        'Prefer': 'resolution=merge-duplicates,return=minimal',
    })
    req = urllib.request.Request(path, data=body, headers=headers, method='POST')
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            resp.read()
        return len(rows), 0
    except urllib.error.HTTPError as e:
        err_body = e.read().decode(errors='ignore')
        log('upsert_http_error', {'status': e.code, 'body': err_body[:500]})
        return 0, len(rows)


def main() -> None:
    parser = argparse.ArgumentParser(
        description='Load TravelCast focus airports into Supabase'
    )
    parser.add_argument('--csv', default=CSV_DEFAULT,
                        help='Path to focus airports CSV (relative to project root)')
    parser.add_argument('--dry-run', action='store_true',
                        help='Validate and print rows but do not write to Supabase')
    parser.add_argument('--limit', type=int, default=None,
                        help='Process only the first N active rows (for testing)')
    args = parser.parse_args()

    load_env()

    sb_url: str | None = None
    sb_key: str | None = None
    if not args.dry_run:
        try:
            sb_url, sb_key = get_supabase_creds()
        except RuntimeError as e:
            log('supabase_config_error', str(e))
            sys.exit(1)

    csv_path = ROOT / args.csv
    if not csv_path.exists():
        log('csv_not_found', {'path': str(csv_path)})
        sys.exit(1)

    all_rows = list(csv.DictReader(csv_path.open(encoding='utf-8')))
    log('csv_loaded', {'path': str(csv_path), 'total_rows': len(all_rows)})

    # Validate columns
    if all_rows:
        missing_cols = REQUIRED_COLS - set(all_rows[0].keys())
        if missing_cols:
            log('missing_columns', {'missing': sorted(missing_cols)})
            sys.exit(1)

    # Build clean airport dicts — skip inactive and invalid rows
    clean: list[dict] = []
    rejected: list[dict] = []

    for idx, row in enumerate(all_rows, start=2):
        if not parse_bool(row.get('active', 'true')):
            log('skipped_inactive', {'row': idx, 'iata': row.get('iata', '')})
            continue
        apt = row_to_airport(row)
        if apt is None:
            log('rejected_row', {'row': idx, 'iata': row.get('iata', ''), 'reason': 'missing identity or lat/lon'})
            rejected.append({'row': idx, 'data': dict(row)})
            continue
        clean.append(apt)

    log('validation_summary', {
        'total_csv_rows': len(all_rows),
        'active_valid': len(clean),
        'rejected': len(rejected),
    })

    if rejected:
        log('rejected_detail', rejected)

    if not clean:
        log('no_rows_to_load', 'Nothing to upsert — check CSV content')
        sys.exit(1)

    if args.limit:
        clean = clean[:args.limit]
        log('limit_applied', {'limit': args.limit, 'will_upsert': len(clean)})

    # Upsert
    upserted, errors = upsert_airports(sb_url, sb_key, clean, dry_run=args.dry_run)

    log('load_complete', {
        'upserted': upserted,
        'errors': errors,
        'dry_run': args.dry_run,
        'timestamp': utc_now(),
    })

    if errors:
        sys.exit(1)


if __name__ == '__main__':
    main()
