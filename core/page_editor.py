"""Quick page-level edits: header & footer, insert blank page, etc.

These act directly on a fitz.Document loaded by PDFDocument.
"""

from __future__ import annotations
import re
from datetime import datetime
import fitz


def _hex_to_rgb01(hex_str: str):
    h = hex_str.lstrip("#")
    if len(h) != 6:
        return (0.0, 0.0, 0.0)
    return (int(h[0:2], 16) / 255.0,
            int(h[2:4], 16) / 255.0,
            int(h[4:6], 16) / 255.0)


def _expand_tokens(text: str, page_num: int, total_pages: int,
                   filename: str = "") -> str:
    """Expand {page}, {total}, {date}, {filename} tokens."""
    if not text:
        return ""
    now = datetime.now()
    out = text
    out = out.replace("{page}", str(page_num))
    out = out.replace("{total}", str(total_pages))
    out = out.replace("{date}", now.strftime("%Y-%m-%d"))
    out = out.replace("{time}", now.strftime("%H:%M"))
    out = out.replace("{filename}", filename)
    return out


def _builtin_font(style: str = "regular") -> str:
    s = (style or "").lower()
    if "bold" in s and "italic" in s: return "hebi"
    if "bold" in s: return "hebo"
    if "italic" in s: return "heit"
    if "mono" in s or "courier" in s: return "cour"
    if "serif" in s or "times" in s: return "tiro"
    return "helv"


def add_header_footer(pdf_document,
                      header_left: str = "",
                      header_center: str = "",
                      header_right: str = "",
                      footer_left: str = "",
                      footer_center: str = "",
                      footer_right: str = "",
                      font_size: float = 10.0,
                      color_hex: str = "#444444",
                      style: str = "regular",
                      margin: float = 36.0,        # PDF points from edge
                      page_range: tuple | None = None,
                      filename: str = "") -> int:
    """Draw a header/footer onto every page in range.

    page_range: None for all pages, or (start_idx, end_idx) inclusive.
    Returns the number of pages affected.
    """
    if not pdf_document or not pdf_document.doc:
        raise RuntimeError("No PDF open")
    doc = pdf_document.doc
    total = doc.page_count
    if page_range is None:
        a, b = 0, total - 1
    else:
        a, b = page_range
        a = max(0, a); b = min(total - 1, b)

    rgb = _hex_to_rgb01(color_hex)
    font = _builtin_font(style)
    count = 0

    for pno in range(a, b + 1):
        page = doc[pno]
        w, h = page.rect.width, page.rect.height
        page_num_disp = pno + 1

        # Header band
        header_top = margin / 3
        header_h = font_size + 4
        header_band = fitz.Rect(margin, header_top, w - margin,
                                header_top + header_h)
        third_w = (w - 2 * margin) / 3
        if header_left:
            r = fitz.Rect(margin, header_top, margin + third_w,
                          header_top + header_h)
            page.insert_textbox(r, _expand_tokens(header_left, page_num_disp,
                                                  total, filename),
                                fontname=font, fontsize=font_size,
                                color=rgb, align=0)
        if header_center:
            r = fitz.Rect(margin + third_w, header_top,
                          margin + 2 * third_w, header_top + header_h)
            page.insert_textbox(r, _expand_tokens(header_center, page_num_disp,
                                                  total, filename),
                                fontname=font, fontsize=font_size,
                                color=rgb, align=1)
        if header_right:
            r = fitz.Rect(margin + 2 * third_w, header_top, w - margin,
                          header_top + header_h)
            page.insert_textbox(r, _expand_tokens(header_right, page_num_disp,
                                                  total, filename),
                                fontname=font, fontsize=font_size,
                                color=rgb, align=2)

        # Footer band
        footer_bottom = h - margin / 3 - font_size - 4
        if footer_left:
            r = fitz.Rect(margin, footer_bottom, margin + third_w,
                          footer_bottom + font_size + 4)
            page.insert_textbox(r, _expand_tokens(footer_left, page_num_disp,
                                                  total, filename),
                                fontname=font, fontsize=font_size,
                                color=rgb, align=0)
        if footer_center:
            r = fitz.Rect(margin + third_w, footer_bottom,
                          margin + 2 * third_w, footer_bottom + font_size + 4)
            page.insert_textbox(r, _expand_tokens(footer_center, page_num_disp,
                                                  total, filename),
                                fontname=font, fontsize=font_size,
                                color=rgb, align=1)
        if footer_right:
            r = fitz.Rect(margin + 2 * third_w, footer_bottom, w - margin,
                          footer_bottom + font_size + 4)
            page.insert_textbox(r, _expand_tokens(footer_right, page_num_disp,
                                                  total, filename),
                                fontname=font, fontsize=font_size,
                                color=rgb, align=2)
        count += 1

    pdf_document.mark_dirty()
    return count


def insert_blank_page(pdf_document, after_page_index: int,
                      width: float | None = None,
                      height: float | None = None) -> int:
    """Insert a blank page after the given page index. Returns new page idx."""
    if not pdf_document or not pdf_document.doc:
        raise RuntimeError("No PDF open")
    doc = pdf_document.doc
    # Default to same size as the page we're inserting after
    if width is None or height is None:
        if 0 <= after_page_index < doc.page_count:
            ref = doc[after_page_index]
            width = ref.rect.width
            height = ref.rect.height
        else:
            width, height = 595.276, 841.890  # A4
    new_idx = max(0, min(doc.page_count, after_page_index + 1))
    doc.new_page(pno=new_idx, width=width, height=height)
    pdf_document.mark_dirty()
    return new_idx


def add_text_to_page(pdf_document,
                     page_index: int,
                     point: tuple[float, float],
                     text: str,
                     font_size: float = 12.0,
                     color_hex: str = "#000000",
                     style: str = "regular",
                     max_width: float | None = None):
    """Insert text on a page at a given point.

    Creates a FreeText annotation that's still editable by other PDF
    viewers — and easy to remove if needed.
    """
    if not text:
        raise ValueError("No text to insert")
    if not pdf_document or not pdf_document.doc:
        raise RuntimeError("No PDF open")
    page = pdf_document.doc[page_index]
    x, y = point
    # Estimate a sensible default box
    if max_width is None:
        max_width = min(400, page.rect.width - x - 20)
    # Crude height estimate
    line_count = max(1, text.count("\n") + 1)
    box_h = font_size * 1.6 * line_count + 4
    rect = fitz.Rect(x, y - font_size, x + max_width, y - font_size + box_h)
    rgb = _hex_to_rgb01(color_hex)
    font = _builtin_font(style)

    # Use a FreeText annotation
    try:
        annot = page.add_freetext_annot(rect, text,
                                        fontsize=font_size,
                                        fontname=font,
                                        text_color=rgb,
                                        fill_color=None,
                                        border_color=None,
                                        align=0)
        if annot:
            annot.update()
    except Exception:
        # Fallback: write directly into the content stream
        page.insert_textbox(rect, text,
                            fontname=font, fontsize=font_size,
                            color=rgb, align=0)
    pdf_document.mark_dirty()


def insert_image_on_page(pdf_document,
                         page_index: int,
                         rect: tuple,
                         image_path: str,
                         keep_aspect: bool = True):
    """Place an image inside a rectangle on the page.

    rect: (x0, y0, x1, y1) in PDF points.
    """
    if not pdf_document or not pdf_document.doc:
        raise RuntimeError("No PDF open")
    page = pdf_document.doc[page_index]
    fr = fitz.Rect(*rect)
    page.insert_image(fr, filename=image_path,
                      keep_proportion=keep_aspect)
    pdf_document.mark_dirty()
