"""Font handling for inserting text into PDFs in ANY language.

The idea (as suggested): when we draw or edit text, we first detect which
SCRIPT the text is written in, then pick a font that actually supports that
script. PDF's 14 built-in fonts only cover Latin, so for everything else we
either use one of PyMuPDF's built-in CJK fonts or a Noto font bundled with
the app.

Architecture
------------
* `detect_script(text)`  -> a short script id like "latin", "bangla",
  "arabic", "cjk_jp", ...
* `SCRIPT_FONTS`         -> maps each script id to how to draw it: either a
  built-in PyMuPDF font name, or a bundled .ttf file.
* `font_for_page(page, text)` -> the one call sites use. It detects the
  script, makes sure the right font is available on the page, and returns
  the (fontname, fontfile) pair to hand straight to insert_text/textbox.

Adding support for a new language later is just: drop a Noto .ttf in
resources/fonts and add one line to SCRIPT_FONTS.
"""

import os

# resources/fonts lives next to this package's parent.
_PKG_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_BUNDLED_DIR = os.path.join(_PKG_ROOT, "resources", "fonts")


def _bundled(name: str) -> str:
    return os.path.join(_BUNDLED_DIR, name)


# Backwards-compatible constant (other code imports this).
BANGLA_FONT_PATH = _bundled("NotoSansBengali.ttf")


# --------------------------------------------------------------------------
# 1) script detection
# --------------------------------------------------------------------------
# Each entry: script id -> list of (start, end) Unicode ranges.
_SCRIPT_RANGES = {
    "bangla":      [(0x0980, 0x09FF)],
    "devanagari":  [(0x0900, 0x097F)],          # Hindi, Marathi, etc.
    "arabic":      [(0x0600, 0x06FF), (0x0750, 0x077F), (0x08A0, 0x08FF)],
    "hebrew":      [(0x0590, 0x05FF)],
    "thai":        [(0x0E00, 0x0E7F)],
    "cjk_jp":      [(0x3040, 0x309F), (0x30A0, 0x30FF)],   # kana => Japanese
    "korean":      [(0xAC00, 0xD7A3), (0x3130, 0x318F)],   # Hangul
    "han":         [(0x4E00, 0x9FFF), (0x3400, 0x4DBF),
                    (0xF900, 0xFAFF)],                     # Chinese ideographs
}

# Order matters: kana (Japanese) and Hangul (Korean) are checked before plain
# Han, because Japanese/Korean text also contains Han characters.
_SCRIPT_PRIORITY = ["bangla", "devanagari", "arabic", "hebrew", "thai",
                    "cjk_jp", "korean", "han"]


def _in_ranges(cp, ranges) -> bool:
    return any(lo <= cp <= hi for lo, hi in ranges)


def detect_script(text: str) -> str:
    """Return the dominant non-Latin script id in `text`, or 'latin' if the
    text is plain Latin-1 (drawable with the built-in fonts)."""
    if not text:
        return "latin"
    found = set()
    for c in text:
        cp = ord(c)
        if cp <= 0xFF:
            continue  # Latin-1, ignore
        for script in _SCRIPT_PRIORITY:
            if _in_ranges(cp, _SCRIPT_RANGES[script]):
                found.add(script)
                break
    if not found:
        # has non-Latin chars but none we specifically know — treat as needing
        # a broad font
        return "other" if needs_unicode_font(text) else "latin"
    # pick by priority
    for script in _SCRIPT_PRIORITY:
        if script in found:
            return script
    return "latin"


def needs_unicode_font(text: str) -> bool:
    """True if text has characters outside Latin-1."""
    return any(ord(c) > 0xFF for c in (text or ""))


# kept for backward compatibility with earlier code
def has_bangla(text: str) -> bool:
    return _in_ranges_any(text, _SCRIPT_RANGES["bangla"])


def has_cjk(text: str) -> bool:
    return any(detect_script(text) in ("cjk_jp", "korean", "han")
               for _ in [0])


def _in_ranges_any(text, ranges) -> bool:
    return any(_in_ranges(ord(c), ranges) for c in (text or ""))


