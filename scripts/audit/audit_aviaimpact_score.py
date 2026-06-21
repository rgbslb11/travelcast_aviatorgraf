#!/usr/bin/env python3
"""
scripts/audit/audit_aviaimpact_score.py
Phase D2 — AviaImpact Score v0.1 audit.

10-check audit for D2 scaffold correctness and doctrine compliance.
Follows project audit pattern.
"""

import subprocess
import sys
import py_compile
import tokenize
import io
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

PASS = 'PASS'
FAIL = 'FAIL'
WARN = 'WARN'

results = []


def result(status, check, detail=''):
    tag = f'[{status}]'
    msg = f'{tag} {check}'
    if detail:
        msg += f': {detail}'
    print(msg)
    results.append((status, check))


def _code_token_lines(path):
    """Extract lines containing code tokens — excludes string/comment-only lines."""
    src = Path(path).read_text(encoding='utf-8', errors='replace')
    code_lines = set()
    try:
        tokens = list(tokenize.generate_tokens(io.StringIO(src).readline))
    except tokenize.TokenError:
        return src.splitlines()
    for tok_type, tok_string, tok_start, _, _ in tokens:
        if tok_type in (tokenize.NAME, tokenize.OP, tokenize.NUMBER):
            code_lines.add(tok_start[0])
    lines = src.splitlines()
    return [lines[i - 1] for i in sorted(code_lines) if 0 < i <= len(lines)]


# ─────────────────────────────────────────────────────────────────────────────
# Check 1: Required D2 files exist
# ─────────────────────────────────────────────────────────────────────────────
REQUIRED_FILES = [
    'sql/14_aviaimpact_score_v0_1.sql',
    'scripts/scoring/aviaimpact_score.py',
    'scripts/audit/audit_aviaimpact_score.py',
    'docs/AVIAIMPACT_SCORE_V0_1.md',
    'docs/AVIAIMPACT_SOURCE_DOCTRINE.md',
    'docs/AVIAIMPACT_OPERATOR_REVIEW.md',
]

missing = [f for f in REQUIRED_FILES if not (ROOT / f).exists()]
if missing:
    result(FAIL, 'Check 1: Required D2 files exist', f'Missing: {missing}')
else:
    result(PASS, 'Check 1: Required D2 files exist')


# ─────────────────────────────────────────────────────────────────────────────
# Check 2: AviaImpact scoring script compiles
# ─────────────────────────────────────────────────────────────────────────────
scoring_script = ROOT / 'scripts' / 'scoring' / 'aviaimpact_score.py'
if scoring_script.exists():
    try:
        py_compile.compile(str(scoring_script), doraise=True)
        result(PASS, 'Check 2: aviaimpact_score.py compiles')
    except py_compile.PyCompileError as e:
        result(FAIL, 'Check 2: aviaimpact_score.py compiles', str(e))
else:
    result(FAIL, 'Check 2: aviaimpact_score.py compiles', 'File missing')


# ─────────────────────────────────────────────────────────────────────────────
# Check 3: aviaimpact_score.py --self-test passes
# ─────────────────────────────────────────────────────────────────────────────
if scoring_script.exists():
    try:
        proc = subprocess.run(
            [sys.executable, str(scoring_script), '--self-test'],
            capture_output=True, text=True, cwd=str(ROOT), timeout=30
        )
        if proc.returncode == 0:
            result(PASS, 'Check 3: aviaimpact_score.py --self-test passes')
        else:
            detail = (proc.stdout + proc.stderr).strip()[:300]
            result(FAIL, 'Check 3: aviaimpact_score.py --self-test passes',
                   f'exit {proc.returncode}: {detail}')
    except subprocess.TimeoutExpired:
        result(FAIL, 'Check 3: aviaimpact_score.py --self-test passes', 'Timed out')
    except Exception as e:
        result(FAIL, 'Check 3: aviaimpact_score.py --self-test passes', str(e))
else:
    result(FAIL, 'Check 3: aviaimpact_score.py --self-test passes', 'File missing')


# ─────────────────────────────────────────────────────────────────────────────
# Check 4: SQL includes required tables and views
# ─────────────────────────────────────────────────────────────────────────────
sql_file = ROOT / 'sql' / '14_aviaimpact_score_v0_1.sql'
sql_text = ''
if sql_file.exists():
    sql_text = sql_file.read_text(encoding='utf-8').lower()

