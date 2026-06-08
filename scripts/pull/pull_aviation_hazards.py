#!/usr/bin/env python3
"""Pull aviation hazard products (SIGMETs, AIRMETs, CWAs) from AviationWeather.gov.

Source:  https://aviationweather.gov/api/data/sigmet?format=json
         https://aviationweather.gov/api/data/airmet?format=json
         https://aviationweather.gov/api/data/cwa?format=json
Auth:    None (public API, no key required)
Writes:  data/raw/aviation_hazards_sigmet_raw.json
         data/raw/aviation_hazards_airmet_raw.json
         data/raw/aviation_hazards_cwa_raw.json
         data/raw/aviation_hazards_parsed.json (combined parsed output)
         aviation_hazard_products (Supabase, upserted on hazard_id)
         feed_runs (source_system_id='aviationweather_api')
Doctrine: Aviation Hazards = Aviation Weather Truth (AviationWeather.gov)

Usage:
  python pull_aviation_hazards.py [--dry-run] [--limit N]
"""
from __future__ import annotations
import argparse, datetime, json, re, sys, urllib.error, urllib.request
from datetime import timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from lib_pull import (
    load_env, get_supabase_creds, write_feed_run,
    http_get_json, save_raw, log, ROOT, utc_now,
    _sb_headers,
)

# ─────────────────────────────── constants ───────────────────────────

SIGMET_URL = 'https://aviationweather.gov/api/data/sigmet?format=json'
AIRMET_URL = 'https://aviationweather.gov/api/data/airmet?format=json'
CWA_URL    = 'https://aviationweather.gov/api/data/cwa?format=json'
SOURCE_ID  = 'aviationweather_api'
AWX_HEADERS = {'User-Agent': 'TravelCast-AviatorGraf/1.0 (aviation weather; python urllib)'}

# ─────────────────────────────── focus airports ──────────────────────

# 71 focus airports — IATA codes.
# ICAO variants for domestic = 'K' + IATA.
# Special ICAO codes for non-contiguous airports listed separately.
_FOCUS_IATA: frozenset[str] = frozenset({
    'BOS', 'BDL', 'PVD', 'ORF', 'RIC',
    'IAD', 'DCA', 'BWI', 'PHL',
    'JFK', 'LGA', 'EWR',
    'CLT', 'RDU', 'CHS', 'JAX',
    'TPA', 'PIE', 'MCO', 'MIA', 'FLL', 'PBI',
    'ATL', 'BNA', 'MEM', 'MSY',
    'DTW', 'CLE', 'PIT', 'CVG', 'CMH',
    'MDW', 'ORD', 'MKE', 'MSP',
    'DFW', 'DAL', 'IAH', 'HOU', 'AUS', 'SAT',
    'ABQ', 'OKC', 'TUL',
    'DEN', 'SLC',
    'LAS', 'PHX', 'TUS', 'ELP',
    'SFO', 'OAK', 'SJC', 'SAN', 'LAX', 'BUR', 'LGB', 'ONT', 'SMF',
    'PDX', 'SEA', 'BOI',
    'HNL', 'OGG', 'ANC',
    'SJU',
    'GEG', 'RNO', 'FAT',
})

# Non-K ICAO codes for non-contiguous focus airports.
_SPECIAL_ICAO_TO_IATA: dict[str, str] = {
    'PHNL': 'HNL',
    'PHOG': 'OGG',
    'PANC': 'ANC',
    'TJSJ': 'SJU',
}

# Build frozenset of all ICAO codes (domestic K-prefix + special).
_FOCUS_ICAO: frozenset[str] = frozenset(
    {f'K{iata}' for iata in _FOCUS_IATA
     if iata not in {'HNL', 'OGG', 'ANC', 'SJU'}}
    | set(_SPECIAL_ICAO_TO_IATA.keys())
)

