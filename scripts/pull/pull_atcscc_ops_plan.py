#!/usr/bin/env python3
"""Pull ATCSCC advisory / NAS status data and cache raw data locally.

Sources (tried in order):
  1. https://nasstatus.faa.gov/api/airport-status-information  (XML — full NAS status)
  2. https://www.fly.faa.gov/adv/adv_str.xml  (XML — structured advisory list)
Auth:    None (public APIs, no key required)
Writes:  data/raw/atcscc_advisories.json  (normalised advisory list)
         data/raw/atcscc_raw.xml          (raw XML from primary source)
         feed_runs (source_system_id='atcscc_advisories')
Doctrine: ATCSCC / FAA NAS = Current Operational Impact (operational truth)

Usage:
  python pull_atcscc_ops_plan.py [--dry-run]
"""
from __future__ import annotations
import argparse, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from lib_pull import (
    load_env, get_supabase_creds,
    write_feed_run, http_get_text, save_raw, log, ROOT, utc_now,
)

NAS_STATUS_URL  = 'https://nasstatus.faa.gov/api/airport-status-information'
ATCSCC_ADV_URL  = 'https://www.fly.faa.gov/adv/adv_str.xml'
SOURCE_ID       = 'atcscc_advisories'


def _xml_text(node, *tags: str) -> str:
    """Return the stripped text of the first matching tag in node, or ''.

    Tries each tag variant (original, upper, lower) with explicit is-not-None
    checks to avoid the ElementTree DeprecationWarning from truth-value testing.
    """
    for tag in tags:
        for variant in (tag, tag.upper(), tag.lower()):
            el = node.find(variant)
            if el is not None and el.text:
                return el.text.strip()
    return ''


def _parse_nas_xml(xml_text: str) -> list[dict]:
    """Parse NAS status XML into a list of normalised advisory dicts."""
    import xml.etree.ElementTree as ET
    advisories: list[dict] = []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as e:
        log('xml_parse_error', str(e))
        return advisories

    # Try multiple known element paths used by FAA NAS status XML schemas.
    # The exact schema varies across FAA system versions.
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

    # Also check for Initiative / Advisory elements (ATCSCC advisory list format)
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


def main() -> None:
    parser = argparse.ArgumentParser(description='Pull ATCSCC advisory and NAS status data')
    parser.add_argument('--dry-run', action='store_true',
                        help='Fetch and cache locally but do not write feed_runs to Supabase')
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

    xml_text: str = ''
    source_used: str = ''
    fetch_error: str | None = None

    # Try primary source
    try:
        xml_text = http_get_text(NAS_STATUS_URL)
        source_used = NAS_STATUS_URL
        log('nas_status_fetched', {'source': source_used, 'bytes': len(xml_text)})
    except Exception as e:
        log('nas_status_error', {'url': NAS_STATUS_URL, 'error': str(e)})
        fetch_error = str(e)

    # Fallback to ATCSCC advisory XML if primary failed or returned empty
    if not xml_text.strip() or '<' not in xml_text:
        try:
            xml_text = http_get_text(ATCSCC_ADV_URL)
            source_used = ATCSCC_ADV_URL
            fetch_error = None
            log('atcscc_adv_fetched', {'source': source_used, 'bytes': len(xml_text)})
        except Exception as e:
            log('atcscc_adv_error', {'url': ATCSCC_ADV_URL, 'error': str(e)})
            if not fetch_error:
                fetch_error = str(e)

    # Save raw XML
    raw_xml_path = (ROOT / 'data' / 'raw' / 'atcscc_raw.xml')
    raw_xml_path.parent.mkdir(parents=True, exist_ok=True)
    if xml_text:
        raw_xml_path.write_text(xml_text, encoding='utf-8')
        log('raw_xml_saved', {'file': 'data/raw/atcscc_raw.xml'})

    # Parse
    advisories: list[dict] = []
    if xml_text and '<' in xml_text:
        advisories = _parse_nas_xml(xml_text)
        log('advisories_parsed', {'count': len(advisories)})
    else:
        log('no_xml_to_parse', 'Both sources returned no XML — check connectivity')

    # Save normalised cache
    output = {
        'retrieved_at': utc_now(),
        'source': source_used,
        'advisory_count': len(advisories),
        'advisories': advisories,
    }
    save_raw('atcscc_advisories', output)
    log('advisories_cached', {'file': 'data/raw/atcscc_advisories.json', 'count': len(advisories)})

    if args.dry_run:
        for adv in advisories[:10]:
            log('advisory_dry_run', adv)

    write_feed_run(
        sb_url, sb_key, SOURCE_ID,
        success=fetch_error is None and len(advisories) >= 0,
        records=len(advisories),
        error=fetch_error,
        dry_run=args.dry_run,
    )


if __name__ == '__main__':
    main()
