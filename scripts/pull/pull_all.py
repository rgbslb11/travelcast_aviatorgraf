#!/usr/bin/env python3
"""Orchestrator — run all TravelCast pull scripts in sequence.

Execution order:
  1. pull_faa_nas_status.py        (FAA NAS operational data → snapshots + feed_runs)
  2. pull_aviationweather_metar_taf.py  (METAR/TAF raw cache + feed_runs)
  3. pull_nws_forecasts.py         (NWS forecast cache + feed_runs)
  4. pull_atcscc_ops_plan.py       (ATCSCC advisory cache + feed_runs)
  5. rebuild_airport_status_snapshots.py  (comprehensive snapshot merge)

Usage:
  python pull_all.py [--dry-run] [--limit N] [--skip-rebuild]
"""
from __future__ import annotations
import argparse, subprocess, sys, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from lib_pull import load_env, utc_now, log

SCRIPTS = [
    'pull_faa_nas_status.py',
    'pull_aviationweather_metar_taf.py',
    'pull_nws_forecasts.py',
    'pull_atcscc_ops_plan.py',
]
REBUILD_SCRIPT = 'rebuild_airport_status_snapshots.py'

PULL_DIR = Path(__file__).parent


def run(script: str, extra_args: list[str]) -> tuple[bool, float]:
    """Run a script in the pull directory. Returns (ok, elapsed_seconds)."""
    cmd = [sys.executable, str(PULL_DIR / script)] + extra_args
    log('script_start', {'script': script, 'args': extra_args})
    t0 = time.monotonic()
    result = subprocess.run(cmd)
    elapsed = round(time.monotonic() - t0, 2)
    ok = result.returncode == 0
    log('script_done', {'script': script, 'ok': ok, 'elapsed_s': elapsed})
    return ok, elapsed


def main() -> None:
    parser = argparse.ArgumentParser(description='Run all TravelCast pull scripts')
    parser.add_argument('--dry-run', action='store_true',
                        help='Pass --dry-run to all scripts — no Supabase writes')
    parser.add_argument('--limit', type=int, default=None,
                        help='Pass --limit N to all scripts')
    parser.add_argument('--skip-rebuild', action='store_true',
                        help='Skip rebuild_airport_status_snapshots.py after individual pulls')
    args = parser.parse_args()

    load_env()
    start = utc_now()
    log('pull_all_start', {'dry_run': args.dry_run, 'limit': args.limit})

    # Build shared extra args list (dry-run and limit apply to all scripts)
    shared: list[str] = []
    if args.dry_run:
        shared.append('--dry-run')
    if args.limit:
        shared += ['--limit', str(args.limit)]

    results: dict[str, dict] = {}

    # Run individual pull scripts
    for script in SCRIPTS:
        ok, elapsed = run(script, shared)
        results[script] = {'ok': ok, 'elapsed_s': elapsed}

    # Run rebuild (always, unless skipped) — uses caches from scripts above
    if not args.skip_rebuild:
        ok, elapsed = run(REBUILD_SCRIPT, shared)
        results[REBUILD_SCRIPT] = {'ok': ok, 'elapsed_s': elapsed}

    # Summary
    passed = [s for s, r in results.items() if r['ok']]
    failed = [s for s, r in results.items() if not r['ok']]
    total_elapsed = sum(r['elapsed_s'] for r in results.values())

    log('pull_all_complete', {
        'started_at': start,
        'finished_at': utc_now(),
        'total_elapsed_s': round(total_elapsed, 2),
        'scripts_run': len(results),
        'passed': len(passed),
        'failed': len(failed),
        'failed_scripts': failed,
        'dry_run': args.dry_run,
    })

    if failed:
        print(f'\n{len(failed)} script(s) failed: {", ".join(failed)}', file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