# Pre-compiled regex for word-boundary IATA matching in free text.
_IATA_PATTERN: re.Pattern = re.compile(
    r'\b(' + '|'.join(sorted(_FOCUS_IATA, key=len, reverse=True)) + r')\b'
)
# Regex for ICAO codes in free text (no word-boundary needed for 4-letter codes).
_ICAO_PATTERN: re.Pattern = re.compile(
    r'\b(' + '|'.join(sorted(_FOCUS_ICAO, key=len, reverse=True)) + r')\b'
)

# Reverse map: ICAO → IATA for domestic K-prefix airports.
def _icao_to_iata(icao: str) -> str:
    if icao in _SPECIAL_ICAO_TO_IATA:
        return _SPECIAL_ICAO_TO_IATA[icao]
    if icao.startswith('K') and len(icao) == 4:
        return icao[1:]
    return icao


# ─────────────────────────────── timestamp helpers ───────────────────

def iso_utc_from_epoch(value: object) -> str | None:
    """Convert any timestamp value to an ISO-8601 UTC string for Supabase.

    Handles:
    - None → None
    - int/float epoch seconds (< 1e11) → "2026-06-08T01:55:00Z"
    - int/float epoch milliseconds (>= 1e11) → converted to seconds first
    - ISO string with T → normalized to Z suffix ("2026-06-08T01:55:00Z")
    - "YYYY-MM-DD HH:MM:SS" string → "2026-06-08T01:55:00Z"
    - Unparseable → None (warning logged via return None)
    """
    if value is None:
        return None
    # Numeric epoch
    if isinstance(value, (int, float)):
        try:
            epoch_s = float(value)
            if epoch_s >= 1e11:  # milliseconds — divide down
                epoch_s /= 1000.0
            dt = datetime.datetime.fromtimestamp(epoch_s, tz=timezone.utc)
            return dt.strftime('%Y-%m-%dT%H:%M:%SZ')
        except (OSError, OverflowError, ValueError):
            return None
    # String handling
    s = str(value).strip()
    if not s:
        return None
    # Already ISO with T separator
    if 'T' in s:
        # Normalize +00:00 and .000Z variants → plain Z
        s = s.replace('+00:00', 'Z').replace('+0000', 'Z')
        if s.endswith('.000Z'):
            s = s[:-5] + 'Z'
        elif '.' in s and s.endswith('Z'):
            s = s[:s.index('.')] + 'Z'
        if not s.endswith('Z'):
            s += 'Z'
        return s
    # "YYYY-MM-DD HH:MM:SS" or "YYYY-MM-DD HH:MM:SS.ffffff"
    if ' ' in s and len(s) >= 19:
        try:
            s_clean = s[:19]  # drop microseconds
            dt = datetime.datetime.strptime(s_clean, '%Y-%m-%d %H:%M:%S')
            return dt.strftime('%Y-%m-%dT%H:%M:%SZ')
        except ValueError:
            pass
    # Plain date "YYYY-MM-DD"
    if len(s) == 10 and s[4] == '-':
        return s + 'T00:00:00Z'
    return None


# ─────────────────────────────── parsing ─────────────────────────────

def parse_sigmet(raw: dict) -> dict | None:
    """Parse a SIGMET record from https://aviationweather.gov/api/data/sigmet?format=json.

    Returns None if both hazard_id and raw_text are empty, or on any exception.
    """
    try:
        # Composite key: icaoId + seriesId (e.g. KKCI-91E)
        icao_id   = raw.get('icaoId', '')
        series_id = raw.get('seriesId', '')
        hazard_id = f'{icao_id}-{series_id}' if icao_id or series_id else ''
        raw_text  = raw.get('rawAirSigmet') or raw.get('rawSigmet', '')
        if not hazard_id and not raw_text:
            return None

        geom = raw.get('coords', '') or raw.get('geom', '')
        geometry_geojson = {'type': 'raw_coords', 'coords': geom} if geom else None

        return {
            'hazard_id':              hazard_id,
            'hazard_type':            'SIGMET',
            'subtype':                raw.get('hazard', ''),
            'raw_text':               raw_text,
            'begins_at_utc':          iso_utc_from_epoch(raw.get('validTimeFrom')),
            'ends_at_utc':            iso_utc_from_epoch(raw.get('validTimeTo')),
            'issued_at_utc':          iso_utc_from_epoch(raw.get('creationTime')),
            'altitude_top_ft':        raw.get('altitudeHi1'),
            'altitude_bottom_ft':     raw.get('altitudeLow1'),
            'movement_from_degrees':  raw.get('movementDir'),
            'movement_speed_kt':      raw.get('movementSpd'),
            'geometry_geojson':       geometry_geojson,
            'source_system_id':       SOURCE_ID,
            'fetched_at_utc':         utc_now(),
            'parse_status':           'ok',
        }
    except Exception as e:
        log('sigmet_parse_exception', str(e))
        return None


