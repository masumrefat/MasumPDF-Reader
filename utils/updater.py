"""
Check GitHub for a newer version of MasumPDF Reader.

This quietly asks GitHub for the latest release tag and compares it to the
version running now. It is best-effort: if there is no internet, or GitHub
is unreachable, it simply does nothing (it never blocks or slows the app).
"""

import json
import urllib.request

from utils.constants import APP_VERSION, GITHUB_REPO


def _parse_version(text):
    """Turn a version string like 'v4.7.0' or '4.7.0' into a tuple (4,7,0)."""
    text = (text or "").strip().lstrip("vV")
    parts = []
    for piece in text.split("."):
        num = ""
        for ch in piece:
            if ch.isdigit():
                num += ch
            else:
                break
        parts.append(int(num) if num else 0)
    while len(parts) < 3:
        parts.append(0)
    return tuple(parts[:3])


def get_latest_version(timeout=4):
    """Return the latest version string from GitHub Releases, or None.

    Never raises — returns None on any problem (no internet, no releases…).
    """
    if not GITHUB_REPO or "/" not in GITHUB_REPO:
        return None
    url = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
    try:
        req = urllib.request.Request(
            url, headers={"Accept": "application/vnd.github+json",
                          "User-Agent": "MasumPDF-Reader"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        tag = data.get("tag_name") or data.get("name")
        return tag
    except Exception:
        return None


def check_for_update(timeout=4):
    """Compare the latest GitHub version with the running one.

    Returns a dict {'update': True/False, 'latest': '4.8.0', 'url': ...}
    or None if the check could not be done.
    """
    latest = get_latest_version(timeout=timeout)
    if not latest:
        return None
    try:
        is_newer = _parse_version(latest) > _parse_version(APP_VERSION)
    except Exception:
        return None
    return {
        "update": is_newer,
        "latest": latest.lstrip("vV"),
        "current": APP_VERSION,
        "url": f"https://github.com/{GITHUB_REPO}/releases/latest",
    }


def get_download_url(timeout=4):
    """Find a downloadable zip in the latest GitHub release.

    Looks for an attached .zip asset first; if none, falls back to GitHub's
    auto-generated source zip. Returns a URL string, or None.
    """
    if not GITHUB_REPO or "/" not in GITHUB_REPO:
        return None
    api = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
    try:
        req = urllib.request.Request(
            api, headers={"Accept": "application/vnd.github+json",
                          "User-Agent": "MasumPDF-Reader"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        # prefer an attached .zip asset
        for asset in data.get("assets", []):
            name = (asset.get("name") or "").lower()
            if name.endswith(".zip"):
                return asset.get("browser_download_url")
        # fall back to the source-code zip GitHub makes automatically
        return data.get("zipball_url")
    except Exception:
        return None


def download_update(dest_path, timeout=60):
    """Download the latest release zip to dest_path. Returns True on success.

    Best-effort and safe: returns False on any problem instead of raising.
    """
    url = get_download_url()
    if not url:
        return False
    try:
        req = urllib.request.Request(
            url, headers={"User-Agent": "MasumPDF-Reader"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = resp.read()
        if not data or len(data) < 1000:
            return False
        with open(dest_path, "wb") as f:
            f.write(data)
        return True
    except Exception:
        return False
