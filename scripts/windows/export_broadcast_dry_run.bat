@echo off
REM export_broadcast_dry_run.bat — Run the broadcast batch export in dry-run mode.
REM No export files are written. Logs export decisions to console only.
REM Limits to 5 airports so the dry run is fast and readable.
REM
REM No secrets in this file. Python scripts read .env automatically.

cd /d "%~dp0..\.."
echo ============================================================
echo  TravelCast Broadcast Export — DRY RUN (limit 5)
echo  No files will be written to data\exports\
echo ============================================================
python scripts\export\export_broadcast_batch.py --dry-run --limit 5
echo.
echo --- Dry run complete. Review output above. ---
pause
