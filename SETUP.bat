@echo off
REM ============================================================
REM  MasumPDF Reader - COMPLETE one-click setup
REM  Created by Chowdhury Mohammad Masum Refat (MIT License)
REM
REM  Double-click this ONE file. It does everything:
REM    1. Installs Python if it is missing.
REM    2. Installs all required packages.
REM    3. Builds a real MasumPDFReader.exe (your logo, faster start).
REM    4. Creates a Desktop shortcut with your logo.
REM    5. Registers the app so you can set it as the default PDF app.
REM ============================================================

setlocal EnableDelayedExpansion
cd /d "%~dp0"

echo.
echo   ===========================================
echo    MasumPDF Reader - full setup
echo    by Chowdhury Mohammad Masum Refat
echo   ===========================================
echo.

REM ---------- 1. Find or install Python ----------
REM The app needs Python 3.9 or newer.
set "PYEXE="
where py >nul 2>nul && set "PYEXE=py"
if not defined PYEXE ( where python >nul 2>nul && set "PYEXE=python" )

REM If Python is present, check its version is new enough (3.9+).
set "PYOK="
if defined PYEXE (
    for /f "tokens=2 delims= " %%v in ('"!PYEXE!" --version 2^>^&1') do set "PYVER=%%v"
    for /f "tokens=1,2 delims=." %%a in ("!PYVER!") do (
        set "PYMAJ=%%a"
        set "PYMIN=%%b"
    )
    REM accept Python 3.9 or newer (or any version 4+)
    if !PYMAJ! GTR 3 set "PYOK=1"
    if !PYMAJ! EQU 3 if !PYMIN! GEQ 9 set "PYOK=1"
)

if defined PYOK (
    echo   [1/5] Python !PYVER! found - already good, skipping install.
) else (
    if defined PYEXE (
        echo   [1/5] Python !PYVER! is too old ^(need 3.9+^) - installing a newer one ...
    ) else (
        echo   [1/5] Python not found - installing it ...
    )
    set "PYEXE="
    set "PYINST="
    REM If a Python installer happens to be bundled here, use it (offline).
    REM Normally it is downloaded from the web below.
    if exist "%~dp0python-bundled.exe" (
        echo         Using the bundled Python installer.
        set "PYINST=%~dp0python-bundled.exe"
    )

    REM Download Python from python.org (needs internet).
    if not defined PYINST (
        echo         Downloading Python from python.org ^(needs internet^) ...
        set "PYINST=%TEMP%\python_masumpdf_setup.exe"
        set "PYURL=https://www.python.org/ftp/python/3.12.4/python-3.12.4-amd64.exe"
        powershell -Command "try { Invoke-WebRequest -Uri '!PYURL!' -OutFile '!PYINST!' -UseBasicParsing } catch { exit 1 }"
        if errorlevel 1 (
            echo.
            echo   [ERROR] Could not download Python ^(no internet, or it is blocked^).
            echo   PLEASE: go to https://www.python.org/downloads/ , install Python,
            echo   TICK "Add Python to PATH", restart, then run SETUP.bat again.
            echo.
            pause
            exit /b 1
        )
    )

    echo         Installing Python, please wait ...
    "!PYINST!" /quiet InstallAllUsers=1 PrependPath=1 Include_test=0 Include_launcher=1
    REM only delete if it was a downloaded temp copy (keep the bundled one)
    if /I not "!PYINST!"=="%~dp0python-bundled.exe" del "!PYINST!" >nul 2>nul

    REM Find Python directly where the installer put it (PATH not refreshed yet)
    set "PYEXE="
    where py >nul 2>nul && set "PYEXE=py"
    if not defined PYEXE ( where python >nul 2>nul && set "PYEXE=python" )
    for %%P in (Python314 Python313 Python312 Python311 Python310) do (
        if not defined PYEXE if exist "%ProgramFiles%\%%P\python.exe" set "PYEXE=%ProgramFiles%\%%P\python.exe"
        if not defined PYEXE if exist "%LocalAppData%\Programs\Python\%%P\python.exe" set "PYEXE=%LocalAppData%\Programs\Python\%%P\python.exe"
    )

    if not defined PYEXE (
        echo.
        echo   Python was installed, but Windows needs to refresh.
        echo   Please CLOSE this window and double-click SETUP.bat ONE more time.
        echo.
        pause
        exit /b 0
    )
    echo   [1/5] Python installed.
)
for /f "delims=" %%v in ('"!PYEXE!" --version 2^>^&1') do echo         Using %%v

REM ---------- 2. Environment + packages ----------
echo   [2/5] Setting up the app and installing packages ...

