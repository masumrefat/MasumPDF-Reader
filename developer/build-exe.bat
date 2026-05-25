@echo off
REM ============================================================
REM  Build MasumPDFReader.exe  (includes PySide6/Qt6)
REM  Created by Chowdhury Mohammad Masum Refat (MIT License)
REM
REM  This creates a standalone Windows app folder:
REM      developer\app_exe\MasumPDFReader.exe
REM
REM  Important:
REM    - PySide6 is installed from requirements.txt.
REM    - PyInstaller is told to collect PySide6 and shiboken6 files.
REM    - The output is an ONEDIR app, which is more reliable for Qt apps
REM      than one-file mode.
REM ============================================================

setlocal EnableDelayedExpansion
cd /d "%~dp0.."

echo.
echo   ===========================================
echo    Building MasumPDFReader.exe with PySide6
echo    by Chowdhury Mohammad Masum Refat
echo   ===========================================
echo.

REM Make sure the environment exists (developer\install.bat creates it)
if not exist ".venv\Scripts\python.exe" (
    echo   The app environment is missing.
    echo   Please run developer\install.bat first, then run this again.
    echo.
    pause
    exit /b 1
)

echo   Updating pip and installing all app dependencies ...
".venv\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 (
    echo   [ERROR] Could not update pip.
    pause
    exit /b 1
)

".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (
    echo   [ERROR] Could not install requirements.txt.
    echo   PySide6 must install successfully before building the exe.
    pause
    exit /b 1
)

echo.
echo   Installing/Updating PyInstaller and Qt hooks ...
".venv\Scripts\python.exe" -m pip install --upgrade pyinstaller pyinstaller-hooks-contrib
if errorlevel 1 (
    echo   [ERROR] Could not install PyInstaller. Check your internet.
    pause
    exit /b 1
)

echo.
echo   Checking that PySide6 imports correctly ...
".venv\Scripts\python.exe" -c "import PySide6, shiboken6; print('PySide6 OK:', PySide6.__version__)"
if errorlevel 1 (
    echo   [ERROR] PySide6 is not installed correctly in .venv.
    pause
    exit /b 1
)

echo.
echo   Cleaning old build files ...
rmdir /s /q build 2>nul
rmdir /s /q dist 2>nul
rmdir /s /q "%~dp0app_exe" 2>nul

echo.
echo   Building the program. This can take a few minutes ...
".venv\Scripts\pyinstaller.exe" --noconfirm --clean --windowed ^
    --name MasumPDFReader ^
    --icon resources\icons\app.ico ^
    --add-data "resources;resources" ^
    --collect-all PySide6 ^
    --collect-all shiboken6 ^
    --collect-all fitz ^
    --hidden-import PySide6.QtPrintSupport ^
    --hidden-import PySide6.QtSvg ^
    --hidden-import PySide6.QtXml ^
    launcher.py
if errorlevel 1 (
    echo   [ERROR] Build failed. Please send the messages above for help.
    pause
    exit /b 1
)

echo.
echo   Building the separate updater program ...
".venv\Scripts\pyinstaller.exe" --noconfirm --clean --console ^
    --name UpdaterRunner ^
    updater_runner.py
if errorlevel 1 (
    echo   [ERROR] Updater build failed.
    pause
    exit /b 1
)

echo.
echo   Copying the built app folder ...
xcopy /e /i /y "dist\MasumPDFReader\*" "%~dp0app_exe\" >nul
if errorlevel 1 (
    echo   [ERROR] Could not copy built files.
    pause
    exit /b 1
)

echo.
echo   Copying updater into the app folder ...
if exist "dist\UpdaterRunner\UpdaterRunner.exe" (
    xcopy /e /i /y "dist\UpdaterRunner\*" "%~dp0app_exe\" >nul
) else (
    echo   [ERROR] UpdaterRunner.exe was not created.
    pause
    exit /b 1
)
copy /y "VERSION.txt" "%~dp0app_exe\VERSION.txt" >nul 2>nul

echo.
echo   Testing that the exe file exists ...
if not exist "%~dp0app_exe\MasumPDFReader.exe" (
    echo   [ERROR] MasumPDFReader.exe was not created.
    pause
    exit /b 1
)

echo.
echo   ===========================================
echo    Done!
echo    Standalone app folder:
echo      %~dp0app_exe\
echo.
echo    Main exe:
echo      %~dp0app_exe\MasumPDFReader.exe
echo.
echo    PySide6/Qt6 files are bundled inside this app_exe folder.
echo    UpdaterRunner.exe is also bundled for automatic updates.
echo    Keep the whole app_exe folder together; do not move only the exe.
echo.
echo    For GitHub automatic updates:
echo      1. Zip the whole developer\app_exe folder.
echo      2. Upload that zip as a GitHub Release asset.
echo      3. Use a newer tag such as v1.0.3.
echo   ===========================================
echo.
pause
endlocal