def parse_airmet(raw: dict) -> dict | None:
    """Parse an AIRMET record from https://aviationweather.gov/api/data/airmet?format=json.

    The airmet endpoint returns region/time/type summary only — no raw text or explicit id.
    Builds a synthetic hazard_id from region + hazard + validTimeFrom.
    """
    try:
        region    = raw.get('region', '')
        hazard    = (raw.get('hazard') or '').replace('-', '_').upper()
        valid_from_raw = raw.get('validTimeFrom', '')
        # Synthetic id: region+hazard+validtime is unique per product window
        hazard_id = f'AIRMET-{region}-{hazard}-{valid_from_raw}' if region or hazard else ''
        if not hazard_id:
            return None

        begins_iso = iso_utc_from_epoch(raw.get('validTimeFrom'))
        ends_iso   = iso_utc_from_epoch(raw.get('validTimeTo'))
        issued_iso = iso_utc_from_epoch(raw.get('receiptTime'))

        # Build synthetic raw text with readable ISO times
        raw_text = (
            f"AIRMET {hazard} FOR REGION {region}"
            f" VALID {begins_iso or valid_from_raw} TO {ends_iso or raw.get('validTimeTo','')}."
            f" Receipt time: {issued_iso or raw.get('receiptTime', '')}."
        )

        return {
            'hazard_id':              hazard_id,
            'hazard_type':            'AIRMET',
            'subtype':                hazard,
            'raw_text':               raw_text,
            'begins_at_utc':          begins_iso,
            'ends_at_utc':            ends_iso,
            'issued_at_utc':          issued_iso,
            'altitude_top_ft':        None,
            'altitude_bottom_ft':     None,
            'movement_from_degrees':  None,
            'movement_speed_kt':      None,
            'geometry_geojson':       None,
            'source_system_id':       SOURCE_ID,
            'fetched_at_utc':         utc_now(),
            'parse_status':           'ok',
        }
    except Exception as e:
        log('airmet_parse_exception', str(e))
        return None


def parse_cwa(raw: dict) -> dict | None:
    """Parse a Center Weather Advisory record from the AviationWeather.gov API.

    CWA response fields: cwsu, name, receiptTime, validTimeFrom, validTimeTo,
    seriesId, hazard, qualifier, base, top, geom, coords, rawText.
    Returns None on any exception or if no usable identifier exists.
    """
    try:
        cwsu      = raw.get('cwsu', '')
        series_id = raw.get('seriesId', '')
        hazard_id = f'{cwsu}-{series_id}' if cwsu or series_id else ''
        raw_text  = raw.get('rawText', '') or raw.get('rawCwa', '')

        coords = raw.get('coords')
        geometry_geojson = {'type': 'polygon', 'coords': coords} if coords else None

        return {
            'hazard_id':              hazard_id,
            'hazard_type':            'CWA',
            'subtype':                raw.get('hazard', ''),
            'raw_text':               raw_text,
            'begins_at_utc':          iso_utc_from_epoch(raw.get('validTimeFrom')),
            'ends_at_utc':            iso_utc_from_epoch(raw.get('validTimeTo')),
            'issued_at_utc':          iso_utc_from_epoch(raw.get('receiptTime')),
            'altitude_top_ft':        raw.get('top'),
            'altitude_bottom_ft':     raw.get('base'),
            'movement_from_degrees':  None,
            'movement_speed_kt':      None,
            'geometry_geojson':       geometry_geojson,
            'source_system_id':       SOURCE_ID,
            'fetched_at_utc':         utc_now(),
            'parse_status':           'ok',
        }
    except Exception as e:
        log('cwa_parse_exception', str(e))
        return None


