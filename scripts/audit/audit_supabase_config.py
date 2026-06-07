#!/usr/bin/env python3
"""
Supabase placeholder/config audit for TravelCast AviatorGraf Prep.

Checks that js/config.js is internally consistent:
  - Placeholder values  → demoMode: true
  - Real credentials    → demoMode: false
  - No service_role key anywhere

Exits 0 on pass, 1 on fail.
"""
import re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / 'js' / 'config.js'

if not CONFIG.exists():
    print('FAIL: js/config.js not found')
    sys.exit(1)

text = CONFIG.read_text(errors='ignore')
issues = []

# service_role key must never appear in any frontend file
for path in (ROOT / 'js').rglob('*.js'):
    content = path.read_text(errors='ignore')
    if 'service_role' in content.lower():
        issues.append(f'{path.relative_to(ROOT).as_posix()}: service_role key — remove immediately')

# Detect placeholder values
placeholder_url = 'REPLACE_WITH_SUPABASE_URL' in text
placeholder_key = 'REPLACE_WITH_SUPABASE_ANON_KEY' in text

# Detect demo mode setting
demo_true  = bool(re.search(r'demoMode\s*:\s*true',  text))
demo_false = bool(re.search(r'demoMode\s*:\s*false', text))

# Detect apparent real credentials
real_url = bool(re.search(r'supabaseUrl\s*:\s*["\']https://[a-z0-9]+\.supabase\.co["\']', text))
real_key = bool(re.search(r'eyJ[a-zA-Z0-9_-]{20,}', text))

# Consistency rules
if placeholder_url and demo_false:
    issues.append('Placeholder Supabase URL present but demoMode is false — set demoMode: true')
if placeholder_key and demo_false:
    issues.append('Placeholder anon key present but demoMode is false — set demoMode: true')
if real_url and real_key and demo_true:
    issues.append('Real credentials present but demoMode is true — set demoMode: false for live mode')
if real_url and not real_key:
    issues.append('Real Supabase URL set but anon key looks like a placeholder')
if real_key and not real_url:
    issues.append('JWT present but Supabase URL is a placeholder or missing')

if issues:
    print('Supabase config audit FAILED:')
    for i in issues:
        print(f'  {i}')
    sys.exit(1)

# Report state
if real_url and real_key and demo_false:
    state = 'LIVE mode — real credentials, demoMode: false'
elif placeholder_url and demo_true:
    state = 'DEMO mode — placeholders, demoMode: true'
else:
    state = 'UNKNOWN state — review js/config.js manually'

print(f'Supabase config audit passed. Config: {state}')
