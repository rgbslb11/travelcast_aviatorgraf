@echo off
REM refresh_data_dry_run.bat — Run a full pull cycle in dry-run mode.
REM No data is written to Supabase. Safe to run at any time.
REM
REM No secrets in this file. Python scripts read .env automatically.

cd /d "%~dp0..\.."
echo ============================================================
echo  TravelCast Data Refresh — DRY RUN
echo  No Supabase writes will occur.
echo ============================================================
python scripts\pull\pull_all.py --dry-run
echo.
echo --- Dry run complete. Review output above. ---
pause
