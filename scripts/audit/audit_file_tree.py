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
]
missing=[x for x in required if not (ROOT/x).exists()]
if missing:
    print('Missing:', missing); sys.exit(1)
print('File tree audit passed.')