# --------------------------------------------------------------------------
# 2) script -> font registry
# --------------------------------------------------------------------------
# Two kinds of entry:
#   ("builtin", "japan")   -> a PyMuPDF base font, no file needed
#   ("file", "Noto….ttf")  -> a bundled font file in resources/fonts
SCRIPT_FONTS = {
    "latin":      ("builtin", "helv"),
    "bangla":     ("file", "NotoSansBengali.ttf"),
    "devanagari": ("file", "NotoSansDevanagari-Regular.ttf"),
    "arabic":     ("file", "NotoSansArabic-Regular.ttf"),
    "hebrew":     ("file", "NotoSansHebrew-Regular.ttf"),
    "thai":       ("file", "NotoSansThai-Regular.ttf"),
    # CJK uses PyMuPDF's built-in fonts (no big files to bundle):
    "cjk_jp":     ("builtin", "japan"),
    "korean":     ("builtin", "korea"),
    "han":        ("builtin", "china-s"),
}


def bangla_font() -> str | None:
    return BANGLA_FONT_PATH if os.path.isfile(BANGLA_FONT_PATH) else None


_SYS_FONT_DIRS = [
    "/usr/share/fonts", "/usr/local/share/fonts",
    os.path.expanduser("~/.fonts"),
    "C:/Windows/Fonts", "/Library/Fonts", "/System/Library/Fonts",
    os.path.expanduser("~/Library/Fonts"),
]
_WIDE_HINTS = ["NotoSans-Regular", "Arial Unicode", "ArialUni", "Arial",
               "Tahoma", "DejaVuSans"]
_wide_cache = (False, None)


def wide_font() -> str | None:
    """A broad-coverage system font, for scripts we don't have a bundled font
    for. Cached after first lookup."""
    global _wide_cache
    import glob
    checked, path = _wide_cache
    if checked:
        return path
    found = None
    for d in _SYS_FONT_DIRS:
        if not d or not os.path.isdir(d):
            continue
        for hint in _WIDE_HINTS:
            for ext in ("ttf", "otf", "ttc"):
                m = glob.glob(os.path.join(d, "**", f"*{hint}*.{ext}"),
                              recursive=True)
                if m:
                    found = m[0]
                    break
            if found:
                break
        if found:
            break
    _wide_cache = (True, found)
    return found


def font_file_for(text: str) -> str | None:
    """Path to a font FILE that supports `text`, or None if a built-in font
    (Latin or CJK) should be used instead."""
    script = detect_script(text)
    kind, val = SCRIPT_FONTS.get(script, ("builtin", "helv"))
    if kind == "file":
        p = _bundled(val)
        if os.path.isfile(p):
            return p
    if script in ("latin", "cjk_jp", "korean", "han"):
        return None  # built-in handles it
    # bundled file missing or unknown script -> best-effort system font
    return wide_font()


# --------------------------------------------------------------------------
# 3) the one call sites use
# --------------------------------------------------------------------------
_registered = set()


def font_for_page(page, text: str, default: str = "helv"):
    """Detect the script of `text`, ensure a supporting font is on `page`,
    and return (fontname, fontfile) for insert_text / insert_textbox.

    * Latin            -> (default, None)
    * CJK              -> ("japan"/"korea"/"china-s", None)   [built-in]
    * Bangla/Arabic/…  -> (alias, path) with the bundled Noto font embedded
    """
    if not needs_unicode_font(text):
        return default, None

    script = detect_script(text)
    kind, val = SCRIPT_FONTS.get(script, (None, None))

    # CJK / built-in fonts: no file, just use the name
    if kind == "builtin" and val and val != "helv":
        return val, None

    # file-based fonts (Bangla, Arabic, Hebrew, Thai, Devanagari, or fallback)
    path = font_file_for(text)
    if not path:
        return default, None

    # register the file on this page once; alias per script keeps them distinct
    alias = "f_" + script
    try:
        doc = page.parent
        key = (id(doc), id(page), alias)
        if key not in _registered:
            page.insert_font(fontname=alias, fontfile=path)
            _registered.add(key)
        return alias, path
    except Exception:
        return default, None


