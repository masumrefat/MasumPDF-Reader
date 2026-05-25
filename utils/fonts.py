"""Font handling for inserting / editing PDF text in many languages.

PDF built-in fonts only cover simple Latin text.  When the user edits or adds
text in another language, this module chooses a font that can display that
script and uses HTML-based drawing for scripts that require shaping/joining
(Bangla, Hindi, Arabic, Thai, etc.).

Important: this makes inserted replacement text visible and shaped correctly,
but it still cannot always reuse the exact original embedded/subset PDF font.
"""

import os
import glob

_PKG_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_BUNDLED_DIR = os.path.join(_PKG_ROOT, "resources", "fonts")


def _bundled(name: str) -> str:
    return os.path.join(_BUNDLED_DIR, name)


# Backwards-compatible constant (other code imports this).
BANGLA_FONT_PATH = _bundled("NotoSansBengali.ttf")


# --------------------------------------------------------------------------
# 1) script detection
# --------------------------------------------------------------------------
_SCRIPT_RANGES = {
    "bangla":      [(0x0980, 0x09FF)],
    "devanagari":  [(0x0900, 0x097F)],      # Hindi, Marathi, Nepali
    "gujarati":    [(0x0A80, 0x0AFF)],
    "gurmukhi":    [(0x0A00, 0x0A7F)],      # Punjabi
    "tamil":       [(0x0B80, 0x0BFF)],
    "telugu":      [(0x0C00, 0x0C7F)],
    "kannada":     [(0x0C80, 0x0CFF)],
    "malayalam":   [(0x0D00, 0x0D7F)],
    "sinhala":     [(0x0D80, 0x0DFF)],
    "arabic":      [(0x0600, 0x06FF), (0x0750, 0x077F), (0x08A0, 0x08FF)],
    "hebrew":      [(0x0590, 0x05FF)],
    "thai":        [(0x0E00, 0x0E7F)],
    "myanmar":     [(0x1000, 0x109F)],
    "cyrillic":    [(0x0400, 0x04FF), (0x0500, 0x052F)],
    "greek":       [(0x0370, 0x03FF)],
    "cjk_jp":      [(0x3040, 0x309F), (0x30A0, 0x30FF)],   # Kana => Japanese
    "korean":      [(0xAC00, 0xD7A3), (0x3130, 0x318F)],   # Hangul
    "han":         [(0x4E00, 0x9FFF), (0x3400, 0x4DBF),
                    (0xF900, 0xFAFF)],                     # Chinese ideographs
}

_SCRIPT_PRIORITY = [
    "bangla", "devanagari", "gujarati", "gurmukhi", "tamil", "telugu",
    "kannada", "malayalam", "sinhala", "arabic", "hebrew", "thai",
    "myanmar", "cjk_jp", "korean", "han", "cyrillic", "greek",
]


def _in_ranges(cp, ranges) -> bool:
    return any(lo <= cp <= hi for lo, hi in ranges)


def _in_ranges_any(text, ranges) -> bool:
    return any(_in_ranges(ord(c), ranges) for c in (text or ""))


def needs_unicode_font(text: str) -> bool:
    """True if text has characters outside Latin-1."""
    return any(ord(c) > 0xFF for c in (text or ""))


def detect_script(text: str) -> str:
    """Return a script id like latin, bangla, arabic, cjk_jp, etc."""
    found = set()
    for ch in (text or ""):
        cp = ord(ch)
        for script, ranges in _SCRIPT_RANGES.items():
            if _in_ranges(cp, ranges):
                found.add(script)
                break
    if not found:
        return "other" if needs_unicode_font(text) else "latin"
    for script in _SCRIPT_PRIORITY:
        if script in found:
            return script
    return "latin"


# kept for backward compatibility with earlier code
def has_bangla(text: str) -> bool:
    return _in_ranges_any(text, _SCRIPT_RANGES["bangla"])


def has_cjk(text: str) -> bool:
    return detect_script(text) in ("cjk_jp", "korean", "han")


