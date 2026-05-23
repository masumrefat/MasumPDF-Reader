"""PDF document wrapper.

Wraps PyMuPDF (fitz) so the UI code never touches fitz directly.
This keeps PDF logic in one place and makes the UI easy to test or swap.
"""

import os
import fitz   # PyMuPDF
from PySide6.QtGui import QImage, QPixmap


class PDFDocument:
    """Represents one open PDF file with helpers for rendering, search, etc."""

    def __init__(self, path: str, password: str | None = None):
        self.path = path
        self.password = password or ""
        self.doc = fitz.open(path)
        self._dirty = False

        # Undo support: snapshots of the document bytes taken right before
        # each edit. Undo restores the most recent snapshot. PDFs have no
        # native undo, so a byte-snapshot stack is the most reliable approach
        # and works uniformly for text, images, highlights, stamps, etc.
        self._undo_stack: list[bytes] = []
        self._undo_labels: list[str] = []
        self._max_undo = 12   # cap memory use

        if self.doc.needs_pass:
            if not password or not self.doc.authenticate(password):
                # leave the document open but mark it as locked
                self._locked = True
            else:
                self._locked = False
        else:
            self._locked = False

    # ---- basic properties ----
    @property
    def is_locked(self) -> bool:
        return self._locked

    @property
    def page_count(self) -> int:
        return self.doc.page_count

    @property
    def dirty(self) -> bool:
        return self._dirty

    def mark_dirty(self, value: bool = True):
        self._dirty = value

    # ---- undo support ----
    def _detect_line_style(self, page, rect):
        """Read the font name, size, color and weight of the existing text in
        a line, so an edit can REUSE them (like Sejda does) instead of falling
        back to a generic font.

        Returns (fontname, size, color_rgb01, bold, italic) or (None,...)."""
        try:
            d = page.get_text("dict")
            best = None
            for block in d.get("blocks", []):
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        sb = fitz.Rect(span["bbox"])
                        # does this span sit inside the clicked line area?
                        if (sb.y0 >= rect.y0 - 3 and sb.y1 <= rect.y1 + 3 and
                                sb.x1 > rect.x0 - 3 and sb.x0 < rect.x1 + 3):
                            # Prefer the LARGEST font in the region (so a
                            # heading's size wins), then the widest span.
                            span_size = span.get("size", 0)
                            score = (round(span_size, 1), sb.width)
                            if best is None or score > best[0]:
                                col = span.get("color", 0)
                                r = ((col >> 16) & 255) / 255.0
                                g = ((col >> 8) & 255) / 255.0
                                b = (col & 255) / 255.0
                                fontname = span.get("font", "")
                                # PyMuPDF span "flags": bit 4 (16) = bold,
                                # bit 1 (2) = italic. Also check the font name.
                                flags = span.get("flags", 0)
                                nm = fontname.lower()
                                bold = bool(flags & 16) or "bold" in nm \
                                    or "black" in nm or "heavy" in nm \
                                    or "semibold" in nm
                                italic = bool(flags & 2) or "italic" in nm \
                                    or "oblique" in nm
                                best = (score, fontname,
                                        span.get("size", 0), (r, g, b),
                                        bold, italic)
            if best:
                return best[1], best[2], best[3], best[4], best[5]
        except Exception:
            pass
        return None, None, None, False, False

    def _usable_font(self, font_name):
        """Turn a detected font name into one PyMuPDF can actually write with.
        Tries the original name first (works for standard fonts), else maps to
        the closest built-in by style."""
        from core.text_line_editor import _builtin_font_for
        if not font_name:
            return "helv"
        # Standard PDF font names PyMuPDF accepts directly
        standard = {
            "helvetica": "helv", "times-roman": "tiro", "times": "tiro",
            "courier": "cour", "symbol": "symb",
        }
        key = font_name.lower().split("+")[-1]  # strip subset prefix like ABCDEF+
        if key in standard:
            return standard[key]
        # otherwise map by style (serif/bold/italic/mono)
        return _builtin_font_for(font_name)

    def edit_line_in_memory(self, page_index: int, line_bbox: tuple,
                            new_text: str, font_size=None, font_hint="",
                            color_hex="#000000") -> dict:
        """Replace the text in a line, editing the OPEN document in memory.

        Does NOT save to disk — it just changes the in-memory document and
        marks it dirty, so the user is only asked to save when they close.
        Call push_undo() before this to allow undo.
        """
        from core.text_line_editor import _hex_to_rgb01, _builtin_font_for
        if page_index < 0 or page_index >= self.doc.page_count:
            raise IndexError("Page out of range")
        page = self.doc[page_index]
        rect = fitz.Rect(*line_bbox)

        # Read the ORIGINAL font, size and color FIRST (before we erase), so
        # the edit keeps the same look — this is how Sejda avoids changing the
        # style. We only fall back to a generic font if detection fails.
        det_font, det_size, det_color, det_bold, det_italic = \
            self._detect_line_style(page, rect)

        # white-out the old text
        page.add_redact_annot(rect, fill=(1, 1, 1))
        page.apply_redactions()

        if new_text:
            # color: keep original unless the caller asked for a specific one
            if color_hex and color_hex.lower() not in ("#000000", "", None):
                rgb = _hex_to_rgb01(color_hex)
            elif det_color is not None:
                rgb = det_color
            else:
                rgb = _hex_to_rgb01(color_hex)
            # font: reuse the detected one; fall back to hint/style
            fname = self._usable_font(det_font) if det_font \
                else _builtin_font_for(font_hint)
            # size: the size read directly from the document (det_size) is the
            # most reliable. A caller may pass font_size from a UI cache, but
            # if it disagrees a lot with what's actually on the page, trust the
            # document — this is what stops headings collapsing to body size.
            if det_size and det_size > 0:
                if font_size and abs(font_size - det_size) <= 1.5:
                    size = font_size      # close enough, honour caller
                else:
                    size = det_size       # trust the real on-page size
            else:
                size = (font_size
                        or max(8.0, min(48.0, rect.height * 0.85)))
            # Give the text room: let it extend to the right page edge and a
            # little below, so longer replacement text still fits.
            page_rect = page.rect
            box = fitz.Rect(rect.x0, rect.y0,
                            min(page_rect.x1 - 4, rect.x0 + rect.width * 4),
                            rect.y1 + size * 2)
            # Draw via the shared helper: it auto-detects the script, shapes
            # complex scripts correctly, and KEEPS the original size, color and
            # bold/italic so a heading stays a heading after editing.
            try:
                from utils.fonts import draw_text
                draw_text(page, box, new_text, size, color=rgb,
                          default_font=fname, align=0,
                          bold=det_bold, italic=det_italic)
            except Exception:
                # extreme fallback — never let the line vanish
                try:
                    page.insert_textbox(box, new_text, fontname=fname,
                                        fontsize=size, color=rgb, align=0)
                except Exception:
                    page.insert_text((rect.x0, rect.y1 - 2), new_text,
                                     fontsize=10, color=rgb)
        self._dirty = True
        return {"changed": True, "page": page_index + 1, "new_text": new_text}

    def recolor_line_in_memory(self, page_index: int, line_bbox: tuple,
                               color_hex="#000000") -> dict:
        """Change only the COLOR of the text in a line, keeping the same words.

        Reads the existing text in the line, white-outs it, and redraws the
        same text in the new color. Edits in memory (no save). This is what
        lets the user color a single line.
        """
        from core.text_line_editor import _hex_to_rgb01, _builtin_font_for
        if page_index < 0 or page_index >= self.doc.page_count:
            raise IndexError("Page out of range")
        page = self.doc[page_index]
        rect = fitz.Rect(*line_bbox)

        # gather the text + a font size from the words in this line
        words = page.get_text("words")
        parts = []
        sizes = []
        for w in words:
            wx0, wy0, wx1, wy1 = w[:4]
            # word is on this line if it overlaps the bbox vertically/horizontally
            if (wx0 >= rect.x0 - 2 and wx1 <= rect.x1 + 2 and
                    wy0 >= rect.y0 - 2 and wy1 <= rect.y1 + 2):
                parts.append(w[4])
        text = " ".join(parts).strip()
        if not text:
            return {"changed": False, "page": page_index + 1}

        rgb = _hex_to_rgb01(color_hex)
        size = max(8.0, min(48.0, rect.height * 0.85))
        page.add_redact_annot(rect, fill=(1, 1, 1))
        page.apply_redactions()
        page_rect = page.rect
        box = fitz.Rect(rect.x0, rect.y0,
                        min(page_rect.x1 - 4, rect.x0 + rect.width * 2),
                        rect.y1 + size * 2)
        placed = False
        used = size
        from utils.fonts import font_for_page
        fn, ff = font_for_page(page, text)
        while used >= 5:
            res = page.insert_textbox(box, text, fontname=fn, fontfile=ff,
                                      fontsize=used, color=rgb, align=0,
                                      render_mode=0)
            if res >= 0:
                placed = True
                break
            used -= 1
        if not placed:
            try:
                page.insert_text((rect.x0, rect.y1 - 2), text,
                                 fontsize=min(size, rect.height * 0.8),
                                 color=rgb)
            except Exception:
                page.insert_text((rect.x0, rect.y1 - 2), text,
                                 fontsize=10, color=rgb)
        self._dirty = True
        return {"changed": True, "page": page_index + 1, "color": color_hex}

    def push_undo(self, label: str = "edit"):
        """Snapshot current document bytes before an edit, so it can be undone.
        Call this immediately BEFORE making a change."""
        try:
            snapshot = self.doc.tobytes(deflate=True)
        except Exception:
            # if snapshotting fails, skip silently — better than crashing
            return
        self._undo_stack.append(snapshot)
        self._undo_labels.append(label)
        # cap the stack
        if len(self._undo_stack) > self._max_undo:
            self._undo_stack.pop(0)
            self._undo_labels.pop(0)

    def can_undo(self) -> bool:
        return len(self._undo_stack) > 0

    def last_undo_label(self) -> str:
        return self._undo_labels[-1] if self._undo_labels else ""

    def undo(self) -> bool:
        """Restore the most recent snapshot. Returns True if something was
        undone. The current document is replaced by the snapshot."""
        if not self._undo_stack:
            return False
        snapshot = self._undo_stack.pop()
        self._undo_labels.pop()
        try:
            new_doc = fitz.open(stream=snapshot, filetype="pdf")
        except Exception:
            return False
        try:
            self.doc.close()
        except Exception:
            pass
        self.doc = new_doc
        self._dirty = True
        return True

    def clear_undo(self):
        self._undo_stack.clear()
        self._undo_labels.clear()

    def delete_annot_at(self, page_index: int, x: float, y: float,
                        radius: float = 6.0) -> str | None:
        """Delete the topmost annotation whose rectangle contains (or is
        near) the point. Returns a short description of what was deleted,
        or None if nothing was found.

        Handles text, highlights, stamps, comments, signatures, links —
        anything stored as a PDF annotation. (Inserted images that became
        page content are not annotations; use Undo for those.)"""
        if not self.doc or page_index < 0 or page_index >= self.doc.page_count:
            return None
        page = self.doc[page_index]
        pt = fitz.Point(x, y)

        # Collect candidate annotations in one pass, capturing the data we
        # need immediately (reading annot properties lazily later can crash
        # PyMuPDF if the page's annot list changes). We pick the smallest
        # annotation containing the point so overlapping annots resolve to
        # the most specific one.
        best = None          # (area, description, annot)
        try:
            for annot in (page.annots() or []):
                try:
                    r = annot.rect
                except Exception:
                    continue
                rr = fitz.Rect(r.x0 - radius, r.y0 - radius,
                               r.x1 + radius, r.y1 + radius)
                if not rr.contains(pt):
                    continue
                # capture description now, while the handle is valid
                try:
                    atype = annot.type[1] if annot.type else "annotation"
                except Exception:
                    atype = "annotation"
                try:
                    content = (annot.info or {}).get("content", "") or ""
                except Exception:
                    content = ""
                desc = atype + (f": {content[:30]}" if content else "")
                area = max(0.0, r.width) * max(0.0, r.height)
                if best is None or area < best[0]:
                    best = (area, desc, annot)
        except Exception:
            return None

        if best is None:
            return None

        _, desc, hit = best
        try:
            page.delete_annot(hit)
            self.mark_dirty()
            return desc
        except Exception:
            return None

    def file_name(self) -> str:
        return os.path.basename(self.path) if self.path else "Untitled"

    # ---- metadata ----
    def metadata(self) -> dict:
        md = dict(self.doc.metadata or {})
        md["file_path"] = self.path
        md["file_size"] = os.path.getsize(self.path) if self.path and os.path.isfile(self.path) else 0
        md["page_count"] = self.page_count
        md["encrypted"] = bool(self.doc.is_encrypted)
        md["is_pdf"] = self.doc.is_pdf
        return md

    def set_metadata(self, md: dict):
        self.doc.set_metadata(md)
        self._dirty = True

    # ---- rendering ----
    def render_page(self, page_index: int, zoom: float = 1.0, rotation: int = 0,
                    dpi: int | None = None) -> QPixmap:
        """Render a page to a QPixmap. zoom 1.0 = 100%, dpi overrides if set."""
        page = self.doc.load_page(page_index)
        if dpi:
            zoom_factor = dpi / 72.0
        else:
            zoom_factor = zoom
        mat = fitz.Matrix(zoom_factor, zoom_factor)
        if rotation:
            mat = mat * fitz.Matrix(rotation)
        pix = page.get_pixmap(matrix=mat, alpha=False)
        fmt = QImage.Format_RGB888
        img = QImage(pix.samples, pix.width, pix.height, pix.stride, fmt)
        # take a copy so the underlying bytes are owned by Qt
        return QPixmap.fromImage(img.copy())

    def render_thumbnail(self, page_index: int, width: int = 150) -> QPixmap:
        """Render a small thumbnail with a target width in pixels."""
        page = self.doc.load_page(page_index)
        page_w = page.rect.width or 1
        # render at 2x so it looks sharp on hi-DPI screens
        scale = (width * 2) / page_w
        mat = fitz.Matrix(scale, scale)
        pix = page.get_pixmap(matrix=mat, alpha=False)
        img = QImage(pix.samples, pix.width, pix.height, pix.stride,
                     QImage.Format_RGB888)
        qpix = QPixmap.fromImage(img.copy())
        qpix.setDevicePixelRatio(2.0)
        return qpix

    def page_size(self, page_index: int) -> tuple[float, float]:
        page = self.doc.load_page(page_index)
        return page.rect.width, page.rect.height

    # ---- text & search ----
    def page_text(self, page_index: int) -> str:
        return self.doc.load_page(page_index).get_text()

    def all_text(self) -> str:
        return "\n".join(self.page_text(i) for i in range(self.page_count))

    def search_text(self, term: str, case_sensitive: bool = False, whole_word: bool = False):
        """
        Search for `term` in the document.
        Returns: dict {page_index: [fitz.Rect, ...]}
        """
        if not term:
            return {}
        flags = 0
        if not case_sensitive:
            # fitz default is case-insensitive; nothing to do
            pass
        results: dict[int, list] = {}
        for i in range(self.page_count):
            page = self.doc.load_page(i)
            try:
                hits = page.search_for(term, quads=False)
            except Exception:
                hits = []
            if whole_word and hits:
                # filter by word boundaries — simple approach using the page text.
                # Use casefold() rather than lower() so case-insensitive matching
                # works correctly for non-English scripts (German ß, Greek, Turkish,
                # accented letters, etc.).
                words = page.get_text("words")
                wanted = term if case_sensitive else term.casefold()
                filtered = []
                for rect in hits:
                    for w in words:
                        wx0, wy0, wx1, wy1, wtext, *_ = w
                        wt = wtext if case_sensitive else wtext.casefold()
                        if wt == wanted and abs(wx0 - rect.x0) < 1 and abs(wy0 - rect.y0) < 1:
                            filtered.append(rect)
                            break
                hits = filtered
            if hits:
                results[i] = hits
        return results

    # ---- outline / bookmarks ----
    def outline(self) -> list:
        """Return the table-of-contents as [(level, title, page_index), ...]"""
        toc = self.doc.get_toc(simple=True)
        # toc entries are 1-indexed; convert to 0-indexed
        return [(level, title, page - 1) for level, title, page in toc]

    # ---- saving ----
    def save(self, output_path: str | None = None, incremental: bool = False,
             garbage: int = 4, deflate: bool = True):
        """Save the PDF. If output_path is None, save in place."""
        target = output_path or self.path
        # Stamp the producer so saved files show this app - a clean,
        # professional touch with no third-party footprint.
        try:
            from utils.constants import APP_NAME, APP_VERSION
            md = self.doc.metadata or {}
            md["producer"] = f"{APP_NAME} {APP_VERSION}"
            self.doc.set_metadata(md)
        except Exception:
            pass
        if target == self.path and incremental:
            self.doc.save(target, incremental=True, encryption=fitz.PDF_ENCRYPT_KEEP)
        else:
            self.doc.save(target, garbage=garbage, deflate=deflate)
        if not output_path:
            self._dirty = False

    def close(self):
        try:
            self.doc.close()
        except Exception:
            pass

    # ---- page operations ----
    def delete_page(self, page_index: int):
        self.doc.delete_page(page_index)
        self._dirty = True

    def rotate_page(self, page_index: int, degrees: int):
        page = self.doc.load_page(page_index)
        page.set_rotation((page.rotation + degrees) % 360)
        self._dirty = True

    def move_page(self, from_index: int, to_index: int):
        # fitz uses move_page(pno, to)
        self.doc.move_page(from_index, to_index)
        self._dirty = True

    def insert_pdf(self, other_path: str, start_page: int | None = None):
        other = fitz.open(other_path)
        if start_page is None:
            self.doc.insert_pdf(other)
        else:
            self.doc.insert_pdf(other, start_at=start_page)
        other.close()
        self._dirty = True

    def duplicate_page(self, page_index: int):
        self.doc.copy_page(page_index, page_index + 1)
        self._dirty = True

    def extract_pages(self, page_indices: list, output_path: str):
        """Save selected pages as a new PDF."""
        new_doc = fitz.open()
        for idx in page_indices:
            new_doc.insert_pdf(self.doc, from_page=idx, to_page=idx)
        new_doc.save(output_path, garbage=4, deflate=True)
        new_doc.close()
