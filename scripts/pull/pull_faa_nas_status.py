#!/usr/bin/env python3
"""Pull FAA NAS airport events and write airport_status_snapshots rows.

Source:  https://nasstatus.faa.gov/api/airport-events
         Fetched ONCE per run — returns a JSON array of all active airport events.
         Retired endpoint (NXDOMAIN): soa.smext.faa.gov/asws/api/airport/status/{IATA}
Auth:    None (public API, no key required)
Writes:  airport_status_snapshots (snapshot_source='live')
         data/raw/faa_nas_status.json (raw API response)
         feed_runs (source_system_id='faa_nas_status')
Doctrine: FAA NAS Status = Current Operational Impact (operational truth)

Usage:
  python pull_faa_nas_status.py [--dry-run] [--limit N]
"""
from __future__ import annotations
import argparse, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from lib_pull import (
    load_env, get_supabase_creds, get_active_airports,
    insert_snapshots, write_feed_run, http_get_json, save_raw, utc_now, log,
)

FAA_NAS_EVENTS_URL = 'https://nasstatus.faa.gov/api/airport-events'
SOURCE_ID = 'faa_nas_status'

# Avg-delay threshold above which groundDelay escalates from Amber to Red.
GDP_RED_THRESHOLD_MINUTES = 45


def _parse_minutes(val) -> int | None:
    """Parse a delay-minutes value that may be int, float, or a string like '63' or '27.0'."""
    if val is None:
        return None
    try:
        # Use float() first to handle '27.0', then truncate to int
        v = int(float(str(val).split()[0]))
        return v if v > 0 else None
    except (ValueError, TypeError):
        return None


def _extract_reason(obj: dict) -> str | None:
    """Extract a human-readable reason string from a FAA program sub-object."""
    for key in ('reason', 'impactingCondition', 'condition', 'rootCause'):
        val = obj.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
        if isinstance(val, dict):
            # Some fields return nested objects; try text/name sub-keys
            for sub in ('text', 'name', 'value', 'description'):
                inner = val.get(sub)
                if isinstance(inner, str) and inner.strip():
                    return inner.strip()
    return None


def _build_delay_summary(delay_type: str, avg: int | None, max_: int | None,
                         reason: str | None) -> str | None:
    parts = [f'{delay_type} active']
    if avg:
        parts.append(f'avg {avg} min')
    if max_:
        parts.append(f'max {max_} min')
    if reason:
        parts.append(f'({reason})')
    return '. '.join(parts) + '.' if parts else None


