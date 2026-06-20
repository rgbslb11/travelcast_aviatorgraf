#!/usr/bin/env python3
"""Parse TAF forecast periods into structured Supabase rows.

Reads from the data/raw/taf_raw.json cache written by pull_aviationweather_metar_taf.py.
Parses each TAF's fcsts[] (forecast groups) into individual period rows:
  GROUP TYPES: BASE (initial period), FM, TEMPO, PROB, BECMG

DOCTRINE:
  AviationWeather.gov = Aviation Weather Truth.
  TAF is official aviation forecast weather. It does NOT predict FAA operational
  delays, ground stops, ground delay programs, route closures, or AAR.
  NWS forecast impact is a separate source lane (forecast proxy only).
  Empty state is better than invented data.

Staleness rule:
  taf_raw.json older than 8 hours is treated as stale for TravelCast
  aviation-weather production. Re-run pull_aviationweather_metar_taf.py first
  to refresh the raw cache.

Usage:
  python scripts/pull/pull_taf_timeline.py
  python scripts/pull/pull_taf_timeline.py --dry-run
  python scripts/pull/pull_taf_timeline.py --limit 5
  python scripts/pull/pull_taf_timeline.py --fetch    # re-fetch from AviationWeather.gov

Supabase tables written:
  taf_forecasts         — one row per TAF bulletin
  taf_forecast_periods  — one row per forecast group (BASE / FM / TEMPO / PROB / BECMG)

Requires (from .env):
  SUPABASE_URL
  SUPABASE_SERVICE_ROLE_KEY
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts' / 'pull'))
from lib_pull import (
    load_env, log, get_supabase_creds, supabase_post, write_feed_run,
    get_active_airports, http_get_json, save_raw, load_raw, utc_now,
)

SOURCE_ID = 'taf_timeline'
TAF_URL_TEMPLATE = 'https://aviationweather.gov/api/data/taf?ids={ids}&format=json'
BATCH_SIZE = 30
UPSERT_PREFER = 'resolution=merge-duplicates,return=minimal'


# ─── Time helpers ────────────────────────────────────────────────────────────

def epoch_to_iso(ts) -> str | None:
    if ts is None:
        return None
    try:
        return datetime.fromtimestamp(int(ts), tz=timezone.utc).isoformat()
    except (TypeError, ValueError, OSError):
        return None


def parse_issue_time(obj: dict) -> tuple[str | None, str | None]:
    """Return (iso_string, time_component_for_taf_id)."""
    it = obj.get('issueTime')
    if it:
        try:
            dt = datetime.fromisoformat(str(it).replace('Z', '+00:00'))
            return dt.isoformat(), dt.strftime('%Y%m%d-%H%M')
        except (ValueError, TypeError):
            pass
    vt = obj.get('validTimeFrom')
    if vt is not None:
        try:
            dt = datetime.fromtimestamp(int(vt), tz=timezone.utc)
            return dt.isoformat(), dt.strftime('%Y%m%d-%H%M')
        except (TypeError, ValueError, OSError):
            pass
    return None, None


# ─── TAF parsing helpers ─────────────────────────────────────────────────────

def compute_ceiling_ft(clouds: list) -> int | None:
    """Lowest BKN or OVC layer in feet. Returns None if no ceiling."""
    if not clouds:
        return None
    bkn_ovc = [
        c['base'] for c in clouds
        if isinstance(c, dict)
        and c.get('cover') in ('BKN', 'OVC')
        and c.get('base') is not None
    ]
    return min(bkn_ovc) if bkn_ovc else None


def parse_visibility_sm(visib) -> float | None:
    if visib is None:
        return None
    v = str(visib).strip()
    if v == '6+':
        return 6.0
    try:
        return float(v)
    except ValueError:
        return None


def implied_flight_category(ceiling_ft: int | None, visib_sm: float | None) -> str | None:
    """
    Compute implied flight category from ceiling and visibility.
    Returns VFR / MVFR / IFR / LIFR or None if neither value is available.
    This is an implication from source conditions — not a certified determination.
    """
    c = ceiling_ft
    v = visib_sm
    if c is None and v is None:
        return None
    if (c is not None and c < 500) or (v is not None and v < 1.0):
        return 'LIFR'
    if (c is not None and c < 1000) or (v is not None and v < 3.0):
        return 'IFR'
    if (c is not None and c < 3000) or (v is not None and v < 5.0):
        return 'MVFR'
    return 'VFR'


def format_wind_dir(wdir) -> str | None:
    if wdir is None:
        return None
    if isinstance(wdir, str) and wdir.upper() == 'VRB':
        return 'VRB'
    try:
        return f'{int(wdir):03d}'
    except (TypeError, ValueError):
        return str(wdir)


def build_conditions_text(
    fcst: dict,
    ceiling_ft: int | None,
    category: str | None,
) -> str:
    """Concise conditions summary from source fields only. No interpretation added."""
    parts: list[str] = []

    wx = (fcst.get('wxString') or '').strip()
    if wx:
        parts.append(wx)

    clouds = fcst.get('clouds') or []
    sky_parts: list[str] = []
    for c in clouds:
        if not isinstance(c, dict):
            continue
        cover = c.get('cover', '')
        base = c.get('base')
        if cover and base is not None:
            try:
                sky_parts.append(f"{cover}{int(base) // 100:03d}")
            except (TypeError, ValueError):
                sky_parts.append(cover)
        elif cover:
            sky_parts.append(cover)
    if sky_parts:
        parts.append(' '.join(sky_parts))

    visib = fcst.get('visib')
    if visib is not None:
        parts.append(f"VIS {visib}SM")

    wdir = fcst.get('wdir')
    wspd = fcst.get('wspd')
    if wdir is not None and wspd is not None:
        wdir_str = format_wind_dir(wdir) or '???'
        gst = fcst.get('wgst')
        if gst:
            parts.append(f"WIND {wdir_str}/{wspd}G{gst}KT")
        else:
            parts.append(f"WIND {wdir_str}/{wspd}KT")

    if category:
        parts.append(f"[implied:{category}]")

    return ' '.join(parts)


def parse_taf_object(
    obj: dict,
    ap: dict,
    fetched_at: str,
) -> tuple[dict | None, list[dict]]:
    """Parse one raw TAF object into (taf_forecasts_row, list_of_period_rows).
    Returns (None, []) if the object is malformed.
    """
    icao = (obj.get('icaoId') or '').strip().upper()
    if not icao:
        return None, []

    issue_iso, time_component = parse_issue_time(obj)
    if not time_component:
        time_component = 'UNKNOWN'
    taf_id = f'{icao}-{time_component}'

    airport_id = ap.get('airport_id', '')
    iata = ap.get('iata', '')

    taf_row: dict = {
        'taf_id': taf_id,
        'airport_id': airport_id,
        'iata': iata,
        'icao': icao,
        'issue_time_utc': issue_iso,
        'valid_from_utc': epoch_to_iso(obj.get('validTimeFrom')),
        'valid_to_utc': epoch_to_iso(obj.get('validTimeTo')),
        'raw_taf': obj.get('rawTAF') or obj.get('rawTaf'),
        'remarks': None,
        'source_system_id': SOURCE_ID,
        'source_url': 'https://aviationweather.gov/api/data/taf',
        'fetched_at_utc': fetched_at,
        'updated_at': fetched_at,
    }

    fcsts = obj.get('fcsts') or []
    period_rows: list[dict] = []

    for seq, fcst in enumerate(fcsts):
        if not isinstance(fcst, dict):
            continue

        change = fcst.get('fcstChange')
        group_type = change if change else 'BASE'

        clouds = fcst.get('clouds') or []
        ceiling = compute_ceiling_ft(clouds)
        visib_sm = parse_visibility_sm(fcst.get('visib'))
        category = implied_flight_category(ceiling, visib_sm)
        conditions = build_conditions_text(fcst, ceiling, category)

        wdir_raw = fcst.get('wdir')
        wspd_raw = fcst.get('wspd')
        wgst_raw = fcst.get('wgst')

        period_row: dict = {
            'period_id': f'{taf_id}-{seq:02d}',
            'taf_id': taf_id,
            'airport_id': airport_id,
            'iata': iata,
            'icao': icao,
            'seq': seq,
            'group_type': group_type,
            'probability': fcst.get('probability'),
            'valid_from_utc': epoch_to_iso(fcst.get('timeFrom')),
            'valid_to_utc': epoch_to_iso(fcst.get('timeTo')),
            'become_time_utc': epoch_to_iso(fcst.get('timeBec')),
            'wind_dir': format_wind_dir(wdir_raw),
            'wind_speed_kt': int(wspd_raw) if wspd_raw is not None else None,
            'wind_gust_kt': int(wgst_raw) if wgst_raw is not None else None,
            'visibility_sm': str(fcst.get('visib')) if fcst.get('visib') is not None else None,
            'wx_string': fcst.get('wxString') or None,
            'clouds_json': clouds if clouds else None,
            'ceiling_ft': ceiling,
            'flight_category_implied': category,
            'conditions_text': conditions or None,
            'raw_period_json': fcst,
        }
        period_rows.append(period_row)

    return taf_row, period_rows


def batched(lst: list, size: int):
    for i in range(0, len(lst), size):
        yield lst[i:i + size]


# ─── Main ────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description='Parse TAF timeline periods into Supabase taf_forecast_periods'
    )
    parser.add_argument('--dry-run', action='store_true',
                        help='Parse and print; do not write to Supabase')
    parser.add_argument('--limit', type=int, default=None,
                        help='Limit number of TAF objects to process (for testing)')
    parser.add_argument('--fetch', action='store_true',
                        help='Re-fetch TAF data from AviationWeather.gov instead of using cache')
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

    # ── Load TAF raw cache (or fetch fresh) ──────────────────────────────────

    raw_tafs: list | None = None

    if not args.fetch:
        raw_tafs = load_raw('taf_raw')
        if raw_tafs is not None:
            log('taf_cache_loaded', {'count': len(raw_tafs) if isinstance(raw_tafs, list) else 0})
        else:
            log('taf_cache_missing', {
                'note': 'No taf_raw.json found. Run pull_aviationweather_metar_taf.py first, '
                        'or use --fetch to re-fetch from AviationWeather.gov.'
            })

    if raw_tafs is None or args.fetch:
        # Fetch fresh — requires airport list for ICAO IDs
        if url is None or key is None:
            log('fetch_error', {'error': 'Cannot fetch without Supabase creds (needed to get airport list). '
                                'Run with --dry-run using existing taf_raw.json, or configure .env.'})
            sys.exit(1)
        log('taf_fetch_start', {'source': 'AviationWeather.gov'})
        airports = get_active_airports(url, key)
        icaos = [ap['icao'] for ap in airports if ap.get('icao')]
        raw_tafs = []
        for batch in batched(icaos, BATCH_SIZE):
            ids = ','.join(batch)
            taf_url = TAF_URL_TEMPLATE.format(ids=ids)
            try:
                batch_data = http_get_json(taf_url)
                if isinstance(batch_data, list):
                    raw_tafs.extend(batch_data)
            except Exception as exc:
                log('taf_fetch_batch_error', {'ids': ids, 'error': str(exc)})
        save_raw('taf_raw', raw_tafs)
        log('taf_fetch_complete', {'count': len(raw_tafs)})

    if not isinstance(raw_tafs, list):
        log('taf_format_error', {'type': type(raw_tafs).__name__})
        write_feed_run(url, key, SOURCE_ID, success=False,
                       error='taf_raw.json is not a list', dry_run=args.dry_run)
        sys.exit(1)

    if args.limit:
        raw_tafs = raw_tafs[: args.limit]

    # ── Build ICAO lookup from Supabase (or skip in dry-run with no Supabase) ─

    airport_lookup: dict[str, dict] = {}
    if url and key:
        try:
            airports = get_active_airports(url, key)
            airport_lookup = {ap['icao'].upper(): ap for ap in airports if ap.get('icao')}
        except Exception as exc:
            log('airport_lookup_warning', {'error': str(exc), 'note': 'Proceeding with empty lookup'})

    # ── Parse TAFs ───────────────────────────────────────────────────────────

    taf_rows: list[dict] = []
    period_rows: list[dict] = []
    skipped = 0
    errors = 0

    for obj in raw_tafs:
        if not isinstance(obj, dict):
            skipped += 1
            continue
        icao = (obj.get('icaoId') or '').strip().upper()
        ap = airport_lookup.get(icao, {
            'airport_id': icao,
            'iata': icao[:3] if len(icao) == 4 and icao.startswith('K') else icao,
        })
        try:
            taf_row, periods = parse_taf_object(obj, ap, fetched_at)
            if taf_row:
                taf_rows.append(taf_row)
                period_rows.extend(periods)
        except Exception as exc:
            log('parse_error', {'icao': icao, 'error': str(exc)})
            errors += 1

    log('parse_complete', {
        'taf_count': len(taf_rows),
        'period_count': len(period_rows),
        'skipped': skipped,
        'errors': errors,
    })

    # ── Dry-run output ───────────────────────────────────────────────────────

    if args.dry_run:
        for row in taf_rows[:5]:
            log('taf_row_preview', {
                'taf_id': row['taf_id'],
                'icao': row['icao'],
                'issue_time_utc': row['issue_time_utc'],
                'valid_from': row['valid_from_utc'],
                'valid_to': row['valid_to_utc'],
            })
        sample_periods = [p for p in period_rows if p.get('seq', 0) == 0][:5]
        for p in sample_periods:
            log('period_row_preview', {
                'period_id': p['period_id'],
                'icao': p['icao'],
                'group_type': p['group_type'],
                'ceiling_ft': p.get('ceiling_ft'),
                'flight_category_implied': p.get('flight_category_implied'),
                'conditions_text': p.get('conditions_text'),
            })
        write_feed_run(None, None, SOURCE_ID, success=True,
                       records=len(period_rows), dry_run=True)
        return

    # ── Write to Supabase ────────────────────────────────────────────────────

    if not url or not key:
        log('skipping_write', {'reason': 'no supabase creds'})
        return

    write_errors = 0
    taf_count = 0
    period_count = 0

    for batch in batched(taf_rows, 50):
        try:
            supabase_post(url, key, 'taf_forecasts', batch, prefer=UPSERT_PREFER)
            taf_count += len(batch)
        except Exception as exc:
            log('upsert_error', {'table': 'taf_forecasts', 'error': str(exc)})
            write_errors += 1

    for batch in batched(period_rows, 100):
        try:
            supabase_post(url, key, 'taf_forecast_periods', batch, prefer=UPSERT_PREFER)
            period_count += len(batch)
        except Exception as exc:
            log('upsert_error', {'table': 'taf_forecast_periods', 'error': str(exc)})
            write_errors += 1

    save_raw('taf_timeline_parsed', {
        'fetched_at': fetched_at,
        'taf_count': taf_count,
        'period_count': period_count,
        'errors': write_errors,
    })

    success = write_errors == 0
    write_feed_run(url, key, SOURCE_ID, success=success,
                   records=period_count,
                   error=f'{write_errors} write error(s)' if write_errors else None)

    log('done', {
        'taf_forecasts_written': taf_count,
        'taf_periods_written': period_count,
        'write_errors': write_errors,
    })

    if write_errors:
        sys.exit(1)


if __name__ == '__main__':
    main()
