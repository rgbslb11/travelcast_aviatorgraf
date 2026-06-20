#!/usr/bin/env python3
"""Audit NWS CAP / WEA public alert ontology: files, doctrine, and source compliance.

Checks:
  1. SQL migration file exists.
  2. Pull script exists (pull_nws_alerts.py).
  3. Pull script compiles.
  4. Doc files exist (NWS_CAP_WEA_ONTOLOGY.md, PUBLIC_ALERT_SOURCE_DOCTRINE.md,
     AIRPORT_ALERT_MATCHING.md).
  5. Doctrine language is present in doc files (required phrases).
  6. Source label distinctions: public alert truth, aviation weather truth,
     forecast proxy, and operational truth are separated.
  7. Raw payload retention: raw_cap_json field present in SQL.
  8. Stale/expired language present in SQL and pull script.
  9. Prohibited patterns: pull script does not claim delay, GDP, or ground stop
     data from alert content (tokenizer-accurate check — docstrings excluded).
 10. Raw cache files exist (warn if absent — pull has not been run yet).

DOES NOT REQUIRE SUPABASE CONNECTIVITY.

Usage:
  python scripts/audit/audit_public_alert_ontology.py

Source doctrine:
  NWS CAP / WEA = Public Weather Alert Truth.
  NWS alerts are NOT FAA operational delay truth.
  FAA NAS / ATCSCC / official airport / NOTAM sources remain operational truth.
  AviationWeather.gov remains aviation-weather truth.
  NWS forecast impact remains forecast proxy only — separate source lane.
  Empty state is better than invented data.
"""
from __future__ import annotations

import io
import py_compile
import sys
import tokenize as tokenize_mod
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

failures: list[str] = []
warnings: list[str] = []


def fail(msg: str) -> None:
    failures.append(f'FAIL: {msg}')


def warn(msg: str) -> None:
    warnings.append(f'WARN: {msg}')


def ok(msg: str) -> None:
    print(f'  OK  {msg}')


# ─── File existence checks ───────────────────────────────────────────────────

REQUIRED_FILES = [
    ('sql/10_public_alert_ontology.sql',              'SQL migration'),
    ('scripts/pull/pull_nws_alerts.py',               'NWS alert pull script'),
    ('scripts/audit/audit_public_alert_ontology.py',  'this audit script'),
    ('docs/NWS_CAP_WEA_ONTOLOGY.md',                 'NWS CAP ontology doc'),
    ('docs/PUBLIC_ALERT_SOURCE_DOCTRINE.md',          'public alert source doctrine doc'),
    ('docs/AIRPORT_ALERT_MATCHING.md',                'airport alert matching doc'),
]

CACHE_FILES = [
    ('data/raw/nws_alerts_raw.json',    'NWS alerts raw summary (written by pull_nws_alerts.py)'),
    ('data/raw/nws_alerts_parsed.json', 'NWS alerts parsed summary (written by pull_nws_alerts.py)'),
]


def check_required_files() -> None:
    print('\n[1] Required file existence')
    for rel, label in REQUIRED_FILES:
        path = ROOT / rel
        if path.exists():
            ok(f'{rel}')
        else:
            fail(f'Missing {label}: {rel}')


def check_cache_files() -> None:
    print('\n[2] Raw cache files (warn if absent — must run pull_nws_alerts.py first)')
    for rel, label in CACHE_FILES:
        path = ROOT / rel
        if path.exists():
            ok(f'{rel}')
        else:
            warn(f'Cache file not yet written — run pull_nws_alerts.py: {rel} ({label})')


# ─── Compile checks ─────────────────────────────────────────────────────────

PYTHON_SCRIPTS = [
    'scripts/pull/pull_nws_alerts.py',
    'scripts/audit/audit_public_alert_ontology.py',
]


def check_compile() -> None:
    print('\n[3] Python compile checks')
    for rel in PYTHON_SCRIPTS:
        path = ROOT / rel
        if not path.exists():
            fail(f'Cannot compile — file missing: {rel}')
            continue
        try:
            py_compile.compile(str(path), doraise=True)
            ok(f'{rel} compiles')
        except py_compile.PyCompileError as exc:
            fail(f'{rel} compile error: {exc}')


# ─── Doctrine language checks ────────────────────────────────────────────────

DOCTRINE_CHECKS: list[tuple[str, list[str]]] = [
    ('docs/NWS_CAP_WEA_ONTOLOGY.md', [
        'Public Weather Alert',
        'NWS',
        'not FAA',
        'stale',
        'expired',
        'raw',
    ]),
    ('docs/PUBLIC_ALERT_SOURCE_DOCTRINE.md', [
        'Public Weather Alert',
        'NWS',
        'FAA operational',
        'Aviation Weather Truth',
        'forecast proxy',
        'not FAA operational',
    ]),
    ('docs/AIRPORT_ALERT_MATCHING.md', [
        'geometry_intersection',
        'match_confidence',
        'not FAA',
        'weather hazard context',
    ]),
    ('sql/10_public_alert_ontology.sql', [
        'Public Weather Alert',
        'not FAA operational',
        'raw_cap_json',
        'is_expired',
        'is_stale',
        'alert_notice',
        'source_label',
    ]),
]