def parse_faa_event(event: dict | None, airport: dict) -> dict:
    """Map one FAA airport-events object to airport_status_snapshots fields.

    If event is None, the airport has no active FAA/NAS program — NORMAL snapshot.
    Program priority: airportClosure > groundStop > groundDelay > departureDelay / arrivalDelay.
    """
    snap: dict = {
        'airport_id': airport['airport_id'],
        'snapshot_source': 'live',
        'generated_at': utc_now(),
        'freshness_status': 'fresh',
        'current_delay_type': 'None',
        'current_status_code': 'NORMAL',
        'current_reason': 'No active FAA/NAS event',
        'avg_delay_minutes': None,
        'max_delay_minutes': None,
        'delay_summary': None,
        'arrival_runway': None,
        'departure_runway': None,
        'aar': None,
        'current_impact_color': None,
        'source_summary': 'Current Operational Impact — FAA NAS Status',
    }

    if event is None:
        return snap

    # ── airportConfig (runways / AAR) — independent of delay programs ──
    cfg = event.get('airportConfig') or {}
    if cfg:
        arr_rwy = (cfg.get('arrivalRunwayConfig') or cfg.get('arrivalRunways')
                   or cfg.get('arrivalRunway') or cfg.get('arrRunways'))
        dep_rwy = (cfg.get('departureRunwayConfig') or cfg.get('departureRunways')
                   or cfg.get('departureRunway') or cfg.get('depRunways'))
        aar_val = _parse_minutes(cfg.get('arrivalRate') or cfg.get('aar'))
        if arr_rwy:
            snap['arrival_runway'] = str(arr_rwy).strip()
        if dep_rwy:
            snap['departure_runway'] = str(dep_rwy).strip()
        if aar_val:
            snap['aar'] = aar_val

    # ── Program priority: closure → groundStop → groundDelay → delay ──

    closure = event.get('airportClosure')
    if closure and closure is not None and closure is not False:
        snap['current_delay_type'] = 'Airport Closure'
        snap['current_status_code'] = 'AIRPORT_CLOSURE'
        snap['current_reason'] = _extract_reason(closure if isinstance(closure, dict) else {})
        snap['current_impact_color'] = 'Red'
        snap['delay_summary'] = _build_delay_summary(
            'Airport Closure', None, None, snap['current_reason']
        )
        return snap

    gs = event.get('groundStop')
    if gs and gs is not None and gs is not False:
        obj = gs if isinstance(gs, dict) else {}
        reason = _extract_reason(obj)
        snap['current_delay_type'] = 'Ground Stop'
        snap['current_status_code'] = 'GROUND_STOP'
        snap['current_reason'] = reason
        snap['current_impact_color'] = 'Red'
        snap['delay_summary'] = _build_delay_summary('Ground Stop', None, None, reason)
        return snap

    gd = event.get('groundDelay')
    if gd and gd is not None and gd is not False:
        obj = gd if isinstance(gd, dict) else {}
        avg = _parse_minutes(obj.get('averageDelay') or obj.get('avgDelay'))
        max_ = _parse_minutes(obj.get('maximumDelay') or obj.get('maxDelay'))
        reason = _extract_reason(obj)
        color = 'Red' if (avg is not None and avg >= GDP_RED_THRESHOLD_MINUTES) else 'Amber'
        snap['current_delay_type'] = 'Ground Delay Program'
        snap['current_status_code'] = 'GROUND_DELAY_PROGRAM'
        snap['current_reason'] = reason
        snap['avg_delay_minutes'] = avg
        snap['max_delay_minutes'] = max_
        snap['current_impact_color'] = color
        snap['delay_summary'] = _build_delay_summary('Ground Delay Program', avg, max_, reason)
        return snap

    # Arrival and departure delays — take worst / first present
    for prog_key, label in (('arrivalDelay', 'Arrival Delay'),
                            ('departureDelay', 'Departure Delay')):
        prog = event.get(prog_key)
        if prog and prog is not None and prog is not False:
            obj = prog if isinstance(prog, dict) else {}
            avg = _parse_minutes(obj.get('averageDelay') or obj.get('avgDelay') or obj.get('delay'))
            max_ = _parse_minutes(obj.get('maximumDelay') or obj.get('maxDelay'))
            reason = _extract_reason(obj)
            # Escalate to Red only if the reported delay is severe (>= 60 min)
            color = 'Red' if (avg is not None and avg >= 60) else 'Amber'
            snap['current_delay_type'] = label
            snap['current_status_code'] = 'DELAY'
            snap['current_reason'] = reason
            snap['avg_delay_minutes'] = avg
            snap['max_delay_minutes'] = max_
            snap['current_impact_color'] = color
            snap['delay_summary'] = _build_delay_summary(label, avg, max_, reason)
            return snap

    # No active program — leave NORMAL defaults (current_reason already set)
    return snap


