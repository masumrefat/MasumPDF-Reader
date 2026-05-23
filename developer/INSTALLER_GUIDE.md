# Building the Windows Installer (setup.exe)

This guide makes a real Windows installer for **MasumPDF Reader** — the kind
that shows installer pages, installs into Program Files, puts the app in the
Start Menu and Add/Remove Programs, and installs Python automatically if the
user doesn't have it.

Created by **Chowdhury Mohammad Masum Refat** · MIT License

---

## The easy way (no installer build) — `install.bat`

If you just want it working on your own PC, you don't need to build anything:

1. Copy the whole `masumpdf_reader` folder to the Windows PC.
2. Double-click **`install.bat`**.
   - If Python is missing, it downloads and installs it automatically.
   - It then creates a private environment and installs everything.
   - It puts a **MasumPDF Reader** icon on the Desktop.
3. Double-click the Desktop icon (or `run.bat`) to start the app.

That's the simplest path. The steps below are for making a shareable
`setup.exe` that behaves like a normal Windows program installer.

---

## The proper way — a real `setup.exe`

This uses **Inno Setup**, a free, widely used Windows installer builder.

### One-time tools you need
1. **Inno Setup** (free): https://jrsoftware.org/isdl.php — download and install it.
2. **The Python installer**: download `python-3.12.4-amd64.exe` from
   https://www.python.org/downloads/release/python-3124/ and put it **inside the
   `masumpdf_reader` folder**, right next to `installer.iss`.
   (This lets the setup install Python on PCs that don't have it.)

### Build it
1. Open **`installer.iss`** in Inno Setup (double-click the file).
2. Click **Build → Compile** (or press F9).
3. When it finishes, look in the new **`Output`** folder. You'll find:
   **`MasumPDF-Reader-Setup.exe`**

That single file is your installer. Share it with anyone.

### What the installer does for the user
When someone runs `MasumPDF-Reader-Setup.exe`:
1. Shows a welcome page, the MIT license, and a choose-folder page.
2. Copies the app into `C:\Program Files\MasumPDF Reader`.
3. If the PC has no Python, installs Python silently in the background.
4. Builds the app's environment and installs all components.
5. Adds **Start Menu** and (optionally) **Desktop** shortcuts with your logo.
6. Registers the app in **Settings → Apps** so it can be uninstalled cleanly.

The app then appears like any normal Windows program, with your icon.

---

## Notes / honest limits

- The installer needs an internet connection the first time, because pip
  downloads the Python packages during setup. (Python itself is bundled.)
- Installing into Program Files asks for administrator permission — that's
  normal for Windows app installers.
- This is **not** a single compiled `.exe`. The app still runs on Python under
  the hood; the installer just sets everything up so the user never sees that.
  If you later want a fully self-contained `.exe` (no Python at all), that's a
  separate step using PyInstaller — ask and it can be added.
- The author name and license are integrity-checked at startup (see
  `utils/integrity.py`). If they're changed, the app refuses to run.

---

## Making it a REAL .exe (so it can be the default PDF app)

Two things you asked about — "set as default app for all PDFs" and "open
faster" — both need the app to be a real `MasumPDFReader.exe`, not a Python
script. Here is the honest situation and the fix.

### Why "Set as default" didn't work before
Windows can only set a real program (`.exe`) as the default opener for a file
type. The app was running as `pythonw.exe main.py`, which Windows can't attach
to PDF files. So "Always open with…" had nothing solid to point to.

### The fix: build a single .exe with PyInstaller
On a Windows PC, inside this folder, after running `install.bat` once:

    .venv\Scripts\pip install pyinstaller
    .venv\Scripts\pyinstaller --noconfirm --windowed --name MasumPDFReader --icon resources\icons\app.ico --add-data "resources;resources" launcher.py

This produces **`dist\MasumPDFReader\MasumPDFReader.exe`** — a real Windows
program. Copy that `MasumPDFReader` folder's contents into the app folder (or
point the installer's [Files] section at `dist\MasumPDFReader\*`).

Once `MasumPDFReader.exe` exists:
- The Inno Setup installer's file-association entries (already in
  `installer.iss`) register it as a PDF opener.
- After installing, go to **Windows Settings > Apps > Default apps**, search
  **MasumPDF Reader**, and set it as the handler for `.pdf`. Double-clicking any
  PDF will then open it in this app.

### Why a compiled .exe also opens FASTER
A PyInstaller `.exe` bundles Python and all libraries together and loads them
more directly, so it starts faster than running the script through Python each
time. The script version has to import PySide6 and PyMuPDF fresh on every
launch, which is the slow part you noticed.

### Honest note
Building the `.exe` must be done on Windows (PyInstaller can't be run from this
build environment). Everything is prepared — `launcher.py`, the icon, the
installer registry entries — you just run the one PyInstaller command above on
your PC. If you'd rather not, the app still works via `install.bat` and the
desktop shortcut; only the "default PDF app" feature needs the real `.exe`.

---

## "My PDF files show the Python logo, not my app logo"

This happens because the PDF file type is linked to `pythonw.exe`, and Windows
borrows the icon from whatever program opens the file — so you see the Python
snake icon.

### Quick fix (script version) — run `set-default.bat`
1. Run `install.bat` first (if you haven't).
2. Right-click **`set-default.bat`** > **Run as administrator**.
   - This registers a "MasumPDFReader.Document" type whose icon is YOUR
     `app.ico`, and adds the app to the PDF "Open with" list.
3. Open **Settings > Apps > Default apps**, search **MasumPDF Reader**, and set
   it as the handler for `.pdf`.
4. Your PDF files now show the MasumPDF logo.

If the old Python icons are cached, log out and back in (or restart) so Windows
refreshes the thumbnails.

### Best fix — build the .exe
When you build `MasumPDFReader.exe` (see the PyInstaller section above), the
icon is embedded inside the exe itself. Then PDFs associated with it show your
logo automatically, with no registry tricks. This is the cleanest result and is
what a normal Windows app does.

---

## EASIEST PATH (do this if "set as default" isn't working)

The default-app feature only works reliably with a real `.exe`. Here is the
simplest way, with no typing:

1. Double-click **`install.bat`**  (sets up the app + Python).
2. Double-click **`build-exe.bat`**  (makes `app_exe\MasumPDFReader.exe`).
3. Right-click **`set-default.bat`** > **Run as administrator**.
4. Windows **Settings > Apps > Default apps** > search **MasumPDF Reader** >
   set it for `.pdf`.

After this, PDFs open in your app and show your logo. If old icons linger,
restart the PC once so Windows refreshes them.

Why the script-only method fails: modern Windows refuses to treat a Python
script as a real default app and keeps showing the Python icon. The `.exe`
from step 2 is a genuine Windows program, so Windows accepts it.