# --------------------------------------------------------------------------
# 2) script -> font registry
# --------------------------------------------------------------------------
# Entry types:
#   ("builtin", "japan")       -> PyMuPDF CJK built-in font, no file needed
#   ("file", "Noto….ttf")      -> bundled font file in resources/fonts
#   ("system", [name hints])    -> search OS fonts for a suitable font file
SCRIPT_FONTS = {
    "latin":      ("builtin", "helv"),

    # Bundled names first. If the file is not bundled, system candidates below
    # are searched. On Windows, Nirmala UI usually covers many Indic scripts.
    "bangla":     ("file", "NotoSansBengali.ttf"),
    "devanagari": ("file", "NotoSansDevanagari-Regular.ttf"),
    "gujarati":   ("file", "NotoSansGujarati-Regular.ttf"),
    "gurmukhi":   ("file", "NotoSansGurmukhi-Regular.ttf"),
    "tamil":      ("file", "NotoSansTamil-Regular.ttf"),
    "telugu":     ("file", "NotoSansTelugu-Regular.ttf"),
    "kannada":    ("file", "NotoSansKannada-Regular.ttf"),
    "malayalam":  ("file", "NotoSansMalayalam-Regular.ttf"),
    "sinhala":    ("file", "NotoSansSinhala-Regular.ttf"),
    "arabic":     ("file", "NotoSansArabic-Regular.ttf"),
    "hebrew":     ("file", "NotoSansHebrew-Regular.ttf"),
    "thai":       ("file", "NotoSansThai-Regular.ttf"),
    "myanmar":    ("file", "NotoSansMyanmar-Regular.ttf"),

    # CJK uses PyMuPDF's built-in CJK fonts: no huge bundled files needed.
    "cjk_jp":     ("builtin", "japan"),
    "korean":     ("builtin", "korea"),
    "han":        ("builtin", "china-s"),

    "cyrillic":   ("system", ["NotoSans", "Arial", "DejaVuSans", "SegoeUI", "Tahoma"]),
    "greek":      ("system", ["NotoSans", "Arial", "DejaVuSans", "SegoeUI", "Tahoma"]),
}

# Script-specific system font hints.  These are searched when a bundled Noto
# font is not present. The list includes common Windows/macOS/Linux font names.
SCRIPT_SYSTEM_HINTS = {
    "bangla":     ["NotoSansBengali", "Nirmala", "Vrinda", "Shonar", "Solaiman", "Kalpurush", "Bangla", "Siyam"],
    "devanagari": ["NotoSansDevanagari", "Nirmala", "Mangal", "Kokila", "Aparajita", "Sanskrit", "Devanagari"],
    "gujarati":   ["NotoSansGujarati", "Nirmala", "Shruti", "Gujarati"],
    "gurmukhi":   ["NotoSansGurmukhi", "Nirmala", "Raavi", "Gurmukhi"],
    "tamil":      ["NotoSansTamil", "Nirmala", "Latha", "Vijaya", "Tamil"],
    "telugu":     ["NotoSansTelugu", "Nirmala", "Gautami", "Vani", "Telugu"],
    "kannada":    ["NotoSansKannada", "Nirmala", "Tunga", "Kannada"],
    "malayalam":  ["NotoSansMalayalam", "Nirmala", "Kartika", "Rachana", "Lohit-Malayalam", "Malayalam"],
    "sinhala":    ["NotoSansSinhala", "Nirmala", "Iskoola", "Sinhala"],
    "arabic":     ["NotoSansArabic", "Segoe UI", "Tahoma", "Arial", "Geeza", "Arabic"],
    "hebrew":     ["NotoSansHebrew", "Segoe UI", "Arial", "Tahoma", "Hebrew"],
    "thai":       ["NotoSansThai", "Leelawadee", "Tahoma", "Thonburi", "Thai"],
    "myanmar":    ["NotoSansMyanmar", "Myanmar Text", "Padauk", "Myanmar"],
    "cyrillic":   ["NotoSans", "Arial", "DejaVuSans", "LiberationSans", "Segoe UI", "Tahoma"],
    "greek":      ["NotoSans", "Arial", "DejaVuSans", "LiberationSans", "Segoe UI", "Tahoma"],
    "other":      ["NotoSans", "Arial Unicode", "ArialUni", "Arial", "DejaVuSans", "Segoe UI", "Tahoma"],
}

