#!/usr/bin/env python3
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[2]
required = ['index.html','css/app.css','js/app.js','js/modules/airportDashboard.js','js/exporters/exportGeojson.js','README.md','CLAUDE.md']
missing=[x for x in required if not (ROOT/x).exists()]
if missing:
    print('Missing:', missing); sys.exit(1)
print('File tree audit passed.')
