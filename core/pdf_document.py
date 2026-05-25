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
        """Read the visual style of the text inside ``rect``.

        A PDF normally does not contain Word-like editable paragraphs. For a
        clean visual edit we therefore need to copy the original text style as
        closely as possible before covering the old glyphs.  This helper
        returns:

            (fontname, size, color_rgb01, bold, italic, baseline_y, first_x,
             multiline)

        ``baseline_y`` and ``first_x`` let us redraw single-line edits on the
        original baseline instead of inside a generic textbox. That makes the
        replacement much less "messy" and keeps it aligned with the original
        PDF text.
        """
        try:
            d = page.get_text("dict")
            candidates = []
            for block in d.get("blocks", []):
                if block.get("type") != 0:
                    continue
                for line in block.get("lines", []):
                    line_bbox = fitz.Rect(line.get("bbox", rect))
                    if not line_bbox.intersects(rect + (-2, -2, 2, 2)):
                        continue
                    spans = []
                    for span in line.get("spans", []):
                        text = span.get("text", "")
                        if not text.strip():
                            continue
                        sb = fitz.Rect(span.get("bbox", rect))
                        # overlap with the clicked/edit rectangle
                        if not sb.intersects(rect + (-3, -3, 3, 3)):
                            continue
                        spans.append(span)
                    if not spans:
                        continue
                    # Prefer the span with the largest visual size.
                    primary = max(spans, key=lambda sp: (sp.get("size", 0),
                                                         fitz.Rect(sp.get("bbox", rect)).width))
                    col = primary.get("color", 0)
                    rgb = (((col >> 16) & 255) / 255.0,
                           ((col >> 8) & 255) / 255.0,
                           (col & 255) / 255.0)
                    fontname = primary.get("font", "")
                    flags = primary.get("flags", 0)
                    nm = fontname.lower()
                    bold = bool(flags & 16) or "bold" in nm or "black" in nm \
                        or "heavy" in nm or "semibold" in nm
                    italic = bool(flags & 2) or "italic" in nm or "oblique" in nm
                    origin = primary.get("origin") or (fitz.Rect(primary.get("bbox", rect)).x0,
                                                        fitz.Rect(primary.get("bbox", rect)).y1)
                    try:
                        ox, oy = float(origin[0]), float(origin[1])
                    except Exception:
                        ox, oy = line_bbox.x0, line_bbox.y1
                    score = (primary.get("size", 0), line_bbox.width)
                    candidates.append((score, fontname, primary.get("size", 0),
                                       rgb, bold, italic, oy, ox, False))
            if candidates:
                best = max(candidates, key=lambda item: item[0])
                return best[1], best[2], best[3], best[4], best[5], best[6], best[7], best[8]
        except Exception:
            pass
        return None, None, None, False, False, None, None, False

    def _background_color_for_rect(self, page, rect):
        """Best-effort background color behind an edited line.

        Older code always painted white over the original text. On off-white,
        gray, colored, or screenshot-like pages that creates an obvious box.
        We sample a small area around the line and use a bright/neutral median
        color, falling back to white if sampling fails.
        """
        try:
            # Render a small clipped area around the line. 2x scale is enough
            # for a stable sample but still very fast.
            clip = fitz.Rect(rect.x0 - 3, rect.y0 - 3, rect.x1 + 3, rect.y1 + 3)
            clip &= page.rect
            if clip.is_empty:
                return (1, 1, 1)
            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), clip=clip, alpha=False)
            data = pix.samples
            if not data:
                return (1, 1, 1)
            # Sample every few pixels. Prefer bright pixels because the text
            # itself is usually dark and should not influence the fill color.
            vals = []
            step = max(3, pix.n * 8)
            for i in range(0, len(data) - pix.n + 1, step):
                r, g, b = data[i], data[i + 1], data[i + 2]
                if (r + g + b) / 3 >= 160:  # likely background, not text
                    vals.append((r, g, b))
            if not vals:
                vals = [(data[i], data[i + 1], data[i + 2])
                        for i in range(0, len(data) - pix.n + 1, step)]
            if not vals:
                return (1, 1, 1)
            vals.sort(key=lambda c: c[0] + c[1] + c[2])
            r, g, b = vals[len(vals) // 2]
            return (r / 255.0, g / 255.0, b / 255.0)
        except Exception:
            return (1, 1, 1)

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


    def _line_text_and_metrics(self, page, rect):
        """Return best-effort visual text and geometry for the clicked line.

        This is used for *small corrections*.  Instead of redrawing the whole
        line (which changes the whole line font), we find the changed part of
        the typed text and cover/redraw only that part.  The unchanged letters
        stay as the original PDF content, so their exact original font is kept.
        """
        try:
            d = page.get_text("dict")
            best = None
            best_score = -1
            search = rect + (-3, -3, 3, 3)
            for block in d.get("blocks", []):
                if block.get("type") != 0:
                    continue
                for line in block.get("lines", []):
                    lb = fitz.Rect(line.get("bbox", rect))
                    if not lb.intersects(search):
                        continue
                    spans = []
                    for sp in line.get("spans", []):
                        txt = sp.get("text", "")
                        if not txt:
                            continue
                        sb = fitz.Rect(sp.get("bbox", lb))
                        if sb.intersects(search):
                            spans.append(sp)
                    if not spans:
                        continue
                    text = "".join(sp.get("text", "") for sp in spans)
                    if not text.strip():
                        continue
                    overlap = max(0, min(lb.y1, rect.y1) - max(lb.y0, rect.y0))
                    score = overlap * max(1, min(lb.x1, rect.x1) - max(lb.x0, rect.x0))
                    if score > best_score:
                        best_score = score
                        best = (text, lb, spans)
            return best
        except Exception:
            return None

    def _common_change_region(self, old_text: str, new_text: str):
        """Return (start, old_end, replacement) for the changed section."""
        old_text = old_text or ""
        new_text = new_text or ""
        i = 0
        max_i = min(len(old_text), len(new_text))
        while i < max_i and old_text[i] == new_text[i]:
            i += 1
        j_old = len(old_text)
        j_new = len(new_text)
        while j_old > i and j_new > i and old_text[j_old - 1] == new_text[j_new - 1]:
            j_old -= 1
            j_new -= 1
        return i, j_old, new_text[i:j_new]

    def _try_small_text_patch(self, page, rect, old_text, new_text, style, fill):
        """Patch only the changed part of a line and leave the rest untouched.

        Returns True if the small patch was applied.  This is the closest safe
        behaviour to normal PDF editors for small typo fixes.
        """
        if not old_text or not new_text or "\n" in new_text:
            return False
        old_norm = old_text.strip("\n")
        new_norm = new_text.strip("\n")
        if not old_norm or old_norm == new_norm:
            return False

        # Small patch mode uses baseline insert_text. That is good for Latin/CJK
        # typo fixes, but it breaks shaped scripts such as Bangla, Hindi, Arabic,
        # Thai, etc. For those languages, use the full-line draw_text path so
        # glyph joining and conjuncts render correctly.
        try:
            from utils.fonts import is_complex_script
            if is_complex_script(old_norm) or is_complex_script(new_norm):
                return False
        except Exception:
            pass

        start, old_end, repl = self._common_change_region(old_norm, new_norm)
        if start == old_end and not repl:
            return False

        # Only use small-patch mode for small corrections.  If the user rewrites
        # most of the line, full-line overlay is safer and clearer.
        changed_old = max(1, old_end - start)
        changed_new = max(1, len(repl))
        if changed_old > max(14, len(old_norm) * 0.45) or changed_new > max(18, len(old_norm) * 0.55):
            return False

        det_font, det_size, det_color, det_bold, det_italic, baseline_y, first_x = style
        size = float(det_size or max(8.0, min(48.0, rect.height * 0.82)))
        rgb = det_color or (0, 0, 0)
        fname = self._usable_font(det_font) if det_font else "helv"

        # Estimate horizontal character positions.  This is intentionally
        # conservative: cover a tiny bit more around the changed part, but do
        # not touch the full line.
        n = max(1, len(old_norm))
        x0 = rect.x0 + rect.width * (start / n)
        x1 = rect.x0 + rect.width * (old_end / n)
        min_w = max(size * 0.55, 3)
        if x1 - x0 < min_w:
            x1 = x0 + min_w
        patch = fitz.Rect(x0 - 1.2, rect.y0 - 0.8, min(rect.x1 + 3, x1 + 2.0), rect.y1 + 0.8) & page.rect
        page.draw_rect(patch, color=fill, fill=fill, width=0, overlay=True)

        if repl:
            try:
                from utils.fonts import font_for_page, _styled_builtin
                fn, ff = font_for_page(page, repl, fname)
                if ff is None and fn in ("helv", "tiro", "cour"):
                    fn = _styled_builtin(fn, det_bold, det_italic)
                y = (rect.y0 + size) if baseline_y is None else float(baseline_y)
                y = min(max(y, rect.y0 + size * 0.65), rect.y1 + size * 0.15)
                page.insert_text((max(page.rect.x0 + 1, x0), y), repl,
                                 fontname=fn, fontfile=ff, fontsize=size,
                                 color=rgb, overlay=True)
            except Exception:
                try:
                    page.insert_text((max(page.rect.x0 + 1, x0), rect.y1 - 2), repl,
                                     fontsize=size, color=rgb, overlay=True)
                except Exception:
                    return False
        return True

    def edit_line_in_memory(self, page_index: int, line_bbox: tuple,
                            new_text: str, font_size=None, font_hint="",
                            color_hex="#000000") -> dict:
        """Replace a line with a cleaner PDF-editor style overlay.

        This is still not true Word-style PDF reflow (PDFs do not store text in
        that way), but it is much cleaner than the old method because it:

        * samples the real page background instead of always drawing a white box;
        * redraws single-line edits on the original baseline;
        * keeps original font size, color, bold and italic where possible;
        * uses a tight erase rectangle so nearby equations/figures are not hit.
        """
        from core.text_line_editor import _hex_to_rgb01, _builtin_font_for
        if page_index < 0 or page_index >= self.doc.page_count:
            raise IndexError("Page out of range")
        page = self.doc[page_index]
        rect = fitz.Rect(*line_bbox)
        if rect.is_empty:
            return {"changed": False, "page": page_index + 1}

        # Read style before covering anything.
        det_font, det_size, det_color, det_bold, det_italic, baseline_y, first_x, _multi = \
            self._detect_line_style(page, rect)
        fill = self._background_color_for_rect(page, rect)

        # Best fix for font/style changes: for small typo corrections, do NOT
        # redraw the whole line.  Patch only the changed letters/word and leave
        # all other original PDF glyphs untouched.
        metrics = self._line_text_and_metrics(page, rect)
        if metrics:
            old_text, _line_rect, _spans = metrics
            style = (det_font, det_size, det_color, det_bold, det_italic, baseline_y, first_x)
            if self._try_small_text_patch(page, rect, old_text, new_text, style, fill):
                self._dirty = True
                return {"changed": True, "page": page_index + 1, "new_text": new_text, "mode": "small_patch"}

        # Full-line fallback.  This is necessary when the user rewrites most of
        # the line.  It keeps size/color/style as close as PyMuPDF can, but it
        # cannot always reuse a subset-embedded PDF font.
        cover = fitz.Rect(rect.x0 - 0.6, rect.y0 - 0.6,
                          rect.x1 + 0.8, rect.y1 + 0.8) & page.rect
        page.draw_rect(cover, color=fill, fill=fill, width=0, overlay=True)

        if new_text:
            # Color: keep original unless the user intentionally chose another.
            if color_hex and color_hex.lower() not in ("#000000", "", None):
                rgb = _hex_to_rgb01(color_hex)
            elif det_color is not None:
                rgb = det_color
            else:
                rgb = _hex_to_rgb01(color_hex)

            fname = self._usable_font(det_font) if det_font else _builtin_font_for(font_hint)
            if det_size and det_size > 0:
                if font_size and abs(font_size - det_size) <= 1.5:
                    size = float(font_size)
                else:
                    size = float(det_size)
            else:
                size = float(font_size or max(8.0, min(48.0, rect.height * 0.82)))

            # Draw simple one-line replacements at the original text baseline.
            # This avoids the vertical drift caused by insert_textbox.
            single_line = "\n" not in new_text and len(new_text) < 180
            page_rect = page.rect
            try:
                from utils.fonts import detect_script, font_for_page, draw_text
                complex_script = detect_script(new_text) in {"bangla", "devanagari", "arabic", "thai"}
            except Exception:
                complex_script = False

            if single_line and not complex_script:
                try:
                    from utils.fonts import font_for_page, _styled_builtin
                    fn, ff = font_for_page(page, new_text, fname)
                    if ff is None and fn in ("helv", "tiro", "cour"):
                        fn = _styled_builtin(fn, det_bold, det_italic)
                    x = rect.x0 if first_x is None else max(page_rect.x0 + 1, float(first_x))
                    y = (rect.y0 + size) if baseline_y is None else float(baseline_y)
                    # Keep the text visually inside the edited line.
                    y = min(max(y, rect.y0 + size * 0.65), rect.y1 + size * 0.15)
                    page.insert_text((x, y), new_text, fontname=fn, fontfile=ff,
                                     fontsize=size, color=rgb, overlay=True)
                except Exception:
                    # Fallback to boxed text if baseline writing fails.
                    box = fitz.Rect(rect.x0, rect.y0,
                                    min(page_rect.x1 - 4, rect.x0 + max(rect.width * 2.5, 180)),
                                    rect.y1 + size * 0.65)
                    from utils.fonts import draw_text
                    draw_text(page, box, new_text, size, color=rgb,
                              default_font=fname, align=0,
                              bold=det_bold, italic=det_italic)
            else:
                # Longer or multi-line replacement: use a controlled text box.
                # It may wrap, but it should no longer shrink headings or erase
                # a very large block of content.
                box = fitz.Rect(rect.x0, rect.y0,
                                min(page_rect.x1 - 4, rect.x0 + max(rect.width * 2.2, 220)),
                                min(page_rect.y1 - 2, rect.y0 + max(rect.height * 1.6, size * 2.2)))
                try:
                    from utils.fonts import draw_text
                    draw_text(page, box, new_text, size, color=rgb,
                              default_font=fname, align=0,
                              bold=det_bold, italic=det_italic)
                except Exception:
                    page.insert_text((rect.x0, rect.y1 - 2), new_text,
                                     fontsize=min(size, 10), color=rgb,
                                     overlay=True)
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
        # professional touch.
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
