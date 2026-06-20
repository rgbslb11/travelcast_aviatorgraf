# WINDOWS OPERATOR HELPERS
# TravelCast AviatorGraf Prep — scripts/windows/

**Phase B1 — Operator Packaging**
All scripts live in: `scripts\windows\`

---

## Security Rules (Non-Negotiable)

- No secrets are stored in `.bat` files
- Python scripts load credentials automatically from `.env`
- `.env` must remain local-only and must never be committed
- `js/config.js` must remain local-only and must never be committed
- Do not commit generated `data\exports\` files

---

## Script Reference

### start_app.bat
**Purpose:** Start the TravelCast local HTTP server on port 8080.

```
Double-click scripts\windows\start_app.bat
```

- Starts `python -m http.server 8080` from the project root
- The console window stays open while the server is running
- Press `Ctrl+C` to stop the server
- Run `open_app.bat` in a separate window to open the browser

---

### open_app.bat
**Purpose:** Open TravelCast AviatorGraf in the default browser.

```
Double-click scripts\windows\open_app.bat
```

- Opens `http://localhost:8080` in the default browser
- Requires `start_app.bat` to already be running

---

### refresh_data_dry_run.bat
**Purpose:** Run a full pull cycle in dry-run mode (no Supabase writes).

```
Double-click scripts\windows\refresh_data_dry_run.bat
```

- Calls `pull_all.py --dry-run`
- No data is written to Supabase
- Safe to run at any time to verify pull behavior
- Console window stays open after completion (`pause`)

---

### refresh_data_live.bat
**Purpose:** Run a full live data pull cycle. Designed for Task Scheduler.

```
Double-click scripts\windows\refresh_data_live.bat
   — or —
Windows Task Scheduler → Action: run this .bat file
```

- Calls `pull_all.py` (no `--dry-run`)
- Writes FAA NAS, AviationWeather, NWS forecast, ATCSCC, and RouteCast data to Supabase
- **No `pause` at end** — exits cleanly for Task Scheduler automation
- Run `refresh_data_dry_run.bat` first to verify before scheduling

Recommended cadence: every 10 minutes (normal); every 5 minutes (active broadcast prep)

---

### refresh_aviation_hazards.bat
**Purpose:** Pull aviation hazards only (SIGMET / AIRMET / CWA).

```
Double-click scripts\windows\refresh_aviation_hazards.bat
```

- Calls `pull_aviation_hazards.py`
- Source: AviationWeather.gov
- Use when you need a fast hazard refresh without a full pull cycle

---

### refresh_atcscc_ops_plan.bat
**Purpose:** Pull the ATCSCC Operations Plan (auto-discovers advisory URLs).

```
Double-click scripts\windows\refresh_atcscc_ops_plan.bat
```

- Calls `pull_atcscc_ops_plan.py` with no URL argument
- Auto-discovers advisory URLs from the ATCSCC/FAA advisory XML feed — no URL needs to be supplied
- Source: ATCSCC / FAA
- To target a specific plan URL, run from a terminal instead:
  `python scripts\pull\pull_atcscc_ops_plan.py --url "https://www.fly.faa.gov/adv/..."`

---

### rebuild_routecast.bat
**Purpose:** Rebuild RouteCast snapshots from current Supabase data.

```
Double-click scripts\windows\rebuild_routecast.bat
```

- Calls `rebuild_routecast_snapshots.py`
- Use after a full pull cycle if RouteCast needs to be refreshed independently
- RouteCast is a TravelCast prep summary — not an official FAA route forecast

---

### export_broadcast_dry_run.bat
**Purpose:** Run the broadcast batch export in dry-run mode (no files written, limit 5).

```
Double-click scripts\windows\export_broadcast_dry_run.bat
```

- Calls `export_broadcast_batch.py --dry-run --limit 5`
- No files are written to `data\exports\`
- Limit 5 keeps output short and readable
- Logs export decisions to console for review

---

### export_broadcast_live.bat
**Purpose:** Run the broadcast batch export — live, limit 5. Writes packages to `data\exports\`.

```
Double-click scripts\windows\export_broadcast_live.bat
```

- Calls `export_broadcast_batch.py --limit 5`
- Writes up to 5 active-event airport packages to `data\exports\YYYYMMDD_HHMM\`:
  - `dashboard.json`
  - `airports.geojson`
  - `active_events.placefile`
  - `{IATA}_broadcast.json` (active-event airports, up to 5)
  - `manifest.json`
- Run after a live pull cycle for current source-backed packages
- **Do not commit generated export files**
- To export all active-event airports or all 71, run from a terminal:
  `python scripts\export\export_broadcast_batch.py`
  `python scripts\export\export_broadcast_batch.py --all`

---

### run_audits.bat
**Purpose:** Run the full audit suite (no-secrets, source-doctrine, file-tree).

```
Double-click scripts\windows\run_audits.bat
```

- Runs all 3 audits in sequence
- Stops on first failure and prints the failing audit
- All three must pass before committing or pushing changes

---

## Recommended Daily Workflow

```
1. start_app.bat          — start local server (keep window open)
2. open_app.bat           — open browser
3. refresh_data_live.bat  — pull latest data (or let Task Scheduler run it)
4. export_broadcast_live.bat  — export packages when needed
5. run_audits.bat         — run before any commit
```

---

## Tip: Running Individual Source Pulls

For targeted refreshes without `pull_all.py`, run directly from a terminal:

```cmd
cd "C:\TravelCast AviatorGraf\travelcast_aviatorgraf"
python scripts\pull\pull_faa_nas_status.py
python scripts\pull\pull_aviationweather_metar_taf.py
python scripts\pull\pull_aviation_hazards.py
python scripts\pull\pull_nws_forecasts.py
python scripts\pull\pull_atcscc_ops_plan.py
python scripts\pull\rebuild_airport_status_snapshots.py
```

See `docs/FINAL_OPERATOR_COMMANDS.md` for the full command reference.
