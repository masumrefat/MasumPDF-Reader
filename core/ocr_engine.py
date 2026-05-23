"""OCR using pytesseract.

Renders each PDF page to an image, runs Tesseract, and stitches the
recognised text back into a searchable PDF.

Tesseract must be installed on the host:
  Windows  : https://github.com/UB-Mannheim/tesseract/wiki
  macOS    : brew install tesseract
  Linux    : sudo apt install tesseract-ocr
"""

import os
import glob
import fitz


# Common system fonts that cover the "hard" scripts PyMuPDF's built-in
# base fonts do NOT (Arabic, Hebrew, Thai, Devanagari/Indic). We look for
# any of these on the user's machine and embed it so the invisible OCR
# text layer is genuinely searchable in those languages too.
_WIDE_FONT_HINTS = [
    "NotoSans-Regular", "NotoSansArabic-Regular", "NotoSansHebrew-Regular",
    "NotoSansThai-Regular", "NotoSansDevanagari-Regular", "NotoNaskhArabic",
    "Arial Unicode", "ArialUni", "Arial", "Tahoma", "DejaVuSans",
]

_FONT_SEARCH_DIRS = [
    "/usr/share/fonts", "/usr/local/share/fonts",
    os.path.expanduser("~/.fonts"),
    "C:/Windows/Fonts",
    "/Library/Fonts", "/System/Library/Fonts",
    os.path.expanduser("~/Library/Fonts"),
]


def _find_wide_font() -> str | None:
    """Return a path to a broad-Unicode TTF/OTF on this machine, or None."""
    for d in _FONT_SEARCH_DIRS:
        if not d or not os.path.isdir(d):
            continue
        for hint in _WIDE_FONT_HINTS:
            for ext in ("ttf", "otf", "ttc"):
                matches = glob.glob(os.path.join(d, "**", f"*{hint}*.{ext}"),
                                    recursive=True)
                if matches:
                    return matches[0]
    return None


