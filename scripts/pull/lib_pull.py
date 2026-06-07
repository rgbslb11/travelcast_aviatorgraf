#!/usr/bin/env python3
"""Shared utilities for TravelCast AviatorGraf pull engine.

Backend use only. Never import from browser / frontend code.
Secrets must come from environment variables or a local .env file —
never hardcoded.
"""
from __future__ import annotations
import json, os, urllib.request, urllib.error, urllib.parse
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = ROOT / 'data' / 'raw'

PULL_USER_AGENT = 'TravelCast-AviatorGraf/1.0 (aviation weather dashboard; python urllib)'


# ─────────────────────────────── time ────────────────────────────────

def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ─────────────────────────────── logging ─────────────────────────────

def log(event: str, data=None) -> None:
    """Print a structured JSON log line to stdout."""
    entry: dict = {'ts': utc_now(), 'event': event}
    if data is not None:
        entry['data'] = data
    print(json.dumps(entry, default=str))


# ─────────────────────────────── env / config ─────────────────────────

def load_env(dotenv_path: Path | None = None) -> None:
    """Load a .env file into os.environ. Does not overwrite existing vars."""
    if dotenv_path is None:
        dotenv_path = ROOT / '.env'
    if not dotenv_path.exists():
        return
    for line in dotenv_path.read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, _, val = line.partition('=')
        key = key.strip()
        val = val.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = val


def get_supabase_creds() -> tuple[str, str]:
    """Return (url, service_role_key) or raise RuntimeError."""
    url = os.environ.get('SUPABASE_URL', '')
    key = os.environ.get('SUPABASE_SERVICE_ROLE_KEY', '')
    if not url or not key:
        raise RuntimeError(
            'SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set in .env or environment'
        )
    placeholders = {'REPLACE_WITH', 'your-project', 'server_side_only', 'example.com'}
    for p in placeholders:
        if p in url or p in key:
            raise RuntimeError(
                f'SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY appear to contain placeholder values ({p!r})'
            )
    return url.rstrip('/'), key


# ─────────────────────────────── Supabase REST ───────────────────────

def _sb_headers(key: str, extra: dict | None = None) -> dict:
    h = {
        'apikey': key,
        'Authorization': f'Bearer {key}',
        'Content-Type': 'application/json',
        'User-Agent': PULL_USER_AGENT,
    }
    if extra:
        h.update(extra)
    return h


def supabase_get(url: str, key: str, table: str, params: dict | None = None) -> list:
    """GET rows from a Supabase table or view via PostgREST."""
    path = f'{url}/rest/v1/{table}'
    if params:
        path += '?' + urllib.parse.urlencode(params)
    req = urllib.request.Request(path, headers=_sb_headers(key))
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors='ignore')
        raise RuntimeError(f'Supabase GET {table} → HTTP {e.code}: {body[:400]}')


def supabase_post(url: str, key: str, table: str, data: list | dict,
                  prefer: str = 'return=minimal') -> None:
    """POST (insert/upsert) rows into a Supabase table via PostgREST."""
    path = f'{url}/rest/v1/{table}'
    body = json.dumps(data).encode('utf-8')
    req = urllib.request.Request(
        path, data=body,
        headers=_sb_headers(key, {'Prefer': prefer}),
        method='POST',
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            resp.read()
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors='ignore')
        raise RuntimeError(f'Supabase POST {table} → HTTP {e.code}: {body[:400]}')


def write_feed_run(
    url: str | None, key: str | None, source_system_id: str,
    success: bool, records: int | None = None,
    error: str | None = None, dry_run: bool = False,
) -> None:
    """Insert one feed_runs row. Dry-run prints the row instead of writing."""
    row = {
        'source_system_id': source_system_id,
        'retrieved_at_utc': utc_now(),
        'live_fetch_success': success,
        'records_retrieved': records,
        'error': str(error)[:500] if error else None,
    }
    if dry_run:
        log('feed_run_dry_run', row)
        return
    if url is None or key is None:
        log('feed_run_skipped', {'reason': 'no supabase creds', 'row': row})
        return
    supabase_post(url, key, 'feed_runs', row)


