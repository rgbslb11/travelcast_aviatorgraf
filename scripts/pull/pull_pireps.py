#!/usr/bin/env python3
"""Fetch and ingest PIREPs (Pilot Weather Reports) from AviationWeather.gov.

PIREPs are pilot-reported observations of actual flight conditions.
They are Aviation Weather Truth — not FAA operational delay data.

DOCTRINE:
  PIREPs are pilot-reported observations. They are NOT:
    - FAA delay forecasts
    - Ground stop or GDP notifications
    - Route closure information
    - Operational airport status
  Do not claim ground stops, GDPs, route closures, diversions, or delay
  minutes unless sourced from FAA/NAS, ATCSCC, or official operational data.
  Empty state is better than invented data. Do not invent PIREPs, conditions,
  or locations.

Geolocation rule:
  Latitude and longitude are stored ONLY when provided by AviationWeather.gov
  in the source response. If the source provides no lat/lon, is_geolocated
  is set to false and latitude/longitude are stored as NULL.
  Do not infer or invent coordinates from vague location text.

Association rule:
  PIREPs with lat/lon are associated to TravelCast airports within
  the configured radius (default 50 NM) using Haversine distance.
  PIREPs without lat/lon are associated to airports in the fetch batch
  as 'fetch_target' with distance=NULL.

Staleness:
  PIREPs observed more than 2 hours ago are flagged operationally stale
  in the v_pireps_active view.
  Data fetched_at_utc >= 8 hours ago is flagged fetch-stale.

Usage:
  python scripts/pull/pull_pireps.py
  python scripts/pull/pull_pireps.py --dry-run
  python scripts/pull/pull_pireps.py --limit 5
  python scripts/pull/pull_pireps.py --radius 100

Source API:
  https://aviationweather.gov/api/data/pirep
  Parameters: ids (ICAO list), format=json, age=3 (hours)

Supabase tables written:
  pirep_reports              — one row per unique PIREP (keyed by raw text hash)
  pirep_airport_associations — PIREP → nearby airport linkages

Requires (from .env):
  SUPABASE_URL
  SUPABASE_SERVICE_ROLE_KEY
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts' / 'pull'))
from lib_pull import (
    load_env, log, get_supabase_creds, supabase_post, write_feed_run,
    get_active_airports, http_get_json, save_raw, utc_now,
)

SOURCE_ID = 'aviationweather_pirep'
PIREP_URL_TEMPLATE = 'https://aviationweather.gov/api/data/pirep?ids={ids}&format=json&age=3'
BATCH_SIZE = 30
DEFAULT_RADIUS_NM = 50
UPSERT_PREFER = 'resolution=merge-duplicates,return=minimal'


# ─── Geo helpers ─────────────────────────────────────────────────────────────

def haversine_nm(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Haversine distance in nautical miles between two lat/lon points."""
    R = 3440.065  # Earth radius in nautical miles
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


# ─── PIREP parsing helpers ───────────────────────────────────────────────────

def pirep_id(raw_ob: str) -> str:
    """Stable ID from raw PIREP text: 'pirep-{12-char hex hash}'."""
    return 'pirep-' + hashlib.md5(raw_ob.encode('utf-8', errors='replace')).hexdigest()[:12]


def epoch_to_iso(ts) -> str | None:
    if ts is None:
        return None
    try:
        return datetime.fromtimestamp(int(ts), tz=timezone.utc).isoformat()
    except (TypeError, ValueError, OSError):
        return None


def parse_altitude_ft(flt_lvl) -> int | None:
    """Convert flight level (hundreds of feet) to feet. Returns None if unparseable."""
    if flt_lvl is None:
        return None
    v = str(flt_lvl).strip().upper()
    if v in ('DURGC', 'DURC', 'UNKN', ''):
        return None
    try:
        return int(float(v)) * 100
    except (TypeError, ValueError):
        return None


def parse_lat_lon(obj: dict) -> tuple[float | None, float | None]:
    """Return (lat, lon) only if both are present and numeric in the source object."""
    try:
        lat = float(obj['lat'])
        lon = float(obj['lon'])
        return lat, lon
    except (KeyError, TypeError, ValueError):
        return None, None


def classify_report_type(obj: dict) -> str | None:
    """Map AviationWeather.gov pirepType to UA / UUA."""
    pt = (obj.get('pirepType') or obj.get('reportType') or '').strip().upper()
    if pt in ('PIREP', 'UA'):
        return 'UA'
    if pt in ('UUA', 'URGENT PIREP'):
        return 'UUA'
    if pt in ('AIREP',):
        return 'AIREP'
    raw = (obj.get('rawOb') or '')
    if raw.startswith('UUA ') or ' /UUA ' in raw:
        return 'UUA'
    if raw.startswith('UA ') or ' /UA ' in raw:
        return 'UA'
    return pt or None


