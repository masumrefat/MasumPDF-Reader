@echo off
REM ============================================================
REM  MasumPDF Reader - PROPER INSTALLER
REM  Created by Chowdhury Mohammad Masum Refat (MIT License)
REM
REM  This installs the app to a PERMANENT location, so that:
REM    - all files are copied to the install folder
REM    - you can DELETE the downloaded folder afterwards
REM    - the app keeps working from its installed location
REM    - a new version installs over the old one
REM    - UNINSTALL.bat (in the install folder) removes everything
REM
REM  Right-click this file and choose "Run as administrator" so it
REM  can install into Program Files. (If you can't, it installs into
REM  your user folder instead - that also works.)
REM ============================================================

setlocal EnableDelayedExpansion

REM ---- choose install location ----
REM Try Program Files (needs admin). If not allowed, use LocalAppData.
set "INSTALL_BASE=%ProgramFiles%"
mkdir "%ProgramFiles%\_masum_write_test" >nul 2>nul
if errorlevel 1 (
    set "INSTALL_BASE=%LocalAppData%\Programs"
) else (
    rmdir "%ProgramFiles%\_masum_write_test" >nul 2>nul
)
set "INSTALL_DIR=%INSTALL_BASE%\MasumPDF Reader"
set "SRC=%~dp0"

echo.
echo   ===========================================
echo    MasumPDF Reader - Installer
echo    by Chowdhury Mohammad Masum Refat
echo   ===========================================
echo.
echo   The app will be installed to:
echo     %INSTALL_DIR%
echo.
echo   After installing, you can delete the folder you downloaded.
echo.
pause

REM ---- if updating, remove the old install first (keeps it clean) ----
if exist "%INSTALL_DIR%" (
    echo   Found an existing version - updating it ...
    REM keep the user's environment if present to save time? No - clean update.
    rmdir /s /q "%INSTALL_DIR%\ui" >nul 2>nul
    rmdir /s /q "%INSTALL_DIR%\core" >nul 2>nul
    rmdir /s /q "%INSTALL_DIR%\utils" >nul 2>nul
    rmdir /s /q "%INSTALL_DIR%\resources" >nul 2>nul
)

REM ---- copy all program files to the install location ----
echo   Copying files to the install folder ...
mkdir "%INSTALL_DIR%" >nul 2>nul
xcopy /e /i /y /q "%SRC%core"        "%INSTALL_DIR%\core"        >nul
xcopy /e /i /y /q "%SRC%ui"          "%INSTALL_DIR%\ui"          >nul
xcopy /e /i /y /q "%SRC%utils"       "%INSTALL_DIR%\utils"       >nul
xcopy /e /i /y /q "%SRC%resources"   "%INSTALL_DIR%\resources"   >nul
copy /y "%SRC%main.py"          "%INSTALL_DIR%\" >nul
copy /y "%SRC%launcher.py"      "%INSTALL_DIR%\" >nul
copy /y "%SRC%requirements.txt" "%INSTALL_DIR%\" >nul
copy /y "%SRC%LICENSE"          "%INSTALL_DIR%\" >nul 2>nul
copy /y "%SRC%UNINSTALL.bat"    "%INSTALL_DIR%\" >nul 2>nul

REM ---- find or install Python ----
set "PYEXE="
where py >nul 2>nul && set "PYEXE=py"
if not defined PYEXE ( where python >nul 2>nul && set "PYEXE=python" )
if not defined PYEXE (
    echo.
    echo   Python is needed. Please install it from
    echo   https://www.python.org/downloads/  (tick "Add Python to PATH"),
    echo   restart, then run INSTALL.bat again.
    echo.
    pause
    exit /b 1
)

REM ---- build the environment INSIDE the install folder ----
echo   Setting up the app environment (a few minutes) ...
pushd "%INSTALL_DIR%"
"!PYEXE!" -m venv .venv
".venv\Scripts\python.exe" -m pip install --upgrade pip >nul 2>nul
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (
    echo   [ERROR] Could not install packages - check internet.
    popd & pause & exit /b 1
)
popd

REM ---- desktop shortcut pointing to the INSTALLED app ----
echo   Creating a desktop shortcut ...
set "ICON=%INSTALL_DIR%\resources\icons\app.ico"
set "TARGET=%INSTALL_DIR%\.venv\Scripts\pythonw.exe"
set "SHORTCUT=%USERPROFILE%\Desktop\MasumPDF Reader.lnk"
powershell -NoProfile -Command "$s=(New-Object -COM WScript.Shell).CreateShortcut('%SHORTCUT%'); $s.TargetPath='%TARGET%'; $s.Arguments='\"%INSTALL_DIR%\main.py\"'; $s.WorkingDirectory='%INSTALL_DIR%'; $s.IconLocation='%ICON%'; $s.Description='MasumPDF Reader'; $s.Save()" >nul 2>nul

REM ---- register in Windows "Installed apps" + PDF association ----
echo   Registering the app ...
set "UNINST=%INSTALL_DIR%\UNINSTALL.bat"
reg add "HKCU\Software\Microsoft\Windows\CurrentVersion\Uninstall\MasumPDFReader" /v "DisplayName" /d "MasumPDF Reader" /f >nul
reg add "HKCU\Software\Microsoft\Windows\CurrentVersion\Uninstall\MasumPDFReader" /v "DisplayIcon" /d "%ICON%" /f >nul
reg add "HKCU\Software\Microsoft\Windows\CurrentVersion\Uninstall\MasumPDFReader" /v "Publisher" /d "Chowdhury Mohammad Masum Refat" /f >nul
reg add "HKCU\Software\Microsoft\Windows\CurrentVersion\Uninstall\MasumPDFReader" /v "InstallLocation" /d "%INSTALL_DIR%" /f >nul
reg add "HKCU\Software\Microsoft\Windows\CurrentVersion\Uninstall\MasumPDFReader" /v "UninstallString" /d "\"%UNINST%\"" /f >nul
reg add "HKCU\Software\Classes\MasumPDFReader.Document\DefaultIcon" /ve /d "%ICON%" /f >nul
reg add "HKCU\Software\Classes\MasumPDFReader.Document\shell\open\command" /ve /d "\"%TARGET%\" \"%INSTALL_DIR%\main.py\" \"%%1\"" /f >nul
reg add "HKCU\Software\Classes\.pdf\OpenWithProgids" /v "MasumPDFReader.Document" /t REG_SZ /d "" /f >nul
ie4uinit.exe -show >nul 2>nul

echo.
echo   ===========================================
echo    Installed successfully!
echo.
echo    Installed to: %INSTALL_DIR%
echo    A "MasumPDF Reader" icon is on your Desktop.
echo.
echo    You can now DELETE the folder you downloaded -
echo    the app runs from its installed location.
echo.
echo    To remove it later: open the install folder and run
echo    UNINSTALL.bat, or use Windows Settings ^> Apps.
echo   ===========================================
echo.
pause
endlocal
