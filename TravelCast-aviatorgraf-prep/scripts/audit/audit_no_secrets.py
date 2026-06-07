#!/usr/bin/env python3
from pathlib import Path
import re, sys
ROOT = Path(__file__).resolve().parents[2]
FORBIDDEN = [
    r'SUPABASE_SERVICE_ROLE_KEY\s*=\s*[^"\n]*[A-Za-z0-9]{12,}',
    r'BARON_SECRET\s*=\s*[^"\n]*[A-Za-z0-9]{12,}',
    r'OPENWEATHER_API_KEY\s*=\s*[^"\n]*[A-Za-z0-9]{12,}',
    r'SYNOPTIC_API_TOKEN\s*=\s*[^"\n]*[A-Za-z0-9]{12,}',
    r'eyJ[a-zA-Z0-9_-]{20,}',
]
IGNORE = {'.env.example','templates/env.example.template'}
issues=[]
for path in ROOT.rglob('*'):
    if not path.is_file() or path.suffix.lower() in {'.png','.jpg','.jpeg','.zip'}: continue
    rel=str(path.relative_to(ROOT))
    if rel in IGNORE: continue
    text=path.read_text(errors='ignore')
    for pat in FORBIDDEN:
        if re.search(pat, text): issues.append((rel, pat))
if issues:
    print('Potential secret issues:')
    for rel, pat in issues: print(rel, pat)
    sys.exit(1)
print('No-secret audit passed.')
