"""Small file/path helpers."""

import os
import shutil
import platform
import subprocess
from pathlib import Path


def human_size(num_bytes: int) -> str:
    """Format a byte count as a human-readable string."""
    if num_bytes is None:
        return "—"
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if num_bytes < 1024.0:
            return f"{num_bytes:.1f} {unit}"
        num_bytes /= 1024.0
    return f"{num_bytes:.1f} PB"


def file_size(path: str) -> int:
    try:
        return os.path.getsize(path)
    except OSError:
        return 0


def file_exists(path: str) -> bool:
    return bool(path) and os.path.isfile(path)


def open_containing_folder(path: str):
    """Open the OS file browser at the folder containing `path`."""
    if not path:
        return
    folder = os.path.dirname(os.path.abspath(path))
    system = platform.system()
    try:
        if system == "Windows":
            # /select highlights the file
            subprocess.Popen(["explorer", "/select,", os.path.normpath(path)])
        elif system == "Darwin":
            subprocess.Popen(["open", "-R", path])
        else:  # Linux and friends
            subprocess.Popen(["xdg-open", folder])
    except Exception:
        pass


def backup_path(path: str) -> str:
    """Return a sibling backup file path like name.pdf.bak"""
    return path + ".bak"


def make_backup(path: str) -> str | None:
    """Make a .bak copy. Returns backup path or None on failure."""
    if not file_exists(path):
        return None
    bak = backup_path(path)
    try:
        shutil.copy2(path, bak)
        return bak
    except Exception:
        return None


def safe_unique_path(path: str) -> str:
    """Return a non-colliding path by adding (1), (2) ... if needed."""
    p = Path(path)
    if not p.exists():
        return str(p)
    stem, suffix, parent = p.stem, p.suffix, p.parent
    i = 1
    while True:
        candidate = parent / f"{stem} ({i}){suffix}"
        if not candidate.exists():
            return str(candidate)
        i += 1
