@echo off
REM ============================================================
REM  Personal AI OS — launcher
REM
REM  Activates the local virtualenv (if present) and starts main.py.
REM  This script is what Task Scheduler should invoke.
REM ============================================================

setlocal

REM Resolve the project root from this script's location.
set "SCRIPT_DIR=%~dp0"
pushd "%SCRIPT_DIR%\.."

REM Use venv if it exists, otherwise fall back to system Python.
if exist ".venv\Scripts\python.exe" (
    set "PY=.venv\Scripts\python.exe"
) else if exist "venv\Scripts\python.exe" (
    set "PY=venv\Scripts\python.exe"
) else (
    set "PY=python"
)

REM Make sure logs/ exists for stdout redirection.
if not exist "logs" mkdir "logs"

echo [%DATE% %TIME%] Starting Personal AI OS with %PY% >> "logs\runner.log"
"%PY%" main.py >> "logs\runner.log" 2>&1
set "EXITCODE=%ERRORLEVEL%"
echo [%DATE% %TIME%] Exited with code %EXITCODE% >> "logs\runner.log"

popd
endlocal & exit /b %EXITCODE%
