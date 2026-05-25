# MasumPDF Reader source layout

This package keeps application code separated by responsibility:

- `main.py` / `launcher.py` – application entry points.
- `core/` – PDF processing, conversion, compression, annotations, metadata, and research-library logic.
- `ui/` – PySide6 windows, panels, dialogs, styles, icons, and PDF viewer widgets.
- `utils/` – settings, constants, worker threads, file helpers, and translation loading.
- `resources/` – icons, background image, themes, and language JSON files.
- `developer/` – build scripts, installer scripts, and developer-only test helpers.

The root folder now contains only user-facing setup files, source folders, and essential project documentation. Old temporary update reports and generated cache files were removed.
