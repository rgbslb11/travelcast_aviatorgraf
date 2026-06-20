@echo off
REM rebuild_routecast.bat — Rebuild RouteCast snapshots from current Supabase data.
REM Run after a full pull cycle if RouteCast needs to be refreshed independently.
REM RouteCast is a TravelCast prep summary — not an official FAA route forecast.
REM
REM No secrets in this file. Python scripts read .env automatically.

cd /d "%~dp0..\.."
echo --- Rebuilding RouteCast Snapshots ---
python scripts\pull\rebuild_routecast_snapshots.py
echo.
echo --- Done. ---
pause
