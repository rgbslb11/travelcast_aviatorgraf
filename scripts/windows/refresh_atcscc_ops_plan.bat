@echo off
REM refresh_atcscc_ops_plan.bat — Pull the ATCSCC Operations Plan.
REM Source: ATCSCC / FAA
REM Source label: Current Operational Impact — FAA NAS / ATCSCC
REM
REM The script auto-discovers advisory URLs from the ATCSCC advisory XML feed.
REM No URL argument is required for normal operation.
REM
REM To target a specific ops-plan URL, run from a terminal instead:
REM   python scripts\pull\pull_atcscc_ops_plan.py --url "https://www.fly.faa.gov/adv/adv_otherdis.jsp?..."
REM
REM No secrets in this file. Python scripts read .env automatically.

cd /d "%~dp0..\.."
echo --- Refreshing ATCSCC Operations Plan ---
echo Script will auto-discover advisory URLs from the FAA advisory feed.
echo To target a specific URL, run pull_atcscc_ops_plan.py --url "..." from a terminal.
echo.
python scripts\pull\pull_atcscc_ops_plan.py
echo.
echo --- Done. ---
pause
