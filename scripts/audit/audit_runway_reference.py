#!/usr/bin/env python3
"""Audit the static airport runway reference for coverage and doctrine compliance.

Checks:
  1. Runway CSV template exists.
  2. Runway CSV has expected headers.
  3. If data rows exist: validates required fields and no invented values.
  4. Reports which of the 71 TravelCast airports have runway data and which don't.
  5. Does NOT fail if runway rows are missing — population is a separate step.
  6. Does fail if data rows violate required-field rules.
  7. Checks that source field is not 'template' on data rows (must be replaced with
     a real source: 'faa_nasr', 'faa_ais', 'ourairports').

Runway data must not be invented. Only populate from:
  - FAA NASR / FAA AIS (authoritative)
  - OurAirports runways.csv (development baseline)

atis.info and metar-taf.com/metar are candidate cross-check sources only and
must not be listed as 'source' values on data rows.

Usage:
  python scripts/audit/audit_runway_reference.py
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

AIRPORTS_CSV = ROOT / 'data' / 'reference' / 'travelcast_focus_airports.csv'
RUNWAYS_CSV_TEMPLATE = ROOT / 'data' / 'reference' / 'travelcast_airport_runways.template.csv'
RUNWAYS_CSV_LIVE = ROOT / 'data' / 'reference' / 'travelcast_airport_runways.csv'

EXPECTED_HEADERS = {
    'airport_id', 'iata', 'icao', 'runway_id', 'base_end_id', 'reciprocal_end_id',
    'length_ft', 'width_ft', 'surface_type',
    'base_heading_true', 'base_heading_magnetic',
    'reciprocal_heading_true', 'reciprocal_heading_magnetic',
    'base_threshold_lat', 'base_threshold_lon',
    'reciprocal_threshold_lat', 'reciprocal_threshold_lon',
    'base_displaced_threshold_ft', 'reciprocal_displaced_threshold_ft',
    'lighting',
    'base_ils_available', 'base_ils_frequency',
    'reciprocal_ils_available', 'reciprocal_ils_frequency',
    'source', 'source_date', 'notes',
}

REQUIRED_DATA_FIELDS = ['airport_id', 'iata', 'icao', 'runway_id', 'base_end_id']

# Sources that are not allowed as official data source field values
DISALLOWED_SOURCES = {'atis.info', 'metar-taf.com', 'metar-taf', 'template'}

failures: list[str] = []
warnings: list[str] = []


def fail(msg: str) -> None:
    failures.append(f'FAIL: {msg}')


def warn(msg: str) -> None:
    warnings.append(f'WARN: {msg}')


def load_focus_airports() -> list[dict]:
    if not AIRPORTS_CSV.exists():
        fail(f'Focus airports CSV not found: {AIRPORTS_CSV}')
        return []
    with AIRPORTS_CSV.open(newline='', encoding='utf-8') as f:
        return list(csv.DictReader(f))


def check_runway_csv() -> tuple[Path | None, list[dict]]:
    # Prefer the live populated file over the template
    csv_path = RUNWAYS_CSV_LIVE if RUNWAYS_CSV_LIVE.exists() else RUNWAYS_CSV_TEMPLATE

    if not csv_path.exists():
        fail(f'Runway CSV not found. Expected: {RUNWAYS_CSV_TEMPLATE}')
        return None, []

    with csv_path.open(newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        fieldnames = set(reader.fieldnames or [])
        rows = list(reader)

    # Header check
    missing_headers = EXPECTED_HEADERS - fieldnames
    if missing_headers:
        fail(f'Runway CSV missing expected headers: {sorted(missing_headers)}')

    extra_headers = fieldnames - EXPECTED_HEADERS - {'active', 'updated_at', 'loaded_at'}
    if extra_headers:
        warn(f'Runway CSV has unexpected extra headers: {sorted(extra_headers)}')

    return csv_path, rows


def audit_data_rows(rows: list[dict]) -> set[str]:
    icao_set: set[str] = set()
    for idx, row in enumerate(rows, start=2):
        for field in REQUIRED_DATA_FIELDS:
            if not row.get(field, '').strip():
                fail(f'Row {idx}: missing required field "{field}"')

        source = row.get('source', '').strip().lower()
        if source in DISALLOWED_SOURCES:
            fail(
                f'Row {idx} ({row.get("runway_id", "?")}): '
                f'source="{source}" is not an allowed official source. '
                f'Use faa_nasr, faa_ais, or ourairports.'
            )

        icao = row.get('icao', '').strip().upper()
        if icao:
            icao_set.add(icao)
    return icao_set


def main() -> None:
    print('=== Runway Reference Audit ===')
    print()

    # 1. Load focus airports
    airports = load_focus_airports()
    expected_icaos = {row['icao'].strip().upper() for row in airports if row.get('icao')}
    print(f'Focus airports expected: {len(expected_icaos)}')

    # 2. Check runway CSV
    csv_path, rows = check_runway_csv()

    if csv_path:
        print(f'Runway CSV: {csv_path.name}')
        print(f'Data rows found: {len(rows)}')
    else:
        print('Runway CSV: NOT FOUND')

    # 3. Audit data rows (if any)
    covered_icaos: set[str] = set()
    if rows:
        covered_icaos = audit_data_rows(rows)
        missing = expected_icaos - covered_icaos
        extra = covered_icaos - expected_icaos

        print()
        print(f'Airports with runway data:  {len(covered_icaos)} / {len(expected_icaos)}')
        print(f'Airports missing runway data: {len(missing)}')

        if missing:
            warn(
                f'{len(missing)} focus airports have no runway rows yet: '
                + ', '.join(sorted(missing)[:20])
                + (f' ... and {len(missing) - 20} more' if len(missing) > 20 else '')
            )
        if extra:
            warn(f'{len(extra)} runway rows reference ICAO codes not in focus airport list: '
                 + ', '.join(sorted(extra)))
    else:
        warn(
            'Runway CSV has no data rows. '
            'Populate travelcast_airport_runways.template.csv from FAA NASR / OurAirports data, '
            'then run load_airport_runways.py. '
            'See docs/RUNWAY_REFERENCE.md for instructions.'
        )
        print()
        print(f'Airports missing runway data: {len(expected_icaos)} / {len(expected_icaos)} '
              '(template not yet populated — this is expected at Phase B2)')

    # 4. Print warnings
    if warnings:
        print()
        for w in warnings:
            print(w)

    # 5. Print failures
    print()
    if failures:
        for f_ in failures:
            print(f_)
        print()
        print(f'Runway reference audit: FAILED ({len(failures)} failure(s))')
        sys.exit(1)
    else:
        print('Runway reference audit: PASSED')
        if warnings:
            print(f'  ({len(warnings)} warning(s) — see above)')


if __name__ == '__main__':
    main()
