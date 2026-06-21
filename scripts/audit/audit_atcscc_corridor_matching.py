#!/usr/bin/env python3
"""Audit Phase C3 ATCSCC Playbook + Aviation Hazard Corridor Matching scaffold.

Checks:
  1.  Required C3 files exist.
  2.  Python scripts compile without error.
  3.  SQL includes all required tables.
  4.  SQL includes all required views.
  5.  Doctrine language present in SQL and docs.
  6.  Prohibited phrases absent from executable Python code.
  7.  No fake advisory rows in SQL (no INSERT INTO atcscc_advisories).
  8.  No fake match rows in SQL (no INSERT INTO match tables).
  9.  Warn if no live ATCSCC raw cache exists (pull has not been run).
 10.  Fail if D1/D2/RoadCast scope appears in C3 implemented files.

DOES NOT REQUIRE SUPABASE CONNECTIVITY.

Usage:
  python scripts/audit/audit_atcscc_corridor_matching.py

Source doctrine:
  FAA NAS / ATCSCC / NOTAM = Current Operational Impact (operational aviation truth).
  RouteCast geometry = planning/display scaffold only, not FAA operational delay truth.
  NWS CAP public alerts = Public Weather Alert Truth, not FAA operational delay truth.
  AviationWeather.gov hazards = Aviation Weather Truth, not FAA operational delay truth.
  NWS forecast = forecast proxy only, not FAA operational truth.
  Corridor × advisory matches are context scaffolds — not delay claims, not impact scores.
  Weather hazard context near a corridor is not FAA operational delay truth.
  No impact scoring in C3.
  Empty state is better than invented data.
  Do not invent advisories, matches, restrictions, ground stops, or route closures.
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


# ─── File existence ──────────────────────────────────────────────────────────

REQUIRED_FILES = [
    ('sql/12_atcscc_playbook_corridor_matching.sql',       'SQL migration'),
    ('scripts/pull/pull_atcscc_advisories.py',             'ATCSCC advisory pull script'),
    ('scripts/match/match_routecast_corridor_hazards.py',  'corridor hazard match script'),
    ('scripts/audit/audit_atcscc_corridor_matching.py',    'this audit script'),
    ('docs/ATCSCC_PLAYBOOK_ONTOLOGY.md',                   'ATCSCC playbook ontology doc'),
    ('docs/AVIATION_HAZARD_CORRIDOR_MATCHING.md',          'corridor hazard matching doc'),
    ('docs/C3_SOURCE_DOCTRINE.md',                         'C3 source doctrine doc'),
]


def check_required_files() -> None:
    print('\n[1] Required C3 file existence')
    for rel, label in REQUIRED_FILES:
        path = ROOT / rel
        if path.exists():
            ok(rel)
        else:
            fail(f'Missing {label}: {rel}')


# ─── Compile checks ──────────────────────────────────────────────────────────

PYTHON_SCRIPTS = [
    'scripts/pull/pull_atcscc_advisories.py',
    'scripts/match/match_routecast_corridor_hazards.py',
    'scripts/audit/audit_atcscc_corridor_matching.py',
]


def check_compile() -> None:
    print('\n[2] Python compile checks')
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


# ─── SQL object checks ────────────────────────────────────────────────────────

REQUIRED_SQL_TABLES = [
    'atcscc_advisories',
    'atcscc_playbook_patterns',
    'routecast_corridor_atcscc_matches',
    'routecast_corridor_hazard_context_matches',
]

REQUIRED_SQL_VIEWS = [
    'v_atcscc_advisory_dashboard',
    'v_routecast_atcscc_context',
    'v_routecast_hazard_context',
    'v_c3_matching_audit',
]


def check_sql_objects() -> None:
    sql_path = ROOT / 'sql' / '12_atcscc_playbook_corridor_matching.sql'

    print('\n[3] SQL table presence')
    if not sql_path.exists():
        fail('SQL file missing — cannot check tables')
        return
    sql_text = sql_path.read_text(encoding='utf-8', errors='replace')

    for table in REQUIRED_SQL_TABLES:
        if table in sql_text:
            ok(f'SQL contains table: {table}')
        else:
            fail(f'SQL missing required table: {table}')

    print('\n[4] SQL view presence')
    for view in REQUIRED_SQL_VIEWS:
        if view in sql_text:
            ok(f'SQL contains view: {view}')
        else:
            fail(f'SQL missing required view: {view}')


# ─── Doctrine language checks ─────────────────────────────────────────────────

DOCTRINE_CHECKS: list[tuple[str, list[str]]] = [
    ('sql/12_atcscc_playbook_corridor_matching.sql', [
        'faa_atcscc_operational_truth',
        'faa_atcscc_operational_context_pattern',
        'routecast_atcscc_context_match',
        'corridor_weather_hazard_context_only',
        'not a delay claim',
        'not FAA operational delay truth',
        'planning/display scaffold',
        'not impact scores',
        'empty state is better than invented data',
        'do not invent',
        'Public Weather Alert Truth',
        'operator_review_status',
    ]),
    ('docs/ATCSCC_PLAYBOOK_ONTOLOGY.md', [
        'FAA',
        'ATCSCC',
        'operational truth',
        'not delay',
        'source truth lane',
        'empty state',
        'prohibited',
        'no impact',
    ]),
    ('docs/AVIATION_HAZARD_CORRIDOR_MATCHING.md', [
        'corridor',
        'match_confidence',
        'medium_airport_or_fix_overlap',
        'low_text_context',
        'not FAA operational',
        'operator_review_status',
        'draft',
        'no scoring',
        'Public Weather Alert',
        'Aviation Weather Truth',
    ]),
    ('docs/C3_SOURCE_DOCTRINE.md', [
        'FAA NAS',
        'ATCSCC',
        'RouteCast',
        'planning/display scaffold',
        'not delay truth',
        'NWS',
        'Public Weather Alert',
        'AviationWeather',
        'no impact scoring',
        'empty state',
        'do not invent',
    ]),
]


def check_doctrine() -> None:
    print('\n[5] Doctrine language checks')
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


# ─── Prohibited pattern checks ───────────────────────────────────────────────

def _code_token_lines(source: str) -> list[str]:
    """Return source lines containing executable code tokens (not strings/comments)."""
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


PROHIBITED_PATTERNS: list[tuple[str, list[str]]] = [
    ('scripts/pull/pull_atcscc_advisories.py', [
        'aviaimpact',
        'delay_score',
        'route_closure_score',
        'roadcast_impact',
        'd1_shared_impact',
    ]),
    ('scripts/match/match_routecast_corridor_hazards.py', [
        'aviaimpact',
        'delay_score',
        'route_closure_score',
        'roadcast_impact',
        'd1_shared_impact',
    ]),
]


def check_prohibited_patterns() -> None:
    print('\n[6] Prohibited pattern checks (no impact scoring / D1/D2/RoadCast identifiers)')
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
            fail(f'{rel}: prohibited identifiers in executable code: {found}')
        else:
            ok(f'{rel}: no prohibited identifiers in code')


# ─── No fake advisory rows in SQL ────────────────────────────────────────────

def check_no_fake_advisory_rows() -> None:
    print('\n[7] No fake advisory rows in SQL')
    sql_path = ROOT / 'sql' / '12_atcscc_playbook_corridor_matching.sql'
    if not sql_path.exists():
        fail('SQL missing — cannot check for fake advisory rows')
        return
    sql_text = sql_path.read_text(encoding='utf-8', errors='replace').lower()
    prohibited = [
        'insert into public.atcscc_advisories',
        'insert into atcscc_advisories',
    ]
    found = [p for p in prohibited if p in sql_text]
    if found:
        fail(
            f'sql/12: contains INSERT INTO atcscc_advisories — '
            f'advisory rows must come from pull_atcscc_advisories.py, not SQL migration: {found}'
        )
    else:
        ok('SQL: no INSERT INTO atcscc_advisories (no fake advisory rows)')


# ─── No fake match rows in SQL ────────────────────────────────────────────────

def check_no_fake_match_rows() -> None:
    print('\n[8] No fake match rows in SQL')
    sql_path = ROOT / 'sql' / '12_atcscc_playbook_corridor_matching.sql'
    if not sql_path.exists():
        fail('SQL missing — cannot check for fake match rows')
        return
    sql_text = sql_path.read_text(encoding='utf-8', errors='replace').lower()
    prohibited = [
        'insert into public.routecast_corridor_atcscc_matches',
        'insert into routecast_corridor_atcscc_matches',
        'insert into public.routecast_corridor_hazard_context_matches',
        'insert into routecast_corridor_hazard_context_matches',
    ]
    found = [p for p in prohibited if p in sql_text]
    if found:
        fail(
            f'sql/12: contains INSERT INTO match table — '
            f'match rows must come from match_routecast_corridor_hazards.py, not SQL migration: {found}'
        )
    else:
        ok('SQL: no INSERT INTO match tables (no fake match rows)')


# ─── Raw cache warning ────────────────────────────────────────────────────────

CACHE_FILES = [
    ('data/raw/atcscc_advisories.json',   'NAS NOTAM advisory cache (pull_atcscc_ops_plan.py)'),
    ('data/raw/atcscc_ops_plan_raw.json', 'Ops plan advisory cache (pull_atcscc_ops_plan.py)'),
    ('data/raw/atcscc_c3_advisories.json','C3 parsed advisory cache (pull_atcscc_advisories.py)'),
]


def check_cache_files() -> None:
    print('\n[9] Raw cache files (warn if absent — pull not yet run)')
    for rel, label in CACHE_FILES:
        path = ROOT / rel
        if path.exists():
            ok(f'{rel}')
        else:
            warn(
                f'Cache file not yet written — run pull scripts first: '
                f'{rel} ({label})'
            )
    warn(
        'No live Supabase check — run pull_atcscc_advisories.py then '
        'match_routecast_corridor_hazards.py to populate advisory and match rows.'
    )


# ─── No D1/D2/RoadCast scope ──────────────────────────────────────────────────

OUT_OF_SCOPE = [
    'aviaimpact_score',
    'aviaimpact_v1',
    'd1_shared_impact',
    'd2_aviaimpact',
    'roadcast_highway',
    'roadcast_output',
    'route_delay_score',
    'closure_score',
    'delay_score',
    'impact_color_from_delay',
]

OUT_OF_SCOPE_FILES = [
    ROOT / 'sql'     / '12_atcscc_playbook_corridor_matching.sql',
    ROOT / 'scripts' / 'pull'  / 'pull_atcscc_advisories.py',
    ROOT / 'scripts' / 'match' / 'match_routecast_corridor_hazards.py',
]


def check_no_out_of_scope() -> None:
    print('\n[10] No D1/D2/RoadCast scope in C3 files')
    for path in OUT_OF_SCOPE_FILES:
        if not path.exists():
            warn(f'Scope check skipped — file missing: {path.name}')
            continue
        text = path.read_text(encoding='utf-8', errors='replace').lower()
        found = [p for p in OUT_OF_SCOPE if p in text]
        if found:
            fail(f'{path.name}: D1/D2/RoadCast out-of-scope identifiers found: {found}')
        else:
            ok(f'{path.name}: no D1/D2/RoadCast scope')


# ─── Main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    print('=== C3 ATCSCC Playbook + Corridor Matching Audit ===')
    print()
    print('Doctrine: FAA NAS / ATCSCC = Current Operational Impact (operational truth).')
    print('RouteCast corridor geometry = planning/display scaffold, not FAA delay truth.')
    print('NWS CAP alerts = Public Weather Alert Truth, not FAA operational delay truth.')
    print('AviationWeather.gov hazards = Aviation Weather Truth, not FAA delay truth.')
    print('Corridor matches are context scaffolds. No impact scoring in C3.')
    print('Empty state is better than invented data.')

    check_required_files()
    check_compile()
    check_sql_objects()
    check_doctrine()
    check_prohibited_patterns()
    check_no_fake_advisory_rows()
    check_no_fake_match_rows()
    check_cache_files()
    check_no_out_of_scope()

    print()
    if warnings:
        for w in warnings:
            print(w)
        print()

    if failures:
        for f_ in failures:
            print(f_)
        print()
        print(f'C3 corridor matching audit: FAILED ({len(failures)} failure(s))')
        if warnings:
            print(f'  ({len(warnings)} warning(s) — see above)')
        sys.exit(1)
    else:
        print('C3 corridor matching audit: PASSED')
        if warnings:
            print(f'  ({len(warnings)} warning(s) — see above)')


if __name__ == '__main__':
    main()
