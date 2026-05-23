@echo off
REM ============================================================
REM  MasumPDF Reader - debug launcher
REM  Same as run.bat but keeps the console window open so you
REM  can read any error messages. Use this if run.bat does
REM  nothing when you double-click it.
REM ============================================================

setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo  No virtual environment found. Run install.bat first.
    pause
    exit /b 1
)

echo  Starting MasumPDF Reader in debug mode ...
echo  Close the app window to return to this console.
echo.

".venv\Scripts\python.exe" main.py %*

echo.
echo  ----------------------------------------
echo  App has closed. Exit code: %errorlevel%
echo  ----------------------------------------
pause
endlocal
