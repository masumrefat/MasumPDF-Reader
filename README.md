<p align="center">
  <img src="icons/logo.png" width="120" alt="MasumPDF Reader logo">
</p>

<h1 align="center">MasumPDF Reader</h1>

<p align="center">
  A free, open-source desktop PDF reader, editor and comparison tool — built in Python.<br>
  <strong>For education purpose only.</strong>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.9%2B-blue" alt="Python 3.9+">
  <img src="https://img.shields.io/badge/license-MIT-green" alt="MIT License">
  <img src="https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey" alt="Platforms">
</p>

---

## About

MasumPDF Reader is a desktop application for working with PDF files. You can
read, edit, annotate, sign, organize, convert, OCR, compare, compress, fill
forms, and protect PDFs — all from one window. It is written in Python with
PySide6 (Qt) and PyMuPDF.

This project was created by **Chowdhury Mohammad Masum Refat** and is released
under the MIT License. It is intended for education purposes.

## Features

- **Read & view** — continuous, single, and two-page modes; zoom, rotate, fit, fullscreen; dark and light themes
- **Search** the full document
- **Annotate** — highlight, sticky notes, comments, stamps
- **Edit** — Edit Mode (click any line and type), add text, insert images, color a line, change text color, headers & footers
- **Undo & erase** — undo any edit (Ctrl+Z) or click to delete a single annotation
- **Organize pages** — merge, split, extract, rotate, insert, delete
- **Sign & forms** — place signatures, prepare and fill form fields
- **Compare two PDFs** — word-level, reflow-aware comparison with a color-coded report:
  - 🟩 green = added &nbsp; 🟥 red = removed &nbsp; 🟦 blue = moved (reflow)
  - detects figure / image changes (dashed orange box)
  - downloadable PDF report with bookmarks and "jump to changes"
- **Convert** — PDF ↔ images, PDF → text, PDF → DOCX, OCR scanned PDFs
- **Compress, encrypt/decrypt, edit metadata**
- **Print** with a custom print dialog (page range, copies, grayscale, live preview)
- **Clickable links** — table-of-contents and web links work inside the page
- **Check for updates** — the app can check this GitHub page for new versions

## Install (Windows)

The easy way — just **double-click `SETUP.bat`**.

It does everything automatically:
1. Installs Python (if your PC doesn't have it)
2. Installs all required packages
3. Builds the app with the MasumPDF logo
4. Puts a **MasumPDF Reader** icon on your Desktop

Then open the app from the Desktop icon.

> ⏱️ **Please be patient — the first setup takes about 15–20 minutes**
> (depending on your internet speed). It downloads around **800 MB** of
> components (Python libraries like PySide6 and PyMuPDF) the first time.
> This is normal. Leave the window open and let it finish — it only happens
> once. After that, the app opens instantly. You need an internet connection
> during this first setup.

> 💡 Tip: put the folder in a **short path** like `C:\pdf` before running
> `SETUP.bat` (not deep inside Downloads), so Windows doesn't hit its
> long-path limit.

> To make all PDF files open in this app and show its logo, go to
> **Settings → Apps → Default apps**, search **MasumPDF Reader**, and set it
> for `.pdf` (then restart once).

See `HOW_TO_INSTALL.txt` for the simple version.

## Install (macOS / Linux)

On a Mac, the easy way is to **double-click `SETUP_MAC.command`** — it sets up
everything, then creates a `RUN_MAC.command` you double-click to open the app.
(The first time, macOS may ask you to allow it: right-click → **Open** →
**Open**. That's normal for downloaded scripts.)

Or by hand in Terminal (Mac or Linux):

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

OCR also needs the Tesseract program installed on your system
(`tesseract-ocr` on Linux, or from the Tesseract project on macOS).

> ⏱️ Just like on Windows, the **first setup takes about 15–20 minutes** and
> downloads around **800 MB** of components. This only happens once.

## Built with

- [PySide6](https://doc.qt.io/qtforpython/) — the Qt GUI framework
- [PyMuPDF](https://pymupdf.readthedocs.io/) — PDF rendering and editing
- [Pillow](https://python-pillow.org/), [NumPy](https://numpy.org/) — image handling and comparison
- [pypdf](https://pypdf.readthedocs.io/), [reportlab](https://www.reportlab.com/) — PDF utilities

## Project layout

```
masumpdf_reader/
├── SETUP.bat            # quick run-from-folder setup (Windows)
├── INSTALL.bat          # proper installer (copies to Program Files)
├── UNINSTALL.bat        # removes the app cleanly
├── SETUP_MAC.command    # setup for macOS
├── HOW_TO_INSTALL.txt   # simple instructions
├── main.py              # app entry point + splash screen
├── requirements.txt     # Python packages
├── core/                # PDF engine (rendering, editing, comparison, OCR…)
├── ui/                  # windows, dialogs, viewer, toolbar, panels
├── utils/               # constants, settings, helpers
├── resources/           # icons and themes
└── developer/           # advanced build scripts (not needed by normal users)
```

## Honest notes

- This is a student / education project, not a commercial product. It does its
  job well, but it is smaller in scope than paid tools and may have rough edges.
- **First setup is slow** (about 15–20 minutes, ~800 MB download) because it
  fetches all the components. This is one-time only.
- **Editing existing text** keeps the original font for standard fonts
  (Times, Helvetica, etc.). For unusual embedded fonts, it uses the closest
  matching font, so it may not be pixel-identical — the same limit other PDF
  editors have.
- The PDF comparison is **text-and-figure based**. It catches text changes
  precisely and flags changed figures, but it is not pixel-perfect on every
  scanned or image-only document.
- Scanned PDFs should be run through OCR first for best comparison results.
- The author name and license are checked at startup; the app is meant to be
  used and shared with credit kept intact.

## License

MIT License — © 2026 Chowdhury Mohammad Masum Refat. See [LICENSE](LICENSE).

You are free to use, study, modify and share this software, with the license
and author credit kept in place.
