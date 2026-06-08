#!/usr/bin/env python3
"""RouteCast route context builder for TravelCast AviatorGraf Prep.

Loads configured routes from Supabase, then enriches each route with:
  - Origin/destination airport status from cached airport snapshots
  - ATCSCC advisory text mentions (text search only)
  - Aviation hazard mentions (text search only)

Does NOT make additional API calls. Uses data/raw/ caches only.
Optionally writes route summaries to a log for operator review.
Doctrine:
  - FAA NAS = operational truth
  - NWS forecast = proxy only, NOT official FAA delay forecast
  - ATCSCC text = operational planning context, not delay guarantee

Usage:
  python rebuild_routecast_snapshots.py [--dry-run] [--limit N]
"""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from lib_pull import (
    load_env, get_supabase_creds, write_feed_run,
    load_raw, save_raw, supabase_get, log, utc_now,
)

SOURCE_ID = 'faa_nas_status'  # reuses existing feed system


# ─────────────────────────────── Supabase loaders ────────────────────


def load_routes(sb_url: str, sb_key: str) -> list[dict]:
    """Fetch active routes from Supabase routecast_routes table.

    Returns a list of route dicts. On any error, logs and returns [].
    """
    try:
        rows = supabase_get(
            sb_url,
            sb_key,
            'routecast_routes',
            {
                'active': 'eq.true',
                'select': 'route_id,route_name,origin_airport_id,destination_airport_id,route_string,notes',
                'order': 'sort_order.asc',
            },
        )
        log('routes_loaded', {'count': len(rows)})
        return rows
    except Exception as exc:
        log('routes_load_error', {'error': str(exc)})
        return []


# ─────────────────────────────── Cache loaders ───────────────────────


def load_airport_status_cache() -> dict:
    """Load cached FAA NAS status and return a lookup keyed by IATA code.

    Handles two raw cache shapes:
      - List of event dicts (new format)  → walks the list
      - Dict with an 'events' or 'programs' key (older format) → walks that list

    Returns: {iata: {delay_type, avg_delay, max_delay, reason, impact_color}}
    Returns empty dict on any failure.
    """
    try:
        raw = load_raw('faa_nas_status')
        if raw is None:
            log('airport_cache_missing', {'file': 'faa_nas_status.json'})
            return {}

        # Normalise to a list of event-like dicts
        if isinstance(raw, list):
            events = raw
        elif isinstance(raw, dict):
            # Try common wrapper keys
            events = raw.get('events') or raw.get('programs') or []
        else:
            log('airport_cache_unknown_format', {'type': type(raw).__name__})
            return {}

        lookup: dict[str, dict] = {}
        for ev in events:
            if not isinstance(ev, dict):
                continue
            iata = (
                ev.get('airportId')
                or ev.get('iata')
                or ev.get('airport_id', '')
            ).upper().strip()
            if not iata:
                continue
            # Only keep the first (highest-priority) entry per airport
            if iata not in lookup:
                lookup[iata] = {
                    'delay_type': ev.get('delayType') or ev.get('delay_type') or 'NORMAL',
                    'avg_delay':  ev.get('avgDelay')  or ev.get('avg_delay'),
                    'max_delay':  ev.get('maxDelay')  or ev.get('max_delay'),
                    'reason':     ev.get('reason')    or ev.get('closureReason', ''),
                    'impact_color': ev.get('impact_color') or ev.get('impactColor', 'Green'),
                }

        log('airport_cache_loaded', {'airports_with_events': len(lookup)})
        return lookup
    except Exception as exc:
        log('airport_cache_error', {'error': str(exc)})
        return {}


def load_atcscc_text() -> str:
    """Return combined ATCSCC advisory text from cached files.

    Tries atcscc_ops_plan_raw.json first, then atcscc_advisories.json as fallback.
    Returns empty string on any failure.
    """
    parts: list[str] = []

    try:
        ops_raw = load_raw('atcscc_ops_plan_raw')
        if ops_raw is not None:
            # May be a list of plan dicts or a single dict
            if isinstance(ops_raw, list) and ops_raw:
                first = ops_raw[0]
                if isinstance(first, dict):
                    text = first.get('raw_text') or first.get('text', '')
                    if text:
                        parts.append(str(text))
            elif isinstance(ops_raw, dict):
                text = ops_raw.get('raw_text') or ops_raw.get('text', '')
                if text:
                    parts.append(str(text))
    except Exception as exc:
        log('atcscc_ops_plan_load_error', {'error': str(exc)})

    try:
        advisories = load_raw('atcscc_advisories')
        if advisories is not None:
            if isinstance(advisories, list):
                for item in advisories:
                    if isinstance(item, dict):
                        snippet = item.get('text') or item.get('raw_text') or item.get('advisory_text', '')
                        if snippet:
                            parts.append(str(snippet))
            elif isinstance(advisories, dict):
                snippet = advisories.get('text') or advisories.get('raw_text', '')
                if snippet:
                    parts.append(str(snippet))
    except Exception as exc:
        log('atcscc_advisories_load_error', {'error': str(exc)})

    combined = ' '.join(parts)
    log('atcscc_text_loaded', {'chars': len(combined)})
    return combined


