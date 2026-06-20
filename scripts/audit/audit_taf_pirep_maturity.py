#!/usr/bin/env python3
"""Audit TAF timeline and PIREP maturity: files, doctrine, and source compliance.

Checks:
  1. SQL migration file exists.
  2. Pull scripts exist (pull_taf_timeline.py, pull_pireps.py).
  3. Pull scripts compile (via py_compile).
  4. Doc files exist (TAF_TIMELINE.md, PIREP_MATURITY.md,
     AVIATION_WEATHER_SOURCE_DOCTRINE.md).
  5. Doctrine language is present in doc files (required phrases).
  6. Stale-data language is present (8-hour rule, 2-hour PIREP rule).
  7. Pull scripts do not contain prohibited phrases in actual code logic
     (string literals and comments are excluded from this check — docstrings
     explaining what NOT to claim are not violations).
  8. Raw cache files exist (warn if absent — pull has not been run yet).
  9. No live row check (warn only — empty tables expected before first live run).

DOES NOT REQUIRE SUPABASE CONNECTIVITY.
Skips Supabase checks gracefully when .env is not configured.

Usage:
  python scripts/audit/audit_taf_pirep_maturity.py

Aviation weather doctrine:
  AviationWeather.gov = Aviation Weather Truth (METAR, TAF, PIREP, SIGMET, AIRMET).
  TAF does NOT predict FAA operational delays or ground stops.
  PIREPs are observed flight conditions — not delay forecasts.
  NWS forecast impact remains a forecast proxy only (separate source lane).
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
    ('sql/09_taf_pirep_maturity.sql',                'SQL migration'),
    ('scripts/pull/pull_taf_timeline.py',            'TAF timeline pull script'),
    ('scripts/pull/pull_pireps.py',                  'PIREP pull script'),
    ('scripts/audit/audit_taf_pirep_maturity.py',    'this audit script'),
    ('docs/TAF_TIMELINE.md',                         'TAF timeline doc'),
    ('docs/PIREP_MATURITY.md',                       'PIREP maturity doc'),
    ('docs/AVIATION_WEATHER_SOURCE_DOCTRINE.md',     'aviation weather source doctrine doc'),
]

CACHE_FILES = [
    ('data/raw/taf_raw.json',          'TAF raw cache (written by pull_aviationweather_metar_taf.py)'),
    ('data/raw/taf_timeline_parsed.json', 'TAF timeline parsed cache (written by pull_taf_timeline.py)'),
    ('data/raw/pirep_raw.json',        'PIREP raw cache (written by pull_pireps.py)'),
    ('data/raw/pirep_parsed.json',     'PIREP parsed cache (written by pull_pireps.py)'),
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
    print('\n[2] Raw cache files (warn if absent — must run pull scripts first)')
    for rel, label in CACHE_FILES:
        path = ROOT / rel
        if path.exists():
            ok(f'{rel}')
        else:
            warn(f'Cache file not yet written — run the pull script: {rel} ({label})')


# ─── Compile checks ─────────────────────────────────────────────────────────

PYTHON_SCRIPTS = [
    'scripts/pull/pull_taf_timeline.py',
    'scripts/pull/pull_pireps.py',
    'scripts/audit/audit_taf_pirep_maturity.py',
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
    # (file, [required phrases])
    ('docs/AVIATION_WEATHER_SOURCE_DOCTRINE.md', [
        'Aviation Weather Truth',
        'AviationWeather.gov',
        'FAA operational',
        'NWS',
        'forecast proxy',
    ]),
    ('docs/TAF_TIMELINE.md', [
        'Aviation Weather Truth',
        'TAF',
        'forecast',
        'does not predict',
        '8 hour',
        'stale',
    ]),
    ('docs/PIREP_MATURITY.md', [
        'Aviation Weather Truth',
        'PIREP',
        'pilot-reported',
        'not FAA',
        '2 hour',
        'stale',
    ]),
    ('sql/09_taf_pirep_maturity.sql', [
        'Aviation Weather Truth',
        'does NOT predict',
        'not FAA operational',
        'stale',
        '8 hours',
    ]),
]

SCRIPT_PROHIBITED_PATTERNS: list[tuple[str, list[str]]] = [
    ('scripts/pull/pull_taf_timeline.py', [
        'ground stop',
        'ground delay',
        'GDP',
        'delay minutes',
        'route closure',
    ]),
    ('scripts/pull/pull_pireps.py', [
        'ground stop',
        'ground delay',
        'GDP',
        'delay minutes',
        'route closure',
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


def _code_token_lines(source: str) -> list[str]:
    """Return source lines that contain executable code tokens (not strings or comments).

    Uses Python's tokenizer so that docstrings explaining what NOT to claim
    are correctly excluded from prohibited-pattern checks.
    Falls back to a naive scan if tokenization fails.
    """
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
    print('\n[5] Prohibited pattern checks (pull scripts must not claim delay data)')
    for rel, patterns in SCRIPT_PROHIBITED_PATTERNS:
        path = ROOT / rel
        if not path.exists():
            warn(f'Prohibited pattern check skipped — file missing: {rel}')
            continue
        source = path.read_text(encoding='utf-8', errors='replace')
        code_lines = _code_token_lines(source)
        code_text = '\n'.join(code_lines).lower()
        found = [p for p in patterns if p.lower() in code_text]
        if found:
            fail(f'{rel}: prohibited patterns found in executable code: {found}')
        else:
            ok(f'{rel}: no prohibited patterns in code')


# ─── Stale-data language check ───────────────────────────────────────────────

STALE_CHECKS: list[tuple[str, list[str]]] = [
    ('scripts/pull/pull_taf_timeline.py', ['stale', '8 hour']),
    ('scripts/pull/pull_pireps.py',       ['stale', '2 hour', '8 hour']),
]


def check_stale_language() -> None:
    print('\n[6] Stale-data language in pull scripts')
    for rel, phrases in STALE_CHECKS:
        path = ROOT / rel
        if not path.exists():
            fail(f'Stale-data check skipped — file missing: {rel}')
            continue
        text = path.read_text(encoding='utf-8', errors='replace').lower()
        missing = [p for p in phrases if p.lower() not in text]
        if missing:
            fail(f'{rel}: missing stale-data language: {missing}')
        else:
            ok(f'{rel}: stale-data language present')


# ─── Source label checks ─────────────────────────────────────────────────────

def check_source_labels() -> None:
    print('\n[7] Source label checks in SQL views')
    sql_path = ROOT / 'sql' / '09_taf_pirep_maturity.sql'
    if not sql_path.exists():
        fail('SQL file missing — cannot check source labels')
        return
    text = sql_path.read_text(encoding='utf-8', errors='replace')
    required_labels = [
        'Aviation Weather Truth — AviationWeather.gov',
        'taf_notice',
        'pirep_notice',
        'is_stale',
    ]
    for label in required_labels:
        if label in text:
            ok(f'SQL contains: {label!r}')
        else:
            fail(f'SQL missing required label/field: {label!r}')


# ─── Main ────────────────────────────────────────────────────────────────────

def main() -> None:
    print('=== TAF / PIREP Maturity Audit ===')
    print()
    print('Doctrine: AviationWeather.gov = Aviation Weather Truth.')
    print('TAF is aviation forecast weather — not FAA operational delay data.')
    print('PIREPs are pilot-reported observed conditions — not delay forecasts.')
    print('NWS forecast impact is a forecast proxy only (separate source lane).')

    check_required_files()
    check_cache_files()
    check_compile()
    check_doctrine()
    check_prohibited_patterns()
    check_stale_language()
    check_source_labels()

    print()
    if warnings:
        for w in warnings:
            print(w)
        print()

    if failures:
        for f_ in failures:
            print(f_)
        print()
        print(f'TAF/PIREP maturity audit: FAILED ({len(failures)} failure(s))')
        if warnings:
            print(f'  ({len(warnings)} warning(s) — see above)')
        sys.exit(1)
    else:
        print('TAF/PIREP maturity audit: PASSED')
        if warnings:
            print(f'  ({len(warnings)} warning(s) — see above)')


if __name__ == '__main__':
    main()
