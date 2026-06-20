#!/usr/bin/env python3
"""Load static airport runway reference data from CSV into Supabase.

Static runway reference describes physical runway inventory only:
identifiers, headings, length, width, surface, threshold coordinates,
lighting, and ILS availability.

This script does NOT fetch live web data. It reads a pre-populated CSV
that must be built from official sources (FAA NASR, FAA AIS, OurAirports).

Source hierarchy:
  1. FAA NASR / FAA AIS  — authoritative (preferred)
  2. OurAirports         — open development baseline
  atis.info / metar-taf.com — candidate cross-check only, not official input

Doctrine:
  Static runway reference does NOT describe active runway configuration,
  closures, AAR, arrival/departure flows, or operational runway use.
  Live/operational runway data must remain sourced from FAA/NAS, ATCSCC,
  or official operational sources.

Usage:
  python scripts/load/load_airport_runways.py --dry-run
  python scripts/load/load_airport_runways.py
  python scripts/load/load_airport_runways.py --csv data/reference/travelcast_airport_runways.csv

Requires (from .env):
  SUPABASE_URL
  SUPABASE_SERVICE_ROLE_KEY
"""
from __future__ import annotations

import argparse
import csv
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts' / 'pull'))
from lib_pull import load_env, log

TABLE = 'airport_runways'
DEFAULT_CSV = ROOT / 'data' / 'reference' / 'travelcast_airport_runways.template.csv'

REQUIRED_FIELDS = [
    'airport_id',
    'iata',
    'icao',
    'runway_id',
    'base_end_id',
]

OPTIONAL_INT_FIELDS = [
    'length_ft',
    'width_ft',
    'base_displaced_threshold_ft',
    'reciprocal_displaced_threshold_ft',
]

OPTIONAL_FLOAT_FIELDS = [
    'base_heading_true',
    'base_heading_magnetic',
    'reciprocal_heading_true',
    'reciprocal_heading_magnetic',
    'base_threshold_lat',
    'base_threshold_lon',
    'reciprocal_threshold_lat',
    'reciprocal_threshold_lon',
]

OPTIONAL_BOOL_FIELDS = [
    'base_ils_available',
    'reciprocal_ils_available',
]


def _parse_bool(v: str | None) -> bool:
    if v is None:
        return False
    return str(v).strip().lower() in {'true', '1', 'yes', 'y'}


def _parse_int(v: str | None) -> int | None:
    if not v or not v.strip():
        return None
    try:
        return int(v.strip())
    except ValueError:
        return None


def _parse_float(v: str | None) -> float | None:
    if not v or not v.strip():
        return None
    try:
        return float(v.strip())
    except ValueError:
        return None


def validate_and_parse(rows: list[dict], issues: list[str]) -> list[dict]:
    clean: list[dict] = []
    for idx, row in enumerate(rows, start=2):
        row_issues: list[str] = []

        # Required field check
        for field in REQUIRED_FIELDS:
            val = row.get(field, '').strip()
            if not val:
                row_issues.append(f'Row {idx}: missing required field "{field}"')

        if row_issues:
            issues.extend(row_issues)
            continue

        # Build clean record
        record: dict = {
            'runway_id': row['runway_id'].strip(),
            'airport_id': row['airport_id'].strip().upper(),
            'iata': row['iata'].strip().upper(),
            'icao': row['icao'].strip().upper(),
            'runway_designator': row.get('runway_designator', '').strip() or
                                 f"{row['base_end_id'].strip()}/{row.get('reciprocal_end_id', '').strip()}".rstrip('/'),
            'base_end_id': row['base_end_id'].strip(),
            'reciprocal_end_id': row.get('reciprocal_end_id', '').strip() or None,
            'surface_type': row.get('surface_type', '').strip() or None,
            'lighting': row.get('lighting', '').strip() or None,
            'base_ils_frequency': row.get('base_ils_frequency', '').strip() or None,
            'reciprocal_ils_frequency': row.get('reciprocal_ils_frequency', '').strip() or None,
            'source': row.get('source', 'template').strip() or 'template',
            'source_date': row.get('source_date', '').strip() or None,
            'notes': row.get('notes', '').strip() or None,
            'active': _parse_bool(row.get('active', 'true')),
            'updated_at': datetime.now(timezone.utc).isoformat(),
        }

        for field in OPTIONAL_INT_FIELDS:
            record[field] = _parse_int(row.get(field))

        for field in OPTIONAL_FLOAT_FIELDS:
            record[field] = _parse_float(row.get(field))

        for field in OPTIONAL_BOOL_FIELDS:
            record[field] = _parse_bool(row.get(field))

        clean.append(record)
    return clean


