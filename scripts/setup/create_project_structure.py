#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DIRS = [
    '.claude/commands','prompts','templates','sql','scripts/setup','scripts/load','scripts/pull','scripts/audit',
    'css','js/modules','js/exporters','js/sampleData','data/reference','data/exports','docs','audit'
]

for d in DIRS:
    (ROOT / d).mkdir(parents=True, exist_ok=True)
print(f"Verified project structure under {ROOT}")