REQUIRED_TABLES = [
    'aviaimpact_model_versions',
    'aviaimpact_component_definitions',
    'aviaimpact_draft_scores',
]

REQUIRED_VIEWS = [
    'v_aviaimpact_model_registry',
    'v_aviaimpact_component_registry',
    'v_aviaimpact_draft_review_queue',
    'v_aviaimpact_audit_summary',
]

if sql_file.exists():
    missing_tables = [
        t for t in REQUIRED_TABLES
        if f'create table if not exists public.{t}' not in sql_text
    ]
    missing_views = [
        v for v in REQUIRED_VIEWS
        if f'create or replace view public.{v}' not in sql_text
    ]
    if missing_tables or missing_views:
        issues = []
        if missing_tables:
            issues.append(f'missing tables: {missing_tables}')
        if missing_views:
            issues.append(f'missing views: {missing_views}')
        result(FAIL, 'Check 4: SQL required tables and views', '; '.join(issues))
    else:
        result(PASS, 'Check 4: SQL required tables and views')
else:
    result(FAIL, 'Check 4: SQL required tables and views', 'SQL file missing')


# ─────────────────────────────────────────────────────────────────────────────
# Check 5: SQL seeds aviaimpact_v0_1 model and 5 required components
# ─────────────────────────────────────────────────────────────────────────────
REQUIRED_MODEL_SEED = 'aviaimpact_v0_1'
REQUIRED_COMPONENTS = [
    'official_operational_status_component',
    'aviation_weather_component',
    'public_alert_context_component',
    'routecast_context_component',
    'forecast_proxy_component',
]

if sql_file.exists():
    issues = []
    if f"'{REQUIRED_MODEL_SEED}'" not in sql_text:
        issues.append(f'model seed missing: {REQUIRED_MODEL_SEED}')
    missing_comps = [c for c in REQUIRED_COMPONENTS if f"'{c}'" not in sql_text]
    if missing_comps:
        issues.append(f'missing component seeds: {missing_comps}')
    if issues:
        result(FAIL, 'Check 5: SQL seeds model and 5 components', '; '.join(issues))
    else:
        result(PASS, 'Check 5: SQL seeds aviaimpact_v0_1 and 5 required components')
else:
    result(FAIL, 'Check 5: SQL seeds model and 5 components', 'SQL file missing')


# ─────────────────────────────────────────────────────────────────────────────
# Check 6: SQL does NOT insert rows into aviaimpact_draft_scores
# ─────────────────────────────────────────────────────────────────────────────
FORBIDDEN_DRAFT_INSERTS = [
    'insert into public.aviaimpact_draft_scores',
    'insert into aviaimpact_draft_scores',
]

if sql_file.exists():
    found = [p for p in FORBIDDEN_DRAFT_INSERTS if p in sql_text]
    if found:
        result(FAIL, 'Check 6: SQL does not insert live draft scores',
               f'Forbidden INSERT found: {found}')
    else:
        result(PASS, 'Check 6: SQL does not insert live draft scores (correct for D2)')
else:
    result(FAIL, 'Check 6: SQL does not insert live draft scores', 'SQL file missing')


# ─────────────────────────────────────────────────────────────────────────────
# Check 7: No prohibited behavior in scoring script
# ─────────────────────────────────────────────────────────────────────────────
PROHIBITED_IDENTIFIERS = [
    'roadcast_score',
    'roadcast_output',
    'roadcast_implementation',
    'generate_public_output',
    'auto_public_release',
    'public_release_default_true',
    'live_scoring_row',
    'd3_roadcast',
    'd4_roadcast',
    'd5_roadcast',
    'invented_impact',
    'delay_from_nws',
    'delay_from_geometry',
    'delay_from_context',
]

if scoring_script.exists():
    code_lines = _code_token_lines(scoring_script)
    code_text = '\n'.join(code_lines).lower()
    found = [p for p in PROHIBITED_IDENTIFIERS if p in code_text]
    if found:
        result(FAIL, 'Check 7: No prohibited identifiers in scoring script',
               f'Found: {found}')
    else:
        result(PASS, 'Check 7: No prohibited identifiers in scoring script')
