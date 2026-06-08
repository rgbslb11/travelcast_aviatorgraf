#!/usr/bin/env python3
"""Pull ATCSCC Operations Plan and NAS status advisory data.

Sources (tried in order):
  1. data/raw/faa_nas_status.json  (cached FAA NAS event JSON — advisory URLs)
  2. https://www.fly.faa.gov/adv/adv_str.xml  (XML advisory list for URL discovery)
  3. https://www.fly.faa.gov/adv/adv_otherdis.jsp?...  (per-advisory HTML pages)
  4. https://nasstatus.faa.gov/api/airport-status-information  (NAS XML — NOTAM-style advisories)

Auth:    None (public FAA pages, no key required)

Writes:
  data/raw/atcscc_ops_plan_raw.json   — all fetched advisory HTML text + parsed plans
  data/raw/atcscc_advisories.json     — NOTAM-style advisory list (existing behaviour)
  data/raw/atcscc_raw.xml             — raw NAS status XML (existing behaviour)
  atcscc_operations_plans             — Supabase (one row per ops-plan advisory)
  atcscc_operations_plan_sections     — Supabase (one row per section per plan)
  feed_runs (source_system_id='atcscc_ops_plan')

Doctrine: ATCSCC / FAA NAS = Current Operational Impact (operational truth)
Label:    "Current Operational Impact — FAA NAS / ATCSCC"

Usage:
  python pull_atcscc_ops_plan.py [--dry-run] [--limit N]
  python pull_atcscc_ops_plan.py --url "https://www.fly.faa.gov/adv/adv_otherdis.jsp?..."
"""
from __future__ import annotations

import argparse
import html
import re
import sys
import urllib.parse
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent))
from lib_pull import (
    ROOT,
    http_get_text,
    load_env,
    load_raw,
    log,
    save_raw,
    supabase_post,
    utc_now,
    write_feed_run,
    _sb_headers,
    get_supabase_creds,
)
import urllib.request
import urllib.error

NAS_STATUS_URL = 'https://nasstatus.faa.gov/api/airport-status-information'
ATCSCC_ADV_XML_URL = 'https://www.fly.faa.gov/adv/adv_str.xml'
SOURCE_ID = 'atcscc_ops_plan'

# ─────────────────────────────── section registry ────────────────────────────

# Each entry: (section_key, display_name, list_of_search_patterns)
_SECTIONS = [
    ('NY_SWAP_PLAN',        'NY/NE SWAP Plan',                  ['NY SWAP', 'NY/NE SWAP']),
    ('STAFFING',            'Staffing',                          ['STAFFING']),
    ('TERMINAL_CONSTRAINTS','Terminal Constraints',              ['TERMINAL CONSTRAINTS']),
    ('TERMINAL_ACTIVE',     'Terminal Active',                   ['TERMINAL ACTIVE']),
    ('TERMINAL_PLANNED',    'Terminal Planned',                  ['TERMINAL PLANNED']),
    ('ENROUTE_CONSTRAINTS', 'En Route Constraints',              ['EN ROUTE CONSTRAINTS', 'ENROUTE CONSTRAINTS']),
    ('ENROUTE_ACTIVE',      'En Route Active',                   ['EN ROUTE ACTIVE', 'ENROUTE ACTIVE']),
    ('ENROUTE_PLANNED',     'En Route Planned',                  ['EN ROUTE PLANNED', 'ENROUTE PLANNED']),
    ('CDRS_SWAP',           'CDRs / SWAP / Capping / Tunneling', ['CDRS', 'SWAP/CAPPING', 'CAPPING/TUNNELING']),
    ('RUNWAY_EQUIPMENT',    'Runway / Equipment / SIRs',         ['RUNWAY/EQUIPMENT', 'POSSIBLE SIRS']),
    ('AFP_ACTIVE',          'Airspace Flow Programs — Active',   ['AFP ACTIVE', 'AIRSPACE FLOW PROGRAMS ACTIVE']),
    ('AFP_PLANNED',         'Airspace Flow Programs — Planned',  ['AFP PLANNED', 'AIRSPACE FLOW PROGRAMS PLANNED']),
    ('LAUNCH_REENTRY',      'Planned Launch / Re-entry',         ['PLANNED LAUNCH', 'LAUNCH/REENTRY']),
    ('FLIGHT_CHECKS',       'Flight Checks',                     ['FLIGHT CHECKS']),
    ('VIP_MOVEMENTS',       'VIP Movements',                     ['VIP MOVEMENTS']),
    ('NEXT_WEBINAR',        'Next Planning Webinar',             ['NEXT PLANNING WEBINAR', 'PLANNING WEBINAR']),
]

