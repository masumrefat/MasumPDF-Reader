"""
Tiny launcher for MasumPDF Reader.

This exists so the app can be built into a single MasumPDFReader.exe (via
PyInstaller). A real .exe is what Windows needs to register the app as the
default PDF opener and to pass a double-clicked file path to the app.

Build command (run on Windows, inside this folder, with the venv active):
    pyinstaller --noconfirm --windowed --name MasumPDFReader ^
        --icon resources/icons/app.ico ^
        --add-data "resources;resources" ^
        launcher.py
"""
import os
import sys

# Make sure the app's folder is importable when frozen or run directly.
if getattr(sys, "frozen", False):
    base = os.path.dirname(sys.executable)
else:
    base = os.path.dirname(os.path.abspath(__file__))
if base not in sys.path:
    sys.path.insert(0, base)

from main import main

if __name__ == "__main__":
    main()
