# FINAL OPERATOR COMMANDS
# TravelCast AviatorGraf Prep — Complete Command Reference

**Phase B1 — Operator Packaging**
Working directory for all commands: `C:\TravelCast AviatorGraf\travelcast_aviatorgraf`

---

## Start the App

```cmd
python -m http.server 8080
```
Or double-click: `scripts\windows\start_app.bat`

Then open: `http://localhost:8080`
Or double-click: `scripts\windows\open_app.bat`

---

## Full Pull Cycle

### Dry run (no Supabase writes — safe to run anytime)
```cmd
python scripts\pull\pull_all.py --dry-run
```
Or: `scripts\windows\refresh_data_dry_run.bat`

### Live pull (writes to Supabase)
```cmd
python scripts\pull\pull_all.py
```
Or: `scripts\windows\refresh_data_live.bat`

### Live pull + broadcast export
```cmd
python scripts\pull\pull_all.py --export
```

### Live pull + export (active-event airports only, limit 5)
```cmd
python scripts\pull\pull_all.py --export --export-limit 5
```

### Live pull + export all airports
```cmd
python scripts\pull\pull_all.py --export --export-all
```

### Dry run + dry-run export
```cmd
python scripts\pull\pull_all.py --dry-run --export
```

---

## Individual Pull Scripts

### FAA NAS Status
```cmd
python scripts\pull\pull_faa_nas_status.py
python scripts\pull\pull_faa_nas_status.py --dry-run
python scripts\pull\pull_faa_nas_status.py --limit 10
```
Source label: `Current Operational Impact — FAA NAS / ATCSCC`

### AviationWeather METAR / TAF
```cmd
python scripts\pull\pull_aviationweather_metar_taf.py
python scripts\pull\pull_aviationweather_metar_taf.py --dry-run
```
Source label: `Aviation Weather Truth — AviationWeather.gov`

### Aviation Hazards (SIGMET / AIRMET / CWA)
```cmd
python scripts\pull\pull_aviation_hazards.py
python scripts\pull\pull_aviation_hazards.py --dry-run
```
Or: `scripts\windows\refresh_aviation_hazards.bat`
Source label: `Aviation Weather Truth — AviationWeather.gov`

### NWS Forecast Proxy
```cmd
python scripts\pull\pull_nws_forecasts.py
python scripts\pull\pull_nws_forecasts.py --dry-run
```
Source label: `Forecast Weather Impact — NWS forecast proxy`
Note: NWS forecast proxy is NOT an official FAA delay forecast.

### ATCSCC Operations Plan
```cmd
python scripts\pull\pull_atcscc_ops_plan.py
python scripts\pull\pull_atcscc_ops_plan.py --dry-run
```
Or: `scripts\windows\refresh_atcscc_ops_plan.bat`

The script auto-discovers advisory URLs from the FAA advisory XML feed. No URL argument is needed for normal operation. To target a specific plan URL:
```cmd
python scripts\pull\pull_atcscc_ops_plan.py --url "https://www.fly.faa.gov/adv/adv_otherdis.jsp?..."
```
Source label: `Current Operational Impact — FAA NAS / ATCSCC`

### Rebuild Airport Status Snapshots
```cmd
python scripts\pull\rebuild_airport_status_snapshots.py
python scripts\pull\rebuild_airport_status_snapshots.py --dry-run
```

### Rebuild RouteCast Snapshots
```cmd
python scripts\pull\rebuild_routecast_snapshots.py
python scripts\pull\rebuild_routecast_snapshots.py --dry-run
```
Or: `scripts\windows\rebuild_routecast.bat`
Note: RouteCast is a TravelCast prep summary — not an official FAA route forecast.

---

## Broadcast Export

### Dry run (no files written, limit 5)
```cmd
python scripts\export\export_broadcast_batch.py --dry-run --limit 5
```
Or: `scripts\windows\export_broadcast_dry_run.bat`