def check_doctrine() -> None:
    print('\n[4] Doctrine language checks')
    for rel, phrases in DOCTRINE_CHECKS:
        path = ROOT / rel
        if not path.exists():
            fail(f'Doctrine check skipped — file missing: {rel}')
            continue
        text = path.read_text(encoding='utf-8', errors='replace').lower()
        missing = [p for p in phrases if p.lower() not in text]
        if missing:
            fail(f'{rel}: missing required doctrine phrases: {missing}')
        else:
            ok(f'{rel}: all doctrine phrases present')


# ─── Source label distinction checks ────────────────────────────────────────

SOURCE_LABEL_CHECKS: list[tuple[str, list[str]]] = [
    ('sql/10_public_alert_ontology.sql', [
        'Public Weather Alert — NWS CAP',
        'Aviation Weather Truth',
        'not FAA operational',
        'v_public_alert_source_health',
        'v_public_weather_alerts_dashboard',
        'airport_public_alert_matches',
    ]),
    ('docs/PUBLIC_ALERT_SOURCE_DOCTRINE.md', [
        'Public Weather Alert',
        'Aviation Weather Truth',
        'forecast proxy',
        'FAA NAS',
        'ATCSCC',
    ]),
]


def check_source_labels() -> None:
    print('\n[5] Source label distinction checks')
    for rel, phrases in SOURCE_LABEL_CHECKS:
        path = ROOT / rel
        if not path.exists():
            fail(f'Source label check skipped — file missing: {rel}')
            continue
        text = path.read_text(encoding='utf-8', errors='replace')
        missing = [p for p in phrases if p not in text]
        if missing:
            fail(f'{rel}: missing source label phrase: {missing}')
        else:
            ok(f'{rel}: source label distinctions present')


# ─── Raw payload retention check ────────────────────────────────────────────

def check_raw_payload() -> None:
    print('\n[6] Raw payload retention checks')
    sql_path = ROOT / 'sql' / '10_public_alert_ontology.sql'
    if not sql_path.exists():
        fail('SQL missing — cannot check raw payload retention')
        return
    sql_text = sql_path.read_text(encoding='utf-8', errors='replace')
    pull_path = ROOT / 'scripts' / 'pull' / 'pull_nws_alerts.py'
    pull_text = pull_path.read_text(encoding='utf-8', errors='replace') if pull_path.exists() else ''

    checks = [
        (sql_text, 'sql/10_public_alert_ontology.sql', 'raw_cap_json'),
        (pull_text, 'scripts/pull/pull_nws_alerts.py', 'raw_cap_json'),
    ]
    for text, label, phrase in checks:
        if phrase in text:
            ok(f'{label}: contains {phrase!r}')
        else:
            fail(f'{label}: missing raw payload field {phrase!r}')


# ─── Stale / expired language checks ────────────────────────────────────────

STALE_CHECKS: list[tuple[str, list[str]]] = [
    ('sql/10_public_alert_ontology.sql',    ['is_expired', 'is_stale', '8 hours']),
    ('scripts/pull/pull_nws_alerts.py',     ['stale', 'expires', '8 hour']),
    ('docs/NWS_CAP_WEA_ONTOLOGY.md',        ['stale', 'expired', '8 hour']),
]


def check_stale_language() -> None:
    print('\n[7] Stale / expired language checks')
    for rel, phrases in STALE_CHECKS:
        path = ROOT / rel
        if not path.exists():
            fail(f'Stale check skipped — file missing: {rel}')
            continue
        text = path.read_text(encoding='utf-8', errors='replace').lower()
        missing = [p for p in phrases if p.lower() not in text]
        if missing:
            fail(f'{rel}: missing stale/expired language: {missing}')
        else:
            ok(f'{rel}: stale/expired language present')


# ─── Prohibited pattern checks ───────────────────────────────────────────────

PROHIBITED_PATTERNS: list[tuple[str, list[str]]] = [
    ('scripts/pull/pull_nws_alerts.py', [
        'ground stop',
        'ground delay',
        'GDP',
        'delay minutes',
        'route closure',
        'arrival rate',
    ]),
]


