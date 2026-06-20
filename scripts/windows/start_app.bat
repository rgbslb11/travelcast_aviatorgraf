@echo off
REM start_app.bat — Start the TravelCast local HTTP server on port 8080.
REM The server window stays open while running. Close it to stop the server.
REM Run open_app.bat in a second window to launch the browser.
REM
REM No secrets in this file. Python scripts read .env automatically.

cd /d "%~dp0..\.."
echo ============================================================
echo  TravelCast AviatorGraf — Local Server
echo  http://localhost:8080
echo  Press Ctrl+C to stop.
echo ============================================================
python -m http.server 8080