def load_hazard_text() -> str:
    """Return concatenated raw_text from all aviation hazard records.

    Returns empty string on any failure.
    """
    try:
        raw = load_raw('aviation_hazards_parsed')
        if raw is None:
            log('hazard_cache_missing', {'file': 'aviation_hazards_parsed.json'})
            return ''

        parts: list[str] = []
        records = raw if isinstance(raw, list) else [raw]
        for record in records:
            if isinstance(record, dict):
                txt = record.get('raw_text') or record.get('text', '')
                if txt:
                    parts.append(str(txt))

        combined = ' '.join(parts)
        log('hazard_text_loaded', {'chars': len(combined)})
        return combined
    except Exception as exc:
        log('hazard_text_error', {'error': str(exc)})
        return ''


# ─────────────────────────────── Route helpers ───────────────────────


def _get_airport_iata(airport_id: str) -> str:
    """Return IATA code from an airport_id string.

    Rules:
      - PHNL, PHOG, PANC, TJSJ → pass through unchanged (non-K prefixes)
      - KXXX domestic ICAO → strip leading K to get XXX
      - Anything else → return as-is (already IATA or unknown)
    """
    if not airport_id:
        return ''
    code = airport_id.strip().upper()
    # Non-K ICAO prefixes used in our network — pass through
    passthrough_prefixes = ('PH', 'PA', 'TJ')
    if any(code.startswith(p) for p in passthrough_prefixes):
        return code
    # Domestic ICAO (K + 3-letter IATA)
    if len(code) == 4 and code.startswith('K'):
        return code[1:]
    return code


def summarize_route(
    route: dict,
    airport_cache: dict,
    atcscc_text: str,
    hazard_text: str,
) -> dict:
    """Build an enriched route summary dict.

    Checks cached operational data for origin/destination delays, ATCSCC text
    mentions, and aviation hazard text mentions. Always appends the NWS proxy
    disclaimer.
    """
    origin_id = route.get('origin_airport_id', '')
    dest_id = route.get('destination_airport_id', '')
    origin_iata = _get_airport_iata(origin_id)
    dest_iata = _get_airport_iata(dest_id)

    origin_status = airport_cache.get(origin_iata, {})
    dest_status = airport_cache.get(dest_iata, {})

    origin_delay_type = origin_status.get('delay_type', 'NORMAL')
    dest_delay_type = dest_status.get('delay_type', 'NORMAL')

    # Text-match checks — simple substring search (case-insensitive)
    atcscc_lo = atcscc_text.lower()
    hazard_lo = hazard_text.lower()

    # Tokens to search for: origin IATA, dest IATA, and words from route_string
    search_tokens: list[str] = []
    if origin_iata:
        search_tokens.append(origin_iata.lower())
    if dest_iata:
        search_tokens.append(dest_iata.lower())
    route_string = route.get('route_string', '') or ''
    for word in route_string.split():
        token = word.strip().lower()
        if len(token) >= 3:
            search_tokens.append(token)

    atcscc_mentions = any(tok in atcscc_lo for tok in search_tokens) if search_tokens else False
    hazard_mentions = any(tok in hazard_lo for tok in search_tokens) if search_tokens else False

    # Build operator notes
    bullets: list[str] = []

    origin_delayed = origin_delay_type not in ('NORMAL', '', None)
    dest_delayed = dest_delay_type not in ('NORMAL', '', None)

    if origin_delayed:
        reason = origin_status.get('reason', '')
        avg = origin_status.get('avg_delay')
        detail = f': {reason}' if reason else ''
        delay_note = f' (~{avg} min avg)' if avg else ''
        bullets.append(
            f'Origin {origin_iata} — {origin_delay_type}{detail}{delay_note}. '
            f'Source: Current Operational Impact — FAA NAS / ATCSCC.'
        )

    if dest_delayed:
        reason = dest_status.get('reason', '')
        avg = dest_status.get('avg_delay')
        detail = f': {reason}' if reason else ''
        delay_note = f' (~{avg} min avg)' if avg else ''
        bullets.append(
            f'Destination {dest_iata} — {dest_delay_type}{detail}{delay_note}. '
            f'Source: Current Operational Impact — FAA NAS / ATCSCC.'
        )

    if atcscc_mentions:
        bullets.append(
            f'ATCSCC advisory text references route airports or waypoints. '
            f'Review atcscc_ops_plan_raw.json for details.'
        )

    if hazard_mentions:
        bullets.append(
            f'Aviation hazard records reference route airports or waypoints. '
            f'Review aviation_hazards_parsed.json for details.'
        )

    if bullets:
        notes_body = ' | '.join(bullets)
    else:
        notes_body = 'Route appears clear based on cached data.'

    route_notes = f'{notes_body} NWS forecast impact is not an official FAA delay forecast.'

    return {
        'route_id':              route.get('route_id'),
        'route_name':            route.get('route_name'),
        'origin_airport_id':     origin_id,
        'destination_airport_id': dest_id,
        'origin_iata':           origin_iata,
        'dest_iata':             dest_iata,
        'origin_status':         origin_status,
        'dest_status':           dest_status,
        'origin_delay_type':     origin_delay_type,
        'dest_delay_type':       dest_delay_type,
        'atcscc_mentions':       atcscc_mentions,
        'hazard_mentions':       hazard_mentions,
        'route_notes':           route_notes,
        'generated_at':          utc_now(),
    }