REM Warn if the folder path is very long (Windows fails past ~260 chars).
set "HERE=%CD%"
call :strlen HERE PATHLEN
if !PATHLEN! GTR 90 (
    echo.
    echo   [WARNING] This folder is in a very long / deeply-nested path:
    echo     %CD%
    echo   Windows may fail to install with long paths.
    echo   TIP: Move this folder to a short location like  C:\masum  and
    echo        run SETUP.bat again from there.
    echo.
    choice /C YN /M "Continue anyway"
    if errorlevel 2 exit /b 0
)

if not exist ".venv\Scripts\python.exe" (
    "!PYEXE!" -m venv .venv
    if errorlevel 1 ( echo   [ERROR] Could not create environment. & pause & exit /b 1 )
)
".venv\Scripts\python.exe" -m pip install --upgrade pip >nul 2>nul
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (
    echo.
    echo   [ERROR] Package install failed.
    echo   Most common causes:
    echo     1. No internet connection.
    echo     2. The folder path is too long ^(see warning above^).
    echo        Move the folder to  C:\masum  and try again.
    echo.
    pause
    exit /b 1
)

REM ---------- 3. Build the real .exe ----------
echo   [3/5] Building MasumPDFReader.exe (a few minutes, please wait) ...
".venv\Scripts\python.exe" -m pip install --upgrade pyinstaller >nul 2>nul
".venv\Scripts\pyinstaller.exe" --noconfirm --windowed --name MasumPDFReader --icon resources\icons\app.ico --add-data "resources;resources" launcher.py >nul 2>nul
if exist "dist\MasumPDFReader\MasumPDFReader.exe" (
    xcopy /e /i /y "dist\MasumPDFReader\*" "%~dp0app_exe\" >nul
    set "EXEPATH=%~dp0app_exe\MasumPDFReader.exe"
    echo         Built: app_exe\MasumPDFReader.exe
) else (
    echo         [note] Could not build the .exe. The app will still run via the
    echo                shortcut, but the "default PDF app" icon needs the .exe.
    set "EXEPATH="
)

REM ---------- 4. Desktop shortcut ----------
echo   [4/5] Creating a desktop shortcut ...
set "ICON=%~dp0resources\icons\app.ico"
if defined EXEPATH (
    set "TARGET=!EXEPATH!"
    set "ARGS="
    set "WORKDIR=%~dp0app_exe"
) else (
    set "TARGET=%~dp0.venv\Scripts\pythonw.exe"
    set "ARGS=\"%~dp0main.py\""
    set "WORKDIR=%~dp0"
)
set "SHORTCUT=%USERPROFILE%\Desktop\MasumPDF Reader.lnk"
powershell -NoProfile -Command "$s=(New-Object -COM WScript.Shell).CreateShortcut('%SHORTCUT%'); $s.TargetPath='!TARGET!'; $s.Arguments='!ARGS!'; $s.WorkingDirectory='!WORKDIR!'; $s.IconLocation='%ICON%'; $s.Description='MasumPDF Reader'; $s.Save()" >nul 2>nul

REM ---------- 5. Register as a PDF opener (with your icon) ----------
echo   [5/5] Registering as a PDF opener ...
if defined EXEPATH (
    set "OPENCMD=\"!EXEPATH!\" \"%%1\""
    set "ICONSRC=!EXEPATH!,0"
) else (
    set "OPENCMD=\"%~dp0.venv\Scripts\pythonw.exe\" \"%~dp0main.py\" \"%%1\""
    set "ICONSRC=%ICON%"
)
reg add "HKCU\Software\Classes\MasumPDFReader.Document" /ve /d "PDF Document" /f >nul
reg add "HKCU\Software\Classes\MasumPDFReader.Document\DefaultIcon" /ve /d "!ICONSRC!" /f >nul
reg add "HKCU\Software\Classes\MasumPDFReader.Document\shell\open\command" /ve /d "!OPENCMD!" /f >nul
reg add "HKCU\Software\Classes\.pdf\OpenWithProgids" /v "MasumPDFReader.Document" /t REG_SZ /d "" /f >nul
ie4uinit.exe -show >nul 2>nul

echo.
echo   ===========================================
echo    All done!
echo    - A "MasumPDF Reader" icon is on your Desktop.
if defined EXEPATH (
    echo    - To make PDFs show your logo: open
    echo      Settings ^> Apps ^> Default apps ^> search "MasumPDF Reader"
    echo      and set it for .pdf  ^(then restart once^).
) else (
    echo    - Open the app from the Desktop icon.
)
echo   ===========================================
echo.
pause
endlocal
goto :eof

REM ---- helper: measure length of a variable ----
:strlen <varname> <resultvar>
setlocal EnableDelayedExpansion
set "s=!%~1!"
set "len=0"
for /L %%A in (12,-1,0) do (
    set /a "len|=1<<%%A"
    for %%B in (!len!) do if "!s:~%%B,1!"=="" set /a "len&=~1<<%%A"
)
endlocal & set "%~2=%len%"
goto :eof
