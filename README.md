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
  <img src="https://img.shields.io/badge/version-V1.0.2-blue" alt="Version V1.0.2">
</p>

---

## Why I made this

A good PDF reader is very important in student life, especially for research
work and LaTeX use. Most of the full features for managing PDF files are only
available in paid PDF readers, which are very expensive. Free PDF readers
usually don't have all these functions. So I made a free, open-source PDF
reader that lets you manage PDF files like the paid ones do.

I'm a student and built this for my own research and LaTeX work. The full
source code is in this repository — you can read it, build it yourself, or
run it from source (see below).

## Run from source (see the code yourself)

This is open source. All the code is here in the `core/`, `ui/`, and `utils/`
folders. To run it directly from the source:

```bash
git clone https://github.com/masumrefat/MasumPDF-Reader.git
cd MasumPDF-Reader
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS / Linux:
source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

> The first `pip install` downloads the components (PySide6, PyMuPDF, etc.)
> and can take several minutes.

## Download the installer (Windows)

If you just want to use the app without setting up Python yourself, download
the installer from the [Releases](../../releases) page and run it. The
installer is built from the exact source code in this repository — you can
verify it by building it yourself with the script in `developer/installer.iss`.

> Because the app is new and not code-signed, Windows may show a
> "Windows protected your PC" notice. Click **More info → Run anyway**.
> This is normal for small open-source apps.

## Features

- **Read & view** — tabs, dark/light mode, zoom, rotate, fit, fullscreen
- **Search** the full document
- **Edit Mode** — click any line of text and type to change it
- **Edit** — add text, insert images, color a line, headers & footers
- **Annotate** — highlight, sticky notes, comments, stamps
- **Undo & erase** — undo edits (Ctrl+Z); click to delete a single annotation
- **Organize pages** — merge, split, extract, rotate, insert, delete
- **Sign & forms** — place signatures, fill form fields
- **Compare two PDFs** — word-level report (added = green, removed = red,
  moved = blue, changed figures flagged); downloadable PDF report
- **Convert** — PDF ↔ images, PDF → text, PDF → DOCX, OCR scanned PDFs
- **Compress, encrypt/decrypt, edit metadata**
- **Print** with a custom dialog (page range, copies, grayscale, live preview)

## Built with

- [PySide6](https://doc.qt.io/qtforpython/) — the Qt GUI framework
- [PyMuPDF](https://pymupdf.readthedocs.io/) — PDF rendering and editing
- [Pillow](https://python-pillow.org/), [NumPy](https://numpy.org/) — images and comparison
- [pypdf](https://pypdf.readthedocs.io/), [reportlab](https://www.reportlab.com/) — PDF utilities

## Project layout

```
MasumPDF-Reader/
├── main.py              # app entry point + splash screen
├── launcher.py          # helper to start the app
├── requirements.txt     # Python packages
├── core/                # PDF engine (rendering, editing, comparison, OCR…)
├── ui/                  # windows, dialogs, viewer, toolbar, panels
├── utils/               # constants, settings, update check, helpers
├── resources/           # icons and themes
└── developer/           # build scripts, including the Inno Setup installer
```

## Honest notes

- This is a student / education project, not a commercial product. It works
  well but is smaller in scope than paid tools and may have rough edges.
- Editing existing text keeps the original font for standard fonts (Times,
  Helvetica, etc.). For unusual embedded fonts it uses the closest match, so
  it may not be pixel-identical — the same limit other PDF editors have.
- The comparison is text-and-figure based; run scanned PDFs through OCR first
  for best results.
- First setup downloads the components and takes a few minutes (one time only).

## License

MIT License — © 2026 Chowdhury Mohammad Masum Refat. See [LICENSE](LICENSE).

You are free to use, study, modify and share this software, with the license
and author credit kept in place.