def main() -> None:
    parser = argparse.ArgumentParser(
        description='Load static airport runway reference from CSV into Supabase'
    )
    parser.add_argument(
        '--csv',
        default=str(DEFAULT_CSV),
        help='Path to runway CSV file (default: travelcast_airport_runways.template.csv)',
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Validate CSV and print records without writing to Supabase',
    )
    parser.add_argument(
        '--limit',
        type=int,
        default=None,
        help='Limit the number of rows to load (for testing)',
    )
    args = parser.parse_args()

    load_env()
    csv_path = Path(args.csv)

    if not csv_path.exists():
        print(f'ERROR: CSV file not found: {csv_path}', file=sys.stderr)
        print(
            'Populate the runway CSV from FAA NASR / FAA AIS / OurAirports data, '
            'then run this loader.',
            file=sys.stderr,
        )
        sys.exit(1)

    with csv_path.open(newline='', encoding='utf-8') as f:
        raw_rows = list(csv.DictReader(f))

    if not raw_rows:
        print(
            'WARNING: CSV has no data rows. '
            'Populate the runway CSV from official sources before loading.\n'
            'Template headers are in place. No rows loaded.',
        )
        log('runway_load_skipped', {
            'reason': 'empty_csv',
            'csv': str(csv_path),
            'dry_run': args.dry_run,
        })
        return

    if args.limit:
        raw_rows = raw_rows[: args.limit]

    issues: list[str] = []
    clean = validate_and_parse(raw_rows, issues)

    if issues:
        print(f'Validation errors ({len(issues)}):')
        for issue in issues:
            print(f'  {issue}')
        sys.exit(1)

    print(f'Validated {len(clean)} runway records from {csv_path.name}.')

    if args.dry_run:
        for record in clean:
            print(f'  [dry-run] {record["runway_id"]} ({record["iata"]}) — '
                  f'{record.get("runway_designator")} '
                  f'{record.get("length_ft", "?")}ft '
                  f'source={record["source"]}')
        print(f'Dry run complete. {len(clean)} records validated, no writes.')
        log('runway_load_dry_run', {'count': len(clean), 'csv': str(csv_path)})
        return

    # Live write — requires Supabase credentials
    try:
        from supabase import create_client
    except ImportError:
        print('ERROR: supabase-py not installed. Run: pip install supabase', file=sys.stderr)
        sys.exit(1)

    import os
    url = os.environ.get('SUPABASE_URL', '')
    key = os.environ.get('SUPABASE_SERVICE_ROLE_KEY', '')
    if not url or not key:
        print(
            'ERROR: SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set in .env.',
            file=sys.stderr,
        )
        sys.exit(1)

    client = create_client(url, key)

    loaded = 0
    errors = 0
    for record in clean:
        try:
            client.table(TABLE).upsert(record, on_conflict='runway_id').execute()
            loaded += 1
        except Exception as exc:
            print(f'ERROR upserting {record["runway_id"]}: {exc}', file=sys.stderr)
            errors += 1

    log('runway_load_complete', {
        'loaded': loaded,
        'errors': errors,
        'csv': str(csv_path),
        'dry_run': False,
    })
    print(f'Loaded {loaded} runway records. Errors: {errors}.')
    if errors:
        sys.exit(1)


if __name__ == '__main__':
    main()