class OCREngine:
    # which built-in PyMuPDF base font best fits a given Tesseract language
    _BUILTIN_FONT_FOR = {
        "jpn": "japan", "kor": "korea",
        "chi_sim": "china-s", "chi_tra": "china-t",
    }

    def __init__(self, language: str = "eng", dpi: int = 200):
        self.language = language
        self.dpi = dpi
        self._wide_font_path = None
        self._wide_font_checked = False

    def _wide_font(self) -> str | None:
        if not self._wide_font_checked:
            # Prefer the bundled Noto font for Bengali OCR; otherwise look for
            # a broad system font.
            path = None
            try:
                from utils.fonts import bangla_font, wide_font
                if "ben" in str(self.language):
                    path = bangla_font()
                if not path:
                    path = wide_font() or bangla_font()
            except Exception:
                path = _find_wide_font()
            self._wide_font_path = path
            self._wide_font_checked = True
        return self._wide_font_path

    def is_available(self) -> bool:
        try:
            import pytesseract
            pytesseract.get_tesseract_version()
            return True
        except Exception:
            return False

    def installed_languages(self) -> list:
        """Return the list of language codes Tesseract actually has installed
        on this machine (e.g. ['eng', 'jpn', 'ara']). Empty list if it can't
        be determined."""
        try:
            import pytesseract
            return list(pytesseract.get_languages(config="")) or []
        except Exception:
            return []

    def missing_languages(self) -> list:
        """Of the languages this engine is set to use, which are NOT installed.
        Handles combined codes like 'eng+jpn'."""
        installed = set(self.installed_languages())
        if not installed:
            return []  # can't tell — let Tesseract try and report later
        wanted = [c for c in str(self.language).split("+") if c]
        return [c for c in wanted if c not in installed]


    def ocr_page_to_text(self, pdf_path: str, page_index: int) -> str:
        import pytesseract
        from PIL import Image
        import io
        doc = fitz.open(pdf_path)
        page = doc.load_page(page_index)
        zoom = self.dpi / 72.0
        pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
        img = Image.open(io.BytesIO(pix.tobytes("png")))
        text = pytesseract.image_to_string(img, lang=self.language)
        doc.close()
        return text

    def ocr_pdf_to_searchable(self, pdf_path: str, output_path: str, progress_cb=None):
        """Build a new PDF where each page has an invisible text layer."""
        import pytesseract
        from PIL import Image
        import io

        src = fitz.open(pdf_path)
        out = fitz.open()  # blank target
        total = src.page_count
        zoom = self.dpi / 72.0
        mat = fitz.Matrix(zoom, zoom)

        # Decide once which font(s) we can use for this language.
        primary = self.language.split("+")[0]
        builtin = self._BUILTIN_FONT_FOR.get(primary)  # CJK base font or None
        wide_path = self._wide_font()                   # broad TTF or None
        wide_fontname = "wf0"                            # internal alias

        for i in range(total):
            page = src.load_page(i)
            pix = page.get_pixmap(matrix=mat, alpha=False)
            img = Image.open(io.BytesIO(pix.tobytes("png")))

            new_page = out.new_page(width=page.rect.width, height=page.rect.height)
            img_bytes = pix.tobytes("png")
            new_page.insert_image(new_page.rect, stream=img_bytes)

            # register the wide system font on this page if we have one
            if wide_path:
                try:
                    new_page.insert_font(fontname=wide_fontname, fontfile=wide_path)
                except Exception:
                    wide_path = None  # registration failed; stop trying

            try:
                data = pytesseract.image_to_data(
                    img, lang=self.language, output_type=pytesseract.Output.DICT
                )
            except Exception:
                data = None

            if data:
                for j in range(len(data.get("text", []))):
                    word = data["text"][j].strip()
                    if not word:
                        continue
                    x, y, w, h = (data["left"][j], data["top"][j],
                                  data["width"][j], data["height"][j])
                    x0, y0 = x / zoom, y / zoom
                    rect = fitz.Rect(x0, y0, x0 + w / zoom, y0 + h / zoom)
                    fontsize = max(rect.height * 0.8, 4)
                    self._insert_word(new_page, rect, word, fontsize,
                                      builtin, wide_path, wide_fontname)

            if progress_cb:
                progress_cb(i + 1, total)

        out.save(output_path, garbage=4, deflate=True)
        out.close()
        src.close()

    @staticmethod
    def _insert_word(page, rect, word, fontsize, builtin, wide_path,
                     wide_fontname):
        """Insert one recognised word as an invisible (render_mode=3) text
        box, choosing a font that can actually encode the characters.

        Order of preference:
          1. plain ASCII  -> Helvetica (fast, always works)
          2. a wide system TTF if we found one (covers Arabic/Hebrew/Thai/Indic)
          3. the matching CJK base font for Japanese/Korean/Chinese
          4. Helvetica as a last resort (may drop glyphs, but never crashes)
        """
        attempts = []
        if word.isascii():
            attempts.append("helv")
        # Script-specific CJK base font first — it reliably covers its script.
        if builtin:
            attempts.append(builtin)
        # Generic CJK font: also covers Cyrillic, Greek and CJK ranges.
        attempts.append("china-s")
        # A wide system TTF (if found) is the best shot for Arabic/Hebrew/
        # Thai/Indic, which none of the built-in fonts cover.
        if wide_path:
            attempts.append(wide_fontname)
        # Last resort — never crashes, but may drop unsupported glyphs.
        attempts.append("helv")

        for fontname in attempts:
            try:
                page.insert_textbox(rect, word, fontname=fontname,
                                    fontsize=fontsize, render_mode=3)
                return
            except Exception:
                continue

    @staticmethod
    def is_scanned(pdf_path: str, sample_pages: int = 3) -> bool:
        """Heuristic: if the first few pages have little or no text, treat as scanned."""
        doc = fitz.open(pdf_path)
        n = min(sample_pages, doc.page_count)
        total_text = 0
        for i in range(n):
            total_text += len(doc.load_page(i).get_text().strip())
        doc.close()
        return total_text < 40  # < ~40 chars across sample = probably scanned
