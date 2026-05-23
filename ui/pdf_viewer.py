"""PDF viewer widget — center of the application.

Built on QScrollArea + a QWidget canvas that renders pages with a
QPainter. Supports continuous scroll, single-page, two-page, zoom,
search highlights, click-drag highlight selection, and click-to-place
sign placement.
"""

from PySide6.QtWidgets import (
    QWidget, QScrollArea, QSizePolicy, QApplication,
)
from PySide6.QtCore import Qt, QSize, QRect, Signal, QPoint, QRectF, QPointF
from PySide6.QtGui import (
    QPainter, QColor, QPixmap, QFont, QPen, QBrush, QCursor,
)

from utils.constants import (
    DEFAULT_ZOOM, MIN_ZOOM, MAX_ZOOM, ZOOM_STEP,
    VIEW_SINGLE, VIEW_CONTINUOUS, VIEW_TWO_PAGE, RENDER_DPI,
)


# Tool modes
TOOL_NONE = "none"
TOOL_HIGHLIGHT = "highlight"
TOOL_SIGN = "sign"
TOOL_STAMP = "stamp"
TOOL_COMMENT = "comment"
TOOL_FIELD = "field"      # placing a form field
TOOL_LINK = "link"        # drag a rect for a URL link
TOOL_SELECT_TEXT = "select_text"   # drag a rect to copy text from it
TOOL_FILL_FORM = "fill_form"       # click a form field to fill it
TOOL_INK = "ink"                   # free-hand drawing
TOOL_XMARK = "xmark"               # click to place a cross / X mark
TOOL_LINE_HIGHLIGHT = "line_highlight"
TOOL_RECT = "rect"                 # drag a box -> rectangle annotation
TOOL_CIRCLE = "circle"             # drag a box -> circle/ellipse annotation
TOOL_LINE_COMMENT = "line_comment"
TOOL_LINE_EDIT = "line_edit"
TOOL_LINE_COLOR = "line_color"
TOOL_EDIT_MODE = "edit_mode"
TOOL_ADD_TEXT = "add_text"
TOOL_ADD_IMAGE = "add_image"
TOOL_DELETE_ANNOT = "delete_annot"

# Tools that operate on a clicked text line
LINE_TOOLS = {TOOL_LINE_HIGHLIGHT, TOOL_LINE_COMMENT, TOOL_LINE_EDIT, TOOL_LINE_COLOR, TOOL_EDIT_MODE}