# ─────────────────────────────── airport matching ────────────────────

def match_airports(raw_text: str) -> list[str]:
    """Return deduplicated sorted list of focus IATA codes mentioned in raw_text.

    Checks for IATA codes (word-boundary) and ICAO codes (4-letter).
    Capped at 20 matches.
    """
    found: set[str] = set()
    if not raw_text:
        return []

    for m in _IATA_PATTERN.finditer(raw_text):
        found.add(m.group(1))
        if len(found) >= 20:
            break

    if len(found) < 20:
        for m in _ICAO_PATTERN.finditer(raw_text):
            iata = _icao_to_iata(m.group(1))
            if iata in _FOCUS_IATA:
                found.add(iata)
            if len(found) >= 20:
                break

    return sorted(found)[:20]


# ─────────────────────────────── translation ─────────────────────────

def _extract_token_after(text: str, keyword: str) -> str:
    """Return the first non-whitespace token that follows keyword in text, or ''."""
    idx = text.find(keyword)
    if idx == -1:
        return ''
    rest = text[idx + len(keyword):].lstrip()
    token = re.split(r'\s', rest, maxsplit=1)[0]
    return token.strip(' .,;') if token else ''


def _extract_tops_fl(raw_text: str, altitude_top_ft: object) -> tuple[str, str]:
    """Return (qualifier, fl_string) for the tops altitude, or ('', '').

    qualifier: 'to' or 'above' (derived from raw text when present)
    fl_string: 'FLxxx' formatted string, or ''

    Priority order:
    1. Structured altitude_top_ft field (already parsed from source by parser)
    2. Raw text pattern: TOPS [TO|ABV|ABOVE] FLxxx or TOPS FLxxx
    Never invents values — returns ('', '') when nothing is available.
    """
    qualifier = 'above' if re.search(
        r'\bTOPS\s+(?:ABV|ABOVE)\b', raw_text, re.IGNORECASE
    ) else 'to'

    # Prefer the structured altitude field
    if altitude_top_ft is not None:
        try:
            fl = round(int(altitude_top_ft) / 100)
            return qualifier, f'FL{fl:03d}'
        except (TypeError, ValueError):
            pass

    # Fall back to raw text: TOPS [TO|ABV] FL350 or TOPS 35000
    m = re.search(
        r'\bTOPS\s+(?:(?:TO|ABV|ABOVE)\s+)?(FL(\d{2,3})|\b(\d{3,5})\b)',
        raw_text,
        re.IGNORECASE,
    )
    if m:
        val = m.group(1)
        if val.upper().startswith('FL'):
            return qualifier, val.upper()
        try:
            fl = round(int(val) / 100)
            return qualifier, f'FL{fl:03d}'
        except ValueError:
            pass

    return '', ''


def _fmt_ends(ends_at: object) -> str:
    """Format ends_at_utc for display. Returns HHMMz string or 'unknown'."""
    if not ends_at:
        return 'unknown'
    # Unix epoch integer or float (fallback — normally already converted to ISO)
    if isinstance(ends_at, (int, float)):
        try:
            epoch_s = float(ends_at)
            if epoch_s >= 1e11:
                epoch_s /= 1000.0
            dt = datetime.datetime.fromtimestamp(epoch_s, tz=timezone.utc)
            return dt.strftime('%H%Mz')
        except (OSError, OverflowError, ValueError):
            return str(ends_at)
    s = str(ends_at)
    if 'T' in s:
        try:
            time_part = s.split('T')[1][:5].replace(':', '')
            return f'{time_part}z'
        except (IndexError, AttributeError):
            pass
    return s


