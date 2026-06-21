#!/usr/bin/env python3
"""Parse and ingest ATCSCC / FAA NAS advisory data into the C3 atcscc_advisories table.

DOCTRINE:
  FAA NAS / ATCSCC / official airport / NOTAM sources = Current Operational Impact.
  This is the only operational aviation truth lane.
  Advisory language is FAA operational context — NOT route-impact scoring.
  NWS CAP public alerts are NOT FAA operational delay truth.
  AviationWeather.gov hazards are aviation-weather truth — NOT operational delay truth.
  RouteCast corridor geometry is a planning/display scaffold — NOT operational truth.
  Do not invent advisories, restrictions, ground stops, or route closures.
  Do not claim delays unless explicit advisory language contains a traffic management
  term (GDP, GS, AFP, MIT) — and even then store it ONLY as FAA operational context,
  not as an impact score.
  Empty state is better than invented data.

Sources consumed (in order of preference):
  1. data/raw/atcscc_advisories.json    — NAS XML NOTAM-style advisories
                                          (written by pull_atcscc_ops_plan.py)
  2. data/raw/atcscc_ops_plan_raw.json  — Ops plan advisory text + sections
                                          (written by pull_atcscc_ops_plan.py)
  3. Live fetch from NAS status URL     — if no cache is present
  4. --source-url                       — manual advisory URL (fetch and parse)

Writes (Supabase):
  atcscc_advisories   — C3 advisory storage (one row per advisory; upsert on advisory_id)
  feed_runs           — (source_system_id='atcscc_c3_advisories')

Writes (local):
  data/raw/atcscc_c3_advisories.json   — parsed C3 advisory rows (for match script)

Auth:
  SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY from .env or environment.
  FAA NAS Status sources require no API key.
  Never put API keys in this script.

Usage:
  python scripts/pull/pull_atcscc_advisories.py --dry-run
  python scripts/pull/pull_atcscc_advisories.py --dry-run --limit 5
  python scripts/pull/pull_atcscc_advisories.py
  python scripts/pull/pull_atcscc_advisories.py --source-url "https://www.fly.faa.gov/..."
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import urllib.parse
import urllib.request
import urllib.error
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).parent))
from lib_pull import (
    ROOT as LIB_ROOT,
    load_env,
    log,
    get_supabase_creds,
    http_get_text,
    save_raw,
    load_raw,
    write_feed_run,
    utc_now,
    _sb_headers,
)

SOURCE_ID = 'atcscc_c3_advisories'
NAS_STATUS_URL = 'https://nasstatus.faa.gov/api/airport-status-information'
ATCSCC_ADV_XML_URL = 'https://www.fly.faa.gov/adv/adv_str.xml'


# ─── Conservative parsing helpers ─────────────────────────────────────────────

_TM_TERMS = [
    ('GDP',  ['ground delay program', 'ground delay', 'gdp']),
    ('GS',   ['ground stop', 'ground stops']),
    ('AFP',  ['airspace flow program', 'flow program', 'afp']),
    ('MIT',  ['miles in trail', 'miles-in-trail', ' mit ']),
    ('reroute', ['reroute', 'coded departure route', 'cdr']),
    ('SWAP', ['swap route', 'weather avoidance route']),
    ('staffing', ['staffing', 'short staffed', 'low staffing']),
]

_WEATHER_TERMS = [
    'thunderstorm', 'convective', 'sigmet', 'airmet', 'turbulence',
    'icing', 'low visibility', 'fog', 'snow', 'ice', 'freezing',
    'wind', 'hurricane', 'tropical',
]

_ARTCC_CODES = frozenset({
    'ZAB','ZAN','ZAU','ZBW','ZDC','ZDV','ZFW','ZHU','ZID','ZJX',
    'ZKC','ZLA','ZLC','ZMA','ZME','ZMP','ZNY','ZOA','ZOB','ZSE','ZTL',
})


def _extract_airports(text: str) -> list[str]:
    """Extract IATA or ICAO airport codes mentioned explicitly in text.

    Looks for K+3-letter ICAO codes (e.g. KLAX) and standalone 3-letter IATA
    codes (LAX) surrounded by word boundaries.
    Conservative: only returns codes that look like airports.
    """
    found: list[str] = []
    # ICAO K-prefixed (US): KLAX, KJFK, etc.
    icao = re.findall(r'\bK([A-Z]{3})\b', text)
    found.extend(icao)
    # Also standalone ICAO when 4 uppercase letters all caps
    icao4 = re.findall(r'\b(K[A-Z]{3})\b', text)
    found.extend(icao4)
    # IATA 3-letter standalone (only uppercase, surrounded by word boundaries)
    iata = re.findall(r'\b([A-Z]{3})\b', text)
    found.extend(a for a in iata if a not in _ARTCC_CODES and len(a) == 3)
    seen: set[str] = set()
    result: list[str] = []
    for a in found:
        if a not in seen:
            seen.add(a)
            result.append(a)
    return result


def _extract_facilities(text: str) -> list[str]:
    """Extract ARTCC / facility codes explicitly mentioned in text."""
    upper = text.upper()
    return [code for code in _ARTCC_CODES if code in upper]


def _extract_tm_terms(text: str) -> list[str]:
    """Return traffic management terms found explicitly in text."""
    lower = text.lower()
    found: list[str] = []
    for label, patterns in _TM_TERMS:
        if any(p in lower for p in patterns):
            found.append(label)
    return found


def _extract_weather_terms(text: str) -> list[str]:
    """Return weather terms found explicitly in text."""
    lower = text.lower()
    return [t for t in _WEATHER_TERMS if t in lower]


def _classify_advisory_type(text: str, notam_type: str = '') -> Optional[str]:
    """Return a conservative advisory_type from text and notam type field.

    Only returns a type when the text explicitly uses the term.
    """
    lower = text.lower()
    notam_lower = notam_type.lower()

    if 'ground delay program' in lower or 'ground delay program' in notam_lower or 'gdp' in notam_lower:
        return 'GDP'
    if 'ground stop' in lower or 'ground stop' in notam_lower:
        return 'GS'
    if 'airspace flow program' in lower:
        return 'AFP'
    if 'miles in trail' in lower or 'miles-in-trail' in lower:
        return 'MIT'
    if 'reroute' in lower or 'coded departure route' in lower:
        return 'reroute'
    if 'staffing' in lower:
        return 'staffing'
    if any(t in lower for t in ['thunderstorm', 'convective', 'sigmet']):
        return 'weather'
    # Check NOTAM type field alone
    if notam_type:
        return notam_type.strip().lower().replace(' ', '_') or None
    return None


def _make_advisory_id(source: str, content_key: str) -> str:
    """Create a stable 16-char hex advisory_id from source + content key."""
    raw = f'{source}:{content_key}'
    return hashlib.sha256(raw.encode('utf-8')).hexdigest()[:16]


def _short_summary(raw_text: str, max_len: int = 200) -> str:
    """Return first non-empty line of raw_text as a short summary."""
    for line in raw_text.splitlines():
        line = line.strip()
        if line:
            return line[:max_len]
    return ''


# ─── Source: NAS XML NOTAM-style advisories ───────────────────────────────────

def _parse_notam_cache(notam_data: dict, limit: Optional[int]) -> list[dict]:
    """Parse data/raw/atcscc_advisories.json into C3 advisory rows."""
    raw_advisories = notam_data.get('advisories', [])
    if limit:
        raw_advisories = raw_advisories[:limit]

    rows: list[dict] = []
    for adv in raw_advisories:
        if not isinstance(adv, dict):
            continue
        airport = (adv.get('airport') or '').strip()
        adv_type = (adv.get('type') or '').strip()
        reason = (adv.get('reason') or '').strip()
        avg_delay = (adv.get('avg_delay') or '').strip()
        max_delay = (adv.get('max_delay') or '').strip()

        raw_text = f'Airport: {airport}. Type: {adv_type}. Reason: {reason}.'
        if avg_delay:
            raw_text += f' Avg: {avg_delay}.'
        if max_delay:
            raw_text += f' Max: {max_delay}.'

        content_key = f'{airport}:{adv_type}:{reason[:50]}'
        advisory_id = _make_advisory_id('FAA_NAS_NOTAM', content_key)

        rows.append({
            'advisory_id':             advisory_id,
            'advisory_number':         None,
            'source':                  'FAA_ATCSCC',
            'source_url':              notam_data.get('source', ''),
            'source_timestamp':        notam_data.get('retrieved_at'),
            'event_time_text':         None,
            'raw_text':                raw_text,
            'raw_payload':             json.dumps(adv),
            'advisory_type':           _classify_advisory_type(raw_text, adv_type),
            'operational_category':    None,
            'affected_facilities':     _extract_facilities(raw_text),
            'affected_airports':       [airport] if airport else [],
            'affected_regions':        [],
            'mentioned_routes':        [],
            'mentioned_fix_labels':    [],
            'weather_terms':           _extract_weather_terms(raw_text),
            'traffic_management_terms': _extract_tm_terms(raw_text),
            'parsed_summary':          _short_summary(raw_text),
            'is_active':               True,
            'is_stale':                False,
            'source_truth_lane':       'faa_atcscc_operational_truth',
            'updated_at':              utc_now(),
        })
    return rows


# ─── Source: Ops plan text advisories ─────────────────────────────────────────

def _parse_ops_plan_cache(ops_plan_data: dict, limit: Optional[int]) -> list[dict]:
    """Parse data/raw/atcscc_ops_plan_raw.json into C3 advisory rows."""
    plans = ops_plan_data.get('plans', [])
    if limit:
        plans = plans[:limit]

    rows: list[dict] = []
    for plan in plans:
        if not isinstance(plan, dict):
            continue
        plain_text = (plan.get('plain_text') or '').strip()
        if not plain_text:
            continue

        source_url = plan.get('source_url', '')
        adv_number = plan.get('advisory_number')
        adv_date = plan.get('advisory_date', '')
        event_time = plan.get('event_time')

        content_key = f'{source_url}:{adv_number}:{adv_date}'
        advisory_id = _make_advisory_id('FAA_ATCSCC_OPSPLAN', content_key)

        airports = _extract_airports(plain_text)
        facilities = _extract_facilities(plain_text)
        tm_terms = _extract_tm_terms(plain_text)
        wx_terms = _extract_weather_terms(plain_text)

        # Extract fix labels: 3-6 uppercase letters that look like named fixes
        # (not airports, not ARTCC codes, not common English words)
        _common = frozenset({'THE','AND','FOR','WITH','WILL','HAVE','THIS',
                              'FROM','THAT','THEY','BEEN','WERE','ARE','NOT',
                              'ALL','HAS','HER','HIS','BUT','CAN','WAS','HAS'})
        fix_candidates = re.findall(r'\b([A-Z]{3,6})\b', plain_text)
        fix_labels = [
            f for f in fix_candidates
            if f not in _common
            and f not in _ARTCC_CODES
            and f not in airports
            and not re.match(r'^K[A-Z]{3}$', f)
        ]
        # Deduplicate, keep order
        seen_fixes: set[str] = set()
        unique_fixes: list[str] = []
        for f in fix_labels:
            if f not in seen_fixes:
                seen_fixes.add(f)
                unique_fixes.append(f)

        rows.append({
            'advisory_id':             advisory_id,
            'advisory_number':         str(adv_number) if adv_number is not None else None,
            'source':                  'FAA_ATCSCC',
            'source_url':              source_url,
            'source_timestamp':        ops_plan_data.get('retrieved_at'),
            'event_time_text':         event_time,
            'raw_text':                plain_text[:10000],
            'raw_payload':             json.dumps({
                'advisory_number': adv_number,
                'advisory_date':   adv_date,
                'sections':        [s.get('section_key') for s in plan.get('sections', [])],
            }),
            'advisory_type':           _classify_advisory_type(plain_text),
            'operational_category':    None,
            'affected_facilities':     facilities,
            'affected_airports':       airports,
            'affected_regions':        [],
            'mentioned_routes':        [],
            'mentioned_fix_labels':    unique_fixes[:50],
            'weather_terms':           wx_terms,
            'traffic_management_terms': tm_terms,
            'parsed_summary':          _short_summary(plain_text),
            'is_active':               True,
            'is_stale':                False,
            'source_truth_lane':       'faa_atcscc_operational_truth',
            'updated_at':              utc_now(),
        })
    return rows


# ─── Source: Manual --source-url HTML fetch ───────────────────────────────────

def _fetch_and_parse_url(url: str) -> Optional[dict]:
    """Fetch an advisory URL and return a minimal C3 advisory row, or None on error."""
    try:
        html_src = http_get_text(url, timeout=30)
    except Exception as e:
        log('source_url_fetch_error', {'url': url, 'error': str(e)})
        return None

    import html as html_mod
    from html.parser import HTMLParser

    class _TextCollector(HTMLParser):
        def __init__(self):
            super().__init__(convert_charrefs=True)
            self._in_skip = 0
            self._in_pre = 0
            self.chunks: list[str] = []
            self.pre_chunks: list[str] = []
            self._skip = frozenset({'script','style','head','noscript'})
        def handle_starttag(self, tag, attrs):
            t = tag.lower()
            if t in self._skip: self._in_skip += 1
            if t == 'pre': self._in_pre += 1
        def handle_endtag(self, tag):
            t = tag.lower()
            if t in self._skip and self._in_skip: self._in_skip -= 1
            if t == 'pre' and self._in_pre: self._in_pre -= 1
        def handle_data(self, data):
            if self._in_skip: return
            if self._in_pre: self.pre_chunks.append(data)
            else: self.chunks.append(data)

    parser = _TextCollector()
    try:
        parser.feed(html_src)
    except Exception:
        pass
    parts = parser.pre_chunks if parser.pre_chunks else parser.chunks
    plain_text = '\n'.join(parts)
    plain_text = html_mod.unescape(plain_text)
    plain_text = re.sub(r'\n{3,}', '\n\n', plain_text).strip()

    if not plain_text:
        log('source_url_no_text', {'url': url})
        return None

    parsed = urllib.parse.urlparse(url)
    qs = urllib.parse.parse_qs(parsed.query)
    adv_date = (qs.get('adv_date') or [''])[0]
    advisory_number_raw = (qs.get('advisory_number') or qs.get('advzy') or [''])[0]
    advisory_number: Optional[str] = advisory_number_raw or None

    content_key = f'{url}:{plain_text[:100]}'
    advisory_id = _make_advisory_id('FAA_ATCSCC_URL', content_key)

    airports = _extract_airports(plain_text)
    facilities = _extract_facilities(plain_text)

    return {
        'advisory_id':             advisory_id,
        'advisory_number':         advisory_number,
        'source':                  'FAA_ATCSCC',
        'source_url':              url,
        'source_timestamp':        utc_now(),
        'event_time_text':         None,
        'raw_text':                plain_text[:10000],
        'raw_payload':             json.dumps({'source_url': url, 'adv_date': adv_date}),
        'advisory_type':           _classify_advisory_type(plain_text),
        'operational_category':    None,
        'affected_facilities':     facilities,
        'affected_airports':       airports,
        'affected_regions':        [],
        'mentioned_routes':        [],
        'mentioned_fix_labels':    [],
        'weather_terms':           _extract_weather_terms(plain_text),
        'traffic_management_terms': _extract_tm_terms(plain_text),
        'parsed_summary':          _short_summary(plain_text),
        'is_active':               True,
        'is_stale':                False,
        'source_truth_lane':       'faa_atcscc_operational_truth',
        'updated_at':              utc_now(),
    }


# ─── Supabase upsert ──────────────────────────────────────────────────────────

def _upsert_advisories(sb_url: str, sb_key: str, rows: list[dict]) -> None:
    """Upsert advisory rows into atcscc_advisories on advisory_id."""
    path = f'{sb_url}/rest/v1/atcscc_advisories?on_conflict=advisory_id'
    body = json.dumps(rows).encode('utf-8')
    req = urllib.request.Request(
        path, data=body,
        headers=_sb_headers(sb_key, {
            'Prefer': 'resolution=merge-duplicates,return=minimal',
        }),
        method='POST',
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            resp.read()
        log('advisories_upserted', {'count': len(rows)})
    except urllib.error.HTTPError as e:
        body_err = e.read().decode(errors='ignore')
        raise RuntimeError(
            f'Supabase upsert atcscc_advisories → HTTP {e.code}: {body_err[:400]}'
        )


# ─── Main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description='Parse and ingest ATCSCC C3 advisory data into atcscc_advisories table'
    )
    parser.add_argument(
        '--dry-run', action='store_true',
        help='Parse and log rows but do not write to Supabase',
    )
    parser.add_argument(
        '--limit', type=int, default=None,
        help='Limit number of advisory rows processed per source',
    )
    parser.add_argument(
        '--source-url', type=str, default=None,
        help='Manually fetch and parse a specific ATCSCC advisory URL',
    )
    args = parser.parse_args()

    load_env()

    sb_url: Optional[str] = None
    sb_key: Optional[str] = None
    if not args.dry_run:
        try:
            sb_url, sb_key = get_supabase_creds()
        except RuntimeError as e:
            log('supabase_config_error', str(e))
            sys.exit(1)
    else:
        try:
            sb_url, sb_key = get_supabase_creds()
        except RuntimeError:
            log('supabase_creds_not_available',
                'Dry-run mode — Supabase write will be skipped')

    all_rows: list[dict] = []
    source_log: list[str] = []

    # ── Source 1: NAS XML NOTAM-style advisory cache ──────────────────────────
    notam_data = load_raw('atcscc_advisories')
    if notam_data and isinstance(notam_data, dict):
        notam_rows = _parse_notam_cache(notam_data, args.limit)
        all_rows.extend(notam_rows)
        source_log.append(f'notam_cache:{len(notam_rows)} rows')
        log('source_notam_cache_loaded', {
            'count': len(notam_rows),
            'source': notam_data.get('source', 'unknown'),
        })
    else:
        log('source_notam_cache_missing', {
            'note': 'data/raw/atcscc_advisories.json not found. '
                    'Run pull_atcscc_ops_plan.py first to populate the cache.',
        })

    # ── Source 2: Ops plan raw cache ──────────────────────────────────────────
    ops_plan_data = load_raw('atcscc_ops_plan_raw')
    if ops_plan_data and isinstance(ops_plan_data, dict):
        ops_rows = _parse_ops_plan_cache(ops_plan_data, args.limit)
        all_rows.extend(ops_rows)
        source_log.append(f'ops_plan_cache:{len(ops_rows)} rows')
        log('source_ops_plan_cache_loaded', {
            'count': len(ops_rows),
            'plans_in_cache': len(ops_plan_data.get('plans', [])),
        })
    else:
        log('source_ops_plan_cache_missing', {
            'note': 'data/raw/atcscc_ops_plan_raw.json not found. '
                    'Run pull_atcscc_ops_plan.py first to populate the cache.',
        })

    # ── Source 3: Live NAS fetch if no cache was found ────────────────────────
    if not all_rows and not args.source_url:
        log('attempting_live_nas_fetch', {
            'url': NAS_STATUS_URL,
            'note': 'No raw cache files found — attempting live fetch from FAA NAS status.',
        })
        try:
            import xml.etree.ElementTree as ET
            xml_text = http_get_text(NAS_STATUS_URL, timeout=30)
            log('live_nas_fetch_ok', {'url': NAS_STATUS_URL, 'bytes': len(xml_text)})
            # Build a minimal notam_data structure from the live XML
            try:
                root = ET.fromstring(xml_text)
                notam_advisories: list[dict] = []
                for node in root.findall('.//Airport') + root.findall('.//airport'):
                    arpt = (node.findtext('ARPT') or node.findtext('ICAOCode') or
                            node.get('ID', '')).upper()
                    if arpt:
                        notam_advisories.append({
                            'airport': arpt,
                            'type': node.findtext('Type') or node.findtext('ProgramType') or '',
                            'reason': node.findtext('Reason') or node.findtext('AdvisoryText') or '',
                            'avg_delay': node.findtext('Avg') or '',
                            'max_delay': node.findtext('Max') or '',
                        })
                live_data = {
                    'retrieved_at': utc_now(),
                    'source': NAS_STATUS_URL,
                    'advisories': notam_advisories,
                }
                live_rows = _parse_notam_cache(live_data, args.limit)
                all_rows.extend(live_rows)
                source_log.append(f'live_nas:{len(live_rows)} rows')
                log('live_nas_parsed', {'count': len(live_rows)})
            except ET.ParseError as e:
                log('live_nas_xml_parse_error', str(e))
        except Exception as e:
            log('live_nas_fetch_error', {
                'url': NAS_STATUS_URL,
                'error': str(e),
                'note': 'ATCSCC source URL is established: '
                        + NAS_STATUS_URL + '. Fetch failed — check connectivity.',
            })

    # ── Source 4: Manual --source-url ─────────────────────────────────────────
    if args.source_url:
        log('manual_source_url', {'url': args.source_url})
        row = _fetch_and_parse_url(args.source_url)
        if row:
            all_rows.append(row)
            source_log.append('manual_url:1 row')
            log('manual_source_url_parsed', {'advisory_id': row.get('advisory_id')})
        else:
            log('manual_source_url_no_result', {'url': args.source_url})

    # ── Deduplicate on advisory_id ─────────────────────────────────────────────
    seen_ids: set[str] = set()
    deduped: list[dict] = []
    for row in all_rows:
        aid = row.get('advisory_id') or ''
        if aid and aid not in seen_ids:
            seen_ids.add(aid)
            deduped.append(row)
        elif not aid:
            deduped.append(row)

    log('advisories_ready', {
        'total': len(deduped),
        'sources': source_log,
        'dry_run': args.dry_run,
    })

    if not deduped:
        log('no_advisories_found', {
            'note': 'No ATCSCC advisory data found in any source. '
                    'Run pull_atcscc_ops_plan.py to populate raw cache files. '
                    'This is expected on first run before any pull has occurred. '
                    'Empty state is better than invented data.',
        })
        write_feed_run(
            sb_url, sb_key, SOURCE_ID,
            success=True, records=0, error=None,
            dry_run=args.dry_run,
        )
        return

    # ── Dry-run: log rows ─────────────────────────────────────────────────────
    if args.dry_run:
        for row in deduped[:20]:
            log('advisory_dry_run', {
                'advisory_id':             row.get('advisory_id'),
                'advisory_type':           row.get('advisory_type'),
                'affected_airports':       row.get('affected_airports'),
                'traffic_management_terms': row.get('traffic_management_terms'),
                'weather_terms':           row.get('weather_terms'),
                'parsed_summary':          (row.get('parsed_summary') or '')[:100],
                'source_truth_lane':       row.get('source_truth_lane'),
            })
        if len(deduped) > 20:
            log('dry_run_truncated', {'shown': 20, 'total': len(deduped)})

    # ── Save local C3 advisory cache (always) ─────────────────────────────────
    c3_output = {
        'retrieved_at':  utc_now(),
        'source_log':    source_log,
        'advisory_count': len(deduped),
        'advisories':    deduped,
    }
    save_raw('atcscc_c3_advisories', c3_output)
    log('c3_cache_saved', {
        'file': 'data/raw/atcscc_c3_advisories.json',
        'count': len(deduped),
    })

    # ── Write to Supabase ─────────────────────────────────────────────────────
    success = True
    error_msg: Optional[str] = None
    if not args.dry_run and sb_url and sb_key:
        try:
            _upsert_advisories(sb_url, sb_key, deduped)
        except RuntimeError as e:
            success = False
            error_msg = str(e)
            log('upsert_error', {'error': error_msg})

    write_feed_run(
        sb_url, sb_key, SOURCE_ID,
        success=success,
        records=len(deduped),
        error=error_msg,
        dry_run=args.dry_run,
    )

    log('pull_summary', {
        'advisories_processed': len(deduped),
        'sources': source_log,
        'dry_run': args.dry_run,
        'write_success': success if not args.dry_run else None,
        'source_truth_lane': 'faa_atcscc_operational_truth',
    })


if __name__ == '__main__':
    main()
