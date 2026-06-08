#!/usr/bin/env python3
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[2]
forbidden = ['official FAA delay forecast from NWS','Baron official source','OpenWeather official DOT','forecast equals operational impact']
issues=[]
SKIP_DIRS = {'__pycache__', '.git', 'node_modules'}
for path in ROOT.rglob('*'):
    if any(p in SKIP_DIRS for p in path.parts): continue
    if not path.is_file() or path.suffix.lower() in {'.png','.jpg','.zip','.pyc'}: continue
    if path.name == 'audit_source_doctrine.py': continue
    text=path.read_text(errors='ignore')
    for phrase in forbidden:
        if phrase.lower() in text.lower(): issues.append(f'{path.relative_to(ROOT)} contains {phrase}')
if issues:
    print('\n'.join(issues)); sys.exit(1)
print('Source doctrine audit passed.')
