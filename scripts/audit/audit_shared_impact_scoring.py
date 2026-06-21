#!/usr/bin/env python3
"""
scripts/audit/audit_shared_impact_scoring.py
Phase D1 — Shared Impact Scoring Framework audit.

10-check audit for D1 scaffold correctness and doctrine compliance.
Follows project audit pattern.
"""

import sys
import py_compile
import tokenize
import io
import tempfile
import os
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
    """
    Extract lines that contain code tokens (not string/comment-only lines).
    Used for prohibited-pattern scanning that ignores doc strings and comments.
    """
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
# Check 1: Required D1 files exist
# ─────────────────────────────────────────────────────────────────────────────
REQUIRED_FILES = [
    'sql/13_shared_impact_scoring_framework.sql',
    'scripts/scoring/shared_impact_scoring.py',
    'scripts/audit/audit_shared_impact_scoring.py',
    'docs/SHARED_IMPACT_SCORING_FRAMEWORK.md',
    'docs/IMPACT_SCORE_SOURCE_DOCTRINE.md',
    'docs/IMPACT_SCORE_GUARDRAILS.md',
]

missing = [f for f in REQUIRED_FILES if not (ROOT / f).exists()]
if missing:
    result(FAIL, 'Check 1: Required D1 files exist', f'Missing: {missing}')
else:
    result(PASS, 'Check 1: Required D1 files exist')


# ─────────────────────────────────────────────────────────────────────────────
# Check 2: Scoring utility compiles without error
# ─────────────────────────────────────────────────────────────────────────────
scoring_py = ROOT / 'scripts' / 'scoring' / 'shared_impact_scoring.py'
if scoring_py.exists():
    try:
        py_compile.compile(str(scoring_py), doraise=True)
        result(PASS, 'Check 2: Scoring utility compiles')
    except py_compile.PyCompileError as e:
        result(FAIL, 'Check 2: Scoring utility compiles', str(e))
else:
    result(FAIL, 'Check 2: Scoring utility compiles', 'File missing')


# ─────────────────────────────────────────────────────────────────────────────
# Check 3: SQL includes required tables
# ─────────────────────────────────────────────────────────────────────────────
REQUIRED_TABLES = [
    'impact_score_models',
    'impact_score_source_lanes',
    'impact_score_scale_definitions',
    'impact_score_guardrails',
    'impact_score_input_requirements',
    'impact_score_draft_outputs',
]

sql_file = ROOT / 'sql' / '13_shared_impact_scoring_framework.sql'
if sql_file.exists():
    sql_text = sql_file.read_text(encoding='utf-8').lower()
    missing_tables = [t for t in REQUIRED_TABLES if f'create table if not exists public.{t}' not in sql_text]
    if missing_tables:
        result(FAIL, 'Check 3: SQL required tables', f'Missing: {missing_tables}')
    else:
        result(PASS, 'Check 3: SQL required tables')
else:
    result(FAIL, 'Check 3: SQL required tables', 'SQL file missing')


# ─────────────────────────────────────────────────────────────────────────────
# Check 4: SQL includes required views
# ─────────────────────────────────────────────────────────────────────────────
REQUIRED_VIEWS = [
    'v_impact_score_model_registry',
    'v_impact_score_source_lane_registry',
    'v_impact_score_guardrails',
    'v_impact_score_draft_review_queue',
]

if sql_file.exists():
    missing_views = [v for v in REQUIRED_VIEWS if f'create or replace view public.{v}' not in sql_text]
    if missing_views:
        result(FAIL, 'Check 4: SQL required views', f'Missing: {missing_views}')
    else:
        result(PASS, 'Check 4: SQL required views')
else:
    result(FAIL, 'Check 4: SQL required views', 'SQL file missing')


# ─────────────────────────────────────────────────────────────────────────────
# Check 5: Required source lanes seeded in SQL
# ─────────────────────────────────────────────────────────────────────────────
REQUIRED_LANES = [
    'faa_operational_truth',
    'aviation_weather_truth',
    'public_weather_alert_truth',
    'forecast_proxy',
    'routecast_geometry_scaffold',
    'routecast_context_match',
    'atcscc_context_match',
    'manual_operator_review',
]

if sql_file.exists():
    missing_lanes = [lane for lane in REQUIRED_LANES if f"'{lane}'" not in sql_text]
    if missing_lanes:
        result(FAIL, 'Check 5: Required source lanes seeded', f'Missing: {missing_lanes}')
    else:
        result(PASS, 'Check 5: Required source lanes seeded')
else:
    result(FAIL, 'Check 5: Required source lanes seeded', 'SQL file missing')


# ─────────────────────────────────────────────────────────────────────────────
# Check 6: Required guardrails seeded in SQL
# ─────────────────────────────────────────────────────────────────────────────
REQUIRED_GUARDRAILS = [
    'no_invented_source_data',
    'no_nws_alert_causes_faa_delay',
    'no_routecast_geometry_causes_delay',
    'no_context_match_equals_impact_score',
    'no_forecast_proxy_as_observation',
    'no_aviaimpact_output_in_d1',
    'no_roadcast_output_in_d1',
    'operator_review_required_for_public_release',
]