def parse_pirep_object(obj: dict, fetched_at: str) -> dict | None:
    """Parse one raw PIREP object from AviationWeather.gov into a pirep_reports row.
    Returns None if the object has no raw text (can't be identified).
    """
    raw = (obj.get('rawOb') or obj.get('raw') or '').strip()
    if not raw:
        return None

    pid = pirep_id(raw)
    lat, lon = parse_lat_lon(obj)

    return {
        'pirep_id': pid,
        'report_type': classify_report_type(obj),
        'raw_pirep': raw,
        'observed_at_utc': epoch_to_iso(obj.get('obsTime') or obj.get('observationTime')),
        'aircraft_type': obj.get('acType') or None,
        'altitude_ft': parse_altitude_ft(obj.get('fltLvl')),
        'location_text': obj.get('location') or obj.get('rawOb', '').split('/')[1].strip()
            if '/' in (obj.get('rawOb') or '') else None,
        'latitude': lat,
        'longitude': lon,
        'is_geolocated': (lat is not None and lon is not None),
        'turbulence_intensity': obj.get('tbInt') or None,
        'turbulence_type': obj.get('tbType') or None,
        'turbulence_frequency': obj.get('tbFreq') or None,
        'icing_intensity': obj.get('icgInt') or None,
        'icing_type': obj.get('icgType') or None,
        'sky_cover': obj.get('sky') or None,
        'visibility_sm': str(obj.get('visib')) if obj.get('visib') is not None else None,
        'wx_string': obj.get('wxString') or None,
        'temperature_c': str(obj.get('temp')) if obj.get('temp') is not None else None,
        'wind_dir': str(obj.get('wdir')) if obj.get('wdir') is not None else None,
        'wind_speed_kt': str(obj.get('wspd')) if obj.get('wspd') is not None else None,
        'remarks': obj.get('remarks') or None,
        'source_system_id': SOURCE_ID,
        'source_url': 'https://aviationweather.gov/api/data/pirep',
        'fetched_at_utc': fetched_at,
        'updated_at': fetched_at,
    }


def build_associations(
    pirep_row: dict,
    batch_airports: list[dict],
    all_airports: list[dict],
    radius_nm: float,
) -> list[dict]:
    """Build pirep_airport_associations rows for one PIREP.

    Geolocated PIREPs: associate all airports within radius_nm.
    Non-geolocated PIREPs: associate batch_airports as 'fetch_target'.
    """
    pid = pirep_row['pirep_id']
    assocs: list[dict] = []

    if pirep_row['is_geolocated']:
        plat = float(pirep_row['latitude'])
        plon = float(pirep_row['longitude'])
        for ap in all_airports:
            try:
                alat = float(ap.get('latitude') or 0)
                alon = float(ap.get('longitude') or 0)
                if alat == 0.0 and alon == 0.0:
                    continue
                dist = haversine_nm(plat, plon, alat, alon)
                if dist <= radius_nm:
                    assocs.append({
                        'pirep_id': pid,
                        'airport_id': ap['airport_id'],
                        'iata': ap.get('iata', ''),
                        'icao': ap.get('icao', ''),
                        'distance_nm': round(dist, 2),
                        'association_method': 'radius_match',
                    })
            except (TypeError, ValueError):
                continue
    else:
        # No lat/lon — associate to the airports from this fetch batch as targets
        for ap in batch_airports:
            assocs.append({
                'pirep_id': pid,
                'airport_id': ap['airport_id'],
                'iata': ap.get('iata', ''),
                'icao': ap.get('icao', ''),
                'distance_nm': None,
                'association_method': 'fetch_target',
            })

    return assocs


def batched(lst: list, size: int):
    for i in range(0, len(lst), size):
        yield lst[i:i + size]


