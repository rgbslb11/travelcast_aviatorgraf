#!/usr/bin/env python3
"""Match RouteCast corridors against ATCSCC advisories and weather hazard context.

DOCTRINE:
  RouteCast corridor geometry = PLANNING/DISPLAY SCAFFOLD ONLY.
  Not FAA operational delay truth. Not ATC restriction truth.
  Corridor × advisory matches are CONTEXT SCAFFOLDS — not delay claims,
  not impact scores, not ATC restriction claims.
  FAA NAS / ATCSCC advisories = Current Operational Impact (operational truth).
  NWS CAP alerts = Public Weather Alert Truth — NOT FAA operational delay truth.
  Weather hazard context near a corridor is NOT FAA operational delay truth.
  Do not invent match rows. Do not invent advisories. Do not invent hazards.
  Do not claim a corridor is affected by delay unless explicit ATCSCC advisory
  text supports the term — and even then the output is context match only.
  Empty state is better than invented data.

Match confidence levels:
  high_geometry_intersection  — ONLY when geometry intersection is confirmed.
                                 NOT used in C3 initial scaffold.
  medium_airport_or_fix_overlap — corridor endpoint / fix labels overlap
                                   explicit advisory or hazard text.
  low_text_context             — broad regional / facility text match.
                                  Only written with --include-low-confidence.
  unmatched                    — no safe match found.

Inputs:
  Corridors: data/reference/routecast_top_50_busiest_aviation_routes_v0_1.csv
             (fallback when Supabase routecast_corridors not available)
  ATCSCC advisories: data/raw/atcscc_c3_advisories.json
                     (written by scripts/pull/pull_atcscc_advisories.py)
  NWS alerts:        data/raw/nws_alerts_parsed.json
                     (written by scripts/pull/pull_nws_alerts.py; optional)
  Aviation hazards:  data/raw/aviation_hazards.json
                     (written by scripts/pull/pull_aviation_hazards.py; optional)

Output:
  --dry-run (default):       Log match summary to stdout. No Supabase write.
                             No files written unless explicitly requested.
  --write:                   Write match rows to Supabase (routecast_corridor_atcscc_matches
                             and routecast_corridor_hazard_context_matches).
  --out PATH:                Write a JSON match report to PATH (any mode).
  --write-dry-run-cache:     Write data/raw/c3_match_dry_run.json (explicit opt-in).

Usage:
  python scripts/match/match_routecast_corridor_hazards.py
  python scripts/match/match_routecast_corridor_hazards.py --limit 10
  python scripts/match/match_routecast_corridor_hazards.py --out /tmp/matches.json
  python scripts/match/match_routecast_corridor_hazards.py --write-dry-run-cache
  python scripts/match/match_routecast_corridor_hazards.py --write
  python scripts/match/match_routecast_corridor_hazards.py --write --include-low-confidence
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
import urllib.request
import urllib.error
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts' / 'pull'))
from lib_pull import (
    load_env,
    log,
    get_supabase_creds,
    load_raw,
    save_raw,
    utc_now,
    supabase_get,
    supabase_post,
    _sb_headers,
)

CORRIDOR_CSV = ROOT / 'data' / 'reference' / 'routecast_top_50_busiest_aviation_routes_v0_1.csv'


# ─── Corridor loading ─────────────────────────────────────────────────────────

def _load_corridors_from_csv(limit: Optional[int]) -> list[dict]:
    """Load corridor metadata from the Top-50 reference CSV."""
    if not CORRIDOR_CSV.exists():
        log('csv_not_found', {'path': str(CORRIDOR_CSV)})
        return []
    rows: list[dict] = []
    with CORRIDOR_CSV.open(encoding='utf-8', newline='') as fh:
        reader = csv.DictReader(fh)
        for i, row in enumerate(reader):
            if limit and i >= limit:
                break
            rows.append({
                'corridor_key':           row.get('corridor_key', '').lower(),
                'corridor_name':          row.get('corridor_name', ''),
                'origin_airport_iata':    row.get('origin_airport_iata', '').upper(),
                'origin_airport_icao':    row.get('origin_airport_icao', '').upper(),
                'destination_airport_iata': row.get('destination_airport_iata', '').upper(),
                'destination_airport_icao': row.get('destination_airport_icao', '').upper(),
                'primary_route_label':    row.get('primary_route_label', ''),
                'waypoints':              row.get('waypoints', ''),
            })
    return rows


def _load_corridors_from_supabase(sb_url: str, sb_key: str,
                                  limit: Optional[int]) -> list[dict]:
    """Load active corridors from Supabase routecast_corridors table."""
    params: dict = {
        'active': 'eq.true',
        'select': 'corridor_key,corridor_name,origin_airport_iata,origin_airport_icao,'
                  'destination_airport_iata,destination_airport_icao,primary_route_label',
        'order': 'rank.asc.nullslast',
    }
    if limit:
        params['limit'] = str(limit)
    try:
        rows = supabase_get(sb_url, sb_key, 'routecast_corridors', params)
        log('corridors_from_supabase', {'count': len(rows)})
        return rows
    except RuntimeError as e:
        log('corridors_supabase_error', {'error': str(e)})
        return []


def _load_corridors(sb_url: Optional[str], sb_key: Optional[str],
                    limit: Optional[int]) -> list[dict]:
    """Load corridors from Supabase if available, else CSV fallback."""
    if sb_url and sb_key:
        rows = _load_corridors_from_supabase(sb_url, sb_key, limit)
        if rows:
            return rows
        log('corridors_supabase_empty_using_csv_fallback', {
            'note': 'Supabase corridors empty or unavailable — '
                    'falling back to Top-50 reference CSV. '
                    'Run seed_routecast_corridors.py to populate Supabase.',
        })
    return _load_corridors_from_csv(limit)


# ─── Advisory loading ─────────────────────────────────────────────────────────

def _load_atcscc_advisories(limit: Optional[int]) -> list[dict]:
    """Load C3 advisory rows from data/raw/atcscc_c3_advisories.json."""
    data = load_raw('atcscc_c3_advisories')
    if not data or not isinstance(data, dict):
        log('atcscc_c3_cache_missing', {
            'note': 'data/raw/atcscc_c3_advisories.json not found. '
                    'Run pull_atcscc_advisories.py first.',
        })
        return []
    advisories = data.get('advisories', [])
    if limit:
        advisories = advisories[:limit]
    log('atcscc_advisories_loaded', {'count': len(advisories)})
    return advisories


def _load_nws_alerts(limit: Optional[int]) -> list[dict]:
    """Load NWS alert context from data/raw/nws_alerts_parsed.json if available."""
    data = load_raw('nws_alerts_parsed')
    if not data:
        log('nws_alerts_cache_missing', {
            'note': 'data/raw/nws_alerts_parsed.json not found — '
                    'NWS alert context matching will be skipped. '
                    'Run pull_nws_alerts.py to populate.',
        })
        return []
    alerts = data if isinstance(data, list) else data.get('alerts', [])
    if limit:
        alerts = alerts[:limit]
    log('nws_alerts_loaded', {'count': len(alerts)})
    return alerts


def _load_aviation_hazards(limit: Optional[int]) -> list[dict]:
    """Load aviation hazard context from data/raw/aviation_hazards.json if available."""
    data = load_raw('aviation_hazards')
    if not data:
        log('aviation_hazards_cache_missing', {
            'note': 'data/raw/aviation_hazards.json not found — '
                    'aviation hazard context matching will be skipped. '
                    'Run pull_aviation_hazards.py to populate.',
        })
        return []
    hazards = data if isinstance(data, list) else data.get('hazards', [])
    if limit:
        hazards = hazards[:limit]
    log('aviation_hazards_loaded', {'count': len(hazards)})
    return hazards


# ─── Matching helpers ─────────────────────────────────────────────────────────

def _corridor_airport_set(corridor: dict) -> set[str]:
    """Return the set of airport codes associated with a corridor."""
    codes: set[str] = set()
    for key in ('origin_airport_iata', 'origin_airport_icao',
                'destination_airport_iata', 'destination_airport_icao'):
        val = (corridor.get(key) or '').strip().upper()
        if val and len(val) >= 3:
            codes.add(val)
            # Add both ICAO and IATA variants when possible
            if val.startswith('K') and len(val) == 4:
                codes.add(val[1:])  # K + 3 → bare IATA
    return codes


def _corridor_fix_set(corridor: dict) -> set[str]:
    """Return the set of fix labels / waypoints for a corridor."""
    waypoints_str = corridor.get('waypoints', '')
    fixes: set[str] = set()
    for fix in waypoints_str.split('|'):
        fix = fix.strip().upper()
        if fix and len(fix) >= 3:
            fixes.add(fix)
    return fixes


def _advisory_airport_set(adv: dict) -> set[str]:
    """Return the set of airport codes mentioned in an advisory."""
    codes: set[str] = set()
    for code in (adv.get('affected_airports') or []):
        c = (code or '').strip().upper()
        if c:
            codes.add(c)
            if c.startswith('K') and len(c) == 4:
                codes.add(c[1:])
    return codes


def _advisory_fix_set(adv: dict) -> set[str]:
    """Return the set of fix labels mentioned in an advisory."""
    return {f.strip().upper() for f in (adv.get('mentioned_fix_labels') or []) if f}


def _advisory_route_set(adv: dict) -> set[str]:
    """Return the set of route label terms mentioned in an advisory."""
    return {r.strip().upper() for r in (adv.get('mentioned_routes') or []) if r}


# ─── ATCSCC corridor matching ─────────────────────────────────────────────────

def _match_corridor_to_advisory(
    corridor: dict,
    adv: dict,
    include_low: bool,
) -> Optional[dict]:
    """Return a match row or None if no safe match at acceptable confidence.

    Confidence levels produced here:
      medium_airport_or_fix_overlap — corridor airports / fixes in advisory text
      low_text_context              — only produced when include_low=True

    high_geometry_intersection is NOT produced in C3 initial scaffold.
    """
    corr_airports = _corridor_airport_set(corridor)
    corr_fixes = _corridor_fix_set(corridor)
    adv_airports = _advisory_airport_set(adv)
    adv_fixes = _advisory_fix_set(adv)
    adv_routes = _advisory_route_set(adv)

    # Medium confidence: explicit airport overlap
    airport_overlap = corr_airports & adv_airports
    if airport_overlap:
        matched_terms = sorted(airport_overlap)
        return {
            'corridor_key':           corridor['corridor_key'],
            'advisory_id':            adv.get('advisory_id'),
            'match_type':             'airport_overlap',
            'match_confidence':       'medium_airport_or_fix_overlap',
            'matched_terms':          matched_terms,
            'matched_airports':       sorted(airport_overlap),
            'matched_facilities':     sorted(_advisory_fix_set(adv) & corr_fixes),
            'matched_fixes':          [],
            'match_reason':           f'Corridor airports {sorted(corr_airports)} appear in '
                                      f'advisory affected_airports {sorted(adv_airports)}.',
            'source_truth_lane':      'routecast_atcscc_context_match',
            'operator_review_status': 'draft',
            'created_at':             utc_now(),
        }

    # Medium confidence: explicit fix label overlap
    fix_overlap = corr_fixes & adv_fixes
    if fix_overlap:
        return {
            'corridor_key':           corridor['corridor_key'],
            'advisory_id':            adv.get('advisory_id'),
            'match_type':             'fix_overlap',
            'match_confidence':       'medium_airport_or_fix_overlap',
            'matched_terms':          sorted(fix_overlap),
            'matched_airports':       [],
            'matched_facilities':     [],
            'matched_fixes':          sorted(fix_overlap),
            'match_reason':           f'Corridor fixes {sorted(corr_fixes)} overlap '
                                      f'advisory fix labels {sorted(adv_fixes)}.',
            'source_truth_lane':      'routecast_atcscc_context_match',
            'operator_review_status': 'draft',
            'created_at':             utc_now(),
        }

    # Medium confidence: route label overlap
    route_label = (corridor.get('primary_route_label') or '').upper()
    if route_label and adv_routes:
        route_parts = {p.strip() for p in route_label.replace('/', ' ').split() if p.strip()}
        route_overlap = route_parts & adv_routes
        if route_overlap:
            return {
                'corridor_key':           corridor['corridor_key'],
                'advisory_id':            adv.get('advisory_id'),
                'match_type':             'route_label_overlap',
                'match_confidence':       'medium_airport_or_fix_overlap',
                'matched_terms':          sorted(route_overlap),
                'matched_airports':       [],
                'matched_facilities':     [],
                'matched_fixes':          [],
                'match_reason':           f'Corridor route label terms {sorted(route_overlap)} '
                                          f'appear in advisory mentioned_routes.',
                'source_truth_lane':      'routecast_atcscc_context_match',
                'operator_review_status': 'draft',
                'created_at':             utc_now(),
            }

    # Low confidence: broad facility text match (only when requested)
    if include_low:
        adv_facilities = set(adv.get('affected_facilities') or [])
        if adv_facilities:
            return {
                'corridor_key':           corridor['corridor_key'],
                'advisory_id':            adv.get('advisory_id'),
                'match_type':             'facility_text_match',
                'match_confidence':       'low_text_context',
                'matched_terms':          sorted(adv_facilities),
                'matched_airports':       [],
                'matched_facilities':     sorted(adv_facilities),
                'matched_fixes':          [],
                'match_reason':           f'Advisory mentions facilities {sorted(adv_facilities)} '
                                          f'with no direct corridor airport or fix overlap. '
                                          f'Low-confidence context only.',
                'source_truth_lane':      'routecast_atcscc_context_match',
                'operator_review_status': 'draft',
                'created_at':             utc_now(),
            }

    return None


# ─── Hazard context matching ──────────────────────────────────────────────────

def _match_corridor_to_nws_alert(
    corridor: dict,
    alert: dict,
    include_low: bool,
) -> Optional[dict]:
    """Return a hazard context match row for a corridor × NWS alert, or None.

    NWS CAP alerts are Public Weather Alert Truth — NOT FAA operational delay truth.
    Weather hazard context near a corridor is NOT FAA operational delay truth.
    Confidence: medium_airport_or_fix_overlap only when corridor airports appear
    in the alert's affected area text.
    """
    corr_airports = _corridor_airport_set(corridor)

    # Extract airport codes from alert properties
    props = alert.get('properties') or alert
    area_desc = (props.get('areaDesc') or props.get('area_desc') or '').upper()
    headline = (props.get('headline') or '').upper()
    event = props.get('event') or props.get('hazard_type') or ''
    alert_id = props.get('id') or alert.get('alert_id') or alert.get('id') or ''
    combined_text = f'{area_desc} {headline}'

    # Check if corridor airports appear in area description
    airport_mentions = [a for a in corr_airports if a in combined_text]
    if airport_mentions:
        return {
            'corridor_key':             corridor['corridor_key'],
            'hazard_source':            'nws_cap',
            'hazard_source_id':         str(alert_id),
            'hazard_type':              event,
            'match_type':               'airport_overlap',
            'match_confidence':         'medium_airport_or_fix_overlap',
            'matched_geometry_method':  'text_match_only',
            'matched_terms':            airport_mentions,
            'match_reason':             f'Corridor airports {airport_mentions} appear in '
                                        f'NWS alert area description. '
                                        f'NWS alerts are Public Weather Alert Truth — '
                                        f'not FAA operational delay truth.',
            'source_truth_lane':        'corridor_weather_hazard_context_only',
            'operator_review_status':   'draft',
            'created_at':               utc_now(),
        }

    if include_low and area_desc:
        # Low-confidence: broad area match
        return {
            'corridor_key':             corridor['corridor_key'],
            'hazard_source':            'nws_cap',
            'hazard_source_id':         str(alert_id),
            'hazard_type':              event,
            'match_type':               'text_area_match',
            'match_confidence':         'low_text_context',
            'matched_geometry_method':  'text_match_only',
            'matched_terms':            [],
            'match_reason':             'Low-confidence broad area text context only. '
                                        'NWS alerts are Public Weather Alert Truth — '
                                        'not FAA operational delay truth.',
            'source_truth_lane':        'corridor_weather_hazard_context_only',
            'operator_review_status':   'draft',
            'created_at':               utc_now(),
        }

    return None


def _match_corridor_to_aviation_hazard(
    corridor: dict,
    hazard: dict,
    include_low: bool,
) -> Optional[dict]:
    """Return a hazard context match row for a corridor × aviation hazard, or None.

    AviationWeather.gov SIGMET/AIRMET/CWA = Aviation Weather Truth.
    Not FAA operational delay truth.
    """
    corr_airports = _corridor_airport_set(corridor)

    hazard_type = hazard.get('hazardType') or hazard.get('type') or ''
    hazard_id = hazard.get('seriesId') or hazard.get('hazardId') or hazard.get('id') or ''
    raw_text = (hazard.get('rawAirSigmet') or hazard.get('rawText') or
                hazard.get('cwaText') or '').upper()
    source_name = hazard.get('_source', 'aviationweather')

    # Determine hazard source lane
    if 'sigmet' in source_name.lower() or 'SIGMET' in hazard_type.upper():
        hazard_source = 'aviationweather_sigmet'
    elif 'airmet' in source_name.lower() or 'AIRMET' in hazard_type.upper():
        hazard_source = 'aviationweather_airmet'
    elif 'cwa' in source_name.lower() or 'CWA' in hazard_type.upper():
        hazard_source = 'aviationweather_cwa'
    else:
        hazard_source = 'aviationweather_hazard'

    # Check corridor airports in hazard raw text
    airport_mentions = [a for a in corr_airports if a in raw_text]
    if airport_mentions:
        return {
            'corridor_key':             corridor['corridor_key'],
            'hazard_source':            hazard_source,
            'hazard_source_id':         str(hazard_id),
            'hazard_type':              hazard_type,
            'match_type':               'airport_overlap',
            'match_confidence':         'medium_airport_or_fix_overlap',
            'matched_geometry_method':  'text_match_only',
            'matched_terms':            airport_mentions,
            'match_reason':             f'Corridor airports {airport_mentions} appear in '
                                        f'aviation hazard raw text. '
                                        f'Aviation hazards are Aviation Weather Truth — '
                                        f'not FAA operational delay truth.',
            'source_truth_lane':        'corridor_weather_hazard_context_only',
            'operator_review_status':   'draft',
            'created_at':               utc_now(),
        }

    return None


# ─── Supabase writers ─────────────────────────────────────────────────────────

def _write_atcscc_matches(sb_url: str, sb_key: str, rows: list[dict]) -> None:
    """Insert match rows into routecast_corridor_atcscc_matches."""
    if not rows:
        return
    supabase_post(sb_url, sb_key, 'routecast_corridor_atcscc_matches', rows)
    log('atcscc_matches_written', {'count': len(rows)})


def _write_hazard_matches(sb_url: str, sb_key: str, rows: list[dict]) -> None:
    """Insert match rows into routecast_corridor_hazard_context_matches."""
    if not rows:
        return
    supabase_post(sb_url, sb_key, 'routecast_corridor_hazard_context_matches', rows)
    log('hazard_matches_written', {'count': len(rows)})


# ─── Main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            'Match RouteCast corridors to ATCSCC advisory context and '
            'weather hazard context. Default is dry-run (no Supabase writes).'
        )
    )
    parser.add_argument(
        '--dry-run', action='store_true', default=True,
        help='Log match candidates without writing to Supabase (default)',
    )
    parser.add_argument(
        '--write', action='store_true',
        help='Write match rows to Supabase (overrides dry-run default)',
    )
    parser.add_argument(
        '--limit', type=int, default=None,
        help='Limit corridors and advisories loaded per source',
    )
    parser.add_argument(
        '--include-low-confidence', action='store_true',
        help='Also produce low_text_context match rows (not written by default)',
    )
    parser.add_argument(
        '--out', type=str, default=None, metavar='PATH',
        help='Write a JSON match report to PATH (any mode; no default file written)',
    )
    parser.add_argument(
        '--write-dry-run-cache', action='store_true',
        help='Write data/raw/c3_match_dry_run.json (explicit opt-in; not written by default)',
    )
    args = parser.parse_args()

    # --write overrides the default dry-run
    dry_run = not args.write

    load_env()

    sb_url: Optional[str] = None
    sb_key: Optional[str] = None
    try:
        sb_url, sb_key = get_supabase_creds()
    except RuntimeError as e:
        log('supabase_creds_error', str(e))
        if not dry_run:
            log('write_mode_requires_creds',
                'Cannot write without Supabase credentials. Use --dry-run.')
            sys.exit(1)

    include_low = args.include_low_confidence

    # ── Load corridors ─────────────────────────────────────────────────────────
    corridors = _load_corridors(sb_url, sb_key, args.limit)
    if not corridors:
        log('no_corridors_found', {
            'note': 'No corridors loaded. Run seed_routecast_corridors.py and '
                    'ensure routecast_top_50_busiest_aviation_routes_v0_1.csv exists.',
        })
        return
    log('corridors_loaded', {'count': len(corridors), 'dry_run': dry_run})

    # ── Load advisory context sources ──────────────────────────────────────────
    atcscc_advisories = _load_atcscc_advisories(args.limit)
    nws_alerts = _load_nws_alerts(args.limit)
    aviation_hazards = _load_aviation_hazards(args.limit)

    # ── Match corridors × ATCSCC advisories ───────────────────────────────────
    atcscc_match_rows: list[dict] = []
    atcscc_unmatched = 0

    if atcscc_advisories:
        for corridor in corridors:
            for adv in atcscc_advisories:
                row = _match_corridor_to_advisory(corridor, adv, include_low)
                if row:
                    atcscc_match_rows.append(row)
                else:
                    atcscc_unmatched += 1
        log('atcscc_matching_complete', {
            'corridors': len(corridors),
            'advisories': len(atcscc_advisories),
            'matches_found': len(atcscc_match_rows),
            'unmatched_pairs': atcscc_unmatched,
            'include_low_confidence': include_low,
        })
    else:
        log('atcscc_matching_skipped',
            'No ATCSCC advisories available — run pull_atcscc_advisories.py first.')

    # ── Match corridors × NWS alert context ───────────────────────────────────
    hazard_match_rows: list[dict] = []

    if nws_alerts:
        for corridor in corridors:
            for alert in nws_alerts:
                row = _match_corridor_to_nws_alert(corridor, alert, include_low)
                if row:
                    hazard_match_rows.append(row)
        log('nws_alert_matching_complete', {
            'corridors': len(corridors),
            'alerts': len(nws_alerts),
            'matches_found': sum(1 for r in hazard_match_rows
                                  if r.get('hazard_source') == 'nws_cap'),
        })

    if aviation_hazards:
        for corridor in corridors:
            for hazard in aviation_hazards:
                row = _match_corridor_to_aviation_hazard(corridor, hazard, include_low)
                if row:
                    hazard_match_rows.append(row)
        log('aviation_hazard_matching_complete', {
            'corridors': len(corridors),
            'hazards': len(aviation_hazards),
            'matches_found': sum(1 for r in hazard_match_rows
                                  if r.get('hazard_source', '').startswith('aviationweather')),
        })

    # ── Log dry-run preview ────────────────────────────────────────────────────
    if dry_run:
        for row in atcscc_match_rows[:10]:
            log('atcscc_match_preview', {
                'corridor_key':    row['corridor_key'],
                'advisory_id':     row.get('advisory_id'),
                'match_type':      row['match_type'],
                'match_confidence': row['match_confidence'],
                'matched_terms':   row.get('matched_terms'),
                'source_truth_lane': row['source_truth_lane'],
                'disclaimer':      'Context match only — not a delay claim.',
            })
        if len(atcscc_match_rows) > 10:
            log('atcscc_matches_truncated',
                {'shown': 10, 'total': len(atcscc_match_rows)})

        for row in hazard_match_rows[:10]:
            log('hazard_match_preview', {
                'corridor_key':    row['corridor_key'],
                'hazard_source':   row['hazard_source'],
                'hazard_type':     row.get('hazard_type'),
                'match_confidence': row['match_confidence'],
                'source_truth_lane': row['source_truth_lane'],
                'disclaimer':      'Weather hazard context near a corridor is not FAA delay truth.',
            })
        if len(hazard_match_rows) > 10:
            log('hazard_matches_truncated',
                {'shown': 10, 'total': len(hazard_match_rows)})

    # ── Optional JSON output (only when explicitly requested) ─────────────────
    write_json = args.out or args.write_dry_run_cache
    if write_json:
        match_report = {
            'generated_at':      utc_now(),
            'dry_run':           dry_run,
            'corridors_loaded':  len(corridors),
            'atcscc_matches': [
                {k: v for k, v in r.items() if k != 'created_at'}
                for r in atcscc_match_rows
            ],
            'hazard_matches': [
                {k: v for k, v in r.items() if k != 'created_at'}
                for r in hazard_match_rows
            ],
            'disclaimer': (
                'All rows are context scaffolds. '
                'ATCSCC matches are not delay claims. '
                'Hazard matches are not FAA operational delay truth. '
                'operator_review_status=draft on all system-generated rows.'
            ),
        }
        if args.out:
            out_path = Path(args.out)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(
                json.dumps(match_report, indent=2, default=str), encoding='utf-8'
            )
            log('match_report_written', {'file': str(out_path)})
        if args.write_dry_run_cache:
            save_raw('c3_match_dry_run', match_report)
            log('match_cache_written', {'file': 'data/raw/c3_match_dry_run.json'})

    # ── Write to Supabase (only in --write mode) ───────────────────────────────
    if not dry_run and sb_url and sb_key:
        if atcscc_match_rows:
            try:
                _write_atcscc_matches(sb_url, sb_key, atcscc_match_rows)
            except RuntimeError as e:
                log('atcscc_match_write_error', {'error': str(e)})
        else:
            log('no_atcscc_matches_to_write',
                'No ATCSCC context match rows produced — nothing written.')

        if hazard_match_rows:
            try:
                _write_hazard_matches(sb_url, sb_key, hazard_match_rows)
            except RuntimeError as e:
                log('hazard_match_write_error', {'error': str(e)})
        else:
            log('no_hazard_matches_to_write',
                'No hazard context match rows produced — nothing written.')

    # ── Summary ────────────────────────────────────────────────────────────────
    log('match_summary', {
        'corridors':              len(corridors),
        'atcscc_advisories':      len(atcscc_advisories),
        'nws_alerts':             len(nws_alerts),
        'aviation_hazards':       len(aviation_hazards),
        'atcscc_matches':         len(atcscc_match_rows),
        'hazard_context_matches': len(hazard_match_rows),
        'include_low_confidence': include_low,
        'dry_run':                dry_run,
        'source_truth_disclaimer': (
            'ATCSCC matches are context scaffolds — not delay claims. '
            'Hazard matches are weather context — not FAA operational delay truth.'
        ),
    })


if __name__ == '__main__':
    main()
