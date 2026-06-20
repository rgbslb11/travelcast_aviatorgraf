#!/usr/bin/env python3
"""Seed RouteCast corridor geometry from the Top-50 busiest aviation route source file.

DOCTRINE:
  The Top-50 busiest route source file is a static reference artifact.
  It is NOT live FAA delay truth.
  FAA waypoint/coordinate artifacts are route-geometry inputs, NOT delay truth.
  RouteCast corridor geometry is a planning/display scaffold only.
  RouteCast corridor geometry is NOT FAA operational delay truth.
  FAA NAS / ATCSCC / NOTAM / official airport sources remain operational truth.
  AviationWeather.gov remains aviation-weather truth.
  NWS public alerts provide public weather hazard context only, NOT FAA truth.
  Empty state is better than invented geometry.
  Do not invent waypoint coordinates.
  Do not invent route segments.
  Do not infer FAA airway routing from approximate waypoint data.

Source files (all optional — script warns/fails if missing):
  Top-50 route source CSV: data/reference/top_50_routes.csv (or --source-csv PATH)
  Waypoint coordinates CSV: data/reference/faa_waypoint_coordinates.csv (or --waypoint-coordinates PATH)
  Unresolved labels CSV: data/reference/faa_unresolved_labels.csv (or --unresolved-labels PATH)

Geometry behavior:
  - Build geometry ONLY from resolved waypoint lat/lon coordinates.
  - If fewer than 2 waypoints resolve to coordinates, do not create geometry.
  - geometry_method = 'resolved_waypoint_control_line' when geometry is built.
  - geometry_confidence = 'control_line_scaffold' — needs validation before operational use.
  - geometry_status = 'needs_validation'.
  - unresolved_waypoints stores labels that could not be resolved.

Usage:
  python scripts/routecast/seed_routecast_corridors.py --dry-run
  python scripts/routecast/seed_routecast_corridors.py --write
  python scripts/routecast/seed_routecast_corridors.py --write --source-csv data/reference/top_50_routes.csv
  python scripts/routecast/seed_routecast_corridors.py --write --waypoint-coordinates data/reference/faa_waypoint_coordinates.csv
  python scripts/routecast/seed_routecast_corridors.py --dry-run --limit 10

Supabase tables written (--write only):
  routecast_corridors              — one row per corridor (upsert on corridor_key)
  routecast_corridor_waypoints     — waypoint rows per corridor
  routecast_corridor_geometry      — geometry output per corridor

Requires (from .env):
  SUPABASE_URL
  SUPABASE_SERVICE_ROLE_KEY
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Iterator

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts' / 'pull'))
from lib_pull import (
    load_env, log, get_supabase_creds, supabase_post, write_feed_run, utc_now,
)

SOURCE_ID = 'routecast_corridors_seed'
UPSERT_PREFER = 'resolution=merge-duplicates,return=minimal'

ROUTE_RANK_BASIS = 'static_top_50_busiest_route_reference_not_delay_truth'
DEFAULT_GEOMETRY_CONFIDENCE = 'control_line_scaffold'
DEFAULT_GEOMETRY_STATUS = 'needs_validation'

# ─── Default search paths ─────────────────────────────────────────────────────

DEFAULT_SOURCE_PATHS: list[Path] = [
    ROOT / 'data' / 'reference' / 'top_50_routes.csv',
    ROOT / 'data' / 'reference' / 'top_50_busiest_routes.csv',
    ROOT / 'data' / 'reference' / 'routecast_corridors.csv',
    ROOT / 'data' / 'reference' / 'travelcast_top50_routes.csv',
    ROOT / 'data' / 'reference' / 'travelcast_corridors.csv',
]

DEFAULT_WAYPOINT_COORD_PATHS: list[Path] = [
    ROOT / 'data' / 'reference' / 'faa_waypoint_coordinates.csv',
    ROOT / 'data' / 'reference' / 'faa_waypoints.csv',
    ROOT / 'data' / 'reference' / 'waypoint_coordinates.csv',
    ROOT / 'data' / 'reference' / 'faa_coordinate_manifest.csv',
]

DEFAULT_UNRESOLVED_PATHS: list[Path] = [
    ROOT / 'data' / 'reference' / 'faa_unresolved_labels.csv',
    ROOT / 'data' / 'reference' / 'unresolved_route_labels.csv',
    ROOT / 'data' / 'reference' / 'unresolved_waypoints.csv',
]


# ─── Column name aliases ──────────────────────────────────────────────────────

def _first_col(row: dict, candidates: list[str], default=None):
    """Return the value of the first matching column key, case-insensitive."""
    low = {k.lower(): v for k, v in row.items()}
    for c in candidates:
        v = low.get(c.lower())
        if v is not None and str(v).strip() != '':
            return str(v).strip()
    return default


CORRIDOR_KEY_COLS = ['corridor_key', 'route_key', 'route_id', 'id']
CORRIDOR_NAME_COLS = ['corridor_name', 'route_name', 'city_pair', 'name']
RANK_COLS = ['rank', 'route_rank', 'sort_order', 'priority']
ORIGIN_COLS = ['origin_airport_iata', 'origin', 'origin_airport', 'origin_iata',
               'from_iata', 'from_airport']
DEST_COLS = ['destination_airport_iata', 'destination', 'destination_airport',
             'destination_iata', 'to_iata', 'dest_iata', 'to_airport']
ORIGIN_ICAO_COLS = ['origin_airport_icao', 'origin_icao', 'from_icao']
DEST_ICAO_COLS = ['destination_airport_icao', 'destination_icao', 'to_icao']
ORIGIN_MARKET_COLS = ['origin_market', 'origin_city', 'origin_metro']
DEST_MARKET_COLS = ['destination_market', 'destination_city', 'destination_metro']
ROUTE_LABEL_COLS = ['primary_route_label', 'primary_route', 'route_label',
                    'airway_route', 'route_string', 'route']
WAYPOINTS_COLS = ['waypoints', 'route_waypoints', 'key_waypoints', 'waypoint_list',
                  'route_fixes', 'fixes']
ROUTE_FAMILY_COLS = ['route_family', 'family', 'route_group']
SOURCE_BASIS_COLS = ['source_basis', 'source', 'data_source', 'basis']

WAYPOINT_LABEL_COLS = ['waypoint', 'fix', 'label', 'name', 'identifier', 'id',
                        'waypoint_label', 'fix_id']
LAT_COLS = ['lat', 'latitude', 'lat_dec', 'latitude_dec']
LON_COLS = ['lon', 'longitude', 'lon_dec', 'long', 'longitude_dec']
WP_TYPE_COLS = ['type', 'waypoint_type', 'fix_type']


# ─── File search ──────────────────────────────────────────────────────────────

def find_file(explicit: str | None, defaults: list[Path], label: str) -> Path | None:
    """Locate a file. Returns Path if found, None otherwise."""
    if explicit:
        p = Path(explicit)
        if p.exists():
            return p
        log(f'{label}_path_not_found', {'path': str(p)})
        return None
    for p in defaults:
        if p.exists():
            log(f'{label}_found', {'path': str(p)})
            return p
    return None


# ─── CSV readers ─────────────────────────────────────────────────────────────

def read_csv(path: Path) -> list[dict]:
    """Read CSV file and return list of dicts."""
    try:
        with path.open(newline='', encoding='utf-8-sig') as f:
            return list(csv.DictReader(f))
    except Exception as exc:
        log('csv_read_error', {'path': str(path), 'error': str(exc)})
        return []


def load_waypoint_coords(path: Path | None) -> dict[str, tuple[float, float]]:
    """Return dict mapping waypoint_label.upper() → (lat, lon).
    Returns empty dict if path is None or file cannot be read.
    """
    if path is None:
        return {}
    rows = read_csv(path)
    coords: dict[str, tuple[float, float]] = {}
    for row in rows:
        label = _first_col(row, WAYPOINT_LABEL_COLS)
        lat_s = _first_col(row, LAT_COLS)
        lon_s = _first_col(row, LON_COLS)
        if label and lat_s and lon_s:
            try:
                coords[label.upper()] = (float(lat_s), float(lon_s))
            except (ValueError, TypeError):
                pass
    log('waypoint_coords_loaded', {'count': len(coords), 'path': str(path)})
    return coords


def load_airport_coords() -> dict[str, tuple[float, float]]:
    """Build IATA/ICAO → (lat, lon) from travelcast_focus_airports.csv.
    Used as a fallback coordinate source for endpoint airports.
    """
    csv_path = ROOT / 'data' / 'reference' / 'travelcast_focus_airports.csv'
    if not csv_path.exists():
        csv_path = ROOT / 'data' / 'reference' / 'travelcast_airports_master.csv'
    if not csv_path.exists():
        return {}
    coords: dict[str, tuple[float, float]] = {}
    rows = read_csv(csv_path)
    for row in rows:
        iata = (row.get('iata') or '').strip().upper()
        icao = (row.get('icao') or '').strip().upper()
        lat_s = row.get('latitude') or row.get('lat') or ''
        lon_s = row.get('longitude') or row.get('lon') or ''
        if lat_s and lon_s:
            try:
                latlon = (float(lat_s), float(lon_s))
                if iata:
                    coords[iata] = latlon
                if icao:
                    coords[icao] = latlon
            except (ValueError, TypeError):
                pass
    log('airport_coords_loaded', {'count': len(coords)})
    return coords


# ─── Source CSV parsing ───────────────────────────────────────────────────────

def parse_waypoints_string(wp_str: str | None) -> list[str]:
    """Parse a waypoint string into individual labels.

    Handles space-separated, comma-separated, or semicolon-separated lists.
    Returns empty list if input is None or empty.
    """
    if not wp_str:
        return []
    raw = wp_str.strip()
    if ',' in raw:
        parts = raw.split(',')
    elif ';' in raw:
        parts = raw.split(';')
    else:
        parts = raw.split()
    return [p.strip().upper() for p in parts if p.strip()]


def parse_rank(val: str | None) -> int | None:
    if val is None:
        return None
    try:
        return int(str(val).strip())
    except (ValueError, TypeError):
        return None


def parse_source_csv(path: Path) -> list[dict]:
    """Parse the Top-50 route source CSV into corridor spec dicts.

    Returns a list of raw corridor dicts. Does not resolve coordinates.
    Does not invent missing fields.
    """
    rows = read_csv(path)
    if not rows:
        log('source_csv_empty', {'path': str(path)})
        return []

    corridors: list[dict] = []
    for i, row in enumerate(rows):
        origin_iata = _first_col(row, ORIGIN_COLS)
        dest_iata   = _first_col(row, DEST_COLS)
        if not origin_iata or not dest_iata:
            log('row_skipped_no_airports', {'row': i})
            continue

        corridor_key = _first_col(row, CORRIDOR_KEY_COLS)
        if not corridor_key:
            corridor_key = f'{origin_iata.upper()}-{dest_iata.upper()}'

        corridor_name = _first_col(row, CORRIDOR_NAME_COLS)
        if not corridor_name:
            corridor_name = f'{origin_iata.upper()} → {dest_iata.upper()}'

        corridors.append({
            'corridor_key':              corridor_key,
            'corridor_name':             corridor_name,
            'rank':                      parse_rank(_first_col(row, RANK_COLS)),
            'origin_market':             _first_col(row, ORIGIN_MARKET_COLS),
            'destination_market':        _first_col(row, DEST_MARKET_COLS),
            'origin_airport_iata':       origin_iata.upper(),
            'origin_airport_icao':       (_first_col(row, ORIGIN_ICAO_COLS) or '').upper() or None,
            'destination_airport_iata':  dest_iata.upper(),
            'destination_airport_icao':  (_first_col(row, DEST_ICAO_COLS) or '').upper() or None,
            'primary_route_label':       _first_col(row, ROUTE_LABEL_COLS),
            'route_family':              _first_col(row, ROUTE_FAMILY_COLS),
            'waypoints_raw':             _first_col(row, WAYPOINTS_COLS),
            'source_basis':              _first_col(row, SOURCE_BASIS_COLS),
        })
    log('source_csv_parsed', {'total_rows': len(rows), 'valid_corridors': len(corridors),
                               'path': str(path)})
    return corridors


# ─── Geometry builder ─────────────────────────────────────────────────────────

def build_linestring_geojson(coord_list: list[tuple[float, float]]) -> dict | None:
    """Build a GeoJSON LineString from [(lat, lon), ...] tuples.

    Returns None if fewer than 2 coordinate pairs are provided.
    GeoJSON coordinate order is [lon, lat].
    Does NOT interpolate or invent missing points.
    """
    if len(coord_list) < 2:
        return None
    return {
        'type': 'LineString',
        'coordinates': [[lon, lat] for lat, lon in coord_list],
    }


def resolve_corridor_geometry(
    spec: dict,
    wp_coords: dict[str, tuple[float, float]],
    airport_coords: dict[str, tuple[float, float]],
    source_file_name: str,
) -> tuple[list[dict], dict]:
    """Resolve waypoints for one corridor and build geometry row.

    Returns:
        (waypoint_rows, geometry_row)

    Does not invent coordinates. Marks unresolved waypoints explicitly.
    """
    corridor_key = spec['corridor_key']
    origin_iata  = spec.get('origin_airport_iata', '')
    dest_iata    = spec.get('destination_airport_iata', '')
    route_label  = spec.get('primary_route_label') or ''
    raw_wps      = spec.get('waypoints_raw') or ''

    # Build the ordered waypoint sequence:
    # origin endpoint → intermediate fixes from route label or waypoints field → destination
    all_labels: list[str] = []
    if origin_iata:
        all_labels.append(origin_iata.upper())

    # Prefer the waypoints field; fall back to parsing the route label
    intermediate = parse_waypoints_string(raw_wps)
    if not intermediate and route_label:
        intermediate = parse_waypoints_string(route_label)

    # Remove origin/dest from the intermediate list if they appear
    skip = {origin_iata.upper(), dest_iata.upper()}
    for wp in intermediate:
        if wp not in skip:
            all_labels.append(wp)

    if dest_iata:
        all_labels.append(dest_iata.upper())

    # Resolve each label to (lat, lon) — from waypoint CSV first, then airports
    waypoint_rows: list[dict] = []
    resolved_coords: list[tuple[float, float]] = []
    unresolved_labels: list[str] = []

    for order, label in enumerate(all_labels):
        is_endpoint = (label == origin_iata.upper() or label == dest_iata.upper())
        lat_lon = wp_coords.get(label) or airport_coords.get(label)

        if lat_lon:
            coord_src = 'airport_lookup' if airport_coords.get(label) and not wp_coords.get(label) \
                        else 'faa_waypoint_csv'
            coord_status = 'airport_lookup' if coord_src == 'airport_lookup' else 'resolved'
            resolved_coords.append(lat_lon)
            waypoint_rows.append({
                'corridor_key':     corridor_key,
                'waypoint_order':   order,
                'waypoint_label':   label,
                'waypoint_type':    'airport' if is_endpoint else 'fix',
                'lat':              lat_lon[0],
                'lon':              lat_lon[1],
                'coordinate_source': coord_src,
                'coordinate_status': coord_status,
                'is_route_endpoint': is_endpoint,
            })
        else:
            unresolved_labels.append(label)
            waypoint_rows.append({
                'corridor_key':     corridor_key,
                'waypoint_order':   order,
                'waypoint_label':   label,
                'waypoint_type':    'airport' if is_endpoint else None,
                'lat':              None,
                'lon':              None,
                'coordinate_source': None,
                'coordinate_status': 'unresolved',
                'is_route_endpoint': is_endpoint,
            })

    # Build geometry only if ≥2 resolved coordinates
    geojson = build_linestring_geojson(resolved_coords)
    has_unresolved = bool(unresolved_labels)

    if geojson:
        g_confidence = 'control_line_scaffold'
        g_status     = 'needs_validation'
        g_method     = 'resolved_waypoint_control_line'
        g_type       = 'LineString'
        g_source     = f'waypoint_control_line_from_{source_file_name}'
    else:
        g_confidence = 'needs_source_file' if not all_labels else 'unvalidated'
        g_status     = 'no_geometry'
        g_method     = None
        g_type       = None
        g_source     = None

    if geojson and has_unresolved:
        g_confidence = 'partially_resolved'

    geometry_row = {
        'corridor_key':       corridor_key,
        'geometry_geojson':   json.dumps(geojson) if geojson else None,
        'geometry_type':      g_type,
        'geometry_source':    g_source,
        'geometry_method':    g_method,
        'geometry_confidence': g_confidence,
        'geometry_status':    g_status,
        'unresolved_waypoints': unresolved_labels,
    }

    return waypoint_rows, geometry_row


# ─── Supabase upsert ─────────────────────────────────────────────────────────

def batched(lst: list, size: int) -> Iterator[list]:
    for i in range(0, len(lst), size):
        yield lst[i: i + size]


def upsert_corridors(
    url: str,
    key: str,
    specs: list[dict],
    wp_rows_by_key: dict[str, list[dict]],
    geom_rows_by_key: dict[str, dict],
    source_file: str,
    fetched_at: str,
) -> tuple[int, int, int, int]:
    """Write corridors, waypoints, and geometry to Supabase.

    Returns (corridors_written, waypoints_written, geom_written, errors).
    """
    errors = 0
    c_written = 0
    w_written = 0
    g_written = 0

    # Upsert corridors
    corridor_rows = []
    for spec in specs:
        ck = spec['corridor_key']
        g  = geom_rows_by_key.get(ck, {})
        corridor_rows.append({
            'corridor_key':             spec['corridor_key'],
            'corridor_name':            spec['corridor_name'],
            'rank':                     spec.get('rank'),
            'origin_market':            spec.get('origin_market'),
            'destination_market':       spec.get('destination_market'),
            'origin_airport_iata':      spec.get('origin_airport_iata'),
            'origin_airport_icao':      spec.get('origin_airport_icao'),
            'destination_airport_iata': spec.get('destination_airport_iata'),
            'destination_airport_icao': spec.get('destination_airport_icao'),
            'primary_route_label':      spec.get('primary_route_label'),
            'route_family':             spec.get('route_family'),
            'source_file':              source_file,
            'source_basis':             spec.get('source_basis'),
            'route_rank_basis':         ROUTE_RANK_BASIS,
            'geometry_confidence':      g.get('geometry_confidence', 'unvalidated'),
            'geometry_status':          g.get('geometry_status', 'needs_validation'),
            'updated_at':               fetched_at,
        })

    for batch in batched(corridor_rows, 50):
        try:
            supabase_post(url, key, 'routecast_corridors', batch, prefer=UPSERT_PREFER)
            c_written += len(batch)
        except Exception as exc:
            log('upsert_error', {'table': 'routecast_corridors', 'error': str(exc)})
            errors += 1

    if not c_written:
        log('write_aborted', {'reason': 'no corridors written; skipping waypoints/geometry'})
        return c_written, w_written, g_written, errors

    # Upsert waypoints (delete + re-insert per corridor — simpler than merge by order)
    all_wp_rows = [wp for wps in wp_rows_by_key.values() for wp in wps]
    for batch in batched(all_wp_rows, 100):
        try:
            supabase_post(url, key, 'routecast_corridor_waypoints', batch,
                          prefer=UPSERT_PREFER)
            w_written += len(batch)
        except Exception as exc:
            log('upsert_error', {'table': 'routecast_corridor_waypoints', 'error': str(exc)})
            errors += 1

    # Upsert geometry (requires corridor_id lookup — done in Supabase via corridor_key)
    geom_rows = []
    for spec in specs:
        ck = spec['corridor_key']
        gr = geom_rows_by_key.get(ck)
        if gr:
            gr['updated_at'] = fetched_at
            geom_rows.append(gr)

    for batch in batched(geom_rows, 50):
        try:
            supabase_post(url, key, 'routecast_corridor_geometry', batch,
                          prefer=UPSERT_PREFER)
            g_written += len(batch)
        except Exception as exc:
            log('upsert_error', {'table': 'routecast_corridor_geometry', 'error': str(exc)})
            errors += 1

    return c_written, w_written, g_written, errors


# ─── Main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            'Seed RouteCast corridor geometry from Top-50 busiest aviation route source file. '
            'Default mode is --dry-run. Use --write to write to Supabase.'
        )
    )
    parser.add_argument('--dry-run', action='store_true', default=True,
                        help='Preview corridors without writing (default)')
    parser.add_argument('--write', action='store_true',
                        help='Write corridors to Supabase (overrides --dry-run)')
    parser.add_argument('--limit', type=int, default=None,
                        help='Limit corridors to process')
    parser.add_argument('--source-csv', type=str, default=None,
                        help='Path to Top-50 route source CSV')
    parser.add_argument('--waypoint-coordinates', type=str, default=None,
                        help='Path to FAA waypoint coordinates CSV')
    parser.add_argument('--unresolved-labels', type=str, default=None,
                        help='Path to FAA unresolved route-label CSV (informational)')
    args = parser.parse_args()

    dry_run = not args.write
    load_env()

    url: str | None = None
    key: str | None = None
    if not dry_run:
        try:
            url, key = get_supabase_creds()
        except RuntimeError as exc:
            log('config_error', {'error': str(exc)})
            sys.exit(1)

    fetched_at = utc_now()

    # ── Locate source files ────────────────────────────────────────────────────

    source_path = find_file(args.source_csv, DEFAULT_SOURCE_PATHS, 'source_csv')
    coord_path  = find_file(args.waypoint_coordinates, DEFAULT_WAYPOINT_COORD_PATHS,
                            'waypoint_coords')
    unresolv_path = find_file(args.unresolved_labels, DEFAULT_UNRESOLVED_PATHS,
                              'unresolved_labels')

    if source_path is None:
        searched = [str(p) for p in DEFAULT_SOURCE_PATHS]
        if args.source_csv:
            searched = [args.source_csv] + searched
        msg = (
            'Top-50 route source file not found. '
            'Searched: ' + ', '.join(searched) + '. '
            'Place the source CSV at one of these paths or use --source-csv PATH. '
            'C2 scaffold is in place and will seed corridors when the source file is available.'
        )
        log('source_csv_missing', {'searched': searched})
        print(f'\nWARN: {msg}')
        if not dry_run:
            print('ERROR: --write requested but source file is missing. Cannot seed corridors.')
            write_feed_run(url, key, SOURCE_ID, success=False,
                           error='source_csv_missing', dry_run=False)
            sys.exit(1)
        print('DRY-RUN: No corridors to preview — source file required.')
        write_feed_run(None, None, SOURCE_ID, success=True, records=0, dry_run=True)
        return

    if coord_path is None:
        log('waypoint_coords_missing', {'note': 'corridor geometry will have no resolved waypoints'})
        print('\nWARN: Waypoint coordinates file not found. '
              'Corridors will be seeded without intermediate waypoint geometry. '
              'Airport endpoints will be resolved from the project airport master.')

    log('source_files', {
        'source_csv': str(source_path),
        'waypoint_coords': str(coord_path) if coord_path else None,
        'unresolved_labels': str(unresolv_path) if unresolv_path else None,
    })

    # ── Load coordinate lookups ────────────────────────────────────────────────

    wp_coords     = load_waypoint_coords(coord_path)
    airport_coords = load_airport_coords()

    if unresolv_path:
        unresolved_known = {
            row.get('waypoint', row.get('label', ''))
            for row in read_csv(unresolv_path)
        }
        log('unresolved_labels_loaded', {'count': len(unresolved_known)})
    else:
        unresolved_known: set = set()

    # ── Parse source CSV ───────────────────────────────────────────────────────

    specs = parse_source_csv(source_path)
    if not specs:
        log('no_corridors_parsed', {'path': str(source_path)})
        print('WARN: No valid corridor rows found in source CSV.')
        write_feed_run(url if not dry_run else None,
                       key if not dry_run else None,
                       SOURCE_ID, success=True, records=0, dry_run=dry_run)
        return

    if args.limit:
        specs = specs[: args.limit]

    source_file_name = source_path.name

    # ── Resolve waypoints and build geometry ───────────────────────────────────

    wp_rows_by_key:   dict[str, list[dict]] = {}
    geom_rows_by_key: dict[str, dict]       = {}
    geom_built = 0

    for spec in specs:
        ck = spec['corridor_key']
        wps, geom = resolve_corridor_geometry(
            spec, wp_coords, airport_coords, source_file_name
        )
        wp_rows_by_key[ck]   = wps
        geom_rows_by_key[ck] = geom
        if geom.get('geometry_geojson'):
            geom_built += 1

    log('resolution_complete', {
        'corridors': len(specs),
        'geometry_built': geom_built,
        'no_geometry': len(specs) - geom_built,
    })

    # ── Dry-run preview ────────────────────────────────────────────────────────

    if dry_run:
        print(f'\nDRY-RUN: {len(specs)} corridor(s) from {source_file_name}')
        print(f'  Waypoint coordinates available: {len(wp_coords)} fixes')
        print(f'  Airport coordinates available:  {len(airport_coords)} airports')
        print(f'  Geometry built: {geom_built} / {len(specs)} corridors')
        print()
        for spec in specs[:5]:
            ck   = spec['corridor_key']
            geom = geom_rows_by_key[ck]
            wps  = wp_rows_by_key[ck]
            resolved   = sum(1 for w in wps if w['coordinate_status'] != 'unresolved')
            unresolved = [w['waypoint_label'] for w in wps if w['coordinate_status'] == 'unresolved']
            print(f"  {ck}: {spec['corridor_name']}")
            print(f"    rank={spec.get('rank')}  route={spec.get('primary_route_label')}")
            print(f"    waypoints={len(wps)}  resolved={resolved}  unresolved={unresolved}")
            print(f"    geometry_status={geom['geometry_status']}  "
                  f"confidence={geom['geometry_confidence']}")
        if len(specs) > 5:
            print(f'  ... and {len(specs) - 5} more corridors (use --limit to restrict)')
        print()
        print('NOTE: RouteCast corridor geometry is a planning/display scaffold.')
        print('      It is NOT FAA operational delay truth.')
        print('      Run with --write to write to Supabase.')
        write_feed_run(None, None, SOURCE_ID, success=True, records=len(specs), dry_run=True)
        return

    # ── Write to Supabase ──────────────────────────────────────────────────────

    if not url or not key:
        log('skipping_write', {'reason': 'no supabase credentials'})
        sys.exit(1)

    c_written, w_written, g_written, errors = upsert_corridors(
        url, key, specs, wp_rows_by_key, geom_rows_by_key,
        source_file=str(source_path), fetched_at=fetched_at,
    )

    success = errors == 0
    write_feed_run(url, key, SOURCE_ID, success=success, records=c_written,
                   error=f'{errors} write error(s)' if errors else None)

    log('done', {
        'corridors_written': c_written,
        'waypoints_written': w_written,
        'geometry_written':  g_written,
        'errors':            errors,
    })

    if errors:
        sys.exit(1)


if __name__ == '__main__':
    main()
