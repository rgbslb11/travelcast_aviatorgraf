#!/usr/bin/env python3
"""Load TravelCast airports from CSV into Supabase.

Requires environment variables:
- SUPABASE_URL
- SUPABASE_SERVICE_ROLE_KEY

This script is backend/local only. Never use service-role keys in browser code.
"""
from __future__ import annotations
import argparse, csv, os, sys
from pathlib import Path
from datetime import datetime, timezone

REQUIRED = ['airport_id','iata','icao','display_name','airport_name','city','state','country','region','timezone','latitude','longitude','active','priority_tier']


def parse_bool(v): return str(v).strip().lower() in {'true','1','yes','y'}

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--csv', default='data/reference/travelcast_airports_master.csv')
    parser.add_argument('--dry-run', action='store_true')
    args=parser.parse_args()
    root=Path(__file__).resolve().parents[2]
    csv_path=root/args.csv
    rows=list(csv.DictReader(csv_path.open()))
    issues=[]; clean=[]
    for idx,row in enumerate(rows, start=2):
        for col in REQUIRED:
            if col not in row: issues.append(f'Missing column {col}')
        if row.get('active','').lower() == 'false': continue
        if not row.get('airport_id') or not row.get('icao') or not row.get('latitude') or not row.get('longitude'):
            issues.append(f'Row {idx} active airport missing identity/lat/lon')
            continue
        clean.append({
            'airport_id': row['airport_id'].upper().strip(), 'iata': row.get('iata','').upper().strip(), 'icao': row['icao'].upper().strip(), 'faa_lid': row.get('faa_lid','').upper().strip(),
            'display_name': row.get('display_name'), 'airport_name': row.get('airport_name'), 'city': row.get('city'), 'state': row.get('state'), 'country': row.get('country','US'), 'region': row.get('region'), 'timezone': row.get('timezone'),
            'latitude': float(row['latitude']), 'longitude': float(row['longitude']), 'elevation_ft': int(row['elevation_ft']) if row.get('elevation_ft') else None, 'active': parse_bool(row.get('active','true')), 'raw': row
        })
    report=root/'audit/load_airports_report.md'; report.parent.mkdir(exist_ok=True)
    report.write_text(f"# Airport Load Report\n\nGenerated: {datetime.now(timezone.utc).isoformat()}\n\nRows in CSV: {len(rows)}\nActive clean rows: {len(clean)}\nIssues: {len(issues)}\n\n" + '\n'.join(f'- {i}' for i in issues), encoding='utf-8')
    if issues:
        print(report); sys.exit(1)
    if args.dry_run:
        print(f'Dry run OK: {len(clean)} active airports validated.'); return
    try:
        from supabase import create_client
    except ImportError:
        print('Install supabase first: pip install supabase'); sys.exit(1)
    url=os.environ.get('SUPABASE_URL'); key=os.environ.get('SUPABASE_SERVICE_ROLE_KEY')
    if not url or not key: print('Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY'); sys.exit(1)
    client=create_client(url,key)
    client.table('airports').upsert(clean, on_conflict='airport_id').execute()
    print(f'Upserted {len(clean)} airports. Report: {report}')
if __name__ == '__main__': main()
