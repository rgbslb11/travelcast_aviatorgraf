#!/usr/bin/env python3
"""Audit RouteCast corridor geometry scaffold: files, schema, doctrine, and scope compliance.

Checks:
  1.  Required file existence.
  2.  Python script compiles.
  3.  SQL includes all required tables.
  4.  SQL includes all required views.
  5.  Doctrine language present in SQL and docs.
  6.  Prohibited claims absent from executable code (tokenizer-accurate).
  7.  Style definitions present in SQL.
  8.  Geometry confidence levels documented in SQL and docs.
  9.  No C3 / AviaImpact / RoadCast scope in implemented code.
 10.  Warn if corridor table appears to have no rows (cannot check without Supabase).

DOES NOT REQUIRE SUPABASE CONNECTIVITY.

Usage:
  python scripts/audit/audit_routecast_geometry.py

Source doctrine:
  Top-50 route file = static RouteCast reference, NOT delay truth.
  FAA waypoint/coordinate artifacts = route-geometry inputs, NOT delay truth.
  RouteCast corridor geometry = planning/display scaffold only.
  RouteCast corridor geometry is NOT FAA operational delay truth.
  FAA NAS / ATCSCC / NOTAM = operational aviation truth.
  AviationWeather.gov = aviation-weather truth.
  NWS public alerts = public weather hazard context only.
  NWS forecast impact = forecast proxy only.
  Empty state is better than invented geometry.
  Do not invent waypoint coordinates.
  Do not invent route segments.
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
    ('sql/11_routecast_corridor_geometry.sql',       'SQL migration'),
    ('scripts/routecast/seed_routecast_corridors.py', 'corridor seed script'),
    ('scripts/audit/audit_routecast_geometry.py',    'this audit script'),
    ('docs/ROUTECAST_CORRIDOR_GEOMETRY.md',          'geometry doc'),
    ('docs/ROUTECAST_IMPACT_STYLING.md',             'impact styling doc'),
    ('docs/ROUTECAST_SOURCE_DOCTRINE.md',            'source doctrine doc'),
]


def check_required_files() -> None:
    print('\n[1] Required file existence')
    for rel, label in REQUIRED_FILES:
        path = ROOT / rel
        if path.exists():
            ok(rel)
        else:
            fail(f'Missing {label}: {rel}')


# ─── Compile checks ──────────────────────────────────────────────────────────

PYTHON_SCRIPTS = [
    'scripts/routecast/seed_routecast_corridors.py',
    'scripts/audit/audit_routecast_geometry.py',
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
    'routecast_corridors',
    'routecast_corridor_waypoints',
    'routecast_corridor_geometry',
    'routecast_corridor_styles',
]

REQUIRED_SQL_VIEWS = [
    'v_routecast_corridor_geometry',
    'v_routecast_corridor_map',
    'v_routecast_geometry_audit',
]


def check_sql_objects() -> None:
    sql_path = ROOT / 'sql' / '11_routecast_corridor_geometry.sql'

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
    ('sql/11_routecast_corridor_geometry.sql', [
        'not FAA operational',
        'planning/display scaffold',
        'not delay truth',
        'geometry_confidence',
        'route_rank_basis',
        'static_top_50_busiest_route_reference_not_delay_truth',
        'empty state is better than invented',
        'do not invent',
    ]),
    ('docs/ROUTECAST_CORRIDOR_GEOMETRY.md', [
        'planning/display scaffold',
        'not FAA operational',
        'geometry_confidence',
        'unresolved',
        'control_line_scaffold',
        'empty state',
    ]),
    ('docs/ROUTECAST_IMPACT_STYLING.md', [
        'not FAA operational',
        'not delay truth',
        'style',
        'impact score',
        'public alert context',
    ]),
    ('docs/ROUTECAST_SOURCE_DOCTRINE.md', [
        'Top-50',
        'not delay truth',
        'FAA NAS',
        'ATCSCC',
        'AviationWeather',
        'NWS',
        'public weather alert',
        'planning/display scaffold',
        'do not invent',
        'empty state',
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
            fail(f'{rel}: missing doctrine phrases: {missing}')
        else:
            ok(f'{rel}: all doctrine phrases present')


# ─── Prohibited pattern checks ───────────────────────────────────────────────

PROHIBITED_PATTERNS: list[tuple[str, list[str]]] = [
    ('scripts/routecast/seed_routecast_corridors.py', [
        'ground stop',
        'ground delay',
        'GDP',
        'delay minutes',
        'route closure',
        'arrival rate',
        'aviaimpact',
        'roadcast_impact',
        'atcscc_playbook',
        'invented geometry',
        'invented waypoint',
    ]),
]


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


def check_prohibited_patterns() -> None:
    print('\n[6] Prohibited pattern checks (code must not claim delay/operational data)')
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


# ─── Style definitions check ─────────────────────────────────────────────────

REQUIRED_STYLES = [
    'routecast_default',
    'routecast_selected',
    'routecast_unvalidated',
    'routecast_public_alert_context',
]


def check_style_definitions() -> None:
    print('\n[7] Style definitions in SQL')
    sql_path = ROOT / 'sql' / '11_routecast_corridor_geometry.sql'
    if not sql_path.exists():
        fail('SQL missing — cannot check style definitions')
        return
    sql_text = sql_path.read_text(encoding='utf-8', errors='replace')
    missing = [s for s in REQUIRED_STYLES if s not in sql_text]
    if missing:
        fail(f'SQL missing required style keys: {missing}')
    else:
        ok(f'SQL: all {len(REQUIRED_STYLES)} required style keys present')


# ─── Geometry confidence documentation check ─────────────────────────────────

GEOMETRY_CONFIDENCE_LEVELS = [
    'unvalidated',
    'control_line_scaffold',
    'needs_source_file',
    'partially_resolved',
]


def check_geometry_confidence() -> None:
    print('\n[8] Geometry confidence levels documented')
    sql_path = ROOT / 'sql' / '11_routecast_corridor_geometry.sql'
    doc_path = ROOT / 'docs' / 'ROUTECAST_CORRIDOR_GEOMETRY.md'

    for path, label in [(sql_path, 'SQL'), (doc_path, 'geometry doc')]:
        if not path.exists():
            warn(f'Geometry confidence check skipped — {label} file missing')
            continue
        text = path.read_text(encoding='utf-8', errors='replace')
        missing = [c for c in GEOMETRY_CONFIDENCE_LEVELS if c not in text]
        if missing:
            fail(f'{label}: missing geometry confidence levels: {missing}')
        else:
            ok(f'{label}: all geometry confidence levels documented')


# ─── No out-of-scope C3/D/RoadCast content ────────────────────────────────────

OUT_OF_SCOPE_PATTERNS = [
    'aviaimpact_score',
    'roadcast_highway',
    'atcscc_playbook_match',
    'd1_shared_impact',
    'closure_score',
    'delay_score',
    'impact_color_from_delay',
]


def check_no_out_of_scope() -> None:
    print('\n[9] No C3/D/RoadCast scope in C2 files')
    check_files = [
        ROOT / 'sql'    / '11_routecast_corridor_geometry.sql',
        ROOT / 'scripts' / 'routecast' / 'seed_routecast_corridors.py',
    ]
    for path in check_files:
        if not path.exists():
            warn(f'Scope check skipped — file missing: {path.name}')
            continue
        text = path.read_text(encoding='utf-8', errors='replace').lower()
        found = [p for p in OUT_OF_SCOPE_PATTERNS if p.lower() in text]
        if found:
            fail(f'{path.name}: out-of-scope C3/D/RoadCast patterns found: {found}')
        else:
            ok(f'{path.name}: no out-of-scope C3/D/RoadCast patterns')


# ─── Corridor row warning ─────────────────────────────────────────────────────

def check_no_fake_rows() -> None:
    print('\n[10] No fake/invented route rows in SQL')
    sql_path = ROOT / 'sql' / '11_routecast_corridor_geometry.sql'
    if not sql_path.exists():
        fail('SQL missing — cannot check for fake rows')
        return
    sql_text = sql_path.read_text(encoding='utf-8', errors='replace').lower()
    prohibited = [
        'insert into public.routecast_corridors',
        'insert into routecast_corridors',
    ]
    found = [p for p in prohibited if p in sql_text]
    if found:
        fail(f'sql/11: contains INSERT INTO routecast_corridors — '
             f'route data must come from seed script, not SQL migration: {found}')
    else:
        ok('SQL: no INSERT INTO routecast_corridors (route data seeded by script, not SQL)')
    warn('No live Supabase check — run seed_routecast_corridors.py --dry-run to '
         'verify corridor rows will be built when source CSV is available')


# ─── Main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    print('=== RouteCast Corridor Geometry Audit ===')
    print()
    print('Doctrine: Top-50 route source file = static reference, NOT delay truth.')
    print('FAA waypoint coordinates = geometry inputs, NOT delay truth.')
    print('RouteCast corridor geometry = planning/display scaffold only.')
    print('FAA NAS / ATCSCC / NOTAM remain operational aviation truth.')
    print('Empty state is better than invented geometry.')

    check_required_files()
    check_compile()
    check_sql_objects()
    check_doctrine()
    check_prohibited_patterns()
    check_style_definitions()
    check_geometry_confidence()
    check_no_out_of_scope()
    check_no_fake_rows()

    print()
    if warnings:
        for w in warnings:
            print(w)
        print()

    if failures:
        for f_ in failures:
            print(f_)
        print()
        print(f'RouteCast geometry audit: FAILED ({len(failures)} failure(s))')
        if warnings:
            print(f'  ({len(warnings)} warning(s) — see above)')
        sys.exit(1)
    else:
        print('RouteCast geometry audit: PASSED')
        if warnings:
            print(f'  ({len(warnings)} warning(s) — see above)')


if __name__ == '__main__':
    main()
