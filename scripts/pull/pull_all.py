#!/usr/bin/env python3
"""Orchestrator — run all TravelCast pull scripts in sequence.

Execution order (main scripts):
  1. pull_faa_nas_status.py              (FAA NAS operational data → snapshots + feed_runs)
  2. pull_aviationweather_metar_taf.py   (METAR/TAF raw cache + feed_runs)
  3. pull_aviation_hazards.py            (SIGMETs, AIRMETs, PIREPs raw cache + feed_runs)
  4. pull_nws_forecasts.py               (NWS forecast cache + feed_runs)
  5. pull_atcscc_ops_plan.py             (ATCSCC advisory cache + feed_runs)
  6. rebuild_airport_status_snapshots.py (comprehensive snapshot merge)

Optional enrichment (runs after main scripts, failure does not affect exit code):
  7. rebuild_routecast_snapshots.py      (RouteCast context builder — requires Supabase)

Optional post-pull export (runs last, failure does not affect exit code):
  8. export_broadcast_batch.py           (batch broadcast package export — requires --export flag)

Usage:
  python pull_all.py [--dry-run] [--limit N] [--skip-rebuild] [--skip-routecast]
                     [--export] [--export-limit N] [--export-all]
"""
from __future__ import annotations
import argparse, subprocess, sys, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from lib_pull import load_env, utc_now, log

SCRIPTS = [
    'pull_faa_nas_status.py',
    'pull_aviationweather_metar_taf.py',
    'pull_aviation_hazards.py',
    'pull_nws_forecasts.py',
    'pull_atcscc_ops_plan.py',
]
REBUILD_SCRIPT = 'rebuild_airport_status_snapshots.py'
ROUTECAST_SCRIPT = 'rebuild_routecast_snapshots.py'

PULL_DIR = Path(__file__).parent
EXPORT_SCRIPT = PULL_DIR.parent / 'export' / 'export_broadcast_batch.py'


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
    parser.add_argument('--skip-routecast', action='store_true',
                        help='Skip the optional rebuild_routecast_snapshots.py enrichment step')
    parser.add_argument('--export', action='store_true',
                        help='Run export_broadcast_batch.py after pulls complete')
    parser.add_argument('--export-limit', type=int, default=None, metavar='N',
                        help='Limit export to N airports (passed to export_broadcast_batch.py)')
    parser.add_argument('--export-all', action='store_true',
                        help='Export individual packages for all airports, not just active-event airports')
    args = parser.parse_args()

    load_env()
    start = utc_now()
    log('pull_all_start', {'dry_run': args.dry_run, 'limit': args.limit, 'export': args.export})

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

    # Optional enrichment: RouteCast context builder
    # Failure here does NOT affect the main exit code or failed-scripts count.
    routecast_ok: bool | None = None
    if not args.skip_routecast:
        log('routecast_enrichment_start', {'script': ROUTECAST_SCRIPT})
        try:
            ok, elapsed = run(ROUTECAST_SCRIPT, shared)
            routecast_ok = ok
            if not ok:
                log('routecast_enrichment_failed', {
                    'script': ROUTECAST_SCRIPT,
                    'elapsed_s': elapsed,
                    'note': 'optional step — main run not affected',
                })
            else:
                log('routecast_enrichment_done', {'script': ROUTECAST_SCRIPT, 'elapsed_s': elapsed})
        except Exception as exc:
            routecast_ok = False
            log('routecast_enrichment_error', {'error': str(exc), 'note': 'optional step — main run not affected'})

    # Optional post-pull export: broadcast batch
    # Failure does NOT affect the pull_all exit code.
    export_ok: bool | None = None
    if args.export:
        export_args: list[str] = []
        if args.dry_run:
            export_args.append('--dry-run')
        if args.export_limit is not None:
            export_args += ['--limit', str(args.export_limit)]
        if args.export_all:
            export_args.append('--all')
        log('export_start', {'script': str(EXPORT_SCRIPT.name), 'args': export_args})
        t0 = time.monotonic()
        try:
            result = subprocess.run([sys.executable, str(EXPORT_SCRIPT)] + export_args)
            elapsed = round(time.monotonic() - t0, 2)
            export_ok = result.returncode == 0
            if export_ok:
                log('export_done', {'script': EXPORT_SCRIPT.name, 'elapsed_s': elapsed, 'dry_run': args.dry_run})
            else:
                log('export_failed', {'script': EXPORT_SCRIPT.name, 'elapsed_s': elapsed,
                                      'returncode': result.returncode,
                                      'note': 'optional step — pull results not affected'})
        except Exception as exc:
            export_ok = False
            log('export_error', {'error': str(exc), 'note': 'optional step — pull results not affected'})

    # Summary (main scripts only — routecast and export are excluded from pass/fail counts)
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
        'routecast_enrichment_ok': routecast_ok,
        'export_ok': export_ok,
    })

    if failed:
        print(f'\n{len(failed)} script(s) failed: {", ".join(failed)}', file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
