@echo off
REM export_broadcast_live.bat — Run the broadcast batch export (live, limit 5).
REM Writes dashboard.json, airports.geojson, active_events.placefile,
REM {IATA}_broadcast.json (active-event airports only, up to 5), and manifest.json
REM to data\exports\YYYYMMDD_HHMM\
REM
REM Run after a live data pull for current source-backed packages.
REM Do not commit generated export files.
REM To export all active-event airports, run from a terminal:
REM   python scripts\export\export_broadcast_batch.py
REM To export all 71 airports, run:
REM   python scripts\export\export_broadcast_batch.py --all
REM
REM No secrets in this file. Python scripts read .env automatically.

cd /d "%~dp0..\.."
echo ============================================================
echo  TravelCast Broadcast Export — LIVE (limit 5)
echo  Output: data\exports\YYYYMMDD_HHMM\
echo ============================================================
python scripts\export\export_broadcast_batch.py --limit 5
echo.
echo --- Export complete. Check data\exports\ for output. ---
echo --- Do NOT commit generated export files. ---
pause