class PDFCanvas(QWidget):
    """Inner widget that does the actual page painting."""

    current_page_changed = Signal(int)
    page_clicked = Signal(int, QPoint)
    highlight_selected = Signal(int, object)
    shape_drawn = Signal(int, str, object)
    sign_placement_requested = Signal(int, QPointF)
    stamp_placement_requested = Signal(int, QPointF)
    comment_placement_requested = Signal(int, QPointF)
    field_placement_requested = Signal(int, object)
    link_placement_requested = Signal(int, object)
    line_clicked = Signal(int, object, str)
    text_placement_requested = Signal(int, QPointF)
    image_placement_requested = Signal(int, object)   # page, QRectF
    annot_delete_requested = Signal(int, QPointF)      # page, click point
    navigate_page_requested = Signal(int)              # jump to a page (link)
    link_jumped = Signal()                             # a citation/link was followed
    reference_found = Signal(str)                      # reference text at a citation target
    open_url_requested = Signal(str)                   # open external URL (link)
    inline_edit_committed = Signal(int, object, str)   # page, bbox, new text
    text_copied = Signal(int)                          # number of chars copied
    text_selected_for_note = Signal(str, int)          # text, page index
    form_field_clicked = Signal(int, object, str, str) # page, bbox, name, type
    ink_drawn = Signal(int, object)                    # page, list of points
    xmark_placed = Signal(int, object)                 # page, point

    PAGE_SPACING = 18
    PAGE_BORDER_COLOR = QColor(0, 0, 0, 60)
    SHADOW_COLOR = QColor(0, 0, 0, 80)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.pdf = None
        self.zoom = DEFAULT_ZOOM
        self.rotation = 0
        self.view_mode = VIEW_CONTINUOUS
        # Base render DPI. Can be overridden by Settings ("render quality").
        self.render_dpi = RENDER_DPI

        self._page_pixmaps: dict[int, QPixmap] = {}
        self._page_rects: list[QRect] = []
        self._current_page = 0
        self._background = QColor("#D8D8DE")
        self._search_highlights: dict[int, list] = {}
        self._active_search_hit = None

        self._tool = TOOL_NONE
        self._drag_start_page = -1
        self._drag_start_pdf = None
        self._drag_current_pdf = None
        self._drag_active = False
        self._ink_page = -1
        self._ink_points = []
        self._annot_color = "#E53935"  # current color for ink/marks

        # Line tool state
        self._line_cache: dict[int, list] = {}   # page -> [{"bbox": Rect, "text": str, "font": str, "size": float, "spans": [...]}, ...]
        self._hover_line: tuple[int, int] | None = None   # (page_index, line_index)

        self.setMouseTracking(True)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setAutoFillBackground(True)

    def set_document(self, pdf_document):
        self.pdf = pdf_document
        self._page_pixmaps.clear()
        self._search_highlights.clear()
        self._active_search_hit = None
        self._line_cache.clear()
        self._hover_line = None
        self._relayout()
        self.update()

    def set_zoom(self, zoom):
        zoom = max(MIN_ZOOM, min(MAX_ZOOM, zoom))
        if abs(zoom - self.zoom) < 1e-4:
            return
        self.zoom = zoom
        self._page_pixmaps.clear()
        self._relayout()
        self.update()

    def zoom_in(self):
        self.set_zoom(self.zoom + ZOOM_STEP)

    def zoom_out(self):
        self.set_zoom(self.zoom - ZOOM_STEP)

    def fit_width(self, viewport_w):
        if not self.pdf or self.pdf.page_count == 0:
            return
        w, h = self.pdf.page_size(self._current_page)
        if self.rotation in (90, 270):
            w, h = h, w
        pad = 40
        avail = max(100, viewport_w - pad)
        new_zoom = avail / (w * self.render_dpi / 72.0)
        self.set_zoom(new_zoom)

    def fit_page(self, vw, vh):
        if not self.pdf or self.pdf.page_count == 0:
            return
        w, h = self.pdf.page_size(self._current_page)
        if self.rotation in (90, 270):
            w, h = h, w
        pad = 60
        avail_w = max(100, vw - pad)
        avail_h = max(100, vh - pad)
        zoom_w = avail_w / (w * self.render_dpi / 72.0)
        zoom_h = avail_h / (h * self.render_dpi / 72.0)
        self.set_zoom(min(zoom_w, zoom_h))

    def set_view_mode(self, mode):
        self.view_mode = mode
        self._relayout()
        self.update()

    def set_rotation(self, deg):
        self.rotation = deg % 360
        self._page_pixmaps.clear()
        self._relayout()
        self.update()

    def goto_page(self, page_index):
        if not self.pdf or page_index < 0 or page_index >= self.pdf.page_count:
            return
        self._current_page = page_index
        self.current_page_changed.emit(page_index + 1)

    def current_page(self):
        return self._current_page

    def page_rect_in_canvas(self, page_index):
        if 0 <= page_index < len(self._page_rects):
            return self._page_rects[page_index]
        return QRect()

    def set_search_highlights(self, hits, active=None):
        self._search_highlights = hits or {}
        self._active_search_hit = active
        self.update()

    def set_background(self, color):
        self._background = QColor(color)
        self.update()

    def set_render_dpi(self, dpi: int):
        """Change the base render DPI. Clears cached pixmaps so pages
        re-render at the new quality."""
        dpi = max(72, min(600, int(dpi)))
        if dpi == self.render_dpi:
            return
        self.render_dpi = dpi
        self._page_pixmaps.clear()
        self._relayout()
        self.update()

    def set_tool(self, tool):
        self._tool = tool
        self._drag_active = False
        self._drag_start_pdf = None
        self._drag_current_pdf = None
        self._hover_line = None
        if tool == TOOL_HIGHLIGHT:
            self.setCursor(Qt.IBeamCursor)
        elif tool == TOOL_SELECT_TEXT:
            self.setCursor(Qt.IBeamCursor)
        elif tool in (TOOL_RECT, TOOL_CIRCLE):
            self.setCursor(Qt.CrossCursor)
        elif tool in (TOOL_SIGN, TOOL_STAMP, TOOL_COMMENT, TOOL_ADD_TEXT):
            self.setCursor(Qt.CrossCursor)
        elif tool == TOOL_DELETE_ANNOT:
            self.setCursor(Qt.PointingHandCursor)
        elif tool in (TOOL_FIELD, TOOL_LINK, TOOL_ADD_IMAGE):
            self.setCursor(Qt.CrossCursor)
        elif tool in LINE_TOOLS:
            self.setCursor(Qt.PointingHandCursor)
        else:
            self.unsetCursor()
        self.update()

    # ---- line hit testing ----
    def _ensure_lines_for(self, page_index: int):
        """Lazily build a list of text lines for a page."""
        if page_index in self._line_cache or not self.pdf or not self.pdf.doc:
            return
        lines = []
        try:
            page = self.pdf.doc[page_index]
            pd = page.get_text("dict")
            for block in pd.get("blocks", []):
                if block.get("type") != 0:
                    continue
                block_bbox = block.get("bbox")
                block_lines = block.get("lines", [])
                # full text of the whole block (all its wrapped lines joined)
                block_text = " ".join(
                    "".join(s.get("text", "") for s in bl.get("spans", []))
                    for bl in block_lines).strip()
                for line in block_lines:
                    bbox = line.get("bbox")
                    if not bbox:
                        continue
                    spans = line.get("spans", [])
                    text = "".join(s.get("text", "") for s in spans).strip()
                    if not text:
                        continue
                    # representative span info
                    primary = max(spans, key=lambda s: s.get("size", 0)) if spans else {}
                    lines.append({
                        "bbox": tuple(bbox),                          # (x0, y0, x1, y1)
                        "block_bbox": tuple(block_bbox) if block_bbox else tuple(bbox),
                        "block_text": block_text,
                        "is_multiline": len(block_lines) > 1,
                        "text": text,
                        "font": primary.get("font", ""),
                        "size": float(primary.get("size", 11.0)),
                        "spans": spans,
                    })
        except Exception:
            pass
        self._line_cache[page_index] = lines

    def _line_at(self, page_index: int, pdf_pt: QPointF) -> int:
        """Return the index of the line under a point in PDF coords, or -1."""
        self._ensure_lines_for(page_index)
        for i, ln in enumerate(self._line_cache.get(page_index, [])):
            x0, y0, x1, y1 = ln["bbox"]
            # add a small tolerance vertically
            if x0 - 1 <= pdf_pt.x() <= x1 + 1 and y0 - 2 <= pdf_pt.y() <= y1 + 2:
                return i
        return -1

    def line_info(self, page_index: int, line_index: int):
        self._ensure_lines_for(page_index)
        lines = self._line_cache.get(page_index, [])
        if 0 <= line_index < len(lines):
            return lines[line_index]
        return None

    def invalidate_line_cache(self, page_index: int | None = None):
        """Wipe the cached line bounding boxes (call after page edits)."""
        if page_index is None:
            self._line_cache.clear()
        else:
            self._line_cache.pop(page_index, None)

    def current_tool(self):
        return self._tool

    def invalidate_page(self, page_index):
        self._page_pixmaps.pop(page_index, None)
        self.update()

    def _relayout(self):
        self._page_rects = []
        if not self.pdf or self.pdf.page_count == 0:
            self.setMinimumSize(800, 600)
            return
        spacing = self.PAGE_SPACING
        if self.view_mode == VIEW_TWO_PAGE:
            pairs = []
            i = 0
            while i < self.pdf.page_count:
                if i + 1 < self.pdf.page_count:
                    pairs.append((i, i + 1)); i += 2
                else:
                    pairs.append((i, None)); i += 1
            total_h = spacing; max_pair_w = 0
            row_h_list = []; sizes = {}
            for a, b in pairs:
                wa, ha = self._scaled_size(a)
                wb, hb = (self._scaled_size(b) if b is not None else (0, 0))
                pair_w = wa + (spacing if b is not None else 0) + wb
                pair_h = max(ha, hb)
                max_pair_w = max(max_pair_w, pair_w)
                row_h_list.append((pair_w, pair_h))
                sizes[a] = (wa, ha)
                if b is not None: sizes[b] = (wb, hb)
                total_h += pair_h + spacing
            canvas_w = max_pair_w + spacing * 4
            self.setMinimumSize(canvas_w, total_h)
            y = spacing
            self._page_rects = [QRect() for _ in range(self.pdf.page_count)]
            for (a, b), (pair_w, pair_h) in zip(pairs, row_h_list):
                x_start = (canvas_w - pair_w) // 2
                wa, ha = sizes[a]
                self._page_rects[a] = QRect(x_start, y + (pair_h - ha) // 2, wa, ha)
                if b is not None:
                    wb, hb = sizes[b]
                    self._page_rects[b] = QRect(x_start + wa + spacing,
                                                y + (pair_h - hb) // 2, wb, hb)
                y += pair_h + spacing
        elif self.view_mode == VIEW_SINGLE:
            w, h = self._scaled_size(self._current_page)
            canvas_w = w + spacing * 4
            canvas_h = h + spacing * 2
            self.setMinimumSize(canvas_w, canvas_h)
            self._page_rects = [QRect() for _ in range(self.pdf.page_count)]
            x = (canvas_w - w) // 2
            self._page_rects[self._current_page] = QRect(x, spacing, w, h)
        else:
            total_h = spacing; max_w = 0; sizes = []
            for i in range(self.pdf.page_count):
                w, h = self._scaled_size(i)
                sizes.append((w, h))
                max_w = max(max_w, w)
                total_h += h + spacing
            canvas_w = max_w + spacing * 4
            self.setMinimumSize(canvas_w, total_h)
            y = spacing
            self._page_rects = []
            for w, h in sizes:
                x = (canvas_w - w) // 2
                self._page_rects.append(QRect(x, y, w, h))
                y += h + spacing

    def _scaled_size(self, page_index):
        w, h = self.pdf.page_size(page_index)
        if self.rotation in (90, 270):
            w, h = h, w
        scale = self.zoom * (self.render_dpi / 72.0)
        return int(w * scale), int(h * scale)

    def _pdf_coords_at(self, page_index, point):
        r = self._page_rects[page_index]
        scale = self.zoom * (self.render_dpi / 72.0)
        return QPointF((point.x() - r.left()) / scale,
                       (point.y() - r.top()) / scale)

    def _page_at(self, pos):
        for p, r in enumerate(self._page_rects):
            if not r.isNull() and r.contains(pos):
                return p
        return -1

    def paintEvent(self, event):
        painter = QPainter(self)
        # These render hints make page pixmaps look sharp instead of jagged
        # when Qt needs to scale them (which it always does on hi-DPI screens).
        painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.fillRect(self.rect(), self._background)

        if not self.pdf or self.pdf.page_count == 0:
            cx = self.rect().center().x()
            cy = self.rect().center().y()
            # big friendly icon
            painter.setPen(QColor(190, 195, 205))
            f1 = QFont(); f1.setPointSize(46)
            painter.setFont(f1)
            painter.drawText(self.rect().adjusted(0, -90, 0, -90),
                             Qt.AlignCenter, "\U0001F4C4")
            # heading
            painter.setPen(QColor(90, 95, 110))
            f2 = QFont(); f2.setPointSize(17); f2.setBold(True)
            painter.setFont(f2)
            painter.drawText(self.rect().adjusted(0, -10, 0, -10),
                             Qt.AlignCenter, "Open a PDF to get started")
            # hint
            painter.setPen(QColor(140, 145, 158))
            f3 = QFont(); f3.setPointSize(11)
            painter.setFont(f3)
            painter.drawText(self.rect().adjusted(0, 34, 0, 34),
                             Qt.AlignCenter,
                             "Drag a file here, or use  File  >  Open  (Ctrl+O)")
            return

        for p, r in enumerate(self._page_rects):
            if r.isNull(): continue
            if not event.rect().intersects(r.adjusted(-20, -20, 20, 20)): continue
            painter.fillRect(r.adjusted(3, 3, 3, 3), self.SHADOW_COLOR)
            painter.fillRect(r, QColor("white"))
            pix = self._get_pixmap(p)
            if pix is not None:
                painter.drawPixmap(r, pix)
            if p in self._search_highlights:
                scale = self.zoom * (self.render_dpi / 72.0)
                for idx, rect in enumerate(self._search_highlights[p]):
                    x0 = r.left() + rect.x0 * scale
                    y0 = r.top() + rect.y0 * scale
                    x1 = r.left() + rect.x1 * scale
                    y1 = r.top() + rect.y1 * scale
                    color = (QColor(255, 165, 0, 140)
                             if self._active_search_hit == (p, idx)
                             else QColor(255, 235, 59, 110))
                    painter.fillRect(QRectF(x0, y0, x1 - x0, y1 - y0), color)
            painter.setPen(QPen(self.PAGE_BORDER_COLOR, 1))
            painter.setBrush(Qt.NoBrush)
            painter.drawRect(r)

        if (self._tool in (TOOL_HIGHLIGHT, TOOL_FIELD, TOOL_LINK, TOOL_ADD_IMAGE, TOOL_SELECT_TEXT, TOOL_RECT, TOOL_CIRCLE)
                and self._drag_active
                and self._drag_start_pdf is not None
                and self._drag_current_pdf is not None
                and self._drag_start_page >= 0):
            r = self._page_rects[self._drag_start_page]
            scale = self.zoom * (self.render_dpi / 72.0)
            x0 = r.left() + min(self._drag_start_pdf.x(), self._drag_current_pdf.x()) * scale
            y0 = r.top() + min(self._drag_start_pdf.y(), self._drag_current_pdf.y()) * scale
            x1 = r.left() + max(self._drag_start_pdf.x(), self._drag_current_pdf.x()) * scale
            y1 = r.top() + max(self._drag_start_pdf.y(), self._drag_current_pdf.y()) * scale
            if self._tool == TOOL_HIGHLIGHT:
                fill, pen = QColor(255, 235, 59, 110), QColor(180, 140, 0)
            elif self._tool == TOOL_FIELD:
                fill, pen = QColor(100, 150, 255, 80), QColor(40, 90, 200)
            elif self._tool == TOOL_ADD_IMAGE:
                fill, pen = QColor(255, 140, 0, 70), QColor(180, 90, 0)
            elif self._tool == TOOL_SELECT_TEXT:
                fill, pen = QColor(80, 130, 255, 45), QColor(40, 90, 200)
            else:  # TOOL_LINK
                fill, pen = QColor(0, 200, 100, 70), QColor(0, 130, 60)
            painter.fillRect(QRectF(x0, y0, x1 - x0, y1 - y0), fill)
            painter.setPen(QPen(pen, 1, Qt.DashLine))
            painter.setBrush(Qt.NoBrush)
            painter.drawRect(QRectF(x0, y0, x1 - x0, y1 - y0))

            # For SELECT/COPY, also paint the actual WORDS under the box in
            # solid blue, so the user clearly sees the text being selected
            # (like a real text selection — not just an empty box).
            if self._tool == TOOL_SELECT_TEXT and self.pdf and self.pdf.doc:
                try:
                    import fitz
                    pg = self.pdf.doc[self._drag_start_page]
                    sx0 = min(self._drag_start_pdf.x(), self._drag_current_pdf.x())
                    sy0 = min(self._drag_start_pdf.y(), self._drag_current_pdf.y())
                    sx1 = max(self._drag_start_pdf.x(), self._drag_current_pdf.x())
                    sy1 = max(self._drag_start_pdf.y(), self._drag_current_pdf.y())
                    selrect = fitz.Rect(sx0, sy0, sx1, sy1)
                    sel_color = QColor(60, 120, 240, 90)
                    for wd in pg.get_text("words"):
                        wr = fitz.Rect(wd[0], wd[1], wd[2], wd[3])
                        if wr.intersects(selrect):
                            wx0 = r.left() + wd[0] * scale
                            wy0 = r.top() + wd[1] * scale
                            wx1 = r.left() + wd[2] * scale
                            wy1 = r.top() + wd[3] * scale
                            painter.fillRect(
                                QRectF(wx0, wy0, wx1 - wx0, wy1 - wy0),
                                sel_color)
                except Exception:
                    pass

        # Live free-hand ink preview
        if (self._tool == TOOL_INK and self._drag_active
                and self._ink_page >= 0 and len(self._ink_points) > 1
                and self._ink_page < len(self._page_rects)):
            r = self._page_rects[self._ink_page]
            if not r.isNull():
                scale = self.zoom * (self.render_dpi / 72.0)
                pen = QPen(QColor(self._annot_color), 2)
                painter.setPen(pen)
                painter.setBrush(Qt.NoBrush)
                pts = self._ink_points
                for i in range(1, len(pts)):
                    x0 = r.left() + pts[i-1][0] * scale
                    y0 = r.top() + pts[i-1][1] * scale
                    x1 = r.left() + pts[i][0] * scale
                    y1 = r.top() + pts[i][1] * scale
                    painter.drawLine(int(x0), int(y0), int(x1), int(y1))

        # Hovered text line indicator (for line tools)
        if self._tool in LINE_TOOLS and self._hover_line is not None:
            page_idx, line_idx = self._hover_line
            info = self.line_info(page_idx, line_idx)
            if info is not None and 0 <= page_idx < len(self._page_rects):
                r = self._page_rects[page_idx]
                if not r.isNull():
                    scale = self.zoom * (self.render_dpi / 72.0)
                    x0, y0, x1, y1 = info["bbox"]
                    hx0 = r.left() + x0 * scale
                    hy0 = r.top() + y0 * scale
                    hx1 = r.left() + x1 * scale
                    hy1 = r.top() + y1 * scale
                    if self._tool == TOOL_LINE_HIGHLIGHT:
                        fill, pen = QColor(255, 235, 59, 90), QColor(180, 140, 0)
                    elif self._tool == TOOL_LINE_COMMENT:
                        fill, pen = QColor(100, 150, 255, 70), QColor(40, 90, 200)
                    else:  # TOOL_LINE_EDIT
                        fill, pen = QColor(200, 100, 255, 70), QColor(120, 40, 180)
                    painter.fillRect(QRectF(hx0, hy0, hx1 - hx0, hy1 - hy0), fill)
                    painter.setPen(QPen(pen, 1.2))
                    painter.setBrush(Qt.NoBrush)
                    painter.drawRect(QRectF(hx0, hy0, hx1 - hx0, hy1 - hy0))

    def _get_pixmap(self, page_index):
        if page_index in self._page_pixmaps:
            return self._page_pixmaps[page_index]
        if not self.pdf: return None
        try:
            # device pixel ratio handles Retina / 4K / Windows scaling.
            # Without this, the OS upscales our pixmap and it looks blurry.
            dpr = self.devicePixelRatioF() or 1.0
            render_dpi = int(self.render_dpi * self.zoom * dpr)
            pix = self.pdf.render_page(page_index,
                                       dpi=render_dpi,
                                       rotation=self.rotation)
            if pix is not None and dpr != 1.0:
                pix.setDevicePixelRatio(dpr)
        except Exception:
            return None
        self._page_pixmaps[page_index] = pix
        # Keep memory low on big PDFs: only cache pages near the one we just
        # drew. Far-away pages are dropped and simply re-rendered if scrolled
        # back to. This keeps the app fast and light even on 500-page files.
        if len(self._page_pixmaps) > 12:
            keep_lo = page_index - 4
            keep_hi = page_index + 4
            for cached in list(self._page_pixmaps.keys()):
                if cached < keep_lo or cached > keep_hi:
                    del self._page_pixmaps[cached]
        return pix

    def _update_current_page_from_viewport(self, viewport_top):
        if not self.pdf: return
        center_y = viewport_top + 80
        for p, r in enumerate(self._page_rects):
            if r.isNull(): continue
            if r.top() <= center_y <= r.bottom():
                if p != self._current_page:
                    self._current_page = p
                    self.current_page_changed.emit(p + 1)
                return

    def wheelEvent(self, event):
        if event.modifiers() & Qt.ControlModifier:
            delta = event.angleDelta().y()
            if delta > 0: self.zoom_in()
            elif delta < 0: self.zoom_out()
            event.accept()
        else:
            super().wheelEvent(event)

    def _begin_inline_edit(self, page_index, info):
        """Show a text field right on top of the clicked line so the user can
        type a replacement directly on the page (no popup dialog)."""
        from PySide6.QtWidgets import QLineEdit
        # remove any existing inline editor first
        self._end_inline_edit(commit=False)

        x0, y0, x1, y1 = info["bbox"]
        # convert the line's PDF coords to screen pixels
        if page_index >= len(self._page_rects):
            return
        r = self._page_rects[page_index]
        if r is None or r.isNull():
            return
        scale = self.zoom * (self.render_dpi / 72.0)
        sx0 = r.left() + x0 * scale
        sy0 = r.top() + y0 * scale
        w = max(60, (x1 - x0) * scale + 40)
        h = max(20, (y1 - y0) * scale + 6)

        ed = QLineEdit(self)
        ed.setText(info["text"])
        ed.setGeometry(int(sx0), int(sy0), int(w), int(h))
        ed.setStyleSheet(
            "QLineEdit { border: 2px solid #2667FF; background: #FFFFFF;"
            " color: #000000; padding: 1px 3px; }")
        ed.show()
        ed.setFocus()
        ed.selectAll()
        self._inline_editor = ed
        self._inline_page = page_index
        self._inline_bbox = (x0, y0, x1, y1)
        ed.returnPressed.connect(lambda: self._end_inline_edit(commit=True))
        ed.editingFinished.connect(lambda: self._end_inline_edit(commit=True))

    def _end_inline_edit(self, commit=True):
        ed = getattr(self, "_inline_editor", None)
        if ed is None:
            return
        text = ed.text()
        page = getattr(self, "_inline_page", -1)
        bbox = getattr(self, "_inline_bbox", None)
        self._inline_editor = None
        try:
            ed.deleteLater()
        except Exception:
            pass
        if commit and page >= 0 and bbox is not None:
            from PySide6.QtCore import QRectF
            self.inline_edit_committed.emit(
                page, QRectF(bbox[0], bbox[1], bbox[2] - bbox[0],
                             bbox[3] - bbox[1]), text)

    def mousePressEvent(self, event):
        if not self.pdf or event.button() != Qt.LeftButton:
            super().mousePressEvent(event); return
        p = self._page_at(event.pos())
        if p < 0:
            super().mousePressEvent(event); return
        pdf_pt = self._pdf_coords_at(p, event.pos())

        # FILL FORM: click a form field to fill it inline
        if self._tool == TOOL_FILL_FORM:
            hit = self._form_field_at(p, pdf_pt)
            if hit is not None:
                bbox, name, ftype = hit
                self.form_field_clicked.emit(
                    p, QRectF(bbox[0], bbox[1], bbox[2] - bbox[0],
                              bbox[3] - bbox[1]), name, ftype)
            event.accept(); return

        # FREE-HAND: start a new ink stroke
        if self._tool == TOOL_INK:
            self._ink_page = p
            self._ink_points = [(pdf_pt.x(), pdf_pt.y())]
            self._drag_active = True
            event.accept(); return

        # CROSS / X mark: place it where clicked
        if self._tool == TOOL_XMARK:
            self.xmark_placed.emit(p, QPointF(pdf_pt.x(), pdf_pt.y()))
            event.accept(); return

        # drag-rect tools
        if self._tool in (TOOL_HIGHLIGHT, TOOL_FIELD, TOOL_LINK, TOOL_ADD_IMAGE, TOOL_SELECT_TEXT, TOOL_RECT, TOOL_CIRCLE):
            self._drag_start_page = p
            self._drag_start_pdf = pdf_pt
            self._drag_current_pdf = pdf_pt
            self._drag_active = True
            self.update(); event.accept(); return

        # click-to-place tools
        if self._tool == TOOL_SIGN:
            self.sign_placement_requested.emit(p, pdf_pt)
            event.accept(); return
        if self._tool == TOOL_STAMP:
            self.stamp_placement_requested.emit(p, pdf_pt)
            event.accept(); return
        if self._tool == TOOL_COMMENT:
            self.comment_placement_requested.emit(p, pdf_pt)
            event.accept(); return
        if self._tool == TOOL_ADD_TEXT:
            self.text_placement_requested.emit(p, pdf_pt)
            event.accept(); return
        if self._tool == TOOL_DELETE_ANNOT:
            self.annot_delete_requested.emit(p, pdf_pt)
            event.accept(); return

        # EDIT MODE: click any line to edit it inline (no popup dialog)
        if self._tool == TOOL_EDIT_MODE:
            li = self._line_at(p, pdf_pt)
            if li >= 0:
                info = self.line_info(p, li)
                self._begin_inline_edit(p, info)
            event.accept(); return

        # click-on-a-line tools
        if self._tool in LINE_TOOLS:
            li = self._line_at(p, pdf_pt)
            if li >= 0:
                info = self.line_info(p, li)
                x0, y0, x1, y1 = info["bbox"]
                from PySide6.QtCore import QRectF
                self.line_clicked.emit(p, QRectF(x0, y0, x1 - x0, y1 - y0),
                                       info["text"])
            event.accept(); return

        # No active tool: check whether the click landed on a PDF link
        # (e.g. a chapter link on a table-of-contents page) and follow it.
        if self._tool == TOOL_NONE:
            if self._follow_link_at(p, pdf_pt):
                event.accept(); return

        self.page_clicked.emit(p, QPoint(int(pdf_pt.x()), int(pdf_pt.y())))
        super().mousePressEvent(event)

    def _follow_link_at(self, page_index, pdf_pt) -> bool:
        """If there's a link under the point, act on it. Returns True if a
        link was followed."""
        if not self.pdf or not self.pdf.doc:
            return False
        try:
            page = self.pdf.doc[page_index]
            links = page.get_links()
        except Exception:
            return False
        import fitz
        pt = fitz.Point(pdf_pt.x(), pdf_pt.y())
        for lk in links:
            rect = lk.get("from")
            if rect is None:
                continue
            if not fitz.Rect(rect).contains(pt):
                continue
            kind = lk.get("kind")
            # internal go-to link (chapter/section jump)
            if kind == fitz.LINK_GOTO:
                target = lk.get("page", -1)
                if target is not None and target >= 0:
                    self.link_jumped.emit()
                    # try to grab the reference text at the destination so the
                    # reference collector can save it
                    self._emit_reference_at(target, lk.get("to"))
                    self.navigate_page_requested.emit(target)
                    return True
            # external URL
            elif kind == fitz.LINK_URI:
                uri = lk.get("uri", "")
                if uri:
                    self.open_url_requested.emit(uri)
                    return True
            # named destination / other goto -> try the page if present
            elif kind in (getattr(fitz, "LINK_NAMED", 4),):
                target = lk.get("page", -1)
                if target is not None and target >= 0:
                    self.link_jumped.emit()
                    self.navigate_page_requested.emit(target)
                    return True
        return False

    def _emit_reference_at(self, page_index, to_point):
        """Find the reference text near where a citation link lands, and emit
        it so the collector can save it. Best-effort, offline."""
        if not self.pdf or not self.pdf.doc:
            return
        try:
            import fitz
            page = self.pdf.doc[page_index]
            # destination y on the page (links store a 'to' Point)
            y = None
            if to_point is not None:
                try:
                    y = float(to_point.y)
                except Exception:
                    y = None
            # get text lines with positions
            words = page.get_text("blocks")  # (x0,y0,x1,y1, text, ...)
            if not words:
                return
            # pick the block closest to the landing y (or first block)
            best = None
            if y is not None:
                best = min(words, key=lambda b: abs(((b[1] + b[3]) / 2) - y))
            else:
                best = words[0]
            ref_text = (best[4] if len(best) > 4 else "").strip()
            if ref_text:
                self.reference_found.emit(ref_text)
        except Exception:
            pass

    def mouseMoveEvent(self, event):
        # free-hand ink: collect points as the mouse moves
        if self._tool == TOOL_INK and self._drag_active and self._ink_page >= 0:
            pdf_pt = self._pdf_coords_at(self._ink_page, event.pos())
            if pdf_pt is not None:
                self._ink_points.append((pdf_pt.x(), pdf_pt.y()))
                self.update()
            event.accept(); return

        # drag-rect tools live update
        if self._tool in (TOOL_HIGHLIGHT, TOOL_FIELD, TOOL_LINK, TOOL_ADD_IMAGE, TOOL_SELECT_TEXT, TOOL_RECT, TOOL_CIRCLE) and self._drag_active:
            p = self._drag_start_page
            if p >= 0 and not self._page_rects[p].isNull():
                self._drag_current_pdf = self._pdf_coords_at(p, event.pos())
                self.update(); event.accept(); return

        # line tools: highlight the line under the cursor
        if self._tool in LINE_TOOLS:
            p = self._page_at(event.pos())
            new_hover = None
            if p >= 0:
                pdf_pt = self._pdf_coords_at(p, event.pos())
                li = self._line_at(p, pdf_pt)
                if li >= 0:
                    new_hover = (p, li)
            if new_hover != self._hover_line:
                self._hover_line = new_hover
                self.update()
            event.accept(); return

        # default mode: show a hand cursor when hovering a clickable link
        if self._tool == TOOL_NONE:
            p = self._page_at(event.pos())
            on_link = False
            if p >= 0:
                pdf_pt = self._pdf_coords_at(p, event.pos())
                on_link = self._point_on_link(p, pdf_pt)
            self.setCursor(Qt.PointingHandCursor if on_link else Qt.ArrowCursor)

        super().mouseMoveEvent(event)

    def _form_field_at(self, page_index, pdf_pt):
        """Return (bbox, name, type) of the form field under the point, or None."""
        if not self.pdf or not self.pdf.doc:
            return None
        try:
            import fitz
            page = self.pdf.doc[page_index]
            pt = fitz.Point(pdf_pt.x(), pdf_pt.y())
            for w in page.widgets() or []:
                if fitz.Rect(w.rect).contains(pt):
                    r = w.rect
                    ftype = "checkbox" if w.field_type == fitz.PDF_WIDGET_TYPE_CHECKBOX else "text"
                    return ((r.x0, r.y0, r.x1, r.y1), w.field_name or "", ftype)
        except Exception:
            pass
        return None

    def _point_on_link(self, page_index, pdf_pt) -> bool:
        if not self.pdf or not self.pdf.doc:
            return False
        try:
            links = self.pdf.doc[page_index].get_links()
        except Exception:
            return False
        import fitz
        pt = fitz.Point(pdf_pt.x(), pdf_pt.y())
        for lk in links:
            rect = lk.get("from")
            if rect is not None and fitz.Rect(rect).contains(pt):
                return True
        return False
        if self._hover_line is not None:
            self._hover_line = None
            self.update()
        super().leaveEvent(event)

    def mouseReleaseEvent(self, event):
        # free-hand ink: finish the stroke and emit it
        if self._tool == TOOL_INK and self._drag_active:
            self._drag_active = False
            if self._ink_page >= 0 and len(self._ink_points) > 1:
                self.ink_drawn.emit(self._ink_page, list(self._ink_points))
            self._ink_points = []
            self._ink_page = -1
            self.update(); event.accept(); return
        if (self._tool in (TOOL_HIGHLIGHT, TOOL_FIELD, TOOL_LINK, TOOL_ADD_IMAGE, TOOL_SELECT_TEXT, TOOL_RECT, TOOL_CIRCLE)
                and self._drag_active and event.button() == Qt.LeftButton):
            self._drag_active = False
            tool_was = self._tool
            if (self._drag_start_pdf is not None
                    and self._drag_current_pdf is not None
                    and self._drag_start_page >= 0):
                x0 = min(self._drag_start_pdf.x(), self._drag_current_pdf.x())
                y0 = min(self._drag_start_pdf.y(), self._drag_current_pdf.y())
                x1 = max(self._drag_start_pdf.x(), self._drag_current_pdf.x())
                y1 = max(self._drag_start_pdf.y(), self._drag_current_pdf.y())
                if (x1 - x0) > 2 and (y1 - y0) > 2:
                    rect = QRectF(x0, y0, x1 - x0, y1 - y0)
                    if tool_was == TOOL_HIGHLIGHT:
                        self.highlight_selected.emit(self._drag_start_page, rect)
                    elif tool_was == TOOL_FIELD:
                        self.field_placement_requested.emit(self._drag_start_page, rect)
                    elif tool_was == TOOL_LINK:
                        self.link_placement_requested.emit(self._drag_start_page, rect)
                    elif tool_was == TOOL_ADD_IMAGE:
                        self.image_placement_requested.emit(self._drag_start_page, rect)
                    elif tool_was == TOOL_SELECT_TEXT:
                        self._copy_text_in_rect(self._drag_start_page, x0, y0, x1, y1)
                    elif tool_was == TOOL_RECT:
                        self.shape_drawn.emit(self._drag_start_page, "rect", rect)
                    elif tool_was == TOOL_CIRCLE:
                        self.shape_drawn.emit(self._drag_start_page, "circle", rect)
            self._drag_start_pdf = None
            self._drag_current_pdf = None
            self.update(); event.accept(); return
        super().mouseReleaseEvent(event)

    def _copy_text_in_rect(self, page_index, x0, y0, x1, y1):
        """Pull the text inside the dragged box: copy to clipboard AND offer it
        to the note collector (with its page number)."""
        if not self.pdf or not self.pdf.doc:
            return
        try:
            import fitz
            from PySide6.QtWidgets import QApplication
            page = self.pdf.doc[page_index]
            clip = fitz.Rect(x0, y0, x1, y1)
            text = page.get_text("text", clip=clip).strip()
            if text:
                QApplication.clipboard().setText(text)
                self.text_copied.emit(len(text))
                # offer the snippet (with its page) to the note collector
                self.text_selected_for_note.emit(text, page_index)
            else:
                self.text_copied.emit(0)
        except Exception:
            self.text_copied.emit(0)


class PDFViewer(QScrollArea):
    """ScrollArea hosting a PDFCanvas. This is the public viewer widget."""

    current_page_changed = Signal(int)
    zoom_changed = Signal(float)
    highlight_selected = Signal(int, object)
    shape_drawn = Signal(int, str, object)
    sign_placement_requested = Signal(int, object)
    stamp_placement_requested = Signal(int, object)
    comment_placement_requested = Signal(int, object)
    field_placement_requested = Signal(int, object)
    link_placement_requested = Signal(int, object)
    line_clicked = Signal(int, object, str)
    text_placement_requested = Signal(int, object)
    image_placement_requested = Signal(int, object)
    annot_delete_requested = Signal(int, object)
    navigate_page_requested = Signal(int)
    link_jumped = Signal()
    reference_found = Signal(str)
    open_url_requested = Signal(str)
    inline_edit_committed = Signal(int, object, str)
    text_copied = Signal(int)
    text_selected_for_note = Signal(str, int)
    form_field_clicked = Signal(int, object, str, str)
    ink_drawn = Signal(int, object)
    xmark_placed = Signal(int, object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.canvas = PDFCanvas()
        self.setWidget(self.canvas)
        self.setWidgetResizable(False)
        # browser-style page navigation history (back / forward)
        self._nav_history = []
        self._nav_pos = -1
        self._forward_stack = []
        self.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.canvas.current_page_changed.connect(self.current_page_changed.emit)
        self.canvas.highlight_selected.connect(self.highlight_selected.emit)
        self.canvas.sign_placement_requested.connect(self.sign_placement_requested.emit)
        self.canvas.stamp_placement_requested.connect(self.stamp_placement_requested.emit)
        self.canvas.comment_placement_requested.connect(self.comment_placement_requested.emit)
        self.canvas.field_placement_requested.connect(self.field_placement_requested.emit)
        self.canvas.link_placement_requested.connect(self.link_placement_requested.emit)
        self.canvas.line_clicked.connect(self.line_clicked.emit)
        self.canvas.inline_edit_committed.connect(self.inline_edit_committed.emit)
        self.canvas.text_copied.connect(self.text_copied.emit)
        self.canvas.text_selected_for_note.connect(self.text_selected_for_note.emit)
        self.canvas.form_field_clicked.connect(self.form_field_clicked.emit)
        self.canvas.ink_drawn.connect(self.ink_drawn.emit)
        self.canvas.xmark_placed.connect(self.xmark_placed.emit)
        self.canvas.shape_drawn.connect(self.shape_drawn.emit)
        self.canvas.text_placement_requested.connect(self.text_placement_requested.emit)
        self.canvas.image_placement_requested.connect(self.image_placement_requested.emit)
        self.canvas.annot_delete_requested.connect(self.annot_delete_requested.emit)
        # follow chapter/TOC links: jump to the page internally, open URLs
        self.canvas.navigate_page_requested.connect(self.goto_page)
        self.canvas.navigate_page_requested.connect(self.navigate_page_requested.emit)
        self.canvas.link_jumped.connect(self.link_jumped.emit)
        self.canvas.reference_found.connect(self.reference_found.emit)
        self.canvas.open_url_requested.connect(self.open_url_requested.emit)
        self.verticalScrollBar().valueChanged.connect(self._on_vscroll)

    def set_document(self, pdf_document):
        self.canvas.set_document(pdf_document)

    def goto_page(self, page_index, record=True):
        # Record the EXACT scroll position we're leaving, so Back returns to
        # the precise spot (e.g. the citation in the body), not the page top.
        if record:
            cur_scroll = self.verticalScrollBar().value()
            self._nav_history = self._nav_history[:self._nav_pos + 1]
            self._nav_history.append(cur_scroll)
            self._nav_pos = len(self._nav_history) - 1
            # a fresh jump invalidates any forward history
            self._forward_stack = []
        self.canvas.goto_page(page_index)
        r = self.canvas.page_rect_in_canvas(page_index)
        if not r.isNull():
            self.verticalScrollBar().setValue(max(0, r.top() - 10))

    def go_back(self):
        """Return to the exact scroll position we were at before the jump."""
        if self._nav_pos >= 0 and self._nav_history:
            # remember where we are now so Forward can return here
            here = self.verticalScrollBar().value()
            target_scroll = self._nav_history[self._nav_pos]
            self._nav_pos -= 1
            # store current spot at the position just vacated for forward
            self._forward_stack = getattr(self, "_forward_stack", [])
            self._forward_stack.append(here)
            self.verticalScrollBar().setValue(target_scroll)
            self._sync_page_after_scroll()
            return True
        return False

    def go_forward(self):
        """Go forward again after going back."""
        fs = getattr(self, "_forward_stack", [])
        if fs:
            target = fs.pop()
            # push back onto history
            self._nav_pos += 1
            self.verticalScrollBar().setValue(target)
            self._sync_page_after_scroll()
            return True
        return False

    def _sync_page_after_scroll(self):
        """Update the current-page indicator after we move the scrollbar."""
        try:
            self.canvas.update()
        except Exception:
            pass

    def can_go_back(self):
        return self._nav_pos >= 0 and bool(self._nav_history)

    def can_go_forward(self):
        return bool(getattr(self, "_forward_stack", []))

    def set_zoom(self, zoom):
        vbar = self.verticalScrollBar()
        old_max = max(1, vbar.maximum())
        ratio = vbar.value() / old_max
        self.canvas.set_zoom(zoom)
        self.zoom_changed.emit(self.canvas.zoom)
        vbar.setValue(int(ratio * vbar.maximum()))

    def zoom_in(self):
        self.set_zoom(self.canvas.zoom + ZOOM_STEP)

    def zoom_out(self):
        self.set_zoom(self.canvas.zoom - ZOOM_STEP)

    def fit_width(self):
        self.canvas.fit_width(self.viewport().width())
        self.zoom_changed.emit(self.canvas.zoom)

    def fit_page(self):
        self.canvas.fit_page(self.viewport().width(), self.viewport().height())
        self.zoom_changed.emit(self.canvas.zoom)

    def set_view_mode(self, mode):
        self.canvas.set_view_mode(mode)

    def set_rotation(self, deg):
        self.canvas.set_rotation(deg)

    def set_search_highlights(self, hits, active=None):
        self.canvas.set_search_highlights(hits, active)
        if active is not None:
            page = active[0]
            r = self.canvas.page_rect_in_canvas(page)
            if not r.isNull():
                self.verticalScrollBar().setValue(max(0, r.top() - 20))

    def set_background_color(self, color):
        self.canvas.set_background(color)

    def set_render_dpi(self, dpi: int):
        self.canvas.set_render_dpi(dpi)

    def set_tool(self, tool):
        self.canvas.set_tool(tool)

    def set_annot_color(self, color):
        self.canvas._annot_color = color

    def current_tool(self):
        return self.canvas.current_tool()

    def _on_vscroll(self, value):
        self.canvas._update_current_page_from_viewport(value)
