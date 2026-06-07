#!/usr/bin/env python3
"""
No-secret audit for TravelCast AviatorGraf Prep.

js/config.js may contain the Supabase anon/public JWT. This is
intentional — Supabase's anon key is designed for browser use with
RLS enforcement. Only service_role JWTs are forbidden everywhere.
"""
from pathlib import Path
import base64, json, re, sys

ROOT = Path(__file__).resolve().parents[2]

# Files entirely excluded from secret scanning
IGNORE = {
    '.env.example',
    'templates/env.example.template',
}

# Files permitted to contain a Supabase anon-role JWT (public key by design).
# These files are still checked for service_role JWTs.
ANON_JWT_PERMITTED = {'js/config.js'}

# Literal patterns forbidden everywhere (except IGNORE files)
FORBIDDEN_LITERAL = [
    r'SUPABASE_SERVICE_ROLE_KEY\s*=\s*[^"\n]*[A-Za-z0-9]{12,}',
    r'BARON_SECRET\s*=\s*[^"\n]*[A-Za-z0-9]{12,}',
    r'OPENWEATHER_API_KEY\s*=\s*[^"\n]*[A-Za-z0-9]{12,}',
    r'SYNOPTIC_API_TOKEN\s*=\s*[^"\n]*[A-Za-z0-9]{12,}',
]

# Match complete 3-part JWTs (header.payload.signature) only.
# Avoids false positives from individual base64url segments that start with eyJ
# (e.g. the header {"alg":"HS256"} would match eyJ... but has no role claim).
JWT_RE = re.compile(r'eyJ[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+')


def jwt_role(token):
    """Decode JWT payload, return the role claim or 'unknown' on failure."""
    try:
        parts = token.split('.')
        if len(parts) < 2:
            return 'unknown'
        padded = parts[1] + '=' * (-len(parts[1]) % 4)
        payload = json.loads(base64.b64decode(padded))
        return payload.get('role', 'unknown')
    except Exception:
        return 'unknown'


issues = []

for path in ROOT.rglob('*'):
    if not path.is_file():
        continue
    if path.suffix.lower() in {'.png', '.jpg', '.jpeg', '.zip', '.pyc'}:
        continue
    rel = path.relative_to(ROOT).as_posix()
    if rel in IGNORE or '.git/' in rel:
        continue

    text = path.read_text(errors='ignore')

    # Literal forbidden patterns — flagged in all files
    for pat in FORBIDDEN_LITERAL:
        if re.search(pat, text):
            issues.append((rel, f'forbidden pattern matched: {pat[:60]}'))

    # JWT check — anon JWT allowed only in ANON_JWT_PERMITTED files
    for m in JWT_RE.finditer(text):
        role = jwt_role(m.group())
        if role == 'service_role':
            issues.append((rel, 'service_role JWT detected — remove immediately'))
        elif role in ('anon', 'authenticated') and rel in ANON_JWT_PERMITTED:
            pass  # public anon key in designated config file — permitted
        elif role in ('anon', 'authenticated'):
            issues.append((rel, 'anon JWT found outside js/config.js — move to config only'))
        else:
            issues.append((rel, f'JWT with unrecognised role "{role}" — review'))

if issues:
    print('Potential secret issues:')
    for rel, msg in issues:
        print(f'  {rel}: {msg}')
    sys.exit(1)

print('No-secret audit passed.')