### Live export (active-event airports only, limit 5)
```cmd
python scripts\export\export_broadcast_batch.py --limit 5
```
Or: `scripts\windows\export_broadcast_live.bat`

### Live export (all active-event airports, no limit)
```cmd
python scripts\export\export_broadcast_batch.py
```

### Export with limit
```cmd
python scripts\export\export_broadcast_batch.py --limit 5
```

### Export all airports
```cmd
python scripts\export\export_broadcast_batch.py --all
```

**Output location:** `data\exports\YYYYMMDD_HHMM\`

**Export files:**
- `dashboard.json` — full 71-airport status
- `airports.geojson` — GeoJSON feature collection
- `active_events.placefile` — GRLevelX-style placefile
- `{IATA}_broadcast.json` — per-airport broadcast package
- `manifest.json` — package metadata and source doctrine

**Rule:** Do not commit generated export files.

---

## Audit Suite

### Run all audits
```cmd
python scripts\audit\audit_no_secrets.py
python scripts\audit\audit_source_doctrine.py
python scripts\audit\audit_file_tree.py
```
Or: `scripts\windows\run_audits.bat`

All three audits must pass before any commit or push.

---

## Compile Check (catch syntax errors before running)

```cmd
python -m py_compile scripts\pull\pull_all.py
python -m py_compile scripts\pull\pull_faa_nas_status.py
python -m py_compile scripts\pull\pull_aviationweather_metar_taf.py
python -m py_compile scripts\pull\pull_aviation_hazards.py
python -m py_compile scripts\pull\pull_nws_forecasts.py
python -m py_compile scripts\pull\pull_atcscc_ops_plan.py
python -m py_compile scripts\pull\rebuild_airport_status_snapshots.py
python -m py_compile scripts\pull\rebuild_routecast_snapshots.py
python -m py_compile scripts\export\export_broadcast_batch.py
```

---

## Git Status Check

```cmd
git status
git diff --stat
```

Before committing, verify:
- `js\config.js` is NOT staged (local-only)
- `.env` is NOT staged
- `data\exports\` files are NOT staged
- All 3 audits pass

---

## Source Doctrine Quick Reference

| Source | Label |
|--------|-------|
| FAA NAS / ATCSCC | Current Operational Impact — FAA NAS / ATCSCC |
| AviationWeather.gov | Aviation Weather Truth — AviationWeather.gov |
| NWS / api.weather.gov | Forecast Weather Impact — NWS forecast proxy |
| FAA / OurAirports | Static reference — FAA / OurAirports |
| Baron / OpenWeather | Commercial / Enrichment |
| TravelCast exports | Graphics Output — TravelCast generated package |

NWS forecast proxy is NEVER an official FAA delay forecast.
RouteCast is a TravelCast prep summary, not official FAA routing guidance.
Do not invent aviation, weather, road, closure, alert, delay, or impact data.

---

## Windows Helper Scripts Quick Reference

| Script | Purpose |
|--------|---------|
| `scripts\windows\start_app.bat` | Start local HTTP server on port 8080 |
| `scripts\windows\open_app.bat` | Open app in default browser |
| `scripts\windows\refresh_data_dry_run.bat` | Full pull cycle — dry run |
| `scripts\windows\refresh_data_live.bat` | Full pull cycle — live (Task Scheduler safe) |
| `scripts\windows\refresh_aviation_hazards.bat` | Pull aviation hazards only |
| `scripts\windows\refresh_atcscc_ops_plan.bat` | Pull ATCSCC Ops Plan only |
| `scripts\windows\rebuild_routecast.bat` | Rebuild RouteCast snapshots |
| `scripts\windows\export_broadcast_dry_run.bat` | Broadcast export — dry run |
| `scripts\windows\export_broadcast_live.bat` | Broadcast export — live |
| `scripts\windows\run_audits.bat` | Full audit suite |

Full details: `docs\WINDOWS_OPERATOR_HELPERS.md`
Task Scheduler setup: `docs\WINDOWS_TASK_SCHEDULER.md`
