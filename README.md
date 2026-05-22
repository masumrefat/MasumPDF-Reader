<p align="center">
  <img src="resources/icons/logo.png" width="120" alt="MasumPDF Reader logo">
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
- **Edit** — add text, insert images, change text color, edit a line, headers & footers
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

## Install (Windows)

The easy way — just **double-click `SETUP.bat`**.

It does everything automatically:
1. Installs Python (if your PC doesn't have it)
2. Installs all required packages
3. Builds the app with the MasumPDF logo
4. Puts a **MasumPDF Reader** icon on your Desktop

Then open the app from the Desktop icon.

> To make all PDF files open in this app and show its logo, go to
> **Settings → Apps → Default apps**, search **MasumPDF Reader**, and set it
> for `.pdf` (then restart once).

See `HOW_TO_INSTALL.txt` for the simple version.

## Install (macOS / Linux)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

OCR also needs the Tesseract program installed on your system
(`tesseract-ocr` on Linux, or from the Tesseract project on macOS).

## Built with

- [PySide6](https://doc.qt.io/qtforpython/) — the Qt GUI framework
- [PyMuPDF](https://pymupdf.readthedocs.io/) — PDF rendering and editing
- [Pillow](https://python-pillow.org/), [NumPy](https://numpy.org/) — image handling and comparison
- [pypdf](https://pypdf.readthedocs.io/), [reportlab](https://www.reportlab.com/) — PDF utilities

## Project layout

```
masumpdf_reader/
├── SETUP.bat            # one-click installer (Windows)
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
