#!/usr/bin/env python3
"""Fetch and ingest NWS CAP public weather alerts from api.weather.gov.

NWS CAP alerts are Public Weather Alert Truth for TravelCast.
They are NOT FAA operational delay data.

DOCTRINE:
  NWS CAP / WEA = Public Weather Alert Truth.
  NWS alerts are NOT FAA operational delay truth.
  NWS alerts provide public weather hazard CONTEXT for airports
  and nearby metros. They do NOT predict or confirm:
    - Ground stops (GS)
    - Ground delay programs (GDP)
    - Airport arrival rates (AAR)
    - Route closures or diversions
    - Delay minutes
    - ATCSCC traffic management initiatives
  FAA NAS / ATCSCC / official airport / NOTAM sources remain operational truth.
  AviationWeather.gov remains aviation-weather truth.
  Do not invent alerts, polygons, WEA status, hazards, or impacts.
  Empty state is better than invented data.

Airport matching:
  geometry_intersection — airport lat/lon is inside alert polygon (high confidence)
  zone_text_match       — scaffold field only; not implemented in this phase
  area_text_match       — not implemented; low confidence

Staleness:
  Alert native expiry: expires_at_utc from NWS is authoritative.
  Data freshness: is_stale flag set in view when fetched_at_utc >= 8 hours ago.
  Recommended refresh cadence: every 10–30 minutes in production.

Source:
  https://api.weather.gov/alerts/active
  NWS public API — no API key required.
  User-Agent identification required per NWS API policy.

Usage:
  python scripts/pull/pull_nws_alerts.py
  python scripts/pull/pull_nws_alerts.py --dry-run
  python scripts/pull/pull_nws_alerts.py --limit 20
  python scripts/pull/pull_nws_alerts.py --area TX,LA,MS,AL,GA,FL

Supabase tables written:
  public_weather_alerts       — one row per NWS alert (upsert on alert_id)
  airport_public_alert_matches — airport × alert linkages via geometry intersection

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

SOURCE_ID = 'nws_alerts'
NWS_ALERTS_BASE = 'https://api.weather.gov/alerts/active'
NWS_ACCEPT_HEADER = 'application/geo+json'
MAX_PAGES = 20        # Safety cap on pagination
UPSERT_PREFER = 'resolution=merge-duplicates,return=minimal'


# ─── Geometry helpers ─────────────────────────────────────────────────────────

def _point_in_ring(lon: float, lat: float, ring: list) -> bool:
    """Ray-casting point-in-polygon test.
    ring: list of [lon, lat] pairs (GeoJSON coordinate order).
    """
    n = len(ring)
    inside = False
    j = n - 1
    for i in range(n):
        xi, yi = ring[i][0], ring[i][1]
        xj, yj = ring[j][0], ring[j][1]
        if ((yi > lat) != (yj > lat)) and (
            lon < (xj - xi) * (lat - yi) / (yj - yi) + xi
        ):
            inside = not inside
        j = i
    return inside


def point_in_geometry(lat: float, lon: float, geometry: dict | None) -> bool:
    """Test if a lat/lon point is inside a GeoJSON Polygon or MultiPolygon.
    Returns False if geometry is None, empty, or an unsupported type.
    Only uses the outer ring (index 0) of each polygon; holes are not subtracted.
    """
    if not geometry or not isinstance(geometry, dict):
        return False
    gtype = geometry.get('type', '')
    coords = geometry.get('coordinates')
    if not coords:
        return False

    if gtype == 'Polygon':
        # coords = [ outer_ring, ...inner_rings ]
        try:
            return _point_in_ring(lon, lat, coords[0])
        except (IndexError, TypeError):
            return False

    if gtype == 'MultiPolygon':
        # coords = [ polygon1, polygon2, ... ]
        # each polygon = [ outer_ring, ...inner_rings ]
        for polygon in coords:
            try:
                if _point_in_ring(lon, lat, polygon[0]):
                    return True
            except (IndexError, TypeError):
                continue
        return False

    return False


def bbox_of_geometry(geometry: dict | None) -> tuple[float, float, float, float] | None:
    """Return (min_lon, min_lat, max_lon, max_lat) bounding box of a geometry, or None."""
    if not geometry or not isinstance(geometry, dict):
        return None
    gtype = geometry.get('type', '')
    coords = geometry.get('coordinates')
    if not coords:
        return None

    all_points: list = []
    if gtype == 'Polygon':
        for ring in coords:
            all_points.extend(ring)
    elif gtype == 'MultiPolygon':
        for polygon in coords:
            for ring in polygon:
                all_points.extend(ring)
    else:
        return None

    if not all_points:
        return None
    try:
        lons = [p[0] for p in all_points]
        lats = [p[1] for p in all_points]
        return min(lons), min(lats), max(lons), max(lats)
    except (TypeError, IndexError):
        return None


def point_near_bbox(lat: float, lon: float, bbox: tuple, buffer_deg: float = 0.5) -> bool:
    """Quick pre-filter: is point within buffer degrees of bbox? Avoids full ray cast."""
    min_lon, min_lat, max_lon, max_lat = bbox
    return (
        min_lon - buffer_deg <= lon <= max_lon + buffer_deg
        and min_lat - buffer_deg <= lat <= max_lat + buffer_deg
    )


# ─── NWS API helpers ─────────────────────────────────────────────────────────

def build_fetch_urls(areas: list[str] | None) -> list[str]:
    """Build the list of NWS API URLs to fetch.
    If areas are specified, build per-area URLs.
    Otherwise, fetch all active Actual alerts.
    """
    if areas:
        return [
            f'{NWS_ALERTS_BASE}?area={a.strip().upper()}&status=actual'
            for a in areas
            if a.strip()
        ]
    return [f'{NWS_ALERTS_BASE}?status=actual']


def fetch_all_features(start_url: str) -> tuple[list[dict], int]:
    """Fetch all features from an NWS alerts endpoint, following pagination.
    Returns (features_list, page_count).
    """
    features: list[dict] = []
    url: str | None = start_url
    pages = 0

    while url and pages < MAX_PAGES:
        try:
            data = http_get_json(url, headers={'Accept': NWS_ACCEPT_HEADER})
        except Exception as exc:
            log('nws_fetch_error', {'url': url[:100], 'error': str(exc)})
            break

        if not isinstance(data, dict):
            log('nws_format_error', {'url': url[:100], 'type': type(data).__name__})
            break

        batch = data.get('features') or []
        features.extend(batch)
        pages += 1

        next_url = (data.get('pagination') or {}).get('next')
        url = next_url if next_url and next_url != url else None

    return features, pages


# ─── Alert parsing ────────────────────────────────────────────────────────────

def iso_or_none(val) -> str | None:
    """Return ISO string if val is a non-empty string, else None."""
    if val and isinstance(val, str):
        v = val.strip()
        return v if v else None
    return None


def parse_alert_feature(feature: dict, fetched_at: str) -> dict | None:
    """Parse one NWS GeoJSON feature into a public_alerts row.
    Returns None if the feature has no valid ID.
    """
    if not isinstance(feature, dict):
        return None

    props = feature.get('properties') or {}
    alert_id = props.get('id') or ''
    if not alert_id:
        return None

    geometry = feature.get('geometry')
    has_geom = bool(
        geometry
        and isinstance(geometry, dict)
        and geometry.get('coordinates')
    )

    geocode = props.get('geocode') or {}

    return {
        'alert_id':           alert_id,
        'status':             props.get('status'),
        'message_type':       props.get('messageType'),
        'category':           props.get('category'),
        'severity':           props.get('severity'),
        'urgency':            props.get('urgency'),
        'certainty':          props.get('certainty'),
        'event_type':         props.get('event'),
        'response':           props.get('response'),
        'sent_at_utc':        iso_or_none(props.get('sent')),
        'effective_at_utc':   iso_or_none(props.get('effective')),
        'onset_at_utc':       iso_or_none(props.get('onset')),
        'expires_at_utc':     iso_or_none(props.get('expires')),
        'ends_at_utc':        iso_or_none(props.get('ends')),
        'area_desc':          props.get('areaDesc'),
        'sender':             props.get('sender'),
        'sender_name':        props.get('senderName'),
        'affected_zones':     props.get('affectedZones') or None,
        'geocode_ugc':        geocode.get('UGC') or None,
        'geocode_same':       geocode.get('SAME') or None,
        'headline':           props.get('headline'),
        'description':        props.get('description'),
        'instruction':        props.get('instruction'),
        'parameters_json':    props.get('parameters') or None,
        'geometry_json':      geometry if has_geom else None,
        'has_geometry':       has_geom,
        'raw_cap_json':       feature,
        'nws_alert_url':      props.get('@id') or feature.get('id'),
        'source_system_id':   SOURCE_ID,
        'fetched_at_utc':     fetched_at,
        'updated_at':         fetched_at,
    }


# ─── Airport matching ─────────────────────────────────────────────────────────

def match_alert_to_airports(
    alert_row: dict,
    airports: list[dict],
) -> list[dict]:
    """Return airport_public_alert_matches rows for one alert.

    Matches by geometry_intersection only (high confidence).
    Alerts without geometry produce no associations in this phase.
    Zone/text matching is scaffolded in the schema but not implemented here
    — it requires a zone→airport lookup table (Phase C future work).

    Does NOT claim FAA operational impacts. Match indicates
    'weather alert near/over this airport' only.
    """
    if not alert_row.get('has_geometry') or not alert_row.get('geometry_json'):
        return []

    geometry = alert_row['geometry_json']
    bbox = bbox_of_geometry(geometry)
    alert_id = alert_row['alert_id']
    assocs: list[dict] = []

    for ap in airports:
        try:
            lat = float(ap.get('latitude') or 0)
            lon = float(ap.get('longitude') or 0)
        except (TypeError, ValueError):
            continue
        if lat == 0.0 and lon == 0.0:
            continue

        # Bounding-box pre-filter for efficiency
        if bbox and not point_near_bbox(lat, lon, bbox, buffer_deg=0.1):
            continue

        if point_in_geometry(lat, lon, geometry):
            assocs.append({
                'alert_id':         alert_id,
                'airport_id':       ap['airport_id'],
                'iata':             ap.get('iata', ''),
                'icao':             ap.get('icao', ''),
                'match_method':     'geometry_intersection',
                'match_confidence': 'high',
                'distance_km':      None,
            })

    return assocs


def batched(lst: list, size: int):
    for i in range(0, len(lst), size):
        yield lst[i:i + size]


# ─── Main ────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description='Fetch NWS CAP public weather alerts and ingest into Supabase'
    )
    parser.add_argument('--dry-run', action='store_true',
                        help='Fetch and parse; do not write to Supabase')
    parser.add_argument('--limit', type=int, default=None,
                        help='Limit number of alerts to process (for testing)')
    parser.add_argument(
        '--area',
        type=str,
        default=None,
        help='Comma-separated NWS area codes to fetch (e.g. TX,LA,GA). '
             'Default: fetch all active alerts.',
    )
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

    airports: list[dict] = []
    if url and key:
        airports = get_active_airports(url, key)
    else:
        csv_path = ROOT / 'data' / 'reference' / 'travelcast_focus_airports.csv'
        if csv_path.exists():
            import csv as csv_mod
            with csv_path.open(newline='', encoding='utf-8') as f:
                rows = list(csv_mod.DictReader(f))
            airports = [
                {
                    'airport_id': r.get('icao', '').upper(),
                    'iata': r.get('iata', '').upper(),
                    'icao': r.get('icao', '').upper(),
                    'latitude': float(r.get('latitude') or 0) or None,
                    'longitude': float(r.get('longitude') or 0) or None,
                }
                for r in rows
                if r.get('active', 'true').lower() in ('true', '1', 'yes', '')
                and r.get('icao') and r.get('latitude') and r.get('longitude')
            ]
    airports = [ap for ap in airports
                if ap.get('latitude') is not None and ap.get('longitude') is not None]
    log('airports_loaded', {'count': len(airports)})

    # ── Build fetch URLs ──────────────────────────────────────────────────────

    areas = [a.strip() for a in args.area.split(',')] if args.area else None
    fetch_urls = build_fetch_urls(areas)
    log('fetch_plan', {'urls': len(fetch_urls), 'areas': areas})

    # ── Fetch NWS alerts ──────────────────────────────────────────────────────

    all_features: list[dict] = []
    seen_ids: set[str] = set()
    fetch_errors = 0

    for fetch_url in fetch_urls:
        features, pages = fetch_all_features(fetch_url)
        log('nws_fetch_result', {
            'url': fetch_url[:80],
            'features': len(features),
            'pages': pages,
        })
        for f in features:
            fid = (f.get('properties') or {}).get('id', '')
            if fid and fid not in seen_ids:
                seen_ids.add(fid)
                all_features.append(f)

    log('dedup_complete', {'unique_alerts': len(all_features)})

    if args.limit:
        all_features = all_features[: args.limit]

    # ── Parse alerts ─────────────────────────────────────────────────────────

    alert_rows: list[dict] = []
    assoc_rows: list[dict] = []
    parse_errors = 0
    geom_count = 0

    for feature in all_features:
        try:
            row = parse_alert_feature(feature, fetched_at)
        except Exception as exc:
            log('parse_error', {'error': str(exc)})
            parse_errors += 1
            continue
        if not row:
            continue
        alert_rows.append(row)

        if row.get('has_geometry'):
            geom_count += 1
            new_assocs = match_alert_to_airports(row, airports)
            assoc_rows.extend(new_assocs)

    log('parse_complete', {
        'alerts': len(alert_rows),
        'with_geometry': geom_count,
        'without_geometry': len(alert_rows) - geom_count,
        'airport_associations': len(assoc_rows),
        'parse_errors': parse_errors,
    })

    # Save raw cache
    raw_summary = [
        {'id': f.get('properties', {}).get('id', ''),
         'event': f.get('properties', {}).get('event', ''),
         'area': f.get('properties', {}).get('areaDesc', '')[:60]}
        for f in all_features[:100]
    ]
    save_raw('nws_alerts_raw', raw_summary)
    save_raw('nws_alerts_parsed', {
        'fetched_at': fetched_at,
        'total_alerts': len(alert_rows),
        'with_geometry': geom_count,
        'airport_associations': len(assoc_rows),
        'fetch_errors': fetch_errors,
        'parse_errors': parse_errors,
    })

    # ── Dry-run output ───────────────────────────────────────────────────────

    if args.dry_run:
        for row in alert_rows[:5]:
            log('alert_preview', {
                'alert_id': row['alert_id'][:50],
                'event_type': row.get('event_type'),
                'severity': row.get('severity'),
                'urgency': row.get('urgency'),
                'area_desc': (row.get('area_desc') or '')[:60],
                'has_geometry': row.get('has_geometry'),
                'expires_at_utc': row.get('expires_at_utc'),
            })
        for a in assoc_rows[:5]:
            log('assoc_preview', {
                'alert_id': a['alert_id'][:50],
                'iata': a['iata'],
                'match_method': a['match_method'],
            })
        write_feed_run(None, None, SOURCE_ID, success=True,
                       records=len(alert_rows), dry_run=True)
        return

    # ── Write to Supabase ────────────────────────────────────────────────────

    if not url or not key:
        log('skipping_write', {'reason': 'no supabase creds'})
        return

    write_errors = 0
    alert_count = 0
    assoc_count = 0

    for batch in batched(alert_rows, 50):
        try:
            supabase_post(url, key, 'public_weather_alerts', batch, prefer=UPSERT_PREFER)
            alert_count += len(batch)
        except Exception as exc:
            log('upsert_error', {'table': 'public_weather_alerts', 'error': str(exc)})
            write_errors += 1

    for batch in batched(assoc_rows, 100):
        try:
            supabase_post(url, key, 'airport_public_alert_matches', batch,
                          prefer=UPSERT_PREFER)
            assoc_count += len(batch)
        except Exception as exc:
            log('upsert_error', {
                'table': 'airport_public_alert_matches', 'error': str(exc)
            })
            write_errors += 1

    success = write_errors == 0 and fetch_errors == 0
    write_feed_run(url, key, SOURCE_ID, success=success,
                   records=alert_count,
                   error=f'{write_errors} write error(s)' if write_errors else None)

    log('done', {
        'alerts_written': alert_count,
        'associations_written': assoc_count,
        'write_errors': write_errors,
        'fetch_errors': fetch_errors,
    })

    if write_errors:
        sys.exit(1)


if __name__ == '__main__':
    main()
