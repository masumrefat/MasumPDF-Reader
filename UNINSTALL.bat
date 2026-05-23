@echo off
REM ============================================================
REM  MasumPDF Reader - Uninstall
REM  Created by Chowdhury Mohammad Masum Refat (MIT License)
REM
REM  Removes the installed app, the Desktop shortcut, the PDF
REM  association, and the Windows "Installed apps" entry.
REM  Run this from the installed folder.
REM ============================================================

setlocal
cd /d "%~dp0"
set "INSTALL_DIR=%~dp0"

echo.
echo   ===========================================
echo    MasumPDF Reader - Uninstall
echo   ===========================================
echo.
echo   This will remove MasumPDF Reader from:
echo     %INSTALL_DIR%
echo.
choice /C YN /M "Are you sure you want to uninstall"
if errorlevel 2 goto :cancel

echo.
echo   Removing Desktop shortcut ...
del /q "%USERPROFILE%\Desktop\MasumPDF Reader.lnk" >nul 2>nul

echo   Removing registry entries ...
reg delete "HKCU\Software\Microsoft\Windows\CurrentVersion\Uninstall\MasumPDFReader" /f >nul 2>nul
reg delete "HKCU\Software\Classes\MasumPDFReader.Document" /f >nul 2>nul
reg delete "HKCU\Software\Classes\.pdf\OpenWithProgids" /v "MasumPDFReader.Document" /f >nul 2>nul
ie4uinit.exe -show >nul 2>nul

echo   Removing program files ...
REM Schedule the install folder to delete itself after this script exits
REM (a folder can't fully delete itself while running from inside it).
set "TARGET=%INSTALL_DIR%"
cd /d "%TEMP%"
start "" cmd /c "timeout /t 2 >nul & rmdir /s /q \"%TARGET%\""

echo.
echo   ===========================================
echo    Uninstalled. MasumPDF Reader has been removed.
echo    (Python was NOT removed - other apps may use it.)
echo   ===========================================
echo.
echo   This window will close in a moment.
timeout /t 3 >nul
goto :end

:cancel
echo.
echo   Uninstall cancelled. Nothing was changed.
echo.
pause

:end
endlocal
