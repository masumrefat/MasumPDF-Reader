"""MasumPDF Reader entry point.

Run with:
    python main.py
    python main.py file1.pdf file2.pdf
"""

import sys
import os

# Make sure local imports work when running from any folder
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon

from utils.constants import APP_NAME, APP_ORG, APP_VERSION
from utils.integrity import verify_or_exit
from ui.main_window import MainWindow


def _make_splash(icons_dir):
    """Build a clean splash screen showing the logo, builder name, license
    and the education-purpose notice. Returns a QSplashScreen or None."""
    import os as _os
    from PySide6.QtWidgets import QSplashScreen
    from PySide6.QtGui import QPixmap, QPainter, QColor, QFont, QBrush, QPen
    from PySide6.QtCore import Qt, QRectF
    from utils.constants import (APP_NAME, APP_VERSION, APP_AUTHOR,
                                 APP_LICENSE, APP_PURPOSE)

    W, H = 520, 360
    canvas = QPixmap(W, H)
    canvas.fill(Qt.transparent)

    p = QPainter(canvas)
    p.setRenderHint(QPainter.Antialiasing, True)
    p.setRenderHint(QPainter.SmoothPixmapTransform, True)

    # white rounded card with a thin border
    p.setBrush(QBrush(QColor("#FFFFFF")))
    p.setPen(QPen(QColor("#E2E4EA"), 1))
    p.drawRoundedRect(QRectF(1, 1, W - 2, H - 2), 16, 16)

    # red accent bar along the top
    p.setPen(Qt.NoPen)
    p.setBrush(QBrush(QColor("#E01E26")))
    p.drawRoundedRect(QRectF(1, 1, W - 2, 8), 4, 4)

    # logo
    logo_path = ""
    for n in ("app_256.png", "app.png", "app.ico"):
        cand = _os.path.join(icons_dir, n)
        if _os.path.exists(cand):
            logo_path = cand
            break
    if logo_path:
        logo = QPixmap(logo_path).scaled(
            104, 104, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        p.drawPixmap((W - logo.width()) // 2, 34, logo)

    p.setPen(QColor("#1B2A4A"))
    p.setFont(QFont("Segoe UI", 20, QFont.Bold))
    p.drawText(QRectF(0, 150, W, 34), Qt.AlignHCenter, APP_NAME)

    p.setPen(QColor("#8A8E98"))
    p.setFont(QFont("Segoe UI", 9))
    p.drawText(QRectF(0, 184, W, 18), Qt.AlignHCenter, f"Version {APP_VERSION}")

    p.setPen(QColor("#2B2D33"))
    p.setFont(QFont("Segoe UI", 10))
    p.drawText(QRectF(0, 214, W, 18), Qt.AlignHCenter,
               f"Created by {APP_AUTHOR}")

    p.setPen(QColor("#6B6F78"))
    p.setFont(QFont("Segoe UI", 9))
    p.drawText(QRectF(0, 236, W, 18), Qt.AlignHCenter,
               f"{APP_LICENSE}  \u00b7  \u00a9 2026")

    p.setPen(QColor("#E01E26"))
    p.setFont(QFont("Segoe UI", 10, QFont.Bold))
    p.drawText(QRectF(0, 270, W, 20), Qt.AlignHCenter, APP_PURPOSE)

    p.setPen(QColor("#9AA0AC"))
    p.setFont(QFont("Segoe UI", 8))
    p.drawText(QRectF(0, H - 34, W, 16), Qt.AlignHCenter,
               "Loading, please wait\u2026")
    p.end()

    splash = QSplashScreen(canvas)
    splash.setWindowFlag(Qt.WindowStaysOnTopHint, True)
    return splash


def main():
    # Verify the author name and license are intact before anything else.
    # If they were tampered with, the app shows an error and stops.
    verify_or_exit()

    # On Windows, set an explicit AppUserModelID so the taskbar shows OUR
    # icon (not the generic Python icon) and groups windows under our app.
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
            "MasumPDFReader.Chowdhury.Masum.Refat")
    except Exception:
        pass  # not on Windows, or not available — safe to ignore

    # High-DPI behavior is on by default in Qt 6, but set the policy explicitly
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationDisplayName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)
    app.setOrganizationName(APP_ORG)

    # Try to load an app icon if one is provided in resources/icons
    icons_dir = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "resources", "icons"
    )
    for name in ("app.ico", "app.png", "app_256.png"):
        icon_path = os.path.join(icons_dir, name)
        if os.path.exists(icon_path):
            app.setWindowIcon(QIcon(icon_path))
            break

    # Show a splash screen right away so the user sees the logo immediately
    # while the (heavy) libraries and main window finish loading. It shows the
    # logo, the builder's name, the license, and the education-purpose notice.
    splash = None
    try:
        splash = _make_splash(icons_dir)
        if splash is not None:
            splash.show()
            app.processEvents()
    except Exception:
        splash = None

    window = MainWindow()
    if splash is not None:
        # keep the splash visible briefly so the info can be read
        from PySide6.QtCore import QTimer
        QTimer.singleShot(1400, lambda: splash.finish(window))
        window.show()
    else:
        window.show()

    # Open any files passed on the command line
    for arg in sys.argv[1:]:
        if arg.lower().endswith(".pdf") and os.path.exists(arg):
            try:
                window.open_pdf(arg)
            except Exception as e:
                print(f"Could not open {arg}: {e}")

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