# ─────────────────────────────── HTML extraction ──────────────────────────────

class _PreTextCollector(HTMLParser):
    """Collect text inside <pre> tags, fall back to all visible text."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._in_pre = 0
        self._in_skip = 0
        self.pre_chunks: list[str] = []
        self.all_chunks: list[str] = []
        self._skip_tags = frozenset({'script', 'style', 'head', 'noscript'})

    def handle_starttag(self, tag: str, attrs) -> None:
        t = tag.lower()
        if t == 'pre':
            self._in_pre += 1
        if t in self._skip_tags:
            self._in_skip += 1

    def handle_endtag(self, tag: str) -> None:
        t = tag.lower()
        if t == 'pre' and self._in_pre:
            self._in_pre -= 1
        if t in self._skip_tags and self._in_skip:
            self._in_skip -= 1

    def handle_data(self, data: str) -> None:
        if self._in_skip:
            return
        if self._in_pre:
            self.pre_chunks.append(data)
        else:
            self.all_chunks.append(data)


def _extract_text_from_html(html_src: str) -> str:
    """Extract advisory plain text from HTML.

    Prefers <pre> tag content (advisory text is usually formatted there).
    Falls back to stripping all tags from visible body text.
    Decodes HTML entities, collapses whitespace.
    """
    parser = _PreTextCollector()
    try:
        parser.feed(html_src)
    except Exception:
        # If the parser blows up, fall back to crude regex strip
        return re.sub(r'<[^>]+>', ' ', html_src)

    chunks = parser.pre_chunks if parser.pre_chunks else parser.all_chunks
    raw = '\n'.join(chunks)

    # Decode any remaining HTML entities (convert_charrefs=True handles most,
    # but manual escapes like &amp; may survive in attribute values etc.)
    raw = html.unescape(raw)

    # Collapse excessive blank lines (keep at most two consecutive)
    raw = re.sub(r'\n{3,}', '\n\n', raw)
    # Strip trailing whitespace on each line
    raw = '\n'.join(line.rstrip() for line in raw.splitlines())
    return raw.strip()


# ─────────────────────────────── section parsing ─────────────────────────────

def _parse_sections(raw_text: str) -> list[dict]:
    """Split an ATCSCC ops-plan text into its labelled sections.

    Returns a list of dicts ordered as they appear in the _SECTIONS registry.
    Each dict contains:
      section_key, section_display_name, section_order, raw_text, has_content
    """
    upper = raw_text.upper()

    # Find the character offset of each known header in the source text
    found: list[tuple[int, int, str]] = []  # (char_offset, section_index, section_key)
    for idx, (key, _display, patterns) in enumerate(_SECTIONS):
        for pat in patterns:
            pos = upper.find(pat)
            if pos != -1:
                found.append((pos, idx, key))
                break  # first matching pattern wins for this section

    # Sort by position in text
    found.sort(key=lambda t: t[0])

    results: list[dict] = []
    for rank, (pos, idx, key) in enumerate(found):
        _display = _SECTIONS[idx][1]
        # Text for this section runs from the header line to the next header (or end)
        end = found[rank + 1][0] if rank + 1 < len(found) else len(raw_text)
        # Skip the header line itself
        chunk = raw_text[pos:end]
        lines = chunk.splitlines()
        # Drop header line(s) that are just the section name
        body_lines = lines[1:] if lines else []
        body = '\n'.join(body_lines).strip()
        has_content = bool(body) and body.upper() not in ('NIL', 'N/A', 'NONE')
        results.append({
            'section_key': key,
            'section_display_name': _display,
            'section_order': idx,  # position in the canonical _SECTIONS registry
            'raw_text': body,
            'has_content': has_content,
        })

    return results


# ─────────────────────────────── translation ─────────────────────────────────

def _translate_section(section_key: str, raw_text: str) -> str:
    """Light-touch translation: cleanup + attribution.

    IMPORTANT: Never invent information not in the source text.
    This is cleanup + attribution only — not NLP or inference.
    """
    stripped = (raw_text or '').strip()
    if not stripped or stripped.upper() in ('NIL', 'N/A', 'NONE'):
        return 'Nothing reported for this section.'

    result = stripped

    # For NEXT_WEBINAR: try to surface the time if pattern-detectable
    if section_key == 'NEXT_WEBINAR':
        time_match = re.search(
            r'\b(\d{4})\s*Z\b',  # e.g. "1400Z"
            stripped,
        )
        date_match = re.search(
            r'\b(\d{1,2}/\d{1,2}/\d{2,4}|\d{4}-\d{2}-\d{2})\b',
            stripped,
        )
        note_parts: list[str] = []
        if time_match:
            note_parts.append(f'time noted: {time_match.group(0)}')
        if date_match:
            note_parts.append(f'date noted: {date_match.group(0)}')
        if note_parts:
            result += f'\n\n[TravelCast note: {", ".join(note_parts)}]'

    result += '\n\nTravelCast translation — generated from FAA ATCSCC source text.'
    return result


# ─────────────────────────────── metadata parsing ────────────────────────────

def _parse_advisory_meta(title: str, raw_text: str, adv_date_str: str = '') -> dict:
    """Extract advisory metadata from title string and raw text.

    adv_date_str: value of the adv_date= URL parameter (MMDDYYYY format).
    Never invents values — sets None when a field cannot be parsed.
    """
    advisory_number: Optional[int] = None
    advisory_date: Optional[str] = None
    event_time: Optional[str] = None

    # advisory_number: look for "ADVZY NNN" or "#NNN" in title
    num_match = re.search(r'ADVZY\s+(\d+)', title, re.IGNORECASE)
    if not num_match:
        num_match = re.search(r'#\s*(\d+)', title)
    if num_match:
        try:
            advisory_number = int(num_match.group(1))
        except ValueError:
            pass

    # advisory_date from URL parameter (MMDDYYYY → YYYY-MM-DD)
    if adv_date_str and re.fullmatch(r'\d{8}', adv_date_str):
        mm = adv_date_str[0:2]
        dd = adv_date_str[2:4]
        yyyy = adv_date_str[4:8]
        advisory_date = f'{yyyy}-{mm}-{dd}'

    # event_time: look for range patterns like "0800Z-2000Z" or "VALID 0800Z-2000Z"
    time_range = re.search(
        r'(?:VALID\s+)?(\d{4}Z)\s*[-–]\s*(\d{4}Z)',
        raw_text,
        re.IGNORECASE,
    )
    if time_range:
        event_time = f'{time_range.group(1)}-{time_range.group(2)}'

    return {
        'advisory_number': advisory_number,
        'advisory_date': advisory_date,
        'event_time': event_time,
        'valid_from_utc': None,
        'valid_until_utc': None,
        'title': title,
    }


# ─────────────────────────────── Supabase writers ────────────────────────────

def _upsert_plan(sb_url: str, sb_key: str, plan: dict) -> Optional[int]:
    """Upsert one row in atcscc_operations_plans. Returns the row id or None."""
    path = f'{sb_url}/rest/v1/atcscc_operations_plans?on_conflict=advisory_number,advisory_date'
    body_bytes = __import__('json').dumps(plan).encode('utf-8')
    req = urllib.request.Request(
        path, data=body_bytes,
        headers=_sb_headers(sb_key, {
            'Prefer': 'resolution=merge-duplicates,return=representation',
        }),
        method='POST',
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = __import__('json').loads(resp.read().decode())
            rows = data if isinstance(data, list) else [data]
            if rows and isinstance(rows[0], dict):
                return rows[0].get('id')
            return None
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors='ignore')
        log('plan_upsert_error', {
            'http_code': e.code,
            'error': body[:400],
            'advisory_number': plan.get('advisory_number'),
        })
        return None
    except Exception as e:
        log('plan_upsert_error', {
            'error': str(e),
            'advisory_number': plan.get('advisory_number'),
        })
        return None


def _upsert_sections(sb_url: str, sb_key: str, plan_id: int,
                     sections: list[dict]) -> None:
    """Replace all section rows for plan_id in atcscc_operations_plan_sections."""
    # Delete existing sections for this plan first
    del_path = f'{sb_url}/rest/v1/atcscc_operations_plan_sections?plan_id=eq.{plan_id}'
    del_req = urllib.request.Request(
        del_path,
        headers=_sb_headers(sb_key),
        method='DELETE',
    )
    try:
        with urllib.request.urlopen(del_req, timeout=30) as resp:
            resp.read()
    except Exception as e:
        log('sections_delete_error', {'plan_id': plan_id, 'error': str(e)})

    if not sections:
        return

    # Attach plan_id to each section
    rows = [{**s, 'plan_id': plan_id} for s in sections]
    try:
        supabase_post(sb_url, sb_key, 'atcscc_operations_plan_sections', rows)
        log('sections_written', {'plan_id': plan_id, 'count': len(rows)})
    except Exception as e:
        log('sections_write_error', {'plan_id': plan_id, 'error': str(e)})


# ─────────────────────────────── URL discovery ───────────────────────────────

def _extract_advisory_urls_from_nas_cache(nas_data: object) -> list[str]:
    """Walk the faa_nas_status JSON, extracting all advisoryUrl values."""
    urls: list[str] = []
    records = nas_data if isinstance(nas_data, list) else []

    for r in records:
        if not isinstance(r, dict):
            continue
        # Top-level
        top_url = r.get('advisoryUrl')
        if top_url:
            urls.append(top_url)
        # Nested in program sub-objects
        for sub_key in ('groundDelay', 'groundStop', 'airportClosure',
                        'arrivalDelay', 'departureDelay', 'freeForm'):
            sub = r.get(sub_key)
            if isinstance(sub, dict):
                sub_url = sub.get('advisoryUrl')
                if sub_url:
                    urls.append(sub_url)

    return urls


def _is_ops_plan_url(url: str) -> bool:
    """Return True if the URL looks like an ATCSCC operations plan advisory."""
    u = url.upper()
    parsed = urllib.parse.urlparse(url)
    qs = urllib.parse.parse_qs(parsed.query)
    fac_id = (qs.get('facId') or qs.get('facid') or qs.get('FACID') or [''])[0].upper()
    title = (qs.get('title') or [''])[0].upper()
    # Ops plan facIds or title keyword
    if fac_id in ('ATCSCC', 'DCC'):
        return True
    if 'OPERATIONS PLAN' in title:
        return True
    return False


def _discover_urls_from_adv_xml(xml_text: str) -> list[str]:
    """Parse adv_str.xml and return advisory URLs referencing ATCSCC/DCC."""
    urls: list[str] = []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as e:
        log('adv_xml_parse_error', str(e))
        return urls

    for el in root.iter():
        for attr in ('link', 'url', 'href', 'URL', 'Link', 'Href'):
            val = el.get(attr, '')
            if val and 'fly.faa.gov' in val and _is_ops_plan_url(val):
                urls.append(val)
        # Also check text of elements that look like URLs
        text = (el.text or '').strip()
        if text.startswith('http') and 'fly.faa.gov' in text and _is_ops_plan_url(text):
            urls.append(text)

    return urls


def _adv_date_from_url(url: str) -> str:
    """Extract adv_date= parameter from advisory URL, or return ''."""
    parsed = urllib.parse.urlparse(url)
    qs = urllib.parse.parse_qs(parsed.query)
    return (qs.get('adv_date') or qs.get('adv_Date') or [''])[0]


def _title_from_url(url: str) -> str:
    """Extract title= parameter from advisory URL, or return ''."""
    parsed = urllib.parse.urlparse(url)
    qs = urllib.parse.parse_qs(parsed.query)
    return urllib.parse.unquote_plus(
        (qs.get('title') or [''])[0]
    )


# ─────────────────────────────── legacy NAS XML (kept) ───────────────────────

def _xml_text(node, *tags: str) -> str:
    """Return stripped text of the first matching tag, or ''."""
    for tag in tags:
        for variant in (tag, tag.upper(), tag.lower()):
            el = node.find(variant)
            if el is not None and el.text:
                return el.text.strip()
    return ''


def _parse_nas_xml(xml_text: str) -> list[dict]:
    """Parse NAS status XML into a list of normalised NOTAM-style advisory dicts."""
    advisories: list[dict] = []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as e:
        log('xml_parse_error', str(e))
        return advisories

    airport_nodes = (
        root.findall('.//Airport')
        or root.findall('.//airport')
        or root.findall('.//ARPT')
    )
    for node in airport_nodes:
        arpt = _xml_text(node, 'ARPT', 'ICAOCode', 'Airport') or node.get('ID', '')
        if arpt:
            advisories.append({
                'airport': arpt.upper(),
                'type': _xml_text(node, 'Type', 'ProgramType', 'DelayType'),
                'reason': _xml_text(node, 'Reason', 'AdvisoryText'),
                'avg_delay': _xml_text(node, 'Avg', 'AvgDelay'),
                'max_delay': _xml_text(node, 'Max', 'MaxDelay'),
            })

    for node in root.findall('.//Advisory') + root.findall('.//Initiative'):
        adv_type = node.get('Type', '') or _xml_text(node, 'Type')
        text = _xml_text(node, 'Advisory_Text', 'Text')
        airport = _xml_text(node, 'Airport')
        advisories.append({
            'airport': airport.upper() if airport else 'SYSTEM',
            'type': adv_type.strip(),
            'reason': text[:200],
            'avg_delay': '',
            'max_delay': '',
        })

    return advisories


# ─────────────────────────────── main ────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description='Pull ATCSCC Operations Plan + NAS advisory data'
    )
    parser.add_argument(
        '--dry-run', action='store_true',
        help='Fetch and parse locally but do not write to Supabase',
    )
    parser.add_argument(
        '--limit', type=int, default=None,
        help='Limit number of advisory HTML pages to fetch',
    )
    parser.add_argument(
        '--url',
        type=str,
        default=None,
        help=(
            'Manually supply an ATCSCC advisory URL to fetch and ingest as an '
            'operations plan. Bypasses the _is_ops_plan_url filter. '
            'Auto-discovery still runs; the manual URL is added to the front of '
            'the ops-plan list so it is processed first.'
        ),
    )
    args = parser.parse_args()

    load_env()

    sb_url: Optional[str] = None
    sb_key: Optional[str] = None
    try:
        sb_url, sb_key = get_supabase_creds()
    except RuntimeError as e:
        log('supabase_config_error', str(e))
        if not args.dry_run:
            sys.exit(1)

    # ── Phase 1: Discover advisory URLs ──────────────────────────────────

    all_advisory_urls: list[str] = []
    ops_plan_urls: list[str] = []

    # 1a. Load cached NAS status
    nas_data = load_raw('faa_nas_status')
    if nas_data:
        extracted = _extract_advisory_urls_from_nas_cache(nas_data)
        log('advisory_urls_from_nas_cache', {
            'count': len(extracted),
            'urls': extracted,
        })
        all_advisory_urls.extend(extracted)
    else:
        log('nas_cache_missing', {
            'note': 'data/raw/faa_nas_status.json not found — run pull_faa_nas_status.py first',
        })

    # 1b. Fetch adv_str.xml to find additional ATCSCC URLs
    try:
        adv_xml = http_get_text(ATCSCC_ADV_XML_URL, timeout=30)
        log('adv_xml_fetched', {'url': ATCSCC_ADV_XML_URL, 'bytes': len(adv_xml)})
        xml_urls = _discover_urls_from_adv_xml(adv_xml)
        if xml_urls:
            log('adv_xml_urls_found', {'count': len(xml_urls), 'urls': xml_urls})
        all_advisory_urls.extend(xml_urls)
    except Exception as e:
        log('adv_xml_fetch_error', {'url': ATCSCC_ADV_XML_URL, 'error': str(e)})
        adv_xml = ''

    # Deduplicate, split ops-plan vs. other
    seen: set[str] = set()
    for url in all_advisory_urls:
        if url in seen:
            continue
        seen.add(url)
        if _is_ops_plan_url(url):
            ops_plan_urls.append(url)

    log('advisory_urls_found', {
        'total_unique': len(seen),
        'ops_plan_urls': len(ops_plan_urls),
        'ops_plan_url_list': ops_plan_urls,
    })

    # ── Manual URL injection (--url flag) ─────────────────────────────────
    if args.url:
        manual = args.url.strip()
        log('manual_url_provided', {'url': manual})
        if manual not in ops_plan_urls:
            ops_plan_urls.insert(0, manual)
            log('manual_url_added', {
                'url': manual,
                'total_ops_plan_urls': len(ops_plan_urls),
            })
        else:
            log('manual_url_already_discovered', {'url': manual})

    # ── Phase 2–5: Fetch, extract, parse, translate each ops-plan URL ────

    fetch_errors = 0
    parse_errors = 0
    plans_attempted = 0
    all_plan_raw: list[dict] = []

    # Apply --limit
    urls_to_fetch = ops_plan_urls
    if args.limit is not None:
        urls_to_fetch = ops_plan_urls[: args.limit]

    for url in urls_to_fetch:
        plans_attempted += 1

        # ── Phase 2: Fetch HTML ──────────────────────────────────────────
        try:
            html_src = http_get_text(url, timeout=30)
            log('advisory_text_fetched', {
                'url': url,
                'text_length': len(html_src),
            })
        except Exception as e:
            log('advisory_fetch_error', {'url': url, 'error': str(e)})
            fetch_errors += 1
            continue

        # ── Phase 2b: Extract text from HTML ────────────────────────────
        try:
            plain_text = _extract_text_from_html(html_src)
        except Exception as e:
            log('html_extract_error', {'url': url, 'error': str(e)})
            parse_errors += 1
            plain_text = ''

        # ── Phase 3: Parse sections ──────────────────────────────────────
        try:
            sections = _parse_sections(plain_text)
        except Exception as e:
            log('sections_parse_error', {'url': url, 'error': str(e)})
            parse_errors += 1
            sections = []

        # ── Phase 4: Translate ───────────────────────────────────────────
        for sec in sections:
            try:
                sec['translation'] = _translate_section(
                    sec['section_key'], sec['raw_text']
                )
            except Exception as e:
                log('translate_error', {
                    'url': url,
                    'section': sec.get('section_key'),
                    'error': str(e),
                })
                sec['translation'] = sec.get('raw_text', '')

        # ── Phase 5: Parse metadata ──────────────────────────────────────
        title = _title_from_url(url)
        adv_date_str = _adv_date_from_url(url)
        try:
            meta = _parse_advisory_meta(title, plain_text, adv_date_str)
        except Exception as e:
            log('meta_parse_error', {'url': url, 'error': str(e)})
            parse_errors += 1
            meta = {
                'advisory_number': None,
                'advisory_date': None,
                'event_time': None,
                'valid_from_utc': None,
                'valid_until_utc': None,
                'title': title,
            }

        plan_record = {
            'source_url': url,
            'retrieved_at': utc_now(),
            'plain_text': plain_text,
            'sections': sections,
            **meta,
        }
        all_plan_raw.append(plan_record)

        # Dry-run: print sample
        if args.dry_run:
            preview = plain_text[:500].replace('\n', ' ')
            log('advisory_dry_run', {
                'url': url,
                'title': title,
                'advisory_number': meta.get('advisory_number'),
                'advisory_date': meta.get('advisory_date'),
                'event_time': meta.get('event_time'),
                'sections_found': [s['section_key'] for s in sections],
                'text_preview': preview,
            })
            for sec in sections:
                log('section_dry_run', {
                    'key': sec['section_key'],
                    'display': sec['section_display_name'],
                    'has_content': sec['has_content'],
                    'raw_text_preview': sec['raw_text'][:200],
                })

        # ── Phase 6: Upsert to Supabase ─────────────────────────────────
        if not args.dry_run and sb_url and sb_key:
            plan_row = {
                'source_url': url,
                'advisory_number': meta.get('advisory_number'),
                'advisory_date': meta.get('advisory_date'),
                'title': meta.get('title', ''),
                'event_time': meta.get('event_time'),
                'valid_from_utc': meta.get('valid_from_utc'),
                'valid_until_utc': meta.get('valid_until_utc'),
                'raw_text': plain_text,
                'fetched_at_utc': utc_now(),
                'source_system_id': 'atcscc_advisories',
                'parse_status': 'ok' if sections else 'no_sections',
            }
            plan_id = _upsert_plan(sb_url, sb_key, plan_row)
            if plan_id is not None:
                _upsert_sections(sb_url, sb_key, plan_id, sections)
                log('plan_stored', {
                    'plan_id': plan_id,
                    'advisory_number': meta.get('advisory_number'),
                    'sections': len(sections),
                })
            else:
                log('plan_store_failed', {
                    'advisory_number': meta.get('advisory_number'),
                    'url': url,
                })

    # ── Save combined raw output ──────────────────────────────────────────

    raw_output = {
        'retrieved_at': utc_now(),
        'plans_attempted': plans_attempted,
        'fetch_errors': fetch_errors,
        'parse_errors': parse_errors,
        'ops_plan_urls': ops_plan_urls,
        'plans': all_plan_raw,
    }
    save_raw('atcscc_ops_plan_raw', raw_output)
    log('ops_plan_raw_saved', {
        'file': 'data/raw/atcscc_ops_plan_raw.json',
        'plans': len(all_plan_raw),
    })

    # ── No ops-plan URLs found — record graceful non-failure ─────────────

    if not ops_plan_urls:
        log('ops_plan_not_found', {
            'note': (
                'No ATCSCC operations plan advisory URLs were found in the NAS cache or adv_str.xml. '
                'This may be normal outside of major traffic management events. '
                'NOTAM-style advisory data is still being written via pull_atcscc_ops_plan.py '
                'NAS XML path below.'
            ),
        })

    # ── Preserve existing NAS XML NOTAM-style advisory behaviour ─────────

    xml_text_nas: str = ''
    nas_fetch_error: Optional[str] = None
    source_used_nas: str = ''

    try:
        xml_text_nas = http_get_text(NAS_STATUS_URL, timeout=30)
        source_used_nas = NAS_STATUS_URL
        log('nas_status_fetched', {
            'source': source_used_nas,
            'bytes': len(xml_text_nas),
        })
    except Exception as e:
        nas_fetch_error = str(e)
        log('nas_status_error', {
            'url': NAS_STATUS_URL,
            'error': nas_fetch_error,
        })

    # Fallback to adv_str.xml text (already fetched above) if NAS XML failed
    if (not xml_text_nas.strip() or '<' not in xml_text_nas) and adv_xml:
        xml_text_nas = adv_xml
        source_used_nas = ATCSCC_ADV_XML_URL
        nas_fetch_error = None
        log('nas_xml_fallback', {'source': source_used_nas})
    elif not xml_text_nas.strip() or '<' not in xml_text_nas:
        # Try fetching adv_str.xml again if not already available
        try:
            xml_text_nas = http_get_text(ATCSCC_ADV_XML_URL, timeout=30)
            source_used_nas = ATCSCC_ADV_XML_URL
            nas_fetch_error = None
            log('atcscc_adv_fetched', {
                'source': source_used_nas,
                'bytes': len(xml_text_nas),
            })
        except Exception as e:
            log('atcscc_adv_error', {
                'url': ATCSCC_ADV_XML_URL,
                'error': str(e),
            })
            if not nas_fetch_error:
                nas_fetch_error = str(e)

    # Save raw NAS XML
    raw_xml_path = ROOT / 'data' / 'raw' / 'atcscc_raw.xml'
    raw_xml_path.parent.mkdir(parents=True, exist_ok=True)
    if xml_text_nas:
        raw_xml_path.write_text(xml_text_nas, encoding='utf-8')
        log('raw_xml_saved', {'file': 'data/raw/atcscc_raw.xml'})

    # Parse NOTAM-style advisories
    notam_advisories: list[dict] = []
    if xml_text_nas and '<' in xml_text_nas:
        notam_advisories = _parse_nas_xml(xml_text_nas)
        log('advisories_parsed', {'count': len(notam_advisories)})
    else:
        log('no_xml_to_parse', 'Both NAS sources returned no XML — check connectivity')

    # Save normalised NOTAM cache
    notam_output = {
        'retrieved_at': utc_now(),
        'source': source_used_nas,
        'advisory_count': len(notam_advisories),
        'advisories': notam_advisories,
    }
    save_raw('atcscc_advisories', notam_output)
    log('advisories_cached', {
        'file': 'data/raw/atcscc_advisories.json',
        'count': len(notam_advisories),
    })

    if args.dry_run:
        for adv in notam_advisories[:10]:
            log('advisory_dry_run', adv)

    # ── Final summary + feed_run ──────────────────────────────────────────

    log('pull_summary', {
        'plans_found': len(all_plan_raw),
        'sections_parsed': sum(len(p.get('sections', [])) for p in all_plan_raw),
        'fetch_errors': fetch_errors,
        'parse_errors': parse_errors,
        'notam_advisories': len(notam_advisories),
        'dry_run': args.dry_run,
    })

    overall_success = fetch_errors == 0 and (
        plans_attempted > 0 or len(notam_advisories) > 0
    )
    parse_status = (
        'no_plan_found' if not ops_plan_urls
        else ('partial' if fetch_errors > 0 else 'ok')
    )

    write_feed_run(
        sb_url, sb_key, SOURCE_ID,
        success=overall_success,
        records=len(all_plan_raw) + len(notam_advisories),
        error=(
            f'fetch_errors={fetch_errors}, parse_status={parse_status}'
            if (fetch_errors or parse_status != 'ok')
            else None
        ),
        dry_run=args.dry_run,
    )


if __name__ == '__main__':
    main()
