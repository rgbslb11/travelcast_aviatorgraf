@echo off
REM refresh_data_live.bat — Run a full live data pull cycle.
REM Writes FAA NAS, AviationWeather, NWS, ATCSCC, RouteCast data to Supabase.
REM
REM DESIGNED FOR WINDOWS TASK SCHEDULER — no pause at end.
REM For double-click use, run refresh_data_dry_run.bat first to verify.
REM
REM No secrets in this file. Python scripts read .env automatically.

cd /d "%~dp0..\.."
python scripts\pull\pull_all.py
