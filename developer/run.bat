@echo off
REM ============================================================
REM  MasumPDF Reader - start the app
REM  Double-click this file to open MasumPDF Reader.
REM  You can also drag-and-drop a PDF onto this file to open it.
REM ============================================================

setlocal
cd /d "%~dp0.."

REM If the real built program exists, use it (best).
if exist "app_exe\MasumPDFReader.exe" (
    start "" "app_exe\MasumPDFReader.exe" %*
    goto :end
)

REM Otherwise run the app. If it isn't set up yet, run SETUP first.
if not exist ".venv\Scripts\pythonw.exe" (
    echo.
    echo  The app is not set up yet. Running SETUP.bat ...
    echo.
    call SETUP.bat
    if not exist ".venv\Scripts\pythonw.exe" goto :end
)

start "" ".venv\Scripts\pythonw.exe" main.py %*

:end
endlocal
