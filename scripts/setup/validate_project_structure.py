#!/usr/bin/env python3
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[2]
REQUIRED = [
 'CLAUDE.md','PRODUCT_SPEC.md','DATA_CONTRACT.md','SOURCE_DOCTRINE.md','ACCEPTANCE_CRITERIA.md','TASKS.md','README.md','index.html',
 'js/config.js','js/app.js','css/app.css','audit/day_one_readiness_report.md'
]
missing = [f for f in REQUIRED if not (ROOT/f).exists()]
if missing:
    print('Missing required files:')
    for f in missing: print(' -', f)
    sys.exit(1)
print('Project structure validation passed.')
