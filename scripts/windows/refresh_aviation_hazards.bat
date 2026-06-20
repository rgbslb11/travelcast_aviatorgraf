@echo off
REM refresh_aviation_hazards.bat — Pull aviation hazards only (SIGMET, AIRMET, CWA).
REM Source: AviationWeather.gov
REM Source label: Aviation Weather Truth — AviationWeather.gov
REM
REM No secrets in this file. Python scripts read .env automatically.

cd /d "%~dp0..\.."
echo --- Refreshing Aviation Hazards (SIGMET / AIRMET / CWA) ---
python scripts\pull\pull_aviation_hazards.py
echo.
echo --- Done. ---
pause
