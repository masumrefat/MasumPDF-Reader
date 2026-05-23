@echo off
REM ============================================================
REM  Register MasumPDF Reader as a PDF opener WITH the app icon
REM  Created by Chowdhury Mohammad Masum Refat (MIT License)
REM
REM  This makes Windows show the MasumPDF Reader logo on PDF
REM  files (instead of the Python logo) and lets you pick the
REM  app under Settings > Default apps.
REM
REM  Run this AFTER install.bat. Right-click > "Run as administrator"
REM  is recommended so the icon applies for all PDFs.
REM ============================================================

setlocal
cd /d "%~dp0"

set "APPDIR=%~dp0"
set "ICON=%APPDIR%resources\icons\app.ico"
set "PYW=%APPDIR%.venv\Scripts\pythonw.exe"
set "MAIN=%APPDIR%main.py"

REM If a real built exe exists, prefer it (best result, carries the icon).
if exist "%APPDIR%app_exe\MasumPDFReader.exe" (
    set "OPENCMD=\"%APPDIR%app_exe\MasumPDFReader.exe\" \"%%1\""
    set "ICONSRC=%APPDIR%app_exe\MasumPDFReader.exe,0"
) else if exist "%APPDIR%MasumPDFReader.exe" (
    set "OPENCMD=\"%APPDIR%MasumPDFReader.exe\" \"%%1\""
    set "ICONSRC=%APPDIR%MasumPDFReader.exe,0"
) else (
    set "OPENCMD=\"%PYW%\" \"%MAIN%\" \"%%1\""
    set "ICONSRC=%ICON%"
)

echo Registering MasumPDF Reader as a PDF handler...

REM Define our document type, its icon, and the open command
reg add "HKCU\Software\Classes\MasumPDFReader.Document" /ve /d "PDF Document" /f >nul
reg add "HKCU\Software\Classes\MasumPDFReader.Document\DefaultIcon" /ve /d "%ICONSRC%" /f >nul
reg add "HKCU\Software\Classes\MasumPDFReader.Document\shell\open\command" /ve /d "%OPENCMD%" /f >nul

REM Add ourselves to the "Open with" list for .pdf
reg add "HKCU\Software\Classes\.pdf\OpenWithProgids" /v "MasumPDFReader.Document" /t REG_SZ /d "" /f >nul

REM Tell Windows the icons changed so it refreshes
echo Refreshing icons...
ie4uinit.exe -show >nul 2>nul

echo.
echo   Done.
echo   Now open: Settings ^> Apps ^> Default apps,
echo   search "MasumPDF Reader", and set it for .pdf files.
echo   Your PDF files will then show the MasumPDF logo.
echo.
pause
endlocal
