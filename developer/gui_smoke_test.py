"""GUI smoke test for MasumPDF Reader.

Runs the main window and Research Library for a few seconds to confirm that
PySide6/Qt can create the UI. This is mainly for developer testing.

Windows:
    set QT_QPA_PLATFORM=
    python developer/gui_smoke_test.py

Headless Linux/CI:
    QT_QPA_PLATFORM=offscreen python developer/gui_smoke_test.py
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

try:
    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import QTimer
except Exception as exc:
    print("PySide6 import failed:", exc)
    raise SystemExit(1)

from utils.constants import APP_VERSION
from ui.main_window import MainWindow
from core.research_library import ResearchLibrary
from ui.library_panel import LibraryPanel


def main() -> int:
    app = QApplication([])
    print(f"MasumPDF Reader version: {APP_VERSION}")

    main_window = MainWindow()
    main_window.show()
    app.processEvents()
    print(f"Main window OK: {main_window.windowTitle()} {main_window.width()}x{main_window.height()}")

    if getattr(main_window, "optional_panel_dock", None) is not None:
        print("Optional panel should be disabled but is present")
        return 1
    print("Optional panel disabled OK")

    tab = main_window.current_tab()
    if tab is not None:
        if not hasattr(tab, "tools_sidebar") or not hasattr(tab, "right_info_panel"):
            print("Fixed sidebars/reading rail missing")
            return 1
        print("Fixed sidebar OK: left All Tools; pages/comments integrated into right reading rail")

    library = ResearchLibrary()
    library_panel = LibraryPanel(library)
    library_panel.show()
    app.processEvents()
    print(f"Research Library OK: {library_panel.windowTitle()} {library_panel.width()}x{library_panel.height()}")

    QTimer.singleShot(1500, app.quit)
    app.exec()
    print("GUI smoke test passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