def _code_token_lines(source: str) -> list[str]:
    """Return source lines containing executable code tokens (not strings or comments)."""
    try:
        tokens = list(tokenize_mod.generate_tokens(io.StringIO(source).readline))
    except tokenize_mod.TokenError:
        return [l.lstrip() for l in source.splitlines()
                if not l.lstrip().startswith('#')]

    skip_types = {
        tokenize_mod.STRING, tokenize_mod.COMMENT,
        tokenize_mod.NEWLINE, tokenize_mod.NL,
        tokenize_mod.INDENT, tokenize_mod.DEDENT,
        tokenize_mod.ENCODING, tokenize_mod.ENDMARKER,
    }
    code_line_nums: set[int] = set()
    for tok_type, _, tok_start, tok_end, _ in tokens:
        if tok_type in skip_types:
            continue
        for lineno in range(tok_start[0], tok_end[0] + 1):
            code_line_nums.add(lineno)

    all_lines = source.splitlines()
    return [all_lines[i - 1] for i in sorted(code_line_nums)
            if 0 < i <= len(all_lines)]


def check_prohibited_patterns() -> None:
    print('\n[8] Prohibited pattern checks (script must not claim delay/GDP/ground stop data)')
    for rel, patterns in PROHIBITED_PATTERNS:
        path = ROOT / rel
        if not path.exists():
            warn(f'Prohibited check skipped — file missing: {rel}')
            continue
        source = path.read_text(encoding='utf-8', errors='replace')
        code_lines = _code_token_lines(source)
        code_text = '\n'.join(code_lines).lower()
        found = [p for p in patterns if p.lower() in code_text]
        if found:
            fail(f'{rel}: prohibited patterns in executable code: {found}')
        else:
            ok(f'{rel}: no prohibited patterns in code')


# ─── No sample / invented alert rows in SQL ──────────────────────────────────

def check_no_sample_rows() -> None:
    """Verify SQL does not INSERT invented rows into the alert data tables."""
    print('\n[9] No sample/invented alert rows in SQL')
    sql_path = ROOT / 'sql' / '10_public_alert_ontology.sql'
    if not sql_path.exists():
        fail('SQL missing — cannot check for sample rows')
        return
    sql_text = sql_path.read_text(encoding='utf-8', errors='replace').lower()
    prohibited = [
        'insert into public.public_weather_alerts',
        'insert into public_weather_alerts',
        'insert into public.airport_public_alert_matches',
    ]
    found = [p for p in prohibited if p in sql_text]
    if found:
        fail(f'sql/10_public_alert_ontology.sql: contains INSERT INTO alert table '
             f'(remove invented/sample rows): {found}')
    else:
        ok('SQL: no INSERT INTO alert data tables (no sample rows)')


# ─── Match confidence distinction check ──────────────────────────────────────

def check_match_confidence_distinction() -> None:
    """Verify AIRPORT_ALERT_MATCHING.md documents all confidence levels."""
    print('\n[10] Match confidence distinction in AIRPORT_ALERT_MATCHING.md')
    doc_path = ROOT / 'docs' / 'AIRPORT_ALERT_MATCHING.md'
    if not doc_path.exists():
        fail('AIRPORT_ALERT_MATCHING.md missing — cannot check confidence levels')
        return
    text = doc_path.read_text(encoding='utf-8', errors='replace')
    required = [
        ('geometry_intersection',  'geometry_intersection method'),
        ('match_confidence',       'match_confidence field'),
        ('high confidence',        'high confidence level'),
        ('medium confidence',      'medium confidence level'),
        ('low confidence',         'low confidence level'),
        ('zone_text_match',        'zone_text_match scaffold'),
    ]
    missing = [label for phrase, label in required
               if phrase.lower() not in text.lower()]
    if missing:
        fail(f'docs/AIRPORT_ALERT_MATCHING.md: missing match confidence items: {missing}')
    else:
        ok('docs/AIRPORT_ALERT_MATCHING.md: all confidence levels documented')


# ─── Main ────────────────────────────────────────────────────────────────────

def main() -> None:
    print('=== Public Alert Ontology Audit ===')
    print()
    print('Doctrine: NWS CAP = Public Weather Alert Truth.')
    print('NWS alerts are NOT FAA operational delay truth.')
    print('FAA NAS / ATCSCC / official airport / NOTAM sources remain operational truth.')
    print('AviationWeather.gov remains aviation-weather truth.')
    print('NWS forecast impact remains forecast proxy only.')

    check_required_files()
    check_cache_files()
    check_compile()
    check_doctrine()
    check_source_labels()
    check_raw_payload()
    check_stale_language()
    check_prohibited_patterns()
    check_no_sample_rows()
    check_match_confidence_distinction()

    print()
    if warnings:
        for w in warnings:
            print(w)
        print()

    if failures:
        for f_ in failures:
            print(f_)
        print()
        print(f'Public alert ontology audit: FAILED ({len(failures)} failure(s))')
        if warnings:
            print(f'  ({len(warnings)} warning(s) — see above)')
        sys.exit(1)
    else:
        print('Public alert ontology audit: PASSED')
        if warnings:
            print(f'  ({len(warnings)} warning(s) — see above)')


if __name__ == '__main__':
    main()
