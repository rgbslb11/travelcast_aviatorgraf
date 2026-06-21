#!/usr/bin/env python3
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[2]
required = [
    'index.html',
    'css/app.css',
    'js/app.js',
    'js/modules/airportDashboard.js',
    'js/exporters/exportGeojson.js',
    'README.md',
    'CLAUDE.md',
    'scripts/export/export_broadcast_batch.py',
    # Phase C3 — ATCSCC Playbook + Aviation Hazard Corridor Matching
    'sql/12_atcscc_playbook_corridor_matching.sql',
    'scripts/pull/pull_atcscc_advisories.py',
    'scripts/match/match_routecast_corridor_hazards.py',
    'scripts/audit/audit_atcscc_corridor_matching.py',
    'docs/ATCSCC_PLAYBOOK_ONTOLOGY.md',
    'docs/AVIATION_HAZARD_CORRIDOR_MATCHING.md',
    'docs/C3_SOURCE_DOCTRINE.md',
    # Phase D1 — Shared Impact Scoring Framework
    'sql/13_shared_impact_scoring_framework.sql',
    'scripts/scoring/shared_impact_scoring.py',
    'scripts/audit/audit_shared_impact_scoring.py',
    'docs/SHARED_IMPACT_SCORING_FRAMEWORK.md',
    'docs/IMPACT_SCORE_SOURCE_DOCTRINE.md',
    'docs/IMPACT_SCORE_GUARDRAILS.md',
    # Phase D2 — AviaImpact Score v0.1
    'sql/14_aviaimpact_score_v0_1.sql',
    'scripts/scoring/aviaimpact_score.py',
    'scripts/audit/audit_aviaimpact_score.py',
    'docs/AVIAIMPACT_SCORE_V0_1.md',
    'docs/AVIAIMPACT_SOURCE_DOCTRINE.md',
    'docs/AVIAIMPACT_OPERATOR_REVIEW.md',
]
missing=[x for x in required if not (ROOT/x).exists()]
if missing:
    print('Missing:', missing); sys.exit(1)
print('File tree audit passed.')