def get_active_airports(url: str, key: str, limit: int | None = None) -> list[dict]:
    """Return active airports from Supabase, ordered by IATA."""
    params: dict = {
        'active': 'eq.true',
        'select': 'airport_id,iata,icao,latitude,longitude,display_name,city,state',
        'order': 'iata.asc',
    }
    if limit:
        params['limit'] = str(limit)
    return supabase_get(url, key, 'airports', params)


def insert_snapshots(url: str, key: str, rows: list[dict], dry_run: bool = False) -> None:
    """Insert airport_status_snapshots rows. Dry-run prints a summary."""
    if dry_run:
        log('snapshots_dry_run', {'count': len(rows)})
        for r in rows:
            log('snapshot', {
                'airport_id': r.get('airport_id'),
                'status': r.get('current_status_code'),
                'impact_op': r.get('current_impact_color'),
                'impact_fcst': r.get('forecast_impact_color'),
                'flight_cat': r.get('flight_category'),
            })
        return
    supabase_post(url, key, 'airport_status_snapshots', rows)
    log('snapshots_written', {'count': len(rows)})


# ─────────────────────────────── HTTP helpers ─────────────────────────

def http_get_json(target_url: str, headers: dict | None = None, timeout: int = 30) -> object:
    """HTTP GET returning parsed JSON."""
    h = {'User-Agent': PULL_USER_AGENT}
    if headers:
        h.update(headers)
    req = urllib.request.Request(target_url, headers=h)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode())


def http_get_text(target_url: str, headers: dict | None = None, timeout: int = 30) -> str:
    """HTTP GET returning raw text (for XML or HTML responses)."""
    h = {'User-Agent': PULL_USER_AGENT}
    if headers:
        h.update(headers)
    req = urllib.request.Request(target_url, headers=h)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode(errors='replace')


# ─────────────────────────────── raw cache ───────────────────────────

def save_raw(name: str, data: object) -> Path:
    """Save data as JSON to data/raw/{name}.json."""
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    out = RAW_DIR / f'{name}.json'
    out.write_text(json.dumps(data, indent=2, default=str), encoding='utf-8')
    return out


def load_raw(name: str) -> object | None:
    """Load data/raw/{name}.json. Returns None if missing."""
    path = RAW_DIR / f'{name}.json'
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding='utf-8'))


# ─────────────────────────────── forecast helpers ────────────────────

_RED_FORECAST = frozenset({
    'thunderstorm', 'severe', 'tornado', 'blizzard', 'hurricane',
    'ice storm', 'extreme cold', 'extreme heat', 'dense fog',
})
_AMBER_FORECAST = frozenset({
    'rain', 'snow', 'showers', 'wintry mix', 'sleet', 'freezing',
    'ice', 'fog', 'windy', 'gusty', 'breezy', 'drizzle',
})


def nws_impact(short_forecast: str) -> tuple[str, str]:
    """Return (impact_color, impact_label) from an NWS short forecast string.

    This is a proxy — not an official FAA delay forecast.
    Label wording follows source doctrine: 'Forecast Weather Impact — NWS'.
    """
    lo = short_forecast.lower()
    if any(t in lo for t in _RED_FORECAST):
        return 'Red', 'Significant weather likely — Forecast Weather Impact — NWS forecast proxy'
    if any(t in lo for t in _AMBER_FORECAST):
        return 'Amber', 'Weather may affect operations — Forecast Weather Impact — NWS forecast proxy'
    return 'Green', 'No significant weather — Forecast Weather Impact — NWS forecast proxy'


def overall_impact(operational_color: str | None, forecast_color: str | None) -> str | None:
    """Return the most severe of operational and forecast impact colors."""
    rank = {'Red': 3, 'Amber': 2, 'Green': 1}
    op = rank.get(operational_color or '', 0)
    fc = rank.get(forecast_color or '', 0)
    combined = max(op, fc)
    for color, r in rank.items():
        if r == combined:
            return color
    return None