else:
    result(FAIL, 'Check 7: No prohibited identifiers in scoring script', 'File missing')


# ─────────────────────────────────────────────────────────────────────────────
# Check 8: Docs contain required doctrine language
# ─────────────────────────────────────────────────────────────────────────────
DOCTRINE_PHRASES = {
    'docs/AVIAIMPACT_SCORE_V0_1.md': [
        'aviaimpact draft scores are not faa operational-delay claims',
        'operator review required',
        'empty state is better than invented scoring data',
        'context is not impact',
        'forecast proxy is not observation',
    ],
    'docs/AVIAIMPACT_SOURCE_DOCTRINE.md': [
        'nws alerts are context only',
        'routecast geometry is context/scaffold only',
        'official operational source required for operational delay claims',
        'public release false by default',
        'context match is not impact',
    ],
    'docs/AVIAIMPACT_OPERATOR_REVIEW.md': [
        'operator review required',
        'public release',
        'draft aviaimpact',
        'prohibited',
    ],
}

doc_failures = []
for doc_path, phrases in DOCTRINE_PHRASES.items():
    full = ROOT / doc_path
    if not full.exists():
        doc_failures.append(f'{doc_path}: file missing')
        continue
    text_lower = full.read_text(encoding='utf-8').lower()
    missing_phrases = [p for p in phrases if p not in text_lower]
    if missing_phrases:
        doc_failures.append(f'{doc_path}: missing phrases: {missing_phrases}')

if doc_failures:
    result(FAIL, 'Check 8: Docs contain doctrine language', '; '.join(doc_failures))
else:
    result(PASS, 'Check 8: Docs contain doctrine language')


# ─────────────────────────────────────────────────────────────────────────────
# Check 9: SQL disclaimer present in draft review queue view
# ─────────────────────────────────────────────────────────────────────────────
REQUIRED_DISCLAIMER = (
    'aviaimpact draft scores require operator review '
    'and are not faa operational-delay claims'
)

if sql_file.exists():
    if REQUIRED_DISCLAIMER in sql_text:
        result(PASS, 'Check 9: Draft review queue disclaimer present in SQL')
    else:
        result(FAIL, 'Check 9: Draft review queue disclaimer present in SQL',
               f'Missing: "{REQUIRED_DISCLAIMER}"')
else:
    result(FAIL, 'Check 9: Draft review queue disclaimer present in SQL', 'SQL file missing')


# ─────────────────────────────────────────────────────────────────────────────
# Check 10: D1 files not modified by D2
# ─────────────────────────────────────────────────────────────────────────────
# Warn if D2 files reference D1 table/view names in a way that suggests modification.
# D2 must not alter D1 SQL objects.
D1_TABLES_THAT_D2_MUST_NOT_ALTER = [
    'impact_score_models',
    'impact_score_source_lanes',
    'impact_score_scale_definitions',
    'impact_score_guardrails',
    'impact_score_input_requirements',
    'impact_score_draft_outputs',
]

if sql_file.exists():
    alter_patterns = [
        f'alter table public.{t}' for t in D1_TABLES_THAT_D2_MUST_NOT_ALTER
    ] + [
        f'drop table public.{t}' for t in D1_TABLES_THAT_D2_MUST_NOT_ALTER
    ]
    found_alters = [p for p in alter_patterns if p in sql_text]
    if found_alters:
        result(FAIL, 'Check 10: D2 does not alter D1 tables',
               f'D1 ALTER/DROP found in D2 SQL: {found_alters}')
    else:
        result(PASS, 'Check 10: D2 does not alter D1 tables')
else:
    result(FAIL, 'Check 10: D2 does not alter D1 tables', 'SQL file missing')


# ─────────────────────────────────────────────────────────────────────────────
# Summary
# ─────────────────────────────────────────────────────────────────────────────
print()
passed = sum(1 for s, _ in results if s == PASS)
warned = sum(1 for s, _ in results if s == WARN)
failed = sum(1 for s, _ in results if s == FAIL)
print(f'audit_aviaimpact_score: {passed} passed, {warned} warned, {failed} failed')

if failed:
    sys.exit(1)
sys.exit(0)
