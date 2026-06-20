@echo off
REM ============================================================
REM  Personal AI OS — one-click launcher (Windows).
REM  Double-click this file. It starts the engine + control
REM  server and opens the dashboard in your browser.
REM ============================================================
setlocal
cd /d "%~dp0"

REM Pick the project virtualenv python if present, else system python.
if exist ".venv\Scripts\python.exe" (
    set "PY=.venv\Scripts\python.exe"
) else if exist "venv\Scripts\python.exe" (
    set "PY=venv\Scripts\python.exe"
) else (
    set "PY=python"
)

REM Open the dashboard shortly after the server boots.
start "" /b cmd /c "timeout /t 2 >nul & start """" http://localhost:8800"

echo Starting Personal AI OS... (close this window to stop everything)
"%PY%" control_server.py

endlocal