def main() -> None:
    parser = argparse.ArgumentParser(description='Pull FAA NAS airport events')
    parser.add_argument('--dry-run', action='store_true',
                        help='Fetch data but do not write to Supabase')
    parser.add_argument('--limit', type=int, default=None,
                        help='Limit number of tracked airports processed')
    args = parser.parse_args()

    load_env()

    sb_url: str | None = None
    sb_key: str | None = None
    try:
        sb_url, sb_key = get_supabase_creds()
    except RuntimeError as e:
        log('supabase_config_error', str(e))
        if not args.dry_run:
            sys.exit(1)

    # ── Load tracked airports from Supabase ───────────────────────────
    airports: list[dict] = []
    if sb_url and sb_key:
        try:
            airports = get_active_airports(sb_url, sb_key, limit=args.limit)
            log('airports_loaded', {'count': len(airports), 'source': 'supabase'})
        except Exception as e:
            log('airports_load_error', str(e))

    if not airports:
        log('no_airports', 'No airports to process — exiting')
        write_feed_run(sb_url, sb_key, SOURCE_ID, False, 0,
                       'No airports loaded from Supabase', dry_run=args.dry_run)
        return

    # ── Fetch FAA NAS events ONCE ─────────────────────────────────────
    raw_events: list[dict] = []
    endpoint_ok = False
    fetch_error: str | None = None
    try:
        data = http_get_json(FAA_NAS_EVENTS_URL)
        if isinstance(data, list):
            raw_events = data
        elif isinstance(data, dict):
            # Some versions wrap the list in an envelope
            raw_events = (data.get('items') or data.get('airports')
                          or data.get('events') or [data])
        endpoint_ok = True
        log('faa_events_fetched', {
            'url': FAA_NAS_EVENTS_URL,
            'total_events': len(raw_events),
        })
    except Exception as e:
        fetch_error = str(e)
        log('faa_events_fetch_error', {'url': FAA_NAS_EVENTS_URL, 'error': fetch_error})
        write_feed_run(sb_url, sb_key, SOURCE_ID, False, 0, fetch_error, dry_run=args.dry_run)
        return

    # Save raw response regardless of dry-run
    save_raw('faa_nas_status', raw_events)
    log('raw_saved', {'file': 'data/raw/faa_nas_status.json', 'events': len(raw_events)})

    # ── Index events by airportId (IATA) ──────────────────────────────
    events_by_iata: dict[str, dict] = {}
    for ev in raw_events:
        aid = (ev.get('airportId') or ev.get('airport') or ev.get('iata') or '').strip().upper()
        if aid:
            events_by_iata[aid] = ev

    tracked_iatas = {(a.get('iata') or '').upper() for a in airports if a.get('iata')}
    matched = tracked_iatas & set(events_by_iata)

    log('event_index_built', {
        'total_events_in_response': len(events_by_iata),
        'tracked_airports': len(tracked_iatas),
        'tracked_with_active_event': len(matched),
        'tracked_with_no_event': len(tracked_iatas) - len(matched),
    })

    # ── Build one snapshot per tracked airport ────────────────────────
    snapshots: list[dict] = []
    for apt in airports:
        iata = (apt.get('iata') or '').strip().upper()
        if not iata:
            continue
        event = events_by_iata.get(iata)  # None if no active program
        snap = parse_faa_event(event, apt)
        snapshots.append(snap)

        if args.dry_run:
            log('snapshot_dry_run', {
                'airport': iata,
                'delay_type': snap['current_delay_type'],
                'status_code': snap['current_status_code'],
                'avg_delay': snap['avg_delay_minutes'],
                'impact': snap['current_impact_color'],
            })

    log('pull_summary', {
        'snapshots_built': len(snapshots),
        'endpoint_ok': endpoint_ok,
        'dry_run': args.dry_run,
    })

    # ── Write to Supabase (or dry-run) ────────────────────────────────
    write_ok = False
    write_error: str | None = None
    try:
        insert_snapshots(sb_url, sb_key, snapshots, dry_run=args.dry_run)
        write_ok = True
    except Exception as e:
        write_error = str(e)
        log('snapshot_write_error', write_error)

    write_feed_run(
        sb_url, sb_key, SOURCE_ID,
        success=write_ok,
        records=len(snapshots),
        error=write_error,
        dry_run=args.dry_run,
    )


if __name__ == '__main__':
    main()