_SYS_FONT_DIRS = [
    "/usr/share/fonts", "/usr/local/share/fonts",
    os.path.expanduser("~/.fonts"), os.path.expanduser("~/.local/share/fonts"),
    "C:/Windows/Fonts", "/Library/Fonts", "/System/Library/Fonts",
    os.path.expanduser("~/Library/Fonts"),
]

_font_cache: dict[tuple[str, tuple[str, ...]], str | None] = {}


def _norm_name(s: str) -> str:
    return "".join(ch.lower() for ch in s if ch.isalnum())


def _find_system_font(hints) -> str | None:
    """Find a font file whose file name contains one of the hints."""
    hints = tuple(hints or [])
    key = ("system", tuple(_norm_name(h) for h in hints))
    if key in _font_cache:
        return _font_cache[key]

    files = []
    for d in _SYS_FONT_DIRS:
        if d and os.path.isdir(d):
            for ext in ("ttf", "otf", "ttc"):
                files.extend(glob.glob(os.path.join(d, "**", f"*.{ext}"), recursive=True))

    # Prefer regular fonts over bold/italic variants unless no other exists.
    def score(path, hint):
        name = _norm_name(os.path.basename(path))
        h = _norm_name(hint)
        if h not in name:
            return None
        penalty = 0
        # Prefer normal/regular fonts for editing. Heavy, condensed, or slanted
        # variants can make replacement text look very different from the PDF.
        for bad in ("black", "extrabold", "semibold", "bold", "italic",
                    "oblique", "extralight", "light", "thin", "medium",
                    "condensed", "narrow"):
            if bad in name:
                penalty += 8
        if "regular" in name or name.endswith(h):
            penalty -= 3
        return penalty + abs(len(name) - len(h)) / 1000

    best = None
    best_score = 10**9
    for hint in hints:
        for f in files:
            s = score(f, hint)
            if s is not None and s < best_score:
                best = f
                best_score = s
    _font_cache[key] = best
    return best


def bangla_font() -> str | None:
    return BANGLA_FONT_PATH if os.path.isfile(BANGLA_FONT_PATH) else _find_system_font(SCRIPT_SYSTEM_HINTS["bangla"])


def wide_font() -> str | None:
    return _find_system_font(SCRIPT_SYSTEM_HINTS["other"])


def font_file_for(text: str) -> str | None:
    """Return a font file path for ``text`` if a file font is needed."""
    script = detect_script(text)
    kind, val = SCRIPT_FONTS.get(script, ("system", SCRIPT_SYSTEM_HINTS.get(script, SCRIPT_SYSTEM_HINTS["other"])))

    if kind == "file":
        p = _bundled(val)
        if os.path.isfile(p):
            return p
        return _find_system_font(SCRIPT_SYSTEM_HINTS.get(script, SCRIPT_SYSTEM_HINTS["other"]))

    if kind == "system":
        return _find_system_font(val)

    # built-in Latin and CJK do not need a font file.
    if script in ("latin", "cjk_jp", "korean", "han"):
        return None
    return wide_font()


# --------------------------------------------------------------------------
# 3) the one call sites use
# --------------------------------------------------------------------------
_registered = set()


def font_for_page(page, text: str, default: str = "helv"):
    """Detect the script of text and return (fontname, fontfile)."""
    if not needs_unicode_font(text):
        return default, None

    script = detect_script(text)
    kind, val = SCRIPT_FONTS.get(script, (None, None))

    # PyMuPDF built-in CJK fonts.
    if kind == "builtin" and val and val != "helv":
        return val, None

    path = font_file_for(text)
    if not path:
        return default, None

    alias = "f_" + script
    try:
        doc = page.parent
        key = (id(doc), id(page), alias, path)
        if key not in _registered:
            page.insert_font(fontname=alias, fontfile=path)
            _registered.add(key)
        return alias, path
    except Exception:
        return default, None