# ─────────────────────────────── Main ────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(
        description='Rebuild RouteCast context summaries from cached data'
    )
    parser.add_argument(
        '--dry-run', action='store_true',
        help='Print summaries to stdout; skip writes to data/raw/',
    )
    parser.add_argument(
        '--limit', type=int, default=None,
        help='Process only the first N routes',
    )
    args = parser.parse_args()

    load_env()
    log('routecast_snapshot_start', {'dry_run': args.dry_run, 'limit': args.limit})

    # Supabase creds — needed for route fetch; gracefully degrade if missing
    sb_url: str | None = None
    sb_key: str | None = None
    try:
        sb_url, sb_key = get_supabase_creds()
    except RuntimeError as exc:
        log('supabase_creds_unavailable', {'error': str(exc)})

    # Fetch routes (requires Supabase; exit cleanly if none returned)
    if sb_url and sb_key:
        routes = load_routes(sb_url, sb_key)
    else:
        log('routes_skipped', {'reason': 'no Supabase credentials — cannot fetch routes'})
        routes = []

    if not routes:
        log('routecast_snapshot_exit', {'reason': 'no active routes found'})
        write_feed_run(
            sb_url, sb_key, SOURCE_ID,
            success=False,
            error='No active routes found or Supabase unavailable',
            dry_run=args.dry_run,
        )
        sys.exit(0)

    # Apply limit
    if args.limit:
        routes = routes[: args.limit]
        log('routes_limited', {'limit': args.limit, 'routes_after_limit': len(routes)})

    # Load caches (no API calls — local files only)
    airport_cache = load_airport_status_cache()
    atcscc_text = load_atcscc_text()
    hazard_text = load_hazard_text()

    # Summarize each route
    summaries: list[dict] = []
    for route in routes:
        summary = summarize_route(route, airport_cache, atcscc_text, hazard_text)
        summaries.append(summary)

        if args.dry_run:
            print(json.dumps(summary, indent=2, default=str))

    # Compute pull stats
    routes_processed = len(summaries)
    routes_with_origin_delays = sum(
        1 for s in summaries if s['origin_delay_type'] not in ('NORMAL', '', None)
    )
    routes_with_dest_delays = sum(
        1 for s in summaries if s['dest_delay_type'] not in ('NORMAL', '', None)
    )
    routes_with_atcscc_mentions = sum(1 for s in summaries if s['atcscc_mentions'])
    routes_with_hazard_mentions = sum(1 for s in summaries if s['hazard_mentions'])

    pull_summary = {
        'routes_processed':             routes_processed,
        'routes_with_origin_delays':    routes_with_origin_delays,
        'routes_with_dest_delays':      routes_with_dest_delays,
        'routes_with_atcscc_mentions':  routes_with_atcscc_mentions,
        'routes_with_hazard_mentions':  routes_with_hazard_mentions,
    }
    log('pull_summary', pull_summary)

    # Write output (skip on dry-run)
    if not args.dry_run:
        out_path = save_raw('routecast_summaries', summaries)
        log('routecast_summaries_saved', {'path': str(out_path), 'count': len(summaries)})

    # Record feed run (derivative of faa_nas_status; reuses that source_id)
    write_feed_run(
        sb_url, sb_key, SOURCE_ID,
        success=True,
        records=routes_processed,
        dry_run=args.dry_run,
    )

    log('routecast_snapshot_done', {'routes_processed': routes_processed})


if __name__ == '__main__':
    main()
