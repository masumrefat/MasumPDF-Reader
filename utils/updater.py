"""
GitHub update checker for MasumPDF Reader.

The app checks the latest GitHub Release. If a newer tag is available,
it asks the user every time the app starts until they install the update.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.request
from dataclasses import dataclass
from typing import Optional

from utils.constants import APP_VERSION, GITHUB_REPO


USER_AGENT = "MasumPDF-Reader-Updater"


@dataclass
class UpdateInfo:
    update: bool
    latest: str
    current: str
    url: str
    asset_url: Optional[str] = None
    asset_name: Optional[str] = None
    notes: str = ""
    frozen: bool = False

    def as_dict(self) -> dict:
        return {
            "update": self.update,
            "latest": self.latest,
            "current": self.current,
            "url": self.url,
            "asset_url": self.asset_url,
            "asset_name": self.asset_name,
            "notes": self.notes,
            "frozen": self.frozen,
        }


def is_frozen_app() -> bool:
    """True when running from PyInstaller-built MasumPDFReader.exe."""
    return bool(getattr(sys, "frozen", False))


def _parse_version(text: str | None) -> tuple[int, int, int, int]:
    """Turn 'v1.0.12-beta' into a sortable tuple."""
    text = (text or "").strip().lstrip("vV")
    numbers: list[int] = []
    current = ""
    for ch in text:
        if ch.isdigit():
            current += ch
        elif current:
            numbers.append(int(current))
            current = ""
        if len(numbers) >= 4:
            break
    if current and len(numbers) < 4:
        numbers.append(int(current))
    while len(numbers) < 4:
        numbers.append(0)
    return tuple(numbers[:4])


def _github_latest_release(timeout: int = 8) -> Optional[dict]:
    if not GITHUB_REPO or "/" not in GITHUB_REPO:
        return None
    api = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
    try:
        req = urllib.request.Request(
            api,
            headers={
                "Accept": "application/vnd.github+json",
                "User-Agent": USER_AGENT,
            },
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception:
        return None


def _pick_update_asset(release: dict, frozen: bool) -> tuple[Optional[str], Optional[str]]:
    """Choose the best asset for self-update.

    For the installed/source app, a project zip can work. For PyInstaller exe
    builds, the release MUST contain a portable/exe zip asset because GitHub's
    automatic source zip does not contain the built exe.
    """
    assets = release.get("assets") or []
    zip_assets = []
    exe_assets = []
    for asset in assets:
        name = (asset.get("name") or "").lower()
        url = asset.get("browser_download_url")
        if not url:
            continue
        if name.endswith(".zip"):
            zip_assets.append((name, url, asset.get("name")))
        elif name.endswith(".exe") or name.endswith(".msi"):
            exe_assets.append((name, url, asset.get("name")))

    # Best for self-update: a portable/app_exe zip containing MasumPDFReader.exe.
    preferred_words = ("portable", "app_exe", "app-exe", "windows", "win", "masumpdf")
    for name, url, original in zip_assets:
        if any(word in name for word in preferred_words):
            return url, original
    if zip_assets:
        return zip_assets[0][1], zip_assets[0][2]

    # Installer assets cannot be silently self-applied by the internal updater.
    # Return them only as a fallback for non-frozen/source installs, where opening
    # the release page is still useful.
    if not frozen and exe_assets:
        return exe_assets[0][1], exe_assets[0][2]

    # Source zip fallback works only when the app is installed as Python source.
    if not frozen:
        return release.get("zipball_url"), "GitHub source zip"

    return None, None


def check_for_update(timeout: int = 8) -> Optional[dict]:
    """Return update information, or None if checking failed.

    Returned dict is compatible with older app code and includes:
    update/latest/current/url/asset_url/asset_name/notes/frozen.
    """
    release = _github_latest_release(timeout=timeout)
    if not release:
        return None

    latest = (release.get("tag_name") or release.get("name") or "").strip()
    if not latest:
        return None

    frozen = is_frozen_app()
    try:
        is_newer = _parse_version(latest) > _parse_version(APP_VERSION)
    except Exception:
        return None

    html_url = release.get("html_url") or f"https://github.com/{GITHUB_REPO}/releases/latest"
    asset_url, asset_name = _pick_update_asset(release, frozen=frozen)
    notes = (release.get("body") or "").strip()

    info = UpdateInfo(
        update=is_newer,
        latest=latest.lstrip("vV"),
        current=APP_VERSION,
        url=html_url,
        asset_url=asset_url,
        asset_name=asset_name,
        notes=notes,
        frozen=frozen,
    )
    return info.as_dict()


def get_download_url(timeout: int = 8) -> Optional[str]:
    release = _github_latest_release(timeout=timeout)
    if not release:
        return None
    url, _name = _pick_update_asset(release, frozen=is_frozen_app())
    return url


def download_update(dest_path: str, timeout: int = 180) -> bool:
    """Download latest release asset to dest_path. Returns False on failure."""
    url = get_download_url()
    if not url:
        return False
    try:
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=timeout) as resp, open(dest_path, "wb") as out:
            while True:
                chunk = resp.read(1024 * 256)
                if not chunk:
                    break
                out.write(chunk)
        return os.path.exists(dest_path) and os.path.getsize(dest_path) > 1000
    except Exception:
        return False
