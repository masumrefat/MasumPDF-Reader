"""
Integrity / authorship protection.

This module verifies that the application's author name and license have not
been altered. The author name (Chowdhury Mohammad Masum Refat) and the MIT
license are part of this software's identity. If they are changed, the
verification below fails and the application refuses to start.

NOTE (honest): this is a deterrent, not unbreakable copy protection. This is
open-source Python, so anyone with the source could in principle also edit the
expected hash below or remove the call to verify_integrity(). What this does
guarantee is that you cannot simply rename the author in constants.py (or swap
the license) and have the app keep working — the values, the salt, and this
hash must all agree, so a casual change breaks the app exactly as intended.
"""

import hashlib

from utils.constants import APP_NAME, APP_AUTHOR, APP_LICENSE

# Salt ties the hash to this build so the protected string can't be trivially
# recomputed by editing one constant.
_SALT = "MasumPDF-integrity-v1"

# Precomputed SHA-256 of f"{_SALT}|{APP_NAME}|{APP_AUTHOR}|{APP_LICENSE}"
# with the correct, official values:
#   APP_NAME    = "MasumPDF Reader"
#   APP_AUTHOR  = "Chowdhury Mohammad Masum Refat"
#   APP_LICENSE = "MIT License"
_EXPECTED_HASH = "2e47bbf21bf587cf0e9c374b6a5445a101a5e21f013df08687dc42ebddf81d0c"

# The one true author. Kept here as a second, independent check so that even
# if someone edits constants.py, this file still holds the correct name.
_OFFICIAL_AUTHOR = "Chowdhury Mohammad Masum Refat"
_OFFICIAL_LICENSE = "MIT License"


def _current_hash() -> str:
    combined = f"{_SALT}|{APP_NAME}|{APP_AUTHOR}|{APP_LICENSE}"
    return hashlib.sha256(combined.encode("utf-8")).hexdigest()


def is_intact() -> bool:
    """Return True only if the author name and license are unchanged."""
    if APP_AUTHOR != _OFFICIAL_AUTHOR:
        return False
    if APP_LICENSE != _OFFICIAL_LICENSE:
        return False
    return _current_hash() == _EXPECTED_HASH


def verify_or_exit():
    """Check integrity. If the author/license was tampered with, show an
    error and stop the application.

    Returns the verified author name on success.
    """
    if is_intact():
        return APP_AUTHOR

    message = (
        "Integrity check failed.\n\n"
        "The author name or license of this application has been modified.\n"
        "This software was created by Chowdhury Mohammad Masum Refat and is\n"
        "released under the MIT License. It will not run while that\n"
        "information is altered.\n\n"
        "Please restore the original author name and license."
    )

    # Try to show a graphical error; fall back to console + hard exit.
    try:
        from PySide6.QtWidgets import QApplication, QMessageBox
        app = QApplication.instance()
        if app is not None:
            # Only show a modal dialog if a GUI app is actually running.
            box = QMessageBox()
            box.setIcon(QMessageBox.Critical)
            box.setWindowTitle("MasumPDF Reader — Integrity Error")
            box.setText(message)
            box.exec()
        else:
            print(message)
    except Exception:
        print(message)

    raise SystemExit(1)