# ─── Main ────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description='Fetch PIREPs from AviationWeather.gov and ingest into Supabase'
    )
    parser.add_argument('--dry-run', action='store_true',
                        help='Fetch and parse; do not write to Supabase')
    parser.add_argument('--limit', type=int, default=None,
                        help='Limit number of airports to process (for testing)')
    parser.add_argument('--radius', type=float, default=DEFAULT_RADIUS_NM,
                        help=f'Association radius in nautical miles (default: {DEFAULT_RADIUS_NM})')
    args = parser.parse_args()

    load_env()

    url: str | None = None
    key: str | None = None
    if not args.dry_run:
        try:
            url, key = get_supabase_creds()
        except RuntimeError as exc:
            log('config_error', {'error': str(exc)})
            sys.exit(1)

    fetched_at = utc_now()

    # ── Get active airports ───────────────────────────────────────────────────

    if url and key:
        all_airports = get_active_airports(url, key)
    else:
        # dry-run without Supabase — load from focus airports CSV as fallback
        airports_csv = ROOT / 'data' / 'reference' / 'travelcast_focus_airports.csv'
        if airports_csv.exists():
            import csv as csv_mod
            with airports_csv.open(newline='', encoding='utf-8') as f:
                rows = list(csv_mod.DictReader(f))
            all_airports = [
                {
                    'airport_id': r.get('icao', r.get('iata', '')).upper(),
                    'iata': r.get('iata', '').upper(),
                    'icao': r.get('icao', '').upper(),
                    'latitude': float(r.get('latitude') or 0) or None,
                    'longitude': float(r.get('longitude') or 0) or None,
                    'display_name': r.get('display_name', ''),
                }
                for r in rows
                if r.get('active', 'true').lower() in ('true', '1', 'yes', '')
                and r.get('icao')
            ]
        else:
            log('no_airports', {'error': 'No airport source available for dry-run without Supabase'})
            sys.exit(1)

    if args.limit:
        all_airports = all_airports[: args.limit]

    log('airports_loaded', {'count': len(all_airports)})

    # ── Fetch PIREPs per batch ────────────────────────────────────────────────

    all_raw: list[dict] = []
    raw_by_pirep: dict[str, dict] = {}
    assoc_by_pirep: dict[str, list[dict]] = {}
    fetch_errors = 0

    for batch in batched(all_airports, BATCH_SIZE):
        icaos = [ap['icao'] for ap in batch if ap.get('icao')]
        if not icaos:
            continue
        ids = ','.join(icaos)
        pirep_url = PIREP_URL_TEMPLATE.format(ids=ids)

        try:
            data = http_get_json(pirep_url)
        except Exception as exc:
            log('pirep_fetch_error', {'ids': ids[:60], 'error': str(exc)})
            fetch_errors += 1
            continue

        if not isinstance(data, list):
            log('pirep_format_warning', {'ids': ids[:60], 'type': type(data).__name__})
            continue

        all_raw.extend(data)

        for obj in data:
            if not isinstance(obj, dict):
                continue
            row = parse_pirep_object(obj, fetched_at)
            if not row:
                continue
            pid = row['pirep_id']

            # Deduplicate — keep first occurrence if same raw text seen in multiple batches
            if pid not in raw_by_pirep:
                raw_by_pirep[pid] = row

            # Always collect associations (a PIREP may appear in multiple batch results)
            new_assocs = build_associations(row, batch, all_airports, args.radius)
            existing = assoc_by_pirep.setdefault(pid, [])
            existing_keys = {(a['pirep_id'], a['airport_id']) for a in existing}
            for a in new_assocs:
                k = (a['pirep_id'], a['airport_id'])
                if k not in existing_keys:
                    existing.append(a)
                    existing_keys.add(k)

    log('fetch_complete', {
        'raw_total': len(all_raw),
        'unique_pireps': len(raw_by_pirep),
        'fetch_errors': fetch_errors,
    })

    # Save raw and summary
    save_raw('pirep_raw', all_raw)
    pirep_list = list(raw_by_pirep.values())
    assoc_list = [a for assocs in assoc_by_pirep.values() for a in assocs]

    parsed_summary = {
        'fetched_at': fetched_at,
        'unique_pireps': len(pirep_list),
        'total_associations': len(assoc_list),
        'geolocated': sum(1 for p in pirep_list if p.get('is_geolocated')),
        'fetch_errors': fetch_errors,
    }
    save_raw('pirep_parsed', parsed_summary)

    # ── Dry-run output ───────────────────────────────────────────────────────

    if args.dry_run:
        for row in pirep_list[:5]:
            log('pirep_preview', {
                'pirep_id': row['pirep_id'],
                'report_type': row.get('report_type'),
                'observed_at_utc': row.get('observed_at_utc'),
                'is_geolocated': row.get('is_geolocated'),
                'altitude_ft': row.get('altitude_ft'),
                'turbulence_intensity': row.get('turbulence_intensity'),
                'icing_intensity': row.get('icing_intensity'),
            })
        for a in assoc_list[:5]:
            log('assoc_preview', a)
        write_feed_run(None, None, SOURCE_ID, success=True,
                       records=len(pirep_list), dry_run=True)
        return

    # ── Write to Supabase ────────────────────────────────────────────────────

    if not url or not key:
        log('skipping_write', {'reason': 'no supabase creds'})
        return

    write_errors = 0
    pirep_count = 0
    assoc_count = 0

    for batch in batched(pirep_list, 50):
        try:
            supabase_post(url, key, 'pirep_reports', batch, prefer=UPSERT_PREFER)
            pirep_count += len(batch)
        except Exception as exc:
            log('upsert_error', {'table': 'pirep_reports', 'error': str(exc)})
            write_errors += 1

    for batch in batched(assoc_list, 100):
        try:
            supabase_post(url, key, 'pirep_airport_associations', batch, prefer=UPSERT_PREFER)
            assoc_count += len(batch)
        except Exception as exc:
            log('upsert_error', {'table': 'pirep_airport_associations', 'error': str(exc)})
            write_errors += 1

    success = write_errors == 0 and fetch_errors == 0
    write_feed_run(url, key, SOURCE_ID, success=success,
                   records=pirep_count,
                   error=f'{write_errors} write error(s), {fetch_errors} fetch error(s)'
                         if (write_errors or fetch_errors) else None)

    log('done', {
        'pirep_reports_written': pirep_count,
        'associations_written': assoc_count,
        'write_errors': write_errors,
        'fetch_errors': fetch_errors,
    })

    if write_errors:
        sys.exit(1)


if __name__ == '__main__':
    main()
