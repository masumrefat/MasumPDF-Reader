"""Persistent settings using QSettings.

Holds theme, zoom defaults, recent files, OCR language, etc.
"""

from PySide6.QtCore import QSettings
from .constants import (
    APP_NAME, APP_ORG, RECENT_FILES_MAX,
    DEFAULT_HIGHLIGHT_COLOR, DEFAULT_PEN_COLOR, DEFAULT_PEN_WIDTH,
    THEME_LIGHT, THEME_DARK, VIEW_CONTINUOUS, COLOR_THEMES, DEFAULT_COLOR_THEME,
    DEFAULT_APPEARANCE, APPEARANCES,
)


def _as_bool(value, default=False):
    """QSettings returns strings sometimes — coerce safely to bool."""
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    return str(value).lower() in ("1", "true", "yes", "on")


class AppSettings:
    """Thin wrapper around QSettings with typed getters/setters."""

    def __init__(self):
        self._s = QSettings(APP_ORG, APP_NAME)

    # generic helpers
    def get(self, key, default=None):
        return self._s.value(key, default)

    def set(self, key, value):
        self._s.setValue(key, value)
        self._s.sync()

    # ----- theme -----
    def theme(self) -> str:
        """Return the accent color code.

        Older builds stored "light" or "dark" in this key. Those values are now
        treated as appearance and the accent falls back to blue.
        """
        theme = str(self.get("theme", DEFAULT_COLOR_THEME) or DEFAULT_COLOR_THEME)
        if theme in (THEME_LIGHT, THEME_DARK, "system"):
            return DEFAULT_COLOR_THEME
        return theme if theme in COLOR_THEMES else DEFAULT_COLOR_THEME

    def set_theme(self, theme: str):
        if theme in (THEME_LIGHT, THEME_DARK):
            self.set_appearance(theme)
            theme = self.theme()
        if theme == "system":
            theme = DEFAULT_COLOR_THEME
        if theme not in COLOR_THEMES:
            theme = DEFAULT_COLOR_THEME
        self.set("theme", theme)

    def color_theme(self) -> str:
        return self.theme()

    def set_color_theme(self, theme: str):
        self.set_theme(theme)

    def appearance(self) -> str:
        # Prefer the new key. If an older install still has "theme=dark" or
        # "theme=light", convert that to the new appearance model.
        appearance = str(self.get("appearance", "") or "")
        if appearance in APPEARANCES:
            return appearance
        old_theme = str(self.get("theme", "") or "")
        if old_theme in (THEME_LIGHT, THEME_DARK):
            return old_theme
        return DEFAULT_APPEARANCE

    def set_appearance(self, appearance: str):
        if appearance not in APPEARANCES:
            appearance = DEFAULT_APPEARANCE
        self.set("appearance", appearance)

    def set_app_theme(self, appearance: str, color_theme: str):
        self.set_appearance(appearance)
        self.set_color_theme(color_theme)

    # ----- zoom -----
    def default_zoom(self) -> float:
        try:
            return float(self.get("default_zoom", 1.0))
        except (TypeError, ValueError):
            return 1.0

    def set_default_zoom(self, zoom: float):
        self.set("default_zoom", float(zoom))

    # ----- render quality -----
    def render_quality(self) -> str:
        from utils.constants import DEFAULT_RENDER_QUALITY
        return self.get("render_quality", DEFAULT_RENDER_QUALITY)

    def set_render_quality(self, quality: str):
        self.set("render_quality", quality)

    def render_dpi(self) -> int:
        """Resolved DPI from the chosen quality preset."""
        from utils.constants import RENDER_QUALITY_PRESETS, RENDER_DPI
        return int(RENDER_QUALITY_PRESETS.get(self.render_quality(), RENDER_DPI))

    # ----- auto fit on open -----
    def auto_fit_on_open(self) -> bool:
        return _as_bool(self.get("auto_fit_on_open", True), True)

    def set_auto_fit_on_open(self, on: bool):
        self.set("auto_fit_on_open", bool(on))

    # ----- view mode -----
    def view_mode(self) -> str:
        return self.get("view_mode", VIEW_CONTINUOUS)

    def set_view_mode(self, mode: str):
        self.set("view_mode", mode)

    # ----- recent files -----
    def recent_files(self) -> list:
        raw = self.get("recent_files", [])
        if isinstance(raw, str):
            raw = [raw]
        return list(raw) if raw else []

    def add_recent_file(self, path: str):
        files = self.recent_files()
        if path in files:
            files.remove(path)
        files.insert(0, path)
        files = files[:RECENT_FILES_MAX]
        self.set("recent_files", files)

    def remove_recent_file(self, path: str):
        files = self.recent_files()
        if path in files:
            files.remove(path)
            self.set("recent_files", files)

    def clear_recent_files(self):
        self.set("recent_files", [])

    # ----- OCR -----
    def ocr_language(self) -> str:
        return self.get("ocr_language", "eng")

    def set_ocr_language(self, lang: str):
        self.set("ocr_language", lang)

    # ----- interface (GUI) language -----
    def ui_language(self) -> str:
        return self.get("ui_language", "en")

    def set_ui_language(self, code: str):
        self.set("ui_language", code)

    # ----- annotation defaults -----
    def highlight_color(self) -> str:
        return self.get("annotation_highlight_color", DEFAULT_HIGHLIGHT_COLOR)

    def set_highlight_color(self, color: str):
        self.set("annotation_highlight_color", color)

    def pen_color(self) -> str:
        return self.get("annotation_pen_color", DEFAULT_PEN_COLOR)

    def set_pen_color(self, color: str):
        self.set("annotation_pen_color", color)

    def pen_width(self) -> int:
        try:
            return int(self.get("annotation_pen_width", DEFAULT_PEN_WIDTH))
        except (TypeError, ValueError):
            return DEFAULT_PEN_WIDTH

    def set_pen_width(self, width: int):
        self.set("annotation_pen_width", int(width))

    # ----- autosave -----
    def autosave_enabled(self) -> bool:
        return _as_bool(self.get("autosave_enabled", True), True)

    def set_autosave_enabled(self, enabled: bool):
        self.set("autosave_enabled", bool(enabled))

    def autosave_interval(self) -> int:
        try:
            return int(self.get("autosave_interval", 60))
        except (TypeError, ValueError):
            return 60

    def set_autosave_interval(self, seconds: int):
        self.set("autosave_interval", int(seconds))

    # ----- save folder -----
    def default_save_folder(self) -> str:
        return self.get("default_save_folder", "")

    def set_default_save_folder(self, folder: str):
        self.set("default_save_folder", folder)

    # ----- window geometry -----
    def save_geometry(self, geometry):
        self.set("window_geometry", geometry)

    def load_geometry(self):
        return self.get("window_geometry")