if sql_file.exists():
    missing_guardrails = [g for g in REQUIRED_GUARDRAILS if f"'{g}'" not in sql_text]
    if missing_guardrails:
        result(FAIL, 'Check 6: Required guardrails seeded', f'Missing: {missing_guardrails}')
    else:
        result(PASS, 'Check 6: Required guardrails seeded')
else:
    result(FAIL, 'Check 6: Required guardrails seeded', 'SQL file missing')


# ─────────────────────────────────────────────────────────────────────────────
# Check 7: Docs contain required doctrine language
# ─────────────────────────────────────────────────────────────────────────────
DOCTRINE_PHRASES = {
    'docs/SHARED_IMPACT_SCORING_FRAMEWORK.md': [
        'operator review',
        'no aviaimpact',
        'no roadcast',
        'empty state',
    ],
    'docs/IMPACT_SCORE_SOURCE_DOCTRINE.md': [
        'public alerts are not faa operational truth',
        'routecast geometry is not delay truth',
        'c3 context matches are not impact scores',
        'forecast proxy is not observation',
        'no invented source data',
    ],
    'docs/IMPACT_SCORE_GUARDRAILS.md': [
        'operator review',
        'no aviaimpact',
        'no roadcast',
        'empty state is better than invented',
        'public release',
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
    result(FAIL, 'Check 7: Docs contain doctrine language', '; '.join(doc_failures))
else:
    result(PASS, 'Check 7: Docs contain doctrine language')


# ─────────────────────────────────────────────────────────────────────────────
# Check 8: No prohibited implemented behavior in scoring utility
# ─────────────────────────────────────────────────────────────────────────────
# Scans code token lines (not strings/comments) for prohibited identifiers.
PROHIBITED_IDENTIFIERS = [
    'aviaimpact_score',
    'roadcast_score',
    'aviaimpact_output',
    'roadcast_output',
    'live_score_generate',
    'generate_public_output',
    'auto_public_release',
    'invented_impact',
    'delay_score',
    'route_closure_score',
    'd2_aviaimpact',
    'd3_roadcast',
]

if scoring_py.exists():
    code_lines = _code_token_lines(scoring_py)
    code_text = '\n'.join(code_lines).lower()
    found = [p for p in PROHIBITED_IDENTIFIERS if p in code_text]
    if found:
        result(FAIL, 'Check 8: No prohibited identifiers in scoring utility',
               f'Found: {found}')
    else:
        result(PASS, 'Check 8: No prohibited identifiers in scoring utility')
else:
    result(FAIL, 'Check 8: No prohibited identifiers in scoring utility', 'File missing')


# ─────────────────────────────────────────────────────────────────────────────
# Check 9: SQL contains no INSERT of live score rows
# ─────────────────────────────────────────────────────────────────────────────
# D1 must not insert live output rows into impact_score_draft_outputs.
if sql_file.exists():
    forbidden_inserts = [
        "insert into public.impact_score_draft_outputs",
        "insert into impact_score_draft_outputs",
    ]
    found_inserts = [p for p in forbidden_inserts if p in sql_text]
    if found_inserts:
        result(FAIL, 'Check 9: No live score rows inserted in SQL',
               f'Found prohibited INSERT: {found_inserts}')
    else:
        result(PASS, 'Check 9: No live score rows inserted in SQL')
else:
    result(FAIL, 'Check 9: No live score rows inserted in SQL', 'SQL file missing')


# ─────────────────────────────────────────────────────────────────────────────
# Check 10: Draft output table empty state — warn only (expected in D1)
# ─────────────────────────────────────────────────────────────────────────────
# D1 should not have live scoring output rows — warn if draft output table
# appears to contain INSERT statements for fake scoring rows.
# This check does NOT fail for empty draft output table (that is correct).
if sql_file.exists():
    # Any seed into draft_outputs would be a problem, but empty is correct.
    if "insert into public.impact_score_draft_outputs" in sql_text:
        result(WARN, 'Check 10: Draft output table state',
               'SQL inserts rows into impact_score_draft_outputs — D1 should not seed output rows')
    else:
        result(PASS, 'Check 10: Draft output table state — no live score rows seeded (correct for D1)')
else:
    result(WARN, 'Check 10: Draft output table state', 'SQL file missing — cannot verify')


# ─────────────────────────────────────────────────────────────────────────────
# Summary
# ─────────────────────────────────────────────────────────────────────────────
print()
passed = sum(1 for s, _ in results if s == PASS)
warned = sum(1 for s, _ in results if s == WARN)
failed = sum(1 for s, _ in results if s == FAIL)
print(f'audit_shared_impact_scoring: {passed} passed, {warned} warned, {failed} failed')

if failed:
    sys.exit(1)
sys.exit(0)