def translate_hazard(h: dict) -> str:
    """Generate a plain-language 2–3 sentence summary from parsed hazard fields.

    Extracts only information actually present in the source record.
    Never adds invented data.
    Always appends source attribution.
    """
    suffix = (
        ' Source: AviationWeather.gov.'
        ' TravelCast translation — generated from AviationWeather.gov source text.'
    )
    raw_text   = (h.get('raw_text') or '').upper()
    hazard_id  = h.get('hazard_id', '')
    hazard_type = h.get('hazard_type', '')
    subtype     = (h.get('subtype') or '').upper()
    ends_fmt    = _fmt_ends(h.get('ends_at_utc'))

    if not raw_text:
        return f'No raw text available.{suffix}'

    # Collect optional detail tokens from raw text.
    detail_parts: list[str] = []

    tops_qual, tops_fl = _extract_tops_fl(raw_text, h.get('altitude_top_ft'))
    if tops_fl:
        detail_parts.append(f'Tops {tops_qual} {tops_fl}')

    hail = _extract_token_after(raw_text, 'HAIL TO')
    if hail:
        detail_parts.append(f'Hail to {hail}')

    wind_m = re.search(r'WIND GUSTS? TO ([\d]+\s*KT)', raw_text)
    if wind_m:
        detail_parts.append(f'Wind gusts to {wind_m.group(1).strip()}')

    mov_m = re.search(r'MOV(?:\s+FROM)?\s+([\w]+(?:\s+\d+\s*KT)?)', raw_text)
    if mov_m:
        detail_parts.append(f'Moving {mov_m.group(1).strip()}')

    detail_str = '. '.join(detail_parts) + '.' if detail_parts else ''

    try:
        if hazard_type == 'SIGMET':
            if 'CONV' in subtype or 'CONVECTIVE' in raw_text[:30]:
                line1 = (
                    f'Convective SIGMET {hazard_id} is active through {ends_fmt}.'
                )
            else:
                line1 = (
                    f'{subtype or "SIGMET"} SIGMET {hazard_id}'
                    f' is active through {ends_fmt}.'
                )
            impact = 'TravelCast impact: monitor flights in the affected area.'
            parts = [p for p in [line1, detail_str, impact] if p]
            return ' '.join(parts) + suffix

        if hazard_type == 'AIRMET':
            line1 = (
                f'{subtype or "AIRMET"} AIRMET is active through {ends_fmt}.'
            )
            parts = [p for p in [line1, detail_str] if p]
            return ' '.join(parts) + suffix

        if hazard_type == 'CWA':
            return (
                f'Center Weather Advisory {hazard_id} is active through {ends_fmt}.'
                f'{suffix}'
            )

        return f'See raw advisory text.{suffix}'

    except Exception:
        return f'See raw advisory text.{suffix}'


# ─────────────────────────────── Supabase upsert ─────────────────────

_UPSERT_BATCH = 50


def upsert_hazards(sb_url: str, sb_key: str, hazards: list[dict]) -> int:
    """Upsert aviation_hazard_products rows via Supabase REST PostgREST.

    Uses on_conflict=hazard_id for idempotent upserts.
    Posts in batches of 50. Returns total records written.
    """
    path = f'{sb_url}/rest/v1/aviation_hazard_products?on_conflict=hazard_id'
    prefer = 'resolution=merge-duplicates,return=minimal'
    headers = _sb_headers(sb_key, {'Prefer': prefer})
    total_written = 0

    for i in range(0, len(hazards), _UPSERT_BATCH):
        batch = hazards[i:i + _UPSERT_BATCH]
        body = json.dumps(batch, default=str).encode('utf-8')
        req = urllib.request.Request(path, data=body, headers=headers, method='POST')
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                resp.read()
            total_written += len(batch)
            log('hazards_batch_written', {
                'batch_start': i,
                'batch_size': len(batch),
                'total_so_far': total_written,
            })
        except urllib.error.HTTPError as e:
            err_body = e.read().decode(errors='ignore')
            log('hazards_batch_error', {
                'batch_start': i,
                'http_status': e.code,
                'detail': err_body[:400],
            })
        except Exception as e:
            log('hazards_batch_error', {'batch_start': i, 'error': str(e)})

    return total_written