# Scripts whose letters need shaping/joining. Use insert_htmlbox for these.
_COMPLEX_SCRIPTS = {
    "bangla", "devanagari", "gujarati", "gurmukhi", "tamil", "telugu",
    "kannada", "malayalam", "sinhala", "arabic", "thai", "myanmar",
}


def is_complex_script(text: str) -> bool:
    return detect_script(text) in _COMPLEX_SCRIPTS


def _rgb_to_hex(color) -> str:
    if isinstance(color, str):
        return color if color.startswith("#") else "#" + color
    try:
        r, g, b = color
        return "#%02x%02x%02x" % (int(r * 255), int(g * 255), int(b * 255))
    except Exception:
        return "#000000"


def draw_text(page, rect, text, font_size, color="#000000",
              default_font="helv", align=0, bold=False, italic=False):
    """Draw text inside rect with language-aware font handling."""
    import fitz
    script = detect_script(text)

    # Complex scripts: HTML layout gives proper shaping / joining.
    if script in _COMPLEX_SCRIPTS:
        path = font_file_for(text)
        if path:
            import html as _html
            hex_color = _rgb_to_hex(color)
            align_css = {0: "left", 1: "center", 2: "right"}.get(align, "left")
            weight = "bold" if bold else "normal"
            slant = "italic" if italic else "normal"
            css = (f"@font-face{{font-family:ed;src:url({path});}}"
                   f"*{{font-family:ed;font-size:{font_size}px;"
                   f"color:{hex_color};text-align:{align_css};"
                   f"font-weight:{weight};font-style:{slant};"
                   f"margin:0;padding:0;line-height:1.18;}}")
            try:
                page_h = page.rect.height
                final_box = fitz.Rect(rect.x0, rect.y0, rect.x1,
                                      min(page_h - 2, rect.y1 + font_size * 0.8))
                page.insert_htmlbox(final_box, _html.escape(text), css=css)
                return True
            except Exception:
                try:
                    page.insert_htmlbox(rect, _html.escape(text), css=css)
                    return True
                except Exception:
                    pass

    # Simple scripts / fallback: textbox with suitable font.
    fn, ff = font_for_page(page, text, default_font)
    if ff is None and fn in ("helv", "tiro", "cour"):
        fn = _styled_builtin(fn, bold, italic)
    rgb = color
    if isinstance(color, str):
        h = color.lstrip("#")
        if len(h) == 6:
            rgb = (int(h[0:2], 16) / 255, int(h[2:4], 16) / 255,
                   int(h[4:6], 16) / 255)
        else:
            rgb = (0, 0, 0)

    used = font_size
    while used >= 5:
        try:
            res = page.insert_textbox(rect, text, fontname=fn, fontfile=ff,
                                      fontsize=used, color=rgb, align=align,
                                      render_mode=0)
            if res >= 0:
                return True
        except Exception:
            break
        used -= 1
    try:
        page.insert_text((rect.x0, rect.y1 - 2), text, fontname=fn,
                         fontfile=ff, fontsize=min(font_size, 10), color=rgb)
        return True
    except Exception:
        return False


def _styled_builtin(base: str, bold: bool, italic: bool) -> str:
    table = {
        "helv": {(0, 0): "helv", (1, 0): "hebo", (0, 1): "heit", (1, 1): "hebi"},
        "tiro": {(0, 0): "tiro", (1, 0): "tibo", (0, 1): "tiit", (1, 1): "tibi"},
        "cour": {(0, 0): "cour", (1, 0): "cobo", (0, 1): "coit", (1, 1): "cobi"},
    }
    return table.get(base, table["helv"])[(1 if bold else 0, 1 if italic else 0)]
