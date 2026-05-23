"""Change the color of text on a PDF page.

PDF text editing is genuinely tricky. PDFs store text as glyphs in fonts,
and the embedded font may not exist on the user's system. So we do this:

  1. Read every text span on the page (text + bbox + font + size).
  2. Cover each span with a white rectangle (redaction).
  3. Re-insert the same text at the same position using a built-in font,
     but in the chosen color.

Caveat: the visual result is best on simple text-heavy PDFs. Complex
layouts (multi-column with images, exotic fonts, justified text) may
shift slightly. We use a reasonable substitution font.
"""

import fitz


def _hex_to_rgb01(hex_str: str):
    h = hex_str.lstrip("#")
    if len(h) != 6:
        return (0.0, 0.0, 0.0)
    r = int(h[0:2], 16) / 255.0
    g = int(h[2:4], 16) / 255.0
    b = int(h[4:6], 16) / 255.0
    return (r, g, b)


def _builtin_font_for(span_font: str) -> str:
    """Pick a builtin font that roughly matches the original span's font."""
    name = (span_font or "").lower()
    bold = "bold" in name or "black" in name or "heavy" in name
    italic = "italic" in name or "oblique" in name
    mono = "mono" in name or "courier" in name or "consolas" in name
    serif = ("serif" in name or "times" in name or "roman" in name
             or "georgia" in name)

    if mono:
        if bold and italic: return "cobi"
        if bold: return "cobo"
        if italic: return "coit"
        return "cour"
    if serif:
        if bold and italic: return "tibi"
        if bold: return "tibo"
        if italic: return "tiit"
        return "tiro"
    # default = helvetica
    if bold and italic: return "hebi"
    if bold: return "hebo"
    if italic: return "heit"
    return "helv"


def change_text_color_on_page(input_path: str,
                              output_path: str,
                              page_index: int,
                              new_color_hex: str = "#000000") -> dict:
    """Change the color of all text on one page.

    Returns a dict with stats: spans_changed, spans_skipped.
    """
    doc = fitz.open(input_path)
    if page_index < 0 or page_index >= doc.page_count:
        doc.close()
        raise IndexError("Page out of range")

    page = doc[page_index]
    color = _hex_to_rgb01(new_color_hex)

    # gather all text spans on this page
    page_dict = page.get_text("dict")
    spans = []
    for block in page_dict.get("blocks", []):
        if block.get("type") != 0:  # 0 = text block
            continue
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                text = span.get("text", "")
                if not text.strip():
                    continue
                bbox = span.get("bbox")  # (x0, y0, x1, y1)
                if not bbox:
                    continue
                spans.append({
                    "text": text,
                    "bbox": fitz.Rect(bbox),
                    "size": float(span.get("size", 11)),
                    "font": span.get("font", ""),
                })

    if not spans:
        doc.close()
        raise RuntimeError("This page has no extractable text to recolor. "
                           "Scanned/image-only pages need OCR first.")

    # 1) cover each span with a white rectangle
    for s in spans:
        page.add_redact_annot(s["bbox"], fill=(1, 1, 1))
    page.apply_redactions()

    # 2) re-draw each span in the new color
    changed = 0
    skipped = 0
    from utils.fonts import draw_text
    for s in spans:
        font_name = _builtin_font_for(s["font"])
        bbox = fitz.Rect(s["bbox"])
        try:
            draw_text(page, bbox, s["text"], s["size"], color=color,
                      default_font=font_name, align=0)
            changed += 1
        except Exception:
            skipped += 1

    doc.save(output_path, garbage=4, deflate=True)
    doc.close()
    return {"spans_changed": changed, "spans_skipped": skipped,
            "color": new_color_hex, "page": page_index + 1}
