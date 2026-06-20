@echo off
REM run_audits.bat — Run the full TravelCast audit suite.
REM Checks: no secrets, source doctrine compliance, file tree integrity.
REM All three audits must pass before committing or pushing changes.
REM
REM No secrets in this file. Python scripts read .env automatically.

cd /d "%~dp0..\.."
echo ============================================================
echo  TravelCast Audit Suite
echo ============================================================
echo.
echo [1/3] No-Secret Audit...
python scripts\audit\audit_no_secrets.py
if %errorlevel% neq 0 (
    echo FAIL: audit_no_secrets.py returned errors. Stop and review.
    pause
    exit /b 1
)

echo.
echo [2/3] Source Doctrine Audit...
python scripts\audit\audit_source_doctrine.py
if %errorlevel% neq 0 (
    echo FAIL: audit_source_doctrine.py returned errors. Stop and review.
    pause
    exit /b 1
)

echo.
echo [3/3] File Tree Audit...
python scripts\audit\audit_file_tree.py
if %errorlevel% neq 0 (
    echo FAIL: audit_file_tree.py returned errors. Stop and review.
    pause
    exit /b 1
)

echo.
echo ============================================================
echo  All audits passed.
echo ============================================================
pause
