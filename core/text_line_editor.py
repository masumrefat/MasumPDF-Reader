"""Edit a single line of text on a PDF page.

Same approach as text_editor.py but scoped to one line:
  1. White out the line's bbox with a redaction.
  2. Re-insert the chosen text inside the same bbox using a built-in font.

Caveat (be honest with the user): the original font may not be a built-in
font, so the replacement will use one of helv / tiro / cour with bold /
italic variants picked to roughly match. Layout-heavy PDFs can shift
slightly. Works best on regular text documents.
"""

import fitz


def _hex_to_rgb01(hex_str: str):
    h = hex_str.lstrip("#")
    if len(h) != 6:
        return (0.0, 0.0, 0.0)
    return (int(h[0:2], 16) / 255.0,
            int(h[2:4], 16) / 255.0,
            int(h[4:6], 16) / 255.0)


def _builtin_font_for(span_font: str) -> str:
    name = (span_font or "").lower()
    bold = "bold" in name or "black" in name or "heavy" in name
    italic = "italic" in name or "oblique" in name
    mono = "mono" in name or "courier" in name or "consolas" in name
    serif = ("serif" in name or "times" in name or "roman" in name
             or "georgia" in name)
    if mono:
        return "cobi" if (bold and italic) else "cobo" if bold else "coit" if italic else "cour"
    if serif:
        return "tibi" if (bold and italic) else "tibo" if bold else "tiit" if italic else "tiro"
    return "hebi" if (bold and italic) else "hebo" if bold else "heit" if italic else "helv"


def edit_line_text(input_path: str,
                   output_path: str,
                   page_index: int,
                   line_bbox: tuple,
                   new_text: str,
                   font_size: float | None = None,
                   font_hint: str = "",
                   color_hex: str = "#000000") -> dict:
    """Replace the text inside a line bbox with new_text.

    Returns stats: {"changed": bool, "page": int, "new_text": str}
    """
    doc = fitz.open(input_path)
    if page_index < 0 or page_index >= doc.page_count:
        doc.close()
        raise IndexError("Page out of range")

    page = doc[page_index]
    rect = fitz.Rect(*line_bbox)

    # 1) White-out the line
    page.add_redact_annot(rect, fill=(1, 1, 1))
    page.apply_redactions()

    # 2) Re-insert the new text in the same bbox
    if not new_text:
        # User just wanted to delete the line — nothing to draw
        doc.save(output_path, garbage=4, deflate=True)
        doc.close()
        return {"changed": True, "page": page_index + 1, "new_text": ""}

    rgb = _hex_to_rgb01(color_hex)
    fname = _builtin_font_for(font_hint)
    size = font_size if font_size else max(8.0, min(48.0, rect.height * 0.85))

    # Draw via the shared helper so complex scripts (Bangla conjuncts, etc.)
    # are shaped correctly and every script gets a font that supports it.
    from utils.fonts import draw_text
    draw_text(page, rect, new_text, size, color=rgb, default_font=fname,
              align=0)
    used_size = size

    doc.save(output_path, garbage=4, deflate=True)
    doc.close()
    return {"changed": True, "page": page_index + 1, "new_text": new_text,
            "font_used": fname, "font_size_used": used_size}
