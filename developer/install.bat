@echo off
REM ============================================================
REM  MasumPDF Reader - automatic setup
REM  Created by Chowdhury Mohammad Masum Refat (MIT License)
REM
REM  This installs EVERYTHING needed, start to finish:
REM    1. Checks for Python. If missing, downloads and installs it.
REM    2. Creates a private virtual environment for the app.
REM    3. Installs all required Python packages.
REM    4. Creates a desktop shortcut with the app icon.
REM
REM  Just double-click this file once. No manual steps.
REM ============================================================

setlocal EnableDelayedExpansion
cd /d "%~dp0.."

echo.
echo   ===========================================
echo    MasumPDF Reader - setup
echo    by Chowdhury Mohammad Masum Refat
echo   ===========================================
echo.

REM ---------- 1. Find Python ----------
set "PYEXE="
where py >nul 2>nul && set "PYEXE=py"
if not defined PYEXE (
    where python >nul 2>nul && set "PYEXE=python"
)

if not defined PYEXE (
    echo   Python was not found on this computer.
    echo   I will download and install it for you now.
    echo.
    set "PYINST=%TEMP%\python_masumpdf_setup.exe"
    set "PYURL=https://www.python.org/ftp/python/3.12.4/python-3.12.4-amd64.exe"

    echo   Downloading Python 3.12 ...
    powershell -Command "try { Invoke-WebRequest -Uri '!PYURL!' -OutFile '!PYINST!' -UseBasicParsing } catch { exit 1 }"
    if errorlevel 1 (
        echo.
        echo   [ERROR] Could not download Python automatically.
        echo   Please install Python 3.9+ from https://www.python.org/downloads/
        echo   and tick "Add Python to PATH", then run this again.
        echo.
        pause
        exit /b 1
    )

    echo   Installing Python silently. This may take a minute ...
    "!PYINST!" /quiet InstallAllUsers=1 PrependPath=1 Include_test=0 Include_launcher=1
    del "!PYINST!" >nul 2>nul

    set "PYEXE=py"
    where py >nul 2>nul || set "PYEXE=python"
    where !PYEXE! >nul 2>nul
    if errorlevel 1 (
        echo.
        echo   Python was installed, but this window needs to refresh.
        echo   Please CLOSE this window and run install.bat ONE more time.
        echo.
        pause
        exit /b 0
    )
)

for /f "delims=" %%v in ('!PYEXE! --version 2^>^&1') do echo   Using %%v

REM ---------- 2. Create the virtual environment ----------
echo.
echo   Creating a private environment for the app ...
if not exist ".venv\Scripts\python.exe" (
    !PYEXE! -m venv .venv
    if errorlevel 1 (
        echo   [ERROR] Could not create the virtual environment.
        pause
        exit /b 1
    )
)

REM ---------- 3. Install the required packages ----------
echo   Installing required packages (this can take a few minutes) ...
".venv\Scripts\python.exe" -m pip install --upgrade pip >nul 2>nul
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (
    echo.
    echo   [ERROR] Some packages failed to install.
    echo   Check your internet connection and run install.bat again.
    echo.
    pause
    exit /b 1
)

REM ---------- 4. Make a desktop shortcut with the icon ----------
echo.
echo   Creating a desktop shortcut ...
set "ICON=%~dp0resources\icons\app.ico"
set "TARGET=%~dp0.venv\Scripts\pythonw.exe"
set "WORKDIR=%~dp0"
set "SHORTCUT=%USERPROFILE%\Desktop\MasumPDF Reader.lnk"
powershell -NoProfile -Command "$s=(New-Object -COM WScript.Shell).CreateShortcut('%SHORTCUT%'); $s.TargetPath='%TARGET%'; $s.Arguments='\"%WORKDIR%main.py\"'; $s.WorkingDirectory='%WORKDIR%'; $s.IconLocation='%ICON%'; $s.Description='MasumPDF Reader'; $s.Save()" >nul 2>nul

echo.
echo   ===========================================
echo    Setup complete!
echo    A "MasumPDF Reader" icon is on your Desktop.
echo    You can also double-click run.bat to start.
echo   ===========================================
echo.
pause
endlocal
