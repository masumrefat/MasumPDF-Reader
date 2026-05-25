"""
Self-updater for MasumPDF Reader.

Runs as a separate process after the main app closes. It downloads the latest
GitHub Release asset, replaces the installed app files, then relaunches the app.

Supported modes:
  Source/Python install:
    python updater_runner.py "<install_dir>" "<python_or_pythonw>" "<main.py>" [asset_url]

  PyInstaller exe install:
    UpdaterRunner.exe "<install_dir>" "<MasumPDFReader.exe>" "" [asset_url]
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
import zipfile

USER_AGENT = "MasumPDF-Reader-Updater"


def log(msg: str) -> None:
    print(f"[MasumPDF Updater] {msg}", flush=True)


def get_repo(install_dir: str) -> str:
    """Read GITHUB_REPO from constants.py without importing Qt/app modules."""
    try:
        consts = os.path.join(install_dir, "utils", "constants.py")
        with open(consts, encoding="utf-8") as f:
            for line in f:
                if line.strip().startswith("GITHUB_REPO"):
                    return line.split("=", 1)[1].strip().strip('"').strip("'")
    except Exception:
        pass
    return ""


def get_zip_url(repo: str) -> str | None:
    api = f"https://api.github.com/repos/{repo}/releases/latest"
    req = urllib.request.Request(
        api,
        headers={"Accept": "application/vnd.github+json", "User-Agent": USER_AGENT},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode("utf-8"))

    assets = data.get("assets") or []
    zips = []
    for asset in assets:
        name = (asset.get("name") or "").lower()
        url = asset.get("browser_download_url")
        if name.endswith(".zip") and url:
            zips.append((name, url))

    preferred = ("portable", "app_exe", "app-exe", "windows", "win", "masumpdf")
    for name, url in zips:
        if any(word in name for word in preferred):
            return url
    if zips:
        return zips[0][1]

    # Source zip fallback is useful for Python/source installs, but NOT for exe
    # installs. The runner will reject it later if it cannot find app files.
    return data.get("zipball_url")


def download(url: str, dest: str) -> None:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=180) as resp, open(dest, "wb") as out:
        total = resp.headers.get("Content-Length")
        total_int = int(total) if total and total.isdigit() else 0
        done = 0
        while True:
            chunk = resp.read(1024 * 256)
            if not chunk:
                break
            out.write(chunk)
            done += len(chunk)
            if total_int:
                pct = int(done * 100 / total_int)
                log(f"Downloading... {pct}%")


def main() -> None:
    if len(sys.argv) < 3:
        log("Missing arguments.")
        time.sleep(3)
        return

    install_dir = os.path.abspath(sys.argv[1])
    relaunch_exe = sys.argv[2]
    main_py = sys.argv[3] if len(sys.argv) >= 4 else ""
    asset_url = sys.argv[4] if len(sys.argv) >= 5 and sys.argv[4] else ""

    log("Waiting for the main app to close...")
    time.sleep(2.5)

    try:
        if not asset_url:
            repo = get_repo(install_dir)
            if not repo:
                raise RuntimeError("GitHub repo is not configured in utils/constants.py")
            asset_url = get_zip_url(repo) or ""
        if not asset_url:
            raise RuntimeError("No downloadable .zip asset found in the latest GitHub release")

        tmp_zip = os.path.join(tempfile.gettempdir(), "masumpdf_update_latest.zip")
        tmp_dir = os.path.join(tempfile.gettempdir(), "masumpdf_update_extract")
        if os.path.exists(tmp_dir):
            shutil.rmtree(tmp_dir, ignore_errors=True)
        try:
            os.remove(tmp_zip)
        except Exception:
            pass

        log(f"Downloading update: {asset_url}")
        download(asset_url, tmp_zip)
        if not os.path.exists(tmp_zip) or os.path.getsize(tmp_zip) < 1000:
            raise RuntimeError("Downloaded update file is empty or incomplete")

        log("Extracting update...")
        with zipfile.ZipFile(tmp_zip) as z:
            z.extractall(tmp_dir)

        src_root = find_app_root(tmp_dir)
        if not src_root:
            raise RuntimeError(
                "Could not find MasumPDF app files in the update zip. "
                "For automatic updates, upload a ZIP containing either the project "
                "source folder or the built app_exe folder to GitHub Releases."
            )

        log(f"Installing from: {src_root}")
        copy_over(src_root, install_dir)

        log("Cleaning temporary files...")
        shutil.rmtree(tmp_dir, ignore_errors=True)
        try:
            os.remove(tmp_zip)
        except Exception:
            pass

        log("Update complete.")
    except Exception as exc:
        log(f"Update failed: {exc}")

    relaunch(relaunch_exe, main_py)
    log("This updater window will close shortly.")
    time.sleep(3)


def find_app_root(folder: str) -> str | None:
    """Find either a source app root or a PyInstaller onedir root."""
    candidates = []
    for root, dirs, files in os.walk(folder):
        file_set = set(files)
        dir_set = set(dirs)
        # Source/project zip.
        if "main.py" in file_set and "ui" in dir_set and "core" in dir_set:
            return root
        # PyInstaller onedir zip.
        if "MasumPDFReader.exe" in file_set:
            candidates.append(root)
    if candidates:
        # Prefer the shortest path, usually the app_exe root.
        return sorted(candidates, key=len)[0]
    return None


def copy_over(src: str, dst: str) -> None:
    """Replace app files, preserving virtualenv/user data and this updater."""
    os.makedirs(dst, exist_ok=True)
    skip_names = {
        ".venv", "__pycache__", "build", "dist",
        "masumpdf_update_latest.zip",
    }
    # Keep the currently running updater executable/script to avoid file-lock
    # failures. It can be replaced by the next installer/build.
    running_updater = os.path.basename(sys.executable if getattr(sys, "frozen", False) else __file__).lower()
    extra_skip = {running_updater, "updaterrunner.exe" if running_updater == "updaterrunner.exe" else ""}

    for item in os.listdir(src):
        if item in skip_names or item.lower() in extra_skip:
            log(f"Skipping locked/system item: {item}")
            continue
        s = os.path.join(src, item)
        d = os.path.join(dst, item)
        try:
            if os.path.isdir(s):
                if os.path.exists(d):
                    shutil.rmtree(d, ignore_errors=True)
                shutil.copytree(
                    s,
                    d,
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".venv"),
                )
            else:
                shutil.copy2(s, d)
            log(f"Updated: {item}")
        except Exception as e:
            log(f"Could not update {item}: {e}")


def relaunch(relaunch_exe: str, main_py: str = "") -> None:
    try:
        if main_py:
            subprocess.Popen([relaunch_exe, main_py])
        else:
            subprocess.Popen([relaunch_exe])
        log("App relaunched.")
    except Exception as e:
        log(f"Could not relaunch app: {e}")


if __name__ == "__main__":
    main()
