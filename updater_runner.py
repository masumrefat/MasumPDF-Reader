"""
Separate updater for MasumPDF Reader.

This runs as its OWN process, AFTER the main app has closed. Because the app
is no longer running, its files are not locked, so this can safely replace
them. Steps:
    1. wait a moment for the app to fully close
    2. download the latest release zip from GitHub
    3. unzip it over the install folder
    4. relaunch the app

Usage (the app calls this automatically):
    python updater_runner.py "<install_dir>" "<python_exe>" "<main_py>"
"""

import sys
import os
import time
import zipfile
import tempfile
import shutil
import subprocess
import urllib.request
import json


def log(msg):
    print(f"[updater] {msg}")


def get_repo():
    # read GITHUB_REPO from constants without importing Qt
    try:
        base = os.path.dirname(os.path.abspath(__file__))
        consts = os.path.join(base, "utils", "constants.py")
        repo = ""
        with open(consts, encoding="utf-8") as f:
            for line in f:
                if line.strip().startswith("GITHUB_REPO"):
                    repo = line.split("=", 1)[1].strip().strip('"').strip("'")
                    break
        return repo
    except Exception:
        return ""


def get_zip_url(repo):
    api = f"https://api.github.com/repos/{repo}/releases/latest"
    req = urllib.request.Request(
        api, headers={"Accept": "application/vnd.github+json",
                      "User-Agent": "MasumPDF-Reader"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    for asset in data.get("assets", []):
        if (asset.get("name") or "").lower().endswith(".zip"):
            return asset.get("browser_download_url")
    return data.get("zipball_url")


def main():
    if len(sys.argv) < 4:
        log("missing arguments")
        return
    install_dir = sys.argv[1]
    python_exe = sys.argv[2]
    main_py = sys.argv[3]

    log("waiting for the app to close...")
    time.sleep(2)

    repo = get_repo()
    if not repo:
        log("no repo configured")
        _relaunch(python_exe, main_py)
        return

    try:
        url = get_zip_url(repo)
        log(f"downloading {url}")
        tmp_zip = os.path.join(tempfile.gettempdir(), "masumpdf_update.zip")
        req = urllib.request.Request(url, headers={"User-Agent": "MasumPDF-Reader"})
        with urllib.request.urlopen(req, timeout=120) as resp, \
                open(tmp_zip, "wb") as out:
            shutil.copyfileobj(resp, out)

        log("unzipping...")
        tmp_dir = os.path.join(tempfile.gettempdir(), "masumpdf_update_extract")
        if os.path.exists(tmp_dir):
            shutil.rmtree(tmp_dir, ignore_errors=True)
        with zipfile.ZipFile(tmp_zip) as z:
            z.extractall(tmp_dir)

        # find the folder that actually contains main.py
        src_root = _find_app_root(tmp_dir)
        if not src_root:
            log("could not find app files in the download")
            _relaunch(python_exe, main_py)
            return

        log("copying new files over the old ones...")
        _copy_over(src_root, install_dir)

        log("cleanup...")
        shutil.rmtree(tmp_dir, ignore_errors=True)
        try:
            os.remove(tmp_zip)
        except Exception:
            pass

        log("update complete, restarting app")
    except Exception as e:
        log(f"update failed: {e}")

    _relaunch(python_exe, main_py)


def _find_app_root(folder):
    # the zip may have a top folder; find where main.py lives
    for root, dirs, files in os.walk(folder):
        if "main.py" in files and "core" in dirs and "ui" in dirs:
            return root
    return None


def _copy_over(src, dst):
    # copy code folders + key files, but NEVER touch .venv (keep environment)
    keep_out = {".venv", "__pycache__"}
    for item in os.listdir(src):
        if item in keep_out:
            continue
        s = os.path.join(src, item)
        d = os.path.join(dst, item)
        try:
            if os.path.isdir(s):
                if os.path.exists(d):
                    shutil.rmtree(d, ignore_errors=True)
                shutil.copytree(s, d, ignore=shutil.ignore_patterns(
                    "__pycache__", "*.pyc", ".venv"))
            else:
                shutil.copy2(s, d)
        except Exception as e:
            log(f"skip {item}: {e}")


def _relaunch(python_exe, main_py):
    try:
        subprocess.Popen([python_exe, main_py])
        log("app relaunched")
    except Exception as e:
        log(f"could not relaunch: {e}")


if __name__ == "__main__":
    main()
