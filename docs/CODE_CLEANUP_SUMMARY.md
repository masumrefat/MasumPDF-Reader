# Code Cleanup Summary

This package was cleaned without changing the public app version number.

## Cleaned

- Removed Python cache folders (`__pycache__`) and compiled `.pyc` files.
- Removed temporary development fix-report files from the project root.
- Moved general documentation into the `docs/` folder.
- Kept user-facing install scripts and main launch files in the root folder.
- Kept source code grouped by responsibility:
  - `core/` for PDF, library, reference, notes, conversion, and document logic.
  - `ui/` for windows, panels, dialogs, viewer, toolbar, sidebar, and styles.
  - `utils/` for settings, fonts, translation, updater, integrity, and worker helpers.
  - `resources/` for icons, fonts, backgrounds, and language files.
  - `developer/` for build and smoke-test tools.

## Validation

- Python compile check was run after cleanup.
- App version remains `1.0.2`.
