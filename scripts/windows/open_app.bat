@echo off
REM open_app.bat — Open TravelCast AviatorGraf in the default browser.
REM Requires start_app.bat to already be running on port 8080.
REM
REM No secrets in this file.

echo Opening TravelCast AviatorGraf at http://localhost:8080 ...
start "" http://localhost:8080
