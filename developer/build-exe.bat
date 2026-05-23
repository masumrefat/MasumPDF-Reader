@echo off
REM ============================================================
REM  Build MasumPDFReader.exe  (one click)
REM  Created by Chowdhury Mohammad Masum Refat (MIT License)
REM
REM  This turns the app into a REAL Windows program so it can be
REM  set as the default PDF app and shows YOUR logo on PDF files.
REM
REM  Just double-click this file. It does everything.
REM ============================================================

setlocal
cd /d "%~dp0"

echo.
echo   ===========================================
echo    Building MasumPDFReader.exe
echo    by Chowdhury Mohammad Masum Refat
echo   ===========================================
echo.

REM Make sure the environment exists (install.bat creates it)
if not exist ".venv\Scripts\python.exe" (
    echo   The app environment is missing.
    echo   Please run install.bat first, then run this again.
    echo.
    pause
    exit /b 1
)

echo   Installing the build tool (PyInstaller) ...
".venv\Scripts\python.exe" -m pip install --upgrade pyinstaller >nul 2>nul
if errorlevel 1 (
    echo   [ERROR] Could not install PyInstaller. Check your internet.
    pause
    exit /b 1
)

echo   Building the program. This can take a few minutes ...
".venv\Scripts\pyinstaller.exe" --noconfirm --windowed ^
    --name MasumPDFReader ^
    --icon resources\icons\app.ico ^
    --add-data "resources;resources" ^
    launcher.py
if errorlevel 1 (
    echo   [ERROR] Build failed. Please send the messages above for help.
    pause
    exit /b 1
)

echo.
echo   Copying the program next to the app ...
REM Bring the built exe + its files into the app folder so it can find
REM resources and run from here.
xcopy /e /i /y "dist\MasumPDFReader\*" "%~dp0app_exe\" >nul

echo.
echo   ===========================================
echo    Done!
echo    Your program is here:
echo      %~dp0app_exe\MasumPDFReader.exe
echo.
echo    NEXT STEPS to make it the default PDF app:
echo      1. Right-click set-default.bat  -  Run as administrator
echo      2. Settings ^> Apps ^> Default apps ^> search MasumPDF Reader
echo      3. Set it for .pdf
echo    Your PDFs will then show the MasumPDF logo.
echo   ===========================================
echo.
pause
endlocal
