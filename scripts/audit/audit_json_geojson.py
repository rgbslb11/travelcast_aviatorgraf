#!/usr/bin/env python3
from pathlib import Path
import json, sys
ROOT = Path(__file__).resolve().parents[2]
issues=[]
for path in list((ROOT/'data').rglob('*.json')) + list((ROOT/'data').rglob('*.geojson')):
    try:
        obj=json.loads(path.read_text())
        if path.suffix == '.geojson':
            if obj.get('type') != 'FeatureCollection' or not isinstance(obj.get('features'), list):
                issues.append(f'{path}: invalid FeatureCollection')
    except Exception as e:
        issues.append(f'{path}: {e}')
if issues:
    print('JSON/GeoJSON audit failed:')
    print('\n'.join(issues)); sys.exit(1)
print('JSON/GeoJSON audit passed.')
