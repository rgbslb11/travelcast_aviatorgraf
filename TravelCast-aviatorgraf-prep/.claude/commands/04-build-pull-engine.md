# 04-build-pull-engine — TravelCast Claude Code Command

Build the server-side/local pulling engine.

Create or update scripts under scripts/pull/.

Required scripts:

- pull_all.py
- pull_faa_nas_status.py
- pull_aviationweather_metar_taf.py
- pull_nws_forecasts.py
- pull_atcscc_ops_plan.py
- rebuild_airport_status_snapshots.py

Rules:

- Use environment variables.
- Do not hardcode secrets.
- Write feed_runs rows.
- Store raw payloads where practical.
- Upsert normalized records.
- Support --dry-run and --limit.