# ─────────────────────────────── main ────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description='Pull aviation hazard products from AviationWeather.gov'
    )
    parser.add_argument('--dry-run', action='store_true',
                        help='Fetch and cache locally but do not write to Supabase')
    parser.add_argument('--limit', type=int, default=None,
                        help='Limit total number of parsed hazard records processed')
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

    fetch_errors = 0
    parse_errors = 0

    # ── Fetch SIGMETs ─────────────────────────────────────────────────
    sigmet_raw: list[dict] = []
    try:
        data = http_get_json(SIGMET_URL, headers=AWX_HEADERS)
        if isinstance(data, list):
            sigmet_raw = data
        elif isinstance(data, dict):
            sigmet_raw = data.get('features') or data.get('items') or []
        log('sigmet_fetched', {'url': SIGMET_URL, 'count': len(sigmet_raw)})
    except Exception as e:
        fetch_errors += 1
        log('sigmet_fetch_error', {'url': SIGMET_URL, 'error': str(e)})

    save_raw('aviation_hazards_sigmet_raw', sigmet_raw)
    log('raw_saved', {'file': 'data/raw/aviation_hazards_sigmet_raw.json'})

    # ── Fetch AIRMETs ─────────────────────────────────────────────────
    airmet_raw: list[dict] = []
    try:
        data = http_get_json(AIRMET_URL, headers=AWX_HEADERS)
        if isinstance(data, list):
            airmet_raw = data
        elif isinstance(data, dict):
            airmet_raw = data.get('features') or data.get('items') or []
        log('airmet_fetched', {'url': AIRMET_URL, 'count': len(airmet_raw)})
    except Exception as e:
        fetch_errors += 1
        log('airmet_fetch_error', {'url': AIRMET_URL, 'error': str(e)})

    save_raw('aviation_hazards_airmet_raw', airmet_raw)
    log('raw_saved', {'file': 'data/raw/aviation_hazards_airmet_raw.json'})

    # ── Fetch CWAs ────────────────────────────────────────────────────
    cwa_raw: list[dict] = []
    try:
        data = http_get_json(CWA_URL, headers=AWX_HEADERS)
        if isinstance(data, list):
            cwa_raw = data
        elif isinstance(data, dict):
            cwa_raw = data.get('features') or data.get('items') or []
        log('cwa_fetched', {'url': CWA_URL, 'count': len(cwa_raw)})
    except Exception as e:
        fetch_errors += 1
        log('cwa_fetch_error', {'url': CWA_URL, 'error': str(e)})

    save_raw('aviation_hazards_cwa_raw', cwa_raw)
    log('raw_saved', {'file': 'data/raw/aviation_hazards_cwa_raw.json'})

    # ── Parse ─────────────────────────────────────────────────────────
    sigmet_count = 0
    airmet_count = 0
    cwa_count    = 0
    parsed: list[dict] = []

    for r in sigmet_raw:
        try:
            rec = parse_sigmet(r)
            if rec is None:
                parse_errors += 1
                continue
            sigmet_count += 1
            parsed.append(rec)
        except Exception as e:
            parse_errors += 1
            log('sigmet_record_error', {
                'id': f"{r.get('icaoId','')}-{r.get('seriesId','')}", 'error': str(e)
            })

    for r in airmet_raw:
        try:
            rec = parse_airmet(r)
            if rec is None:
                parse_errors += 1
                continue
            airmet_count += 1
            parsed.append(rec)
        except Exception as e:
            parse_errors += 1
            log('airmet_record_error', {
                'id': f"{r.get('region','')}-{r.get('hazard','')}", 'error': str(e)
            })

    for r in cwa_raw:
        try:
            rec = parse_cwa(r)
            if rec is None:
                parse_errors += 1
                continue
            cwa_count += 1
            parsed.append(rec)
        except Exception as e:
            parse_errors += 1
            log('cwa_record_error', {'id': r.get('cwaId', '?'), 'error': str(e)})

    log('parse_complete', {
        'sigmet_count': sigmet_count,
        'airmet_count': airmet_count,
        'cwa_count': cwa_count,
        'parse_errors': parse_errors,
    })

    # Apply --limit before enrichment / upsert.
    if args.limit and len(parsed) > args.limit:
        log('limit_applied', {'original': len(parsed), 'limit': args.limit})
        parsed = parsed[:args.limit]

    # ── Enrich: airport matching + translation ────────────────────────
    for rec in parsed:
        try:
            rec['affected_airports'] = match_airports(rec.get('raw_text') or '')
        except Exception as e:
            rec['affected_airports'] = []
            log('match_airports_error', {'hazard_id': rec.get('hazard_id'), 'error': str(e)})

        try:
            rec['translation'] = translate_hazard(rec)
        except Exception as e:
            rec['translation'] = (
                'See raw advisory text.'
                ' TravelCast translation — generated from AviationWeather.gov source text.'
            )
            log('translate_error', {'hazard_id': rec.get('hazard_id'), 'error': str(e)})

    # Deduplicate by hazard_id — keep first occurrence.
    # Within-batch duplicate hazard_ids cause PostgreSQL ON CONFLICT to error.
    # AIRMET synthetic IDs (region+hazard+validTimeFrom) can collide when the same
    # product has multiple altitude layers; we keep one record per unique ID.
    seen_ids: set[str] = set()
    deduped: list[dict] = []
    for rec in parsed:
        hid = rec.get('hazard_id') or ''
        if hid not in seen_ids:
            seen_ids.add(hid)
            deduped.append(rec)
        else:
            log('hazard_id_deduped', {'hazard_id': hid, 'action': 'skipped_duplicate'})
    if len(deduped) < len(parsed):
        log('dedup_complete', {'original': len(parsed), 'after_dedup': len(deduped)})
    parsed = deduped

    # Save combined parsed output.
    save_raw('aviation_hazards_parsed', parsed)
    log('parsed_saved', {
        'file': 'data/raw/aviation_hazards_parsed.json',
        'total': len(parsed),
    })

    # ── Dry-run preview ───────────────────────────────────────────────
    if args.dry_run:
        for rec in parsed[:5]:
            log('hazard_dry_run', {
                'hazard_id':   rec.get('hazard_id'),
                'type':        rec.get('hazard_type'),
                'subtype':     rec.get('subtype'),
                'ends_at':     rec.get('ends_at_utc'),
                'airports':    rec.get('affected_airports'),
                'summary':     (rec.get('translation') or '')[:120],
            })

    # ── Upsert to Supabase ────────────────────────────────────────────
    total_written = 0
    write_error: str | None = None
    if not args.dry_run and sb_url and sb_key and parsed:
        try:
            total_written = upsert_hazards(sb_url, sb_key, parsed)
            log('hazards_written', {'total': total_written})
        except Exception as e:
            write_error = str(e)
            log('hazards_write_error', write_error)
    elif args.dry_run:
        log('upsert_skipped', {'reason': 'dry_run', 'would_write': len(parsed)})

    log('pull_summary', {
        'sigmet_count':   sigmet_count,
        'airmet_count':   airmet_count,
        'cwa_count':      cwa_count,
        'total_parsed':   len(parsed),
        'total_written':  total_written,
        'fetch_errors':   fetch_errors,
        'parse_errors':   parse_errors,
        'dry_run':        args.dry_run,
    })

    write_feed_run(
        sb_url, sb_key, SOURCE_ID,
        success=fetch_errors == 0 and write_error is None,
        records=sigmet_count + airmet_count + cwa_count,
        error=write_error,
        dry_run=args.dry_run,
    )


if __name__ == '__main__':
    main()