# scripts whose letters JOIN/RESHAPE and therefore need real text shaping
# (insert_textbox just places glyphs side-by-side and breaks these).
_COMPLEX_SCRIPTS = {"bangla", "devanagari", "arabic", "thai"}


def _rgb_to_hex(color) -> str:
    """Accept a #hex string or an (r,g,b) 0..1 tuple, return #rrggbb."""
    if isinstance(color, str):
        return color if color.startswith("#") else "#" + color
    try:
        r, g, b = color
        return "#%02x%02x%02x" % (int(r * 255), int(g * 255), int(b * 255))
    except Exception:
        return "#000000"


def draw_text(page, rect, text, font_size, color="#000000",
              default_font="helv", align=0, bold=False, italic=False):
    """Draw `text` inside `rect` on `page`, choosing the right method for the
    script:

      * complex scripts (Bangla, Devanagari, Arabic, Thai) -> insert_htmlbox,
        which does proper letter shaping / joining (conjuncts render right).
      * everything else -> insert_textbox with the correct font.

    `bold` / `italic` preserve the original text's weight and slant so an
    edited heading stays a heading. Returns True on success."""
    import fitz
    script = detect_script(text)

    # ---- complex scripts: use HTML layout so conjuncts join correctly ----
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
                   f"margin:0;padding:0;line-height:1.2;}}")
            # insert_htmlbox AUTO-SHRINKS the text if it doesn't fit the box,
            # which is what made edited headings come out tiny. To keep the
            # requested font size, we measure the needed height in a SEPARATE
            # throwaway document (touching the live page would invalidate it),
            # then give the real box that much height so no shrinking happens.
            try:
                import fitz as _fitz
                measure_doc = _fitz.open()
                mp = measure_doc.new_page(width=page.rect.width, height=3000)
                tall = fitz.Rect(rect.x0, 0, rect.x1, 2900)
                spare, _scale = mp.insert_htmlbox(
                    tall, _html.escape(text), css=css)
                used_h = 2900 - spare           # height the text occupied
                measure_doc.close()
            except Exception:
                used_h = (rect.y1 - rect.y0)     # fall back to original height

            try:
                page_h = page.rect.height
                draw_h = min(used_h + font_size * 0.4, page_h - rect.y0 - 2)
                draw_h = max(draw_h, font_size * 1.3)
                final_box = fitz.Rect(rect.x0, rect.y0, rect.x1,
                                      rect.y0 + draw_h)
                page.insert_htmlbox(final_box, _html.escape(text), css=css)
                return True
            except Exception:
                try:
                    page.insert_htmlbox(
                        fitz.Rect(rect.x0, rect.y0, rect.x1, rect.y1),
                        _html.escape(text), css=css)
                    return True
                except Exception:
                    pass  # fall through to textbox

    # ---- simple scripts / fallback: plain textbox with the right font ----
    fn, ff = font_for_page(page, text, default_font)
    # apply bold/italic for built-in Latin fonts when no embedded file is used
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
        res = page.insert_textbox(rect, text, fontname=fn, fontfile=ff,
                                  fontsize=used, color=rgb, align=align,
                                  render_mode=0)
        if res >= 0:
            return True
        used -= 1
    try:
        page.insert_text((rect.x0, rect.y1 - 2), text, fontname=fn,
                         fontfile=ff, fontsize=min(font_size, 10), color=rgb)
        return True
    except Exception:
        return False


def _styled_builtin(base: str, bold: bool, italic: bool) -> str:
    """Map a base built-in font to its bold/italic variant."""
    table = {
        "helv": {(0, 0): "helv", (1, 0): "hebo", (0, 1): "heit", (1, 1): "hebi"},
        "tiro": {(0, 0): "tiro", (1, 0): "tibo", (0, 1): "tiit", (1, 1): "tibi"},
        "cour": {(0, 0): "cour", (1, 0): "cobo", (0, 1): "coit", (1, 1): "cobi"},
    }
    return table.get(base, {}).get((int(bool(bold)), int(bool(italic))), base)
