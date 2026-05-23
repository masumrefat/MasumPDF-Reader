"""Annotation handling: highlight, underline, strikeout, sticky notes, text boxes.

Built on top of PyMuPDF's annotation API.
"""

import fitz
import json
import os
from datetime import datetime


def _hex_to_rgb(hex_color: str) -> tuple[float, float, float]:
    """#RRGGBB -> (r, g, b) floats 0..1"""
    h = hex_color.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    r = int(h[0:2], 16) / 255.0
    g = int(h[2:4], 16) / 255.0
    b = int(h[4:6], 16) / 255.0
    return (r, g, b)


class AnnotationManager:
    """High-level helpers to add and list annotations on a PDFDocument."""

    def __init__(self, pdf_document):
        self.pdf = pdf_document  # PDFDocument wrapper

    # ---- adding ----
    def add_highlight(self, page_index: int, rects: list, color: str = "#FFEB3B",
                      opacity: float = 0.4, author: str = "MasumPDF"):
        page = self.pdf.doc.load_page(page_index)
        # fitz expects a list of fitz.Quad or fitz.Rect; build quads from rects
        quads = [fitz.Quad(fitz.Rect(r).quad) if not isinstance(r, fitz.Rect)
                 else fitz.Rect(r).quad for r in rects]
        annot = page.add_highlight_annot(quads)
        annot.set_colors(stroke=_hex_to_rgb(color))
        annot.set_opacity(opacity)
        annot.set_info(title=author)
        annot.update()
        self.pdf.mark_dirty()
        return annot

    def add_underline(self, page_index: int, rects: list, color: str = "#1976D2"):
        page = self.pdf.doc.load_page(page_index)
        quads = [fitz.Rect(r).quad for r in rects]
        annot = page.add_underline_annot(quads)
        annot.set_colors(stroke=_hex_to_rgb(color))
        annot.update()
        self.pdf.mark_dirty()
        return annot

    def add_strikeout(self, page_index: int, rects: list, color: str = "#D32F2F"):
        page = self.pdf.doc.load_page(page_index)
        quads = [fitz.Rect(r).quad for r in rects]
        annot = page.add_strikeout_annot(quads)
        annot.set_colors(stroke=_hex_to_rgb(color))
        annot.update()
        self.pdf.mark_dirty()
        return annot

    def add_sticky_note(self, page_index: int, point: tuple, text: str,
                        color: str = "#FFC107", author: str = "MasumPDF"):
        page = self.pdf.doc.load_page(page_index)
        annot = page.add_text_annot(fitz.Point(*point), text)
        annot.set_colors(stroke=_hex_to_rgb(color))
        annot.set_info(title=author, content=text)
        annot.update()
        self.pdf.mark_dirty()
        return annot

    def add_text_box(self, page_index: int, rect, text: str, color: str = "#000000",
                     font_size: int = 11):
        """Add a free text annotation."""
        page = self.pdf.doc.load_page(page_index)
        r = fitz.Rect(rect)
        annot = page.add_freetext_annot(r, text, fontsize=font_size,
                                        text_color=_hex_to_rgb(color))
        annot.update()
        self.pdf.mark_dirty()
        return annot

    def add_rectangle(self, page_index: int, rect, color: str = "#E53935", width: int = 2):
        page = self.pdf.doc.load_page(page_index)
        r = fitz.Rect(rect)
        annot = page.add_rect_annot(r)
        annot.set_colors(stroke=_hex_to_rgb(color))
        annot.set_border(width=width)
        annot.update()
        self.pdf.mark_dirty()
        return annot

    def add_circle(self, page_index: int, rect, color: str = "#E53935", width: int = 2):
        page = self.pdf.doc.load_page(page_index)
        r = fitz.Rect(rect)
        annot = page.add_circle_annot(r)
        annot.set_colors(stroke=_hex_to_rgb(color))
        annot.set_border(width=width)
        annot.update()
        self.pdf.mark_dirty()
        return annot

    def add_line(self, page_index: int, p1: tuple, p2: tuple, color: str = "#E53935",
                 width: int = 2):
        page = self.pdf.doc.load_page(page_index)
        annot = page.add_line_annot(fitz.Point(*p1), fitz.Point(*p2))
        annot.set_colors(stroke=_hex_to_rgb(color))
        annot.set_border(width=width)
        annot.update()
        self.pdf.mark_dirty()
        return annot

    def add_ink(self, page_index: int, strokes: list, color: str = "#E53935", width: int = 2):
        """Freehand drawing. strokes = [[(x,y), (x,y), ...], ...]"""
        page = self.pdf.doc.load_page(page_index)
        ink_strokes = [[fitz.Point(x, y) for x, y in stroke] for stroke in strokes]
        annot = page.add_ink_annot(ink_strokes)
        annot.set_colors(stroke=_hex_to_rgb(color))
        annot.set_border(width=width)
        annot.update()
        self.pdf.mark_dirty()
        return annot

    def add_signature_image(self, page_index: int, image_path: str, rect):
        """Stamp a signature image (PNG with alpha works well) onto a page."""
        page = self.pdf.doc.load_page(page_index)
        page.insert_image(fitz.Rect(rect), filename=image_path, keep_proportion=True)
        self.pdf.mark_dirty()

    # ---- listing / deleting ----
    def list_annotations(self) -> list[dict]:
        """Return a list of dicts describing every annotation in the doc."""
        out = []
        for page_index in range(self.pdf.page_count):
            page = self.pdf.doc.load_page(page_index)
            for annot in page.annots() or []:
                info = annot.info or {}
                out.append({
                    "page": page_index + 1,
                    "type": annot.type[1] if annot.type else "Unknown",
                    "author": info.get("title", ""),
                    "content": info.get("content", ""),
                    "rect": list(annot.rect),
                    "creation_date": info.get("creationDate", ""),
                    "modification_date": info.get("modDate", ""),
                })
        return out

    def delete_annotation(self, page_index: int, annot_index: int):
        page = self.pdf.doc.load_page(page_index)
        annots = list(page.annots() or [])
        if 0 <= annot_index < len(annots):
            page.delete_annot(annots[annot_index])
            self.pdf.mark_dirty()

    def clear_page_annotations(self, page_index: int):
        page = self.pdf.doc.load_page(page_index)
        for annot in list(page.annots() or []):
            page.delete_annot(annot)
        self.pdf.mark_dirty()

    # ---- export ----
    def export_annotations(self, output_path: str, fmt: str = "json"):
        """Export every annotation as JSON or plain text."""
        data = self.list_annotations()
        if fmt == "json":
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump({
                    "file": self.pdf.path,
                    "exported_at": datetime.now().isoformat(),
                    "annotations": data,
                }, f, indent=2)
        else:
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(f"Annotations for: {self.pdf.path}\n")
                f.write(f"Exported at: {datetime.now().isoformat()}\n")
                f.write("=" * 60 + "\n\n")
                for a in data:
                    f.write(f"Page {a['page']} — {a['type']}\n")
                    if a["author"]:
                        f.write(f"  Author: {a['author']}\n")
                    if a["content"]:
                        f.write(f"  Content: {a['content']}\n")
                    f.write("\n")
