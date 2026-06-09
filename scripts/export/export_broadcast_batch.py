#!/usr/bin/env python3
"""Batch broadcast export for TravelCast AviatorGraf Prep.

Reads live airport status from Supabase v_airport_status_dashboard and
generates broadcast-ready export files matching the frontend exporter formats.

Writes to data/exports/YYYYMMDD_HHMM/:
  dashboard.json          — all airports, dashboardJson format
  airports.geojson        — all airports, GeoJSON FeatureCollection
  active_events.placefile — airports with active FAA/NAS events (GRLevelX format)
  {IATA}_broadcast.json   — individual broadcast package per active airport
  manifest.json           — export metadata and inventory

Doctrine:
  FAA NAS / ATCSCC = operational truth (Current Operational Impact)
  AviationWeather.gov = aviation weather truth
  NWS = forecast proxy only, NOT an official FAA delay forecast
  TravelCast exports summarize official source data; never invent conditions.

Usage:
  python export_broadcast_batch.py [--dry-run] [--limit N] [--all]
    --dry-run   Print manifest; skip writing files to disk
    --limit N   Process only first N airports
    --all       Generate individual packages for all airports, not just active-event
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / 'pull'))
from lib_pull import (
    ROOT,
    load_env,
    log,
    utc_now,
    get_supabase_creds,
    supabase_get,
)

EXPORTS_DIR = ROOT / 'data' / 'exports'

NWS_PROXY_NOTICE = (
    'Forecast weather impact is an NWS forecast proxy and is '
    'NOT an official FAA delay forecast.'
)
SOURCE_DOCTRINE = {
    'operational':      'Current Operational Impact — FAA NAS Status',
    'forecast':         'Forecast Weather Impact — NWS forecast proxy',
    'aviation_weather': 'Aviation Weather Truth — AviationWeather.gov',
    'graphics':         'Graphics Output — TravelCast generated package',
}
SOURCE_DOCTRINE_STR = ' | '.join(SOURCE_DOCTRINE.values())


# ──────────────────────────────── helpers ─────────────────────────────────────

def _op_impact_color(r: dict) -> str:
    """Infer operational impact color. Matches JS opImpactColor() fallback logic."""
    color = (r.get('current_impact_color') or '').lower()
    if color:
        return color
    dt = (r.get('current_delay_type') or '').lower()
    if dt in ('airport closure', 'ground stop'):
        return 'red'
    if dt in ('ground delay program', 'arrival delay', 'departure delay'):
        return 'amber'
    return 'green'


def _is_active_event(r: dict) -> bool:
    dt = (r.get('current_delay_type') or '').strip()
    return bool(dt) and dt.lower() not in ('none', 'normal')


def _freshness_summary(records: list[dict]) -> dict:
    counts: dict[str, int] = {}
    for r in records:
        s = r.get('freshness_status') or 'unknown'
        counts[s] = counts.get(s, 0) + 1
    return counts


# ──────────────────────────────── formatters ──────────────────────────────────

def _dashboard_json(records: list[dict], generated_at: str) -> dict:
    """Match JS exportDashboardJson.dashboardJson() format."""
    return {
        'product':           'travelcast_airport_status_dashboard',
        'product_version':   '1.0',
        'generated_at':      generated_at,
        'source_mode':       'live',
        'airport_count':     len(records),
        'source_doctrine':   SOURCE_DOCTRINE,
        'nws_proxy_notice':  NWS_PROXY_NOTICE,
        'freshness_summary': _freshness_summary(records),
        'records':           records,
    }


def _airport_feature(r: dict) -> dict:
    """Match JS exportGeojson.airportFeature() format."""
    impact = r.get('current_delay_type') or r.get('forecast_impact_label') or 'Monitor'
    iata = r.get('iata') or r.get('airport_id', '')
    return {
        'type': 'Feature',
        'properties': {
            'title':                 f'{iata} {impact}',
            'airport_id':            r.get('airport_id'),
            'iata':                  r.get('iata'),
            'icao':                  r.get('icao'),
            'display_name':          r.get('display_name'),
            'city':                  r.get('city'),
            'region':                r.get('region'),
            'overall_impact_color':  r.get('overall_impact_color'),
            'current_delay_type':    r.get('current_delay_type'),
            'avg_delay_minutes':     r.get('avg_delay_minutes'),
            'forecast_impact_color': r.get('forecast_impact_color'),
            'forecast_impact_label': r.get('forecast_impact_label'),
            'flight_category':       r.get('flight_category'),
            'freshness_status':      r.get('freshness_status'),
            'last_updated_at':       r.get('last_updated_at'),
            'reason':                r.get('current_reason') or r.get('forecast_impact_reasons'),
            'source':                SOURCE_DOCTRINE['graphics'],
        },
        'geometry': {
            'type':        'Point',
            'coordinates': [float(r['longitude']), float(r['latitude'])],
        },
    }


def _geojson(records: list[dict], generated_at: str) -> dict:
    """Match JS exportGeojson.airportRowsToGeoJSON() format."""
    features = [
        _airport_feature(r) for r in records
        if r.get('latitude') and r.get('longitude')
    ]
    return {
        'type':             'FeatureCollection',
        'generated_at':     generated_at,
        'source_mode':      'live',
        'feature_count':    len(features),
        'source_doctrine':  SOURCE_DOCTRINE_STR,
        'nws_proxy_notice': NWS_PROXY_NOTICE,
        'features':         features,
    }


def _placefile(records: list[dict], generated_at: str) -> str:
    """Match JS exportPlacefile.airportPlacefile() format (GRLevelX)."""
    lines = [
        'Title: TravelCast Airport Impact Overlay',
        f'; Generated: {generated_at}',
        '; Source mode: live',
        f'; Doctrine: {SOURCE_DOCTRINE["operational"]}',
        '; NWS forecast impact is a proxy — NOT an official FAA delay forecast',
        'Refresh: 60',
        'Font: 1, 11, 1, "Arial"',
    ]
    for r in records:
        if not r.get('latitude') or not r.get('longitude'):
            continue
        impact = r.get('current_delay_type') or r.get('forecast_impact_label') or 'Monitor'
        delay = f' - {r["avg_delay_minutes"]} min avg' if r.get('avg_delay_minutes') else ''
        fresh = r.get('freshness_status', '')
        fresh_tag = f' [{fresh}]' if fresh and fresh != 'fresh' else ''
        iata = r.get('iata') or r.get('airport_id', '')
        label = f'{iata}: {impact}{delay}{fresh_tag}'
        lines.append(f'Text: {r["latitude"]},{r["longitude"]},1,"{label}"')
    lines.append('End:')
    return '\n'.join(lines) + '\n'


def _broadcast_package(r: dict, generated_at: str) -> dict:
    """Match JS exportBroadcastPackage.airportBroadcastPackage() format."""
    valid_until = (
        datetime.now(timezone.utc) + timedelta(hours=1)
    ).isoformat()
    return {
        'package_version': '1.0',
        'generated_at':    generated_at,
        'valid_until':     valid_until,
        'source_mode':     'live',
        'source_labels': [
            SOURCE_DOCTRINE['operational'],
            SOURCE_DOCTRINE['forecast'],
            SOURCE_DOCTRINE['aviation_weather'],
            SOURCE_DOCTRINE['graphics'],
        ],
        'nws_proxy_notice': NWS_PROXY_NOTICE,
        'airport': {
            'airport_id':  r.get('airport_id'),
            'iata':        r.get('iata'),
            'icao':        r.get('icao'),
            'display_name': r.get('display_name'),
            'city':        r.get('city'),
            'region':      r.get('region'),
            'latitude':    r.get('latitude'),
            'longitude':   r.get('longitude'),
        },
        'operational_status': {
            'current_delay_type':  r.get('current_delay_type'),
            'current_reason':      r.get('current_reason'),
            'avg_delay_minutes':   r.get('avg_delay_minutes'),
            'max_delay_minutes':   r.get('max_delay_minutes'),
            'arrival_runway':      r.get('arrival_runway'),
            'departure_runway':    r.get('departure_runway'),
            'aar':                 r.get('aar'),
            'current_impact_color': _op_impact_color(r),
            'freshness_status':    r.get('freshness_status'),
            'last_updated_at':     r.get('last_updated_at'),
            'source':              SOURCE_DOCTRINE['operational'],
        },
        'forecast_impact': {
            'forecast_impact_color':   r.get('forecast_impact_color'),
            'forecast_impact_label':   r.get('forecast_impact_label'),
            'forecast_impact_reasons': r.get('forecast_impact_reasons'),
            'source':                  SOURCE_DOCTRINE['forecast'],
            'notice':                  NWS_PROXY_NOTICE,
        },
        'aviation_weather': {
            'metar_condition':  r.get('metar_condition'),
            'metar_wind':       r.get('metar_wind'),
            'flight_category':  r.get('flight_category'),
            'source':           SOURCE_DOCTRINE['aviation_weather'],
        },
    }


# ──────────────────────────────── main ────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description='Generate broadcast export batch from Supabase airport status'
    )
    parser.add_argument('--dry-run', action='store_true',
                        help='Print manifest; do not write files')
    parser.add_argument('--limit', type=int, default=None,
                        help='Process only first N airports')
    parser.add_argument('--all', action='store_true', dest='export_all',
                        help='Generate individual packages for all airports, not just active-event')
    args = parser.parse_args()

    load_env()
    log('export_batch_start', {
        'dry_run': args.dry_run,
        'limit': args.limit,
        'all': args.export_all,
    })

    try:
        sb_url, sb_key = get_supabase_creds()
    except RuntimeError as e:
        log('supabase_creds_error', {'error': str(e)})
        sys.exit(1)

    # Fetch all active airports from the live view
    try:
        records = supabase_get(sb_url, sb_key, 'v_airport_status_dashboard', {
            'order': 'region.asc,iata.asc',
        })
        log('airports_fetched', {'count': len(records), 'source': 'v_airport_status_dashboard'})
    except RuntimeError as e:
        log('airports_fetch_error', {'error': str(e)})
        sys.exit(1)

    if args.limit:
        records = records[: args.limit]
        log('airports_limited', {'limit': args.limit, 'count_after_limit': len(records)})

    active_records = [r for r in records if _is_active_event(r)]
    package_records = records if args.export_all else active_records

    log('active_events_found', {
        'active_count': len(active_records),
        'package_count': len(package_records),
        'note': 'individual packages generated for active-event airports (use --all for all)',
    })

    generated_at = utc_now()
    timestamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M')
    out_dir = EXPORTS_DIR / timestamp

    # Build all output objects
    dashboard = _dashboard_json(records, generated_at)
    geojson   = _geojson(records, generated_at)
    placefile = _placefile(active_records, generated_at)
    packages  = {
        (r.get('iata') or r.get('airport_id', 'UNKNOWN')): _broadcast_package(r, generated_at)
        for r in package_records
    }

    manifest = {
        'export_version':     '1.0',
        'generated_at':       generated_at,
        'source_mode':        'live',
        'export_dir':         str(out_dir),
        'airport_count':      len(records),
        'active_event_count': len(active_records),
        'package_count':      len(packages),
        'exports': {
            'dashboard_json':         'dashboard.json',
            'geojson':                'airports.geojson',
            'placefile':              'active_events.placefile',
            'broadcast_packages':     sorted(f'{iata}_broadcast.json' for iata in packages),
        },
        'freshness_summary':  _freshness_summary(records),
        'source_doctrine':    SOURCE_DOCTRINE,
        'nws_proxy_notice':   NWS_PROXY_NOTICE,
        'active_airports': [
            {
                'iata':         r.get('iata'),
                'delay_type':   r.get('current_delay_type'),
                'impact_color': _op_impact_color(r),
                'avg_delay':    r.get('avg_delay_minutes'),
            }
            for r in active_records
        ],
    }

    if args.dry_run:
        log('export_manifest_dry_run', manifest)
        log('export_batch_done', {
            'dry_run': True,
            'airport_count': len(records),
            'active_event_count': len(active_records),
            'package_count': len(packages),
            'would_write_to': str(out_dir),
        })
        return

    # Write files
    out_dir.mkdir(parents=True, exist_ok=True)

    (out_dir / 'dashboard.json').write_text(
        json.dumps(dashboard, indent=2, default=str), encoding='utf-8')
    log('written', {'file': f'data/exports/{timestamp}/dashboard.json', 'airports': len(records)})

    (out_dir / 'airports.geojson').write_text(
        json.dumps(geojson, indent=2, default=str), encoding='utf-8')
    log('written', {'file': f'data/exports/{timestamp}/airports.geojson',
                    'features': geojson['feature_count']})

    (out_dir / 'active_events.placefile').write_text(placefile, encoding='utf-8')
    log('written', {'file': f'data/exports/{timestamp}/active_events.placefile',
                    'active_airports': len(active_records)})

    for iata, pkg in sorted(packages.items()):
        (out_dir / f'{iata}_broadcast.json').write_text(
            json.dumps(pkg, indent=2, default=str), encoding='utf-8')
    log('broadcast_packages_written', {
        'count': len(packages),
        'dir': f'data/exports/{timestamp}/',
    })

    (out_dir / 'manifest.json').write_text(
        json.dumps(manifest, indent=2, default=str), encoding='utf-8')
    log('written', {'file': f'data/exports/{timestamp}/manifest.json'})

    log('export_batch_done', {
        'dry_run': False,
        'airport_count': len(records),
        'active_event_count': len(active_records),
        'package_count': len(packages),
        'export_dir': str(out_dir),
    })


if __name__ == '__main__':
    main()
