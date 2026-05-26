"""
GitHub update checker for MasumPDF Reader.

Checks GitHub Releases and reports a newer release when either:
1. the release version number is newer than APP_VERSION, or
2. the release has the same app version but a different release tag/build and
   it was published after this local build.

This second rule is important for MasumPDF Reader because some maintenance
builds keep the visible app version at 1.0.2 while the GitHub release/tag name
changes.
"""

from __future__ import annotations

import json
import os
import re
import sys
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from utils.constants import APP_VERSION, GITHUB_REPO

try:
    from utils.constants import APP_RELEASE_TAG, APP_BUILD_DATE
except Exception:  # older constants.py compatibility
    APP_RELEASE_TAG = f"v{APP_VERSION}"
    APP_BUILD_DATE = "1970-01-01T00:00:00Z"


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
    latest_tag: str = ""
    current_tag: str = ""
    published_at: str = ""
    reason: str = ""
    repo: str = ""

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
            "latest_tag": self.latest_tag,
            "current_tag": self.current_tag,
            "published_at": self.published_at,
            "reason": self.reason,
            "repo": self.repo,
        }


def is_frozen_app() -> bool:
    """True when running from PyInstaller-built MasumPDFReader.exe."""
    return bool(getattr(sys, "frozen", False))


def _parse_version(text: str | None) -> tuple[int, int, int, int]:
    """Turn 'v1.0.12-beta' into a sortable 4-part tuple."""
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


def _version_text_from_release(release: dict) -> str:
    """Prefer tag_name, then release name, and extract the first version-like text."""
    raw = f"{release.get('tag_name') or ''} {release.get('name') or ''}".strip()
    match = re.search(r"v?\d+(?:\.\d+){0,3}", raw, flags=re.IGNORECASE)
    return match.group(0).lstrip("vV") if match else (release.get("tag_name") or release.get("name") or "").strip()


def _parse_github_datetime(value: str | None) -> datetime:
    if not value:
        return datetime(1970, 1, 1, tzinfo=timezone.utc)
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
    except Exception:
        return datetime(1970, 1, 1, tzinfo=timezone.utc)


def _request_json(url: str, timeout: int = 8):
    req = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": USER_AGENT,
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _github_releases(timeout: int = 8) -> list[dict]:
    if not GITHUB_REPO or "/" not in GITHUB_REPO:
        return []

    # /releases/latest can miss prereleases and sometimes is not what a small
    # project expects. /releases lets us choose the newest published release
    # ourselves and makes the update button more reliable.
    api = f"https://api.github.com/repos/{GITHUB_REPO}/releases?per_page=20"
    try:
        releases = _request_json(api, timeout=timeout)
        if isinstance(releases, list):
            return [r for r in releases if isinstance(r, dict) and not r.get("draft")]
    except Exception:
        pass

    # Fallback for older behavior.
    try:
        latest = _request_json(f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest", timeout=timeout)
        if isinstance(latest, dict) and latest.get("tag_name"):
            return [latest]
    except Exception:
        pass
    return []


def _pick_release(releases: list[dict]) -> Optional[dict]:
    if not releases:
        return None
    # GitHub normally returns newest first. Sort anyway to avoid surprises.
    return sorted(
        releases,
        key=lambda r: _parse_github_datetime(r.get("published_at") or r.get("created_at")),
        reverse=True,
    )[0]


def _pick_update_asset(release: dict, frozen: bool) -> tuple[Optional[str], Optional[str]]:
    """Choose the best asset for self-update."""
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

    preferred_words = ("portable", "app_exe", "app-exe", "windows", "win", "masumpdf")
    for name, url, original in zip_assets:
        if any(word in name for word in preferred_words):
            return url, original
    if zip_assets:
        return zip_assets[0][1], zip_assets[0][2]

    if not frozen and exe_assets:
        return exe_assets[0][1], exe_assets[0][2]

    # GitHub source zip is still a useful fallback for source/Python installs.
    if not frozen:
        return release.get("zipball_url"), "GitHub source zip"

    return None, None


def _is_new_release(release: dict) -> tuple[bool, str]:
    latest_version = _version_text_from_release(release)
    latest_tag = (release.get("tag_name") or "").strip()
    current_tag = (APP_RELEASE_TAG or f"v{APP_VERSION}").strip()

    latest_tuple = _parse_version(latest_version)
    current_tuple = _parse_version(APP_VERSION)
    if latest_tuple > current_tuple:
        return True, "newer_version"
    if latest_tuple < current_tuple:
        return False, "older_version"

    # Same visible version, but a newer release tag/build. This solves the case
    # where you publish maintenance releases while keeping APP_VERSION = 1.0.2.
    latest_published = _parse_github_datetime(release.get("published_at") or release.get("created_at"))
    local_build = _parse_github_datetime(APP_BUILD_DATE)
    if latest_tag and latest_tag != current_tag and latest_published > local_build:
        return True, "same_version_new_release"

    return False, "same_version"


def check_for_update(timeout: int = 8) -> Optional[dict]:
    """Return update information, or None if checking failed."""
    release = _pick_release(_github_releases(timeout=timeout))
    if not release:
        return None

    latest_version = _version_text_from_release(release)
    latest_tag = (release.get("tag_name") or latest_version).strip()
    if not latest_version:
        return None

    frozen = is_frozen_app()
    is_newer, reason = _is_new_release(release)

    html_url = release.get("html_url") or f"https://github.com/{GITHUB_REPO}/releases/latest"
    asset_url, asset_name = _pick_update_asset(release, frozen=frozen)
    notes = (release.get("body") or "").strip()

    info = UpdateInfo(
        update=is_newer,
        latest=latest_version.lstrip("vV"),
        current=APP_VERSION,
        url=html_url,
        asset_url=asset_url,
        asset_name=asset_name,
        notes=notes,
        frozen=frozen,
        latest_tag=latest_tag,
        current_tag=(APP_RELEASE_TAG or f"v{APP_VERSION}"),
        published_at=release.get("published_at") or release.get("created_at") or "",
        reason=reason,
        repo=GITHUB_REPO,
    )
    return info.as_dict()


def get_download_url(timeout: int = 8) -> Optional[str]:
    release = _pick_release(_github_releases(timeout=timeout))
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
