"""Very small, dependency-free translation system for the GUI.

How it works
------------
* Each UI string is written in English in the code, wrapped in ``tr("...")``.
* Translations live in JSON files under ``resources/i18n/<code>.json`` as a
  simple ``{"English string": "translated string"}`` map.
* If a string has no translation (or the language is English) the original
  English text is shown — so nothing ever breaks or shows blank.

This deliberately uses the English source text as the lookup key, so adding
a new language is just dropping in a JSON file, and partially-translated
files still work (untranslated lines fall back to English).
"""

import os
import json

_PKG_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_I18N_DIR = os.path.join(_PKG_ROOT, "resources", "i18n")

# Languages we ship a starter translation for. (code -> native name)
# Anyone can add more by dropping a <code>.json file in resources/i18n.
AVAILABLE_LANGUAGES = {
    "en": "English",
    "bn": "বাংলা (Bangla)",
    "es": "Español (Spanish)",
    "ar": "العربية (Arabic)",
    "hi": "हिन्दी (Hindi)",
    "ja": "日本語 (Japanese)",
    "zh": "中文 (Chinese)",
    "de": "Deutsch (German)",
}

# scripts that read right-to-left (used so the app can mirror its layout)
RTL_LANGUAGES = {"ar", "he", "fa", "ur"}

_current = "en"
_table: dict[str, str] = {}


def available_languages() -> dict:
    """Return {code: display name}. Includes any extra JSON files found on
    disk that aren't in the built-in list."""
    langs = dict(AVAILABLE_LANGUAGES)
    try:
        for fn in os.listdir(_I18N_DIR):
            if fn.endswith(".json"):
                code = fn[:-5]
                langs.setdefault(code, code)
    except Exception:
        pass
    return langs


def set_language(code: str):
    """Load the translation table for ``code``. Falls back to English."""
    global _current, _table
    code = (code or "en").lower()
    _current = code
    _table = {}
    if code == "en":
        return
    path = os.path.join(_I18N_DIR, f"{code}.json")
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            _table = {str(k): str(v) for k, v in data.items() if v}
    except Exception:
        # missing or broken file → stay on English, don't crash
        _table = {}


def current_language() -> str:
    return _current


def is_rtl() -> bool:
    return _current in RTL_LANGUAGES


def tr(text: str) -> str:
    """Translate ``text`` to the current language, or return it unchanged."""
    if not text:
        return text
    return _table.get(text, text)
