"""Main application window.

Hosts: menu, toolbar, tab widget (for multiple PDFs), left sidebar
(thumbnails / outline), right sidebar (comments / properties), and
the central PDF viewer for the active tab.
"""

from PySide6.QtWidgets import (
    QMainWindow, QTabWidget, QSplitter, QFileDialog, QMessageBox,
    QDockWidget, QStatusBar, QLabel, QInputDialog, QMenuBar, QMenu,
    QApplication, QProgressBar, QWidget, QVBoxLayout, QPushButton,
)
from PySide6.QtCore import Qt, QPoint, QTimer
from PySide6.QtGui import QAction, QKeySequence, QPixmap, QColor

import os
import json
import shutil
from datetime import datetime

from core.pdf_document import PDFDocument
from core.annotation_manager import AnnotationManager
from core.page_manager import PageManager
from core.converter import Converter
from core.security import SecurityManager
from core.metadata import MetadataManager
from core.ocr_engine import OCREngine

from utils.file_utils import (
    human_size, open_containing_folder, make_backup, safe_unique_path, file_exists
)
from utils.settings import AppSettings
from utils.worker_threads import OCRWorker, MergeWorker, ImageExportWorker
from utils.constants import (
    APP_NAME, APP_VERSION, APP_AUTHOR, APP_LICENSE,
    THEME_DARK, THEME_LIGHT, RECENT_FILES_MAX,
    PDF_FILTER, IMAGE_FILTER, ZOOM_LEVELS,
)

from .pdf_viewer import PDFViewer
from .toolbar import MainToolbar
from .sidebar import LeftSidebar, RightSidebar
from .dialogs import (
    PasswordDialog, PropertiesDialog, EncryptDialog, OrganizeDialog,
    SplitDialog, OCRDialog, SignatureDialog, SettingsDialog,
)
from .styles import get_stylesheet, viewer_background
from utils.i18n import tr


class PDFTab(QWidget):
    """One open PDF — owns its PDFDocument, viewer, sidebars."""

    def __init__(self, settings: AppSettings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.document: PDFDocument | None = None
        self.annotations: AnnotationManager | None = None
        self.forms = None
        self.stamps = None
        self.media = None
        self.path: str | None = None
        self._search_hits: dict = {}
        self._flat_hits: list = []  # [(page, hit_index), ...]
        self._active_hit_idx: int = -1

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        from ui.tools_panel import AllToolsPanel
        from ui.collapsible import CollapsiblePanel

        self.splitter = QSplitter(Qt.Horizontal)
        self.splitter.setChildrenCollapsible(False)

        # Far left: All Tools panel (wrapped so it can minimize)
        from utils.constants import THEME_DARK
        is_dark = (self.settings.theme() == THEME_DARK)
        self.tools_panel = AllToolsPanel(dark=is_dark)
        self.tools_wrap = CollapsiblePanel("All Tools", self.tools_panel,
                                           side="left")
        self.tools_wrap.setMinimumWidth(self.tools_wrap.RAIL_WIDTH)

        # Left: Pages / Outline (thumbnails + outline tabs)
        self.left_side = LeftSidebar()
        self.left_wrap = CollapsiblePanel("Pages & Outline", self.left_side,
                                          side="right")
        self.left_wrap.setMinimumWidth(self.left_wrap.RAIL_WIDTH)

        # Center: the viewer (never collapsible)
        self.viewer = PDFViewer()

        # Thin vertical annotation bar beside the PDF (self-contained per tab).
        self._annot_color = "#FFD54F"
        self.annot_bar = self._build_annot_bar()
        # Right-side navigation rail (page number, prev/next, zoom, refresh).
        self.nav_rail = self._build_nav_rail()
        from PySide6.QtWidgets import QWidget as _QW, QHBoxLayout as _QHB
        self.viewer_wrap = _QW()
        _vh = _QHB(self.viewer_wrap)
        _vh.setContentsMargins(0, 0, 0, 0)
        _vh.setSpacing(0)
        _vh.addWidget(self.annot_bar)
        _vh.addWidget(self.viewer, 1)
        _vh.addWidget(self.nav_rail)

        # Floating "Back to text" button — appears over the PDF after the user
        # clicks a citation/link, so they can return to where they were with
        # one click instead of scrolling. Hidden until a link is followed.
        from PySide6.QtWidgets import QPushButton as _QPB
        self.back_to_text_btn = _QPB("\u2190  Back to text", self.viewer)
        self.back_to_text_btn.setCursor(Qt.PointingHandCursor)
        self.back_to_text_btn.setStyleSheet(
            "QPushButton { background: #2667FF; color: white; border: none;"
            " border-radius: 18px; padding: 8px 16px; font-size: 13px;"
            " font-weight: 600; }"
            "QPushButton:hover { background: #1B53E0; }")
        self.back_to_text_btn.hide()
        self.back_to_text_btn.clicked.connect(self._on_back_to_text)
        self.viewer.link_jumped.connect(self._show_back_to_text)

        # Right: Comments / Properties
        self.right_side = RightSidebar()
        self.right_wrap = CollapsiblePanel("Comments", self.right_side,
                                           side="right")
        self.right_wrap.setMinimumWidth(self.right_wrap.RAIL_WIDTH)

        self.splitter.addWidget(self.tools_wrap)
        self.splitter.addWidget(self.viewer_wrap)
        self.splitter.addWidget(self.left_wrap)
        self.splitter.addWidget(self.right_wrap)
        self.splitter.setStretchFactor(0, 0)
        self.splitter.setStretchFactor(1, 1)
        self.splitter.setStretchFactor(2, 0)
        self.splitter.setStretchFactor(3, 0)
        self.splitter.setSizes([210, 700, 200, 260])
        layout.addWidget(self.splitter)

        # Comments / Properties starts minimized so the PDF gets more room.
        # The user can click the rail to show it whenever they need it.
        self.right_wrap.collapse()

        # When any panel collapses or expands, give/take the space from the
        # viewer so the PDF always fills the freed area.
        for wrap in (self.tools_wrap, self.left_wrap, self.right_wrap):
            wrap.collapsed_changed.connect(self._rebalance_splitter)

        # Connect signals
        self.left_side.page_requested.connect(self.viewer.goto_page)
        self.right_side.page_requested.connect(self.viewer.goto_page)
        self.viewer.current_page_changed.connect(self._sync_thumbnails)
        self.viewer.current_page_changed.connect(lambda _: self._nav_sync())
        self.right_side.export_btn.clicked.connect(self._export_annotations)

        # accept drops on the tab too — but the window already handles them

    def _build_annot_bar(self):
        """Thin vertical markup toolbar next to the PDF (self-contained)."""
        from PySide6.QtWidgets import QWidget, QVBoxLayout, QToolButton
        from PySide6.QtCore import QSize
        bar = QWidget()
        bar.setFixedWidth(46)
        bar.setStyleSheet(
            "QWidget { background: #F4F5F7; border-right: 1px solid #DDD; }"
            "QToolButton { border: none; padding: 6px; border-radius: 6px; "
            "font-size: 17px; }"
            "QToolButton:hover { background: #E2E6EE; }"
            "QToolButton:checked { background: #2667FF; color: white; }")
        v = QVBoxLayout(bar)
        v.setContentsMargins(4, 8, 4, 8)
        v.setSpacing(4)
        self._annot_buttons = []

        def add_btn(symbol, tip, tool):
            b = QToolButton()
            b.setText(symbol)
            b.setToolTip(tip)
            b.setCheckable(True)
            b.setFixedSize(QSize(38, 38))
            b.clicked.connect(lambda: self._annot_pick_tool(tool, b))
            v.addWidget(b)
            self._annot_buttons.append(b)
            return b

        add_btn("\u2196", "Select / normal mode", "none")

        # Highlight tool with a dropdown: Highlight / Underline / Strikethrough
        self._add_annot_menu_btn(
            v, "\u270F", "Text markup",
            [("\u270F  Highlight", lambda: self._set_highlight_style("highlight")),
             ("\u0332U  Underline", lambda: self._set_highlight_style("underline")),
             ("\u0336S  Strikethrough", lambda: self._set_highlight_style("strikeout"))])

        # Draw / shapes dropdown: Free-hand / Line / Rectangle / Circle
        self._add_annot_menu_btn(
            v, "\u270D", "Draw & shapes",
            [("\u270D  Free-hand draw", lambda: self._annot_pick_tool_named("ink")),
             ("\u2014  Line", lambda: self._annot_pick_tool_named("line_highlight")),
             ("\u25AD  Rectangle", lambda: self._annot_pick_tool_named("rect")),
             ("\u25CB  Circle", lambda: self._annot_pick_tool_named("circle"))])

        # Marks dropdown: X mark / Checkmark / Dot
        self._add_annot_menu_btn(
            v, "\u2715", "Marks",
            [("\u2715  Cross / X mark", lambda: self._set_mark_kind("xmark")),
             ("\u2713  Check mark", lambda: self._set_mark_kind("check")),
             ("\u2022  Dot", lambda: self._set_mark_kind("dot"))])

        add_btn("\u2014", "Underline a line — click a line", "line_highlight")

        # thin divider line between tools and the color picker
        from PySide6.QtWidgets import QFrame
        div = QFrame()
        div.setFrameShape(QFrame.HLine)
        div.setStyleSheet("color: #D5D8DF; background: #D5D8DF; max-height: 1px;")
        div.setFixedHeight(1)
        v.addSpacing(6)
        v.addWidget(div)
        v.addSpacing(6)

        # small, subtle color dot (not a big bright box)
        self.annot_color_btn = QToolButton()
        self.annot_color_btn.setToolTip("Annotation color — click to change")
        self.annot_color_btn.setFixedSize(QSize(38, 38))
        self._style_color_dot()
        self.annot_color_btn.clicked.connect(self._annot_pick_color)
        v.addWidget(self.annot_color_btn)
        v.addStretch(1)
        return bar

    def _add_annot_menu_btn(self, layout, symbol, tip, options):
        """A toolbar button that opens a small popup menu of sub-tools
        (Adobe-style). `options` is a list of (label, callback)."""
        from PySide6.QtWidgets import QToolButton, QMenu
        from PySide6.QtCore import QSize
        b = QToolButton()
        b.setText(symbol)
        b.setToolTip(tip)
        b.setCheckable(True)
        b.setFixedSize(QSize(38, 38))
        menu = QMenu(b)
        for label, cb in options:
            act = menu.addAction(label)
            act.triggered.connect(lambda checked=False, c=cb: c())
        b.setMenu(menu)
        b.setPopupMode(QToolButton.InstantPopup)
        layout.addWidget(b)
        self._annot_buttons.append(b)
        return b

    def _annot_pick_tool_named(self, tool):
        """Set a drawing tool and check its bar button."""
        # uncheck all, the menu button will reflect active via tool state
        for bb in self._annot_buttons:
            bb.setChecked(False)
        self.viewer.set_tool(tool)
        self.viewer.set_annot_color(self._annot_color)

    def _set_highlight_style(self, style):
        """Choose highlight / underline / strikeout, then arm the markup tool."""
        self._highlight_style = style
        self.viewer.set_tool("highlight")
        self.viewer.set_annot_color(self._annot_color)

    def _set_mark_kind(self, kind):
        """Choose which mark to place (X / check / dot), then arm the tool."""
        self._mark_kind = kind
        self.viewer.set_tool("xmark")
        self.viewer.set_annot_color(self._annot_color)

    def _style_color_dot(self):
        """Render the color picker as a small round dot inside the button,
        not a big bright rectangle."""
        self.annot_color_btn.setStyleSheet(
            "QToolButton {"
            "  border: none; border-radius: 6px;"
            f" background: qradialgradient(cx:0.5, cy:0.5, radius:0.26,"
            f"   fx:0.5, fy:0.5, stop:0 {self._annot_color},"
            f"   stop:0.78 {self._annot_color}, stop:0.82 #C9CDD6,"
            f"   stop:0.86 transparent, stop:1 transparent);"
            "}"
            "QToolButton:hover { background-color: #E2E6EE; }")

    def _annot_pick_tool(self, tool, btn):
        for b in self._annot_buttons:
            b.setChecked(b is btn)
        self.viewer.set_tool(tool)
        self.viewer.set_annot_color(self._annot_color)

    def _annot_pick_color(self):
        from PySide6.QtWidgets import QColorDialog
        col = QColorDialog.getColor(parent=self, title="Choose annotation color")
        if not col.isValid():
            return
        self._annot_color = col.name()
        self._style_color_dot()
        self.viewer.set_annot_color(self._annot_color)
        try:
            self.settings.set_highlight_color(self._annot_color)
        except Exception:
            pass

    def _build_nav_rail(self):
        """Right-side navigation rail: page box, prev/next, refresh, zoom."""
        from PySide6.QtWidgets import (QWidget, QVBoxLayout, QToolButton,
                                       QSpinBox, QLabel, QFrame)
        from PySide6.QtCore import QSize, Qt
        rail = QWidget()
        rail.setFixedWidth(52)
        rail.setStyleSheet(
            "QWidget { background: #F4F5F7; border-left: 1px solid #DDD; }"
            "QToolButton { border: none; padding: 6px; border-radius: 6px;"
            " font-size: 17px; }"
            "QToolButton:hover { background: #E2E6EE; }"
            "QSpinBox { border: 1px solid #CCC; border-radius: 4px;"
            " padding: 2px; }")
        v = QVBoxLayout(rail)
        v.setContentsMargins(6, 10, 6, 10)
        v.setSpacing(6)
        v.setAlignment(Qt.AlignHCenter)

        # current page box
        self.nav_page_box = QSpinBox()
        self.nav_page_box.setMinimum(1)
        self.nav_page_box.setMaximum(1)
        self.nav_page_box.setButtonSymbols(QSpinBox.NoButtons)
        self.nav_page_box.setAlignment(Qt.AlignCenter)
        self.nav_page_box.setFixedWidth(40)
        self.nav_page_box.setToolTip("Current page — type a number and press Enter")
        self.nav_page_box.editingFinished.connect(self._nav_go_to_typed_page)
        v.addWidget(self.nav_page_box, 0, Qt.AlignHCenter)

        # total pages label
        self.nav_total_lbl = QLabel("—")
        self.nav_total_lbl.setStyleSheet("color:#666; font-size: 12px;")
        self.nav_total_lbl.setAlignment(Qt.AlignCenter)
        v.addWidget(self.nav_total_lbl, 0, Qt.AlignHCenter)

        def btn(symbol, tip, fn):
            b = QToolButton()
            b.setText(symbol)
            b.setToolTip(tip)
            b.setFixedSize(QSize(38, 34))
            b.clicked.connect(fn)
            v.addWidget(b, 0, Qt.AlignHCenter)
            return b

        btn("\u25B2", "Previous page", self._nav_prev)
        btn("\u25BC", "Next page", self._nav_next)

        line0 = QFrame(); line0.setFrameShape(QFrame.HLine)
        line0.setStyleSheet("color:#DDD;")
        v.addWidget(line0)

        # Back / Forward — jump to where you were before clicking a link
        self.nav_back_btn = btn("\u2190", "Go back (after clicking a link)",
                                self._nav_back)
        self.nav_fwd_btn = btn("\u2192", "Go forward", self._nav_forward)

        line = QFrame(); line.setFrameShape(QFrame.HLine)
        line.setStyleSheet("color:#DDD;")
        v.addWidget(line)

        btn("\u21BB", "Reload / refresh the page", self._nav_refresh)
        btn("\u2398", "Fit page to width", self._nav_fit)
        btn("\u2295", "Zoom in", lambda: self.viewer.zoom_in())
        btn("\u2296", "Zoom out", lambda: self.viewer.zoom_out())
        v.addStretch(1)
        return rail

    def _nav_sync(self):
        """Keep the rail's page box + total in sync with the document."""
        if not self.document:
            return
        try:
            cur = self.viewer.canvas.current_page() + 1
            total = self.document.page_count
            self.nav_page_box.blockSignals(True)
            self.nav_page_box.setMaximum(max(1, total))
            self.nav_page_box.setValue(cur)
            self.nav_page_box.blockSignals(False)
            self.nav_total_lbl.setText(str(total))
        except Exception:
            pass

    def _nav_go_to_typed_page(self):
        if not self.document:
            return
        self.viewer.goto_page(self.nav_page_box.value() - 1)

    def _nav_prev(self):
        if not self.document:
            return
        cur = self.viewer.canvas.current_page()
        self.viewer.goto_page(max(0, cur - 1))

    def _nav_next(self):
        if not self.document:
            return
        cur = self.viewer.canvas.current_page()
        self.viewer.goto_page(min(self.document.page_count - 1, cur + 1))

    def _nav_refresh(self):
        if not self.document:
            return
        try:
            self.viewer.canvas.invalidate_page(self.viewer.canvas.current_page())
            self.viewer.canvas.update()
        except Exception:
            pass

    def _nav_back(self):
        if self.document:
            self.viewer.go_back()

    def _show_back_to_text(self):
        """Show the floating Back-to-text button after a citation jump."""
        btn = self.back_to_text_btn
        btn.adjustSize()
        self._reposition_back_btn()
        btn.show()
        btn.raise_()

    def _reposition_back_btn(self):
        """Keep the floating button in the bottom-RIGHT corner of the viewer,
        clear of the page text and the scrollbar."""
        btn = self.back_to_text_btn
        vp = self.viewer
        sb_w = vp.verticalScrollBar().width() if vp.verticalScrollBar().isVisible() else 0
        x = vp.width() - btn.width() - sb_w - 16
        y = vp.height() - btn.height() - 18
        btn.move(max(8, x), max(8, y))

    def _on_back_to_text(self):
        """Return to where the user was before clicking the citation."""
        if self.document:
            self.viewer.go_back()
        self.back_to_text_btn.hide()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if getattr(self, "back_to_text_btn", None) and self.back_to_text_btn.isVisible():
            self._reposition_back_btn()

    def _nav_forward(self):
        if self.document:
            self.viewer.go_forward()

    def _nav_fit(self):
        try:
            self.viewer.fit_width()
        except Exception:
            pass

    def open(self, path: str, password: str | None = None) -> bool:
        try:
            doc = PDFDocument(path, password=password)
        except Exception as e:
            QMessageBox.critical(self, "Could not open",
                                 f"Failed to open file:\n{path}\n\n{e}")
            return False
        if doc.is_locked:
            dlg = PasswordDialog(parent=self, message="This PDF is password-protected.")
            if dlg.exec() != PasswordDialog.Accepted:
                doc.close()
                return False
            return self.open(path, password=dlg.value())

        self.document = doc
        self.annotations = AnnotationManager(doc)
        from core.form_manager import FormManager
        from core.stamp_manager import StampManager
        from core.media_manager import MediaManager
        self.forms = FormManager(doc)
        self.stamps = StampManager(doc)
        self.media = MediaManager(doc)
        self.path = path
        # Apply render quality from settings BEFORE setting the document
        # so the first paint is already at the chosen DPI.
        self.viewer.set_render_dpi(self.settings.render_dpi())
        self.viewer.set_document(doc)
        self.left_side.populate(doc)
        self._refresh_right_sidebar()
        self._nav_sync()
        # initial view mode first (affects page layout)
        self.viewer.set_view_mode(self.settings.view_mode())
        # initial zoom: either fit-to-width (default) or the saved default zoom
        if self.settings.auto_fit_on_open():
            # Defer fit-to-width until the viewport has its real size.
            # On first open the viewport may still be 0×0.
            from PySide6.QtCore import QTimer
            QTimer.singleShot(0, self.viewer.fit_width)
        else:
            self.viewer.set_zoom(self.settings.default_zoom())
        return True

    def close_document(self):
        if self.document:
            self.document.close()
            self.document = None
            self.annotations = None
            self.forms = None
            self.stamps = None
            self.media = None
            self.path = None

    def save(self, output_path: str | None = None):
        if not self.document:
            return
        target = output_path or self.path
        if not target:
            return self.save_as()
        # backup before overwrite
        if target == self.path:
            make_backup(self.path)
        self.document.save(target)
        if output_path and output_path != self.path:
            # opened a saved copy — switch to it
            self.path = output_path
        return True

    def save_as(self) -> bool:
        if not self.document:
            return False
        suggested = self.path or "document.pdf"
        path, _ = QFileDialog.getSaveFileName(self, "Save PDF as…", suggested,
                                              PDF_FILTER)
        if not path:
            return False
        if not path.lower().endswith(".pdf"):
            path += ".pdf"
        self.document.save(path)
        return True

    # ---- annotations ----
    def add_sticky_at(self, page_index: int, point: QPoint):
        text, ok = QInputDialog.getMultiLineText(self, "Sticky note", "Note text:")
        if ok and self.annotations:
            self.annotations.add_sticky_note(page_index, (point.x(), point.y()), text)
            self.viewer.canvas._page_pixmaps.pop(page_index, None)
            self.viewer.canvas.update()
            self._refresh_right_sidebar()

    def _export_annotations(self):
        if not self.annotations:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Export comments…", "annotations.json",
            "JSON (*.json);;Text (*.txt)",
        )
        if not path:
            return
        fmt = "txt" if path.lower().endswith(".txt") else "json"
        self.annotations.export_annotations(path, fmt=fmt)
        QMessageBox.information(self, "Exported", f"Annotations saved to:\n{path}")

    def _rebalance_splitter(self, *_):
        """Resize columns so collapsed panels shrink to their rail and the
        viewer absorbs the freed space."""
        sizes = self.splitter.sizes()
        if len(sizes) != 4:
            return
        total = sum(sizes)
        rail = 26  # CollapsiblePanel.RAIL_WIDTH

        def want(wrap, current):
            return rail if wrap.is_collapsed() else max(current, 170)

        tools_w = want(self.tools_wrap, 210 if not self.tools_wrap.is_collapsed() else rail)
        left_w = want(self.left_wrap, 200 if not self.left_wrap.is_collapsed() else rail)
        right_w = want(self.right_wrap, 260 if not self.right_wrap.is_collapsed() else rail)
        viewer_w = max(300, total - tools_w - left_w - right_w)
        # order is now: tools, viewer, pages(left), comments(right)
        self.splitter.setSizes([tools_w, viewer_w, left_w, right_w])

    def _refresh_right_sidebar(self):
        if not self.document:
            return
        # comments
        try:
            anns = self.annotations.list_annotations() if self.annotations else []
        except Exception:
            anns = []
        self.right_side.set_comments(anns)
        # properties
        md = self.document.metadata()
        html = (
            f"<b>File:</b><br>{md.get('file_path', '—')}<br><br>"
            f"<b>Size:</b> {human_size(md.get('file_size', 0))}<br>"
            f"<b>Pages:</b> {md.get('page_count', 0)}<br>"
            f"<b>Encrypted:</b> {'Yes' if md.get('encrypted') else 'No'}<br><br>"
            f"<b>Title:</b> {md.get('title', '') or '—'}<br>"
            f"<b>Author:</b> {md.get('author', '') or '—'}<br>"
            f"<b>Subject:</b> {md.get('subject', '') or '—'}<br>"
            f"<b>Keywords:</b> {md.get('keywords', '') or '—'}<br>"
            f"<b>Producer:</b> {md.get('producer', '') or '—'}<br>"
            f"<b>Creator:</b> {md.get('creator', '') or '—'}<br>"
            f"<b>Created:</b> {md.get('creationDate', '') or '—'}<br>"
            f"<b>Modified:</b> {md.get('modDate', '') or '—'}<br>"
        )
        self.right_side.set_properties_html(html)

    def _sync_thumbnails(self, page_num_1based: int):
        self.left_side.thumbnails.highlight_page(page_num_1based - 1)

    # ---- search ----
    def search(self, term: str, case_sensitive: bool = False, whole_word: bool = False):
        if not self.document:
            return
        if not term:
            self._search_hits = {}
            self._flat_hits = []
            self._active_hit_idx = -1
            self.viewer.set_search_highlights({}, None)
            return
        self._search_hits = self.document.search_text(term, case_sensitive, whole_word)
        # flatten
        self._flat_hits = []
        for page in sorted(self._search_hits.keys()):
            for i in range(len(self._search_hits[page])):
                self._flat_hits.append((page, i))
        self._active_hit_idx = 0 if self._flat_hits else -1
        active = self._flat_hits[0] if self._flat_hits else None
        self.viewer.set_search_highlights(self._search_hits, active)

    def search_next(self):
        if not self._flat_hits:
            return
        self._active_hit_idx = (self._active_hit_idx + 1) % len(self._flat_hits)
        active = self._flat_hits[self._active_hit_idx]
        self.viewer.set_search_highlights(self._search_hits, active)

    def search_prev(self):
        if not self._flat_hits:
            return
        self._active_hit_idx = (self._active_hit_idx - 1) % len(self._flat_hits)
        active = self._flat_hits[self._active_hit_idx]
        self.viewer.set_search_highlights(self._search_hits, active)


class MainWindow(QMainWindow):
    """Top-level window of MasumPDF Reader."""

    def __init__(self, settings: AppSettings | None = None):
        super().__init__()
        # Authorship/license integrity: stop if the author name or license
        # has been altered (created by Chowdhury Mohammad Masum Refat, MIT).
        from utils.integrity import verify_or_exit
        verify_or_exit()
        self.settings = settings or AppSettings()
        # Shared reference collection (literature-review database) — grows
        # across papers as the user clicks citations.
        from core.reference_collection import ReferenceCollection
        self.ref_collection = ReferenceCollection()
        self._ref_panel = None
        # Text/notes collection (saved snippets with their source).
        from core.text_collection import TextCollection
        self.text_collection = TextCollection()
        self._notes_panel = None
        self._save_note_on_select = False  # only prompt when in note mode
        # Research library (personal paper database, persisted to disk).
        from core.research_library import ResearchLibrary
        self.library = ResearchLibrary()
        self._library_panel = None
        self.setWindowTitle(APP_NAME)
        # Load the app logo as the window icon (title bar + taskbar)
        try:
            import os as _os
            from PySide6.QtGui import QIcon as _QIcon
            _icons = _os.path.join(_os.path.dirname(_os.path.dirname(
                _os.path.abspath(__file__))), "resources", "icons")
            for _n in ("app.ico", "app.png", "app_256.png"):
                _p = _os.path.join(_icons, _n)
                if _os.path.exists(_p):
                    self.setWindowIcon(_QIcon(_p))
                    break
        except Exception:
            pass
        self.resize(1400, 900)
        self._worker = None
        self._progress = None
        self._pending_signature_path = None
        self._pending_signature_aspect = 4.0
        self._pending_field = None
        self._pending_stamp = None
        self._pending_comment = None
        self._pending_media = None
        self._pending_text = None
        self._pending_image_path = None
        self._media_via_comment = False
        self._autosave_timer = QTimer(self)
        self._autosave_timer.timeout.connect(self._on_autosave)

        self._build_central()
        self._build_toolbar()
        self._build_menus()
        self._build_statusbar()

        self.setAcceptDrops(True)
        self._apply_theme()
        self._configure_autosave()

        # restore geometry
        geom = self.settings.load_geometry()
        if geom:
            self.restoreGeometry(geom)

        # show "Welcome" if nothing open
        self._open_welcome_tab()

        # Quietly check GitHub for a newer version a few seconds after start.
        # Runs once, never blocks the UI, and stays silent unless there's an
        # update (or the user later checks manually from the Help menu).
        try:
            QTimer.singleShot(
                3000, lambda: self.action_check_updates(manual=False))
        except Exception:
            pass

    # ---- UI construction ----
    def _build_central(self):
        self.tab_widget = QTabWidget()
        self.tab_widget.setTabsClosable(True)
        self.tab_widget.setMovable(True)
        self.tab_widget.setDocumentMode(True)
        self.tab_widget.tabCloseRequested.connect(self._close_tab)
        self.tab_widget.currentChanged.connect(self._tab_changed)
        # Make the close (×) button reliably visible on every platform by
        # drawing our own icon and applying it to each tab's close button.
        self._install_tab_close_icons()
        self.setCentralWidget(self.tab_widget)

    def _make_close_icon(self):
        """Draw a bold, dark × icon for tab close buttons so it stays clearly
        visible on every platform and theme."""
        from PySide6.QtGui import QPixmap, QPainter, QPen, QColor
        from PySide6.QtCore import Qt as _Qt
        # Draw at 2x then let Qt scale down → crisp, anti-aliased edges.
        pm = QPixmap(32, 32)
        pm.fill(_Qt.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.Antialiasing, True)
        pen = QPen(QColor("#2B2B2B"))      # near-black: high contrast
        pen.setWidth(4)                    # bold strokes
        pen.setCapStyle(_Qt.RoundCap)
        p.setPen(pen)
        p.drawLine(10, 10, 22, 22)
        p.drawLine(22, 10, 10, 22)
        p.end()
        from PySide6.QtGui import QIcon
        return QIcon(pm)

    def _install_tab_close_icons(self):
        """Apply the drawn × icon to the close button on each tab, now and
        whenever tabs change."""
        from PySide6.QtWidgets import QTabBar
        icon = self._make_close_icon()
        bar = self.tab_widget.tabBar()
        def apply_icons():
            from PySide6.QtWidgets import QAbstractButton
            for i in range(bar.count()):
                btn = bar.tabButton(i, QTabBar.RightSide)
                if btn is None:
                    btn = bar.tabButton(i, QTabBar.LeftSide)
                if isinstance(btn, QAbstractButton) and btn.icon().isNull():
                    btn.setIcon(icon)
                    from PySide6.QtCore import QSize as _QSize
                    btn.setIconSize(_QSize(16, 16))
        self._apply_tab_close_icons = apply_icons
        # re-apply when tabs are added/removed
        self.tab_widget.currentChanged.connect(lambda *_: apply_icons())

    def _build_toolbar(self):
        self.toolbar = MainToolbar(self)
        self.addToolBar(Qt.TopToolBarArea, self.toolbar)
        tb = self.toolbar
        tb.open_requested.connect(self.action_open)
        tb.save_requested.connect(self.action_save)
        tb.save_as_requested.connect(self.action_save_as)
        tb.print_requested.connect(self.action_print)
        tb.zoom_in_requested.connect(lambda: self._with_tab(lambda t: t.viewer.zoom_in()))
        tb.zoom_out_requested.connect(lambda: self._with_tab(lambda t: t.viewer.zoom_out()))
        tb.fit_width_requested.connect(lambda: self._with_tab(lambda t: t.viewer.fit_width()))
        tb.fit_page_requested.connect(lambda: self._with_tab(lambda t: t.viewer.fit_page()))
        tb.rotate_requested.connect(self._rotate_view)
        tb.view_mode_changed.connect(self._set_view_mode)
        tb.search_text_changed.connect(self._search)
        tb.search_next_requested.connect(lambda: self._with_tab(lambda t: t.search_next()))
        tb.search_prev_requested.connect(lambda: self._with_tab(lambda t: t.search_prev()))
        tb.organize_requested.connect(self.action_organize)
        tb.merge_requested.connect(self.action_merge)
        tb.split_requested.connect(self.action_split)
        tb.extract_requested.connect(self.action_extract_pages)
        tb.convert_to_images_requested.connect(self.action_export_images)
        tb.images_to_pdf_requested.connect(self.action_images_to_pdf)
        tb.extract_text_requested.connect(self.action_extract_text)
        tb.ocr_requested.connect(self.action_ocr)
        tb.encrypt_requested.connect(self.action_encrypt)
        tb.decrypt_requested.connect(self.action_decrypt)
        tb.sign_requested.connect(self.action_sign)
        tb.annotate_highlight_requested.connect(self.action_highlight_toggle)
        tb.annotate_note_requested.connect(self.action_note_hint)
        tb.theme_toggle_requested.connect(self.action_toggle_theme)
        tb.properties_requested.connect(self.action_properties)
        tb.compress_requested.connect(self.action_compress)
        tb.compare_requested.connect(self.action_compare)
        tb.text_color_requested.connect(self.action_text_color)
        tb.create_pdf_requested.connect(self.action_create_pdf)
        tb.prepare_form_requested.connect(self.action_prepare_form)
        tb.fill_form_requested.connect(self.action_fill_form)
        tb.stamp_requested.connect(self.action_stamp)
        tb.comment_requested.connect(self.action_comment)
        tb.media_requested.connect(self.action_media)
        tb.send_review_requested.connect(self.action_send_review)
        tb.mark_reference_requested.connect(self.action_mark_reference_toggle)
        tb.save_note_requested.connect(self.action_save_notes_toggle)
        tb.language_changed.connect(self._on_toolbar_language_changed)

    def _build_menus(self):
        mb: QMenuBar = self.menuBar()
        # File
        file_menu = mb.addMenu(tr("File"))
        a_create = QAction(tr("New blank PDF…"), self)
        a_create.setShortcut("Ctrl+N")
        a_create.triggered.connect(self.action_create_pdf)
        file_menu.addAction(a_create)
        a_open = QAction(tr("Open…"), self)
        a_open.setShortcut("Ctrl+O")
        a_open.triggered.connect(self.action_open)
        file_menu.addAction(a_open)
        self.recent_menu = file_menu.addMenu(tr("Open recent"))
        self._rebuild_recent_menu()
        file_menu.addSeparator()

        a_save = QAction(tr("Save"), self); a_save.setShortcut("Ctrl+S"); a_save.triggered.connect(self.action_save)
        file_menu.addAction(a_save)
        a_save_as = QAction(tr("Save as…"), self); a_save_as.setShortcut("Ctrl+Shift+S")
        a_save_as.triggered.connect(self.action_save_as)
        file_menu.addAction(a_save_as)
        a_save_flat = QAction(tr("Save flattened copy…"), self); a_save_flat.triggered.connect(self.action_save_flattened)
        file_menu.addAction(a_save_flat)
        file_menu.addSeparator()

        a_print = QAction(tr("Print…"), self)
        a_print.setShortcut("Ctrl+P")
        a_print.triggered.connect(self.action_print)
        file_menu.addAction(a_print)
        file_menu.addSeparator()

        a_open_folder = QAction(tr("Open containing folder"), self); a_open_folder.triggered.connect(self.action_open_folder)
        file_menu.addAction(a_open_folder)

        file_menu.addSeparator()
        a_close = QAction(tr("Close tab"), self); a_close.setShortcut("Ctrl+W")
        a_close.triggered.connect(lambda: self._close_tab(self.tab_widget.currentIndex()))
        file_menu.addAction(a_close)
        a_quit = QAction(tr("Quit"), self); a_quit.setShortcut("Ctrl+Q"); a_quit.triggered.connect(self.close)
        file_menu.addAction(a_quit)

        # View
        view_menu = mb.addMenu(tr("View"))
        for label, fn, shortcut in (
            (tr("Zoom in"), lambda: self._with_tab(lambda t: t.viewer.zoom_in()), "Ctrl+="),
            (tr("Zoom out"), lambda: self._with_tab(lambda t: t.viewer.zoom_out()), "Ctrl+-"),
            (tr("Fit width"), lambda: self._with_tab(lambda t: t.viewer.fit_width()), "Ctrl+1"),
            (tr("Fit page"), lambda: self._with_tab(lambda t: t.viewer.fit_page()), "Ctrl+2"),
            (tr("Rotate view"), lambda: self._rotate_view(90), "Ctrl+R"),
            (tr("Back (return to previous spot)"),
             lambda: self._with_tab(lambda t: t.viewer.go_back()), "Alt+Left"),
            (tr("Forward"), lambda: self._with_tab(lambda t: t.viewer.go_forward()), "Alt+Right"),
        ):
            a = QAction(label, self); a.setShortcut(shortcut); a.triggered.connect(fn)
            view_menu.addAction(a)
        view_menu.addSeparator()
        a_full = QAction(tr("Full screen"), self); a_full.setShortcut("F11")
        a_full.triggered.connect(self._toggle_fullscreen)
        view_menu.addAction(a_full)
        view_menu.addSeparator()

        # Panel toggles
        a_tools = QAction(tr("Toggle Tools panel"), self)
        a_tools.setShortcut("Ctrl+Shift+T")
        a_tools.triggered.connect(lambda: self._toggle_panel("tools"))
        view_menu.addAction(a_tools)
        a_pages = QAction(tr("Toggle Pages / Outline panel"), self)
        a_pages.setShortcut("Ctrl+Shift+P")
        a_pages.triggered.connect(lambda: self._toggle_panel("left"))
        view_menu.addAction(a_pages)
        a_comments = QAction(tr("Toggle Comments panel"), self)
        a_comments.setShortcut("Ctrl+Shift+C")
        a_comments.triggered.connect(lambda: self._toggle_panel("right"))
        view_menu.addAction(a_comments)
        a_focus = QAction(tr("Hide all panels (focus mode)"), self)
        a_focus.setShortcut("Ctrl+Shift+F")
        a_focus.triggered.connect(self._focus_mode)
        view_menu.addAction(a_focus)
        view_menu.addSeparator()

        a_theme = QAction(tr("Toggle theme"), self); a_theme.setShortcut("Ctrl+T")
        a_theme.triggered.connect(self.action_toggle_theme)
        view_menu.addAction(a_theme)

        # Edit
        edit_menu = mb.addMenu(tr("Edit"))
        self.a_undo = QAction(tr("Undo"), self)
        self.a_undo.setShortcut("Ctrl+Z")
        self.a_undo.triggered.connect(self.action_undo)
        self.a_undo.setEnabled(False)
        edit_menu.addAction(self.a_undo)
        edit_menu.addSeparator()
        a_find = QAction(tr("Find…"), self); a_find.setShortcut("Ctrl+F")
        a_find.triggered.connect(lambda: self.toolbar.search_input.setFocus())
        edit_menu.addAction(a_find)
        a_props = QAction(tr("Document properties…"), self); a_props.triggered.connect(self.action_properties)
        edit_menu.addAction(a_props)

        # Tools
        tools_menu = mb.addMenu(tr("Tools"))
        for label, fn in (
            (tr("Highlight tool (toggle)"), self.action_highlight_toggle),
            (tr("Add sticky note…"), self.action_note_hint),
            (tr("Add comment (click to place)"), self.action_comment),
            (tr("Add stamp…"), self.action_stamp),
            (tr("Add link / media…"), self.action_media),
            (tr("Sign document…"), self.action_sign),
            (tr("Prepare form fields…"), self.action_prepare_form),
            (tr("Fill and sign…"), self.action_fill_form),
            (tr("Send for review…"), self.action_send_review),
            (tr("Change text color…"), self.action_text_color),
            (tr("Organize pages…"), self.action_organize),
            (tr("Merge PDFs…"), self.action_merge),
            (tr("Split PDF…"), self.action_split),
            (tr("Extract pages…"), self.action_extract_pages),
            (tr("Compare two PDFs…"), self.action_compare),
            (tr("Extract citations…"), self.action_extract_citations),
            (tr("Reference Collection (view)…"), self.open_reference_panel),
            (tr("Collect all references from this PDF…"), self.action_collect_references_now),
            (tr("Mark & collect references (toggle)"), self.action_mark_reference_toggle),
            (tr("Save selected text as notes (toggle)"), self.action_save_notes_toggle),
            (tr("Text/Notes Collection (view)…"), self.open_notes_panel),
            (tr("Research Library…"), self.open_library_panel),
            (tr("Add current PDF to Library"), self.action_add_current_to_library),
            (tr("Compress PDF…"), self.action_compress),
            (tr("Export pages as images…"), self.action_export_images),
            (tr("Build PDF from images…"), self.action_images_to_pdf),
            (tr("Extract text…"), self.action_extract_text),
            (tr("Run OCR…"), self.action_ocr),
            (tr("Encrypt PDF…"), self.action_encrypt),
            (tr("Decrypt PDF…"), self.action_decrypt),
        ):
            a = QAction(label, self); a.triggered.connect(fn)
            tools_menu.addAction(a)

        # Settings
        settings_menu = mb.addMenu(tr("Settings"))
        a_set = QAction(tr("Preferences…"), self); a_set.triggered.connect(self.action_settings)
        settings_menu.addAction(a_set)
        a_clear = QAction(tr("Clear recent files"), self); a_clear.triggered.connect(self._clear_recents)
        settings_menu.addAction(a_clear)

        # Help
        help_menu = mb.addMenu(tr("Help"))
        a_about = QAction(tr("About {app}").replace("{app}", APP_NAME), self); a_about.triggered.connect(self.action_about)
        help_menu.addAction(a_about)
        a_update = QAction(tr("Check for updates…"), self)
        a_update.triggered.connect(lambda: self.action_check_updates(manual=True))
        help_menu.addAction(a_update)

    def _build_statusbar(self):
        from PySide6.QtWidgets import QSpinBox
        sb = QStatusBar()
        self.setStatusBar(sb)
        self.status_page = QLabel("Page —")
        self.status_zoom = QLabel("Zoom 100%")
        self.status_msg = QLabel("Ready")
        self.status_msg.setStyleSheet("color: gray;")

        # Jump-to-page box: type a page number and press Enter to go there.
        self.page_jump = QSpinBox()
        self.page_jump.setMinimum(1)
        self.page_jump.setMaximum(1)
        self.page_jump.setPrefix("Go to ")
        self.page_jump.setToolTip("Type a page number and press Enter to jump")
        self.page_jump.setFixedWidth(110)
        self.page_jump.editingFinished.connect(self._on_page_jump)

        sb.addWidget(self.status_msg, 1)
        sb.addPermanentWidget(self.page_jump)
        sb.addPermanentWidget(self.status_page)
        sb.addPermanentWidget(self.status_zoom)

    def _on_page_jump(self):
        t = self.current_tab()
        if not t or not t.document:
            return
        page = self.page_jump.value() - 1  # 0-based
        try:
            t.viewer.goto_page(page)
        except Exception:
            pass

    # ---- theme ----
    def _apply_theme(self):
        theme = self.settings.theme()
        QApplication.instance().setStyleSheet(get_stylesheet(theme))
        is_dark = (theme == THEME_DARK)
        # update viewer backgrounds + tool panel icon colors
        for i in range(self.tab_widget.count()):
            w = self.tab_widget.widget(i)
            if isinstance(w, PDFTab):
                w.viewer.set_background_color(viewer_background(theme))
                if hasattr(w, "tools_panel"):
                    w.tools_panel.set_dark(is_dark)

    def action_toggle_theme(self):
        cur = self.settings.theme()
        new = THEME_LIGHT if cur == THEME_DARK else THEME_DARK
        self.settings.set_theme(new)
        self._apply_theme()

    # ---- helpers ----
    def current_tab(self) -> PDFTab | None:
        w = self.tab_widget.currentWidget()
        return w if isinstance(w, PDFTab) else None

    def _with_tab(self, fn):
        t = self.current_tab()
        if t and t.document:
            fn(t)

    def _tool_btn_checked(self, name: str) -> bool:
        """Return whether a toggleable tool button is currently checked.
        Looks at the All-Tools panel first, then the top toolbar."""
        t = self.current_tab()
        if t and hasattr(t, "tools_panel"):
            b = t.tools_panel.get(name)
            if b is not None:
                return b.isChecked()
        # fallback to top toolbar (legacy)
        legacy = getattr(self.toolbar, f"{name}_btn", None)
        return legacy.isChecked() if legacy else False

    def _set_tool_btn(self, name: str, checked: bool):
        """Set both the panel and (if it exists) the top toolbar button."""
        t = self.current_tab()
        if t and hasattr(t, "tools_panel"):
            b = t.tools_panel.get(name)
            if b is not None:
                b.setChecked(checked)
        legacy = getattr(self.toolbar, f"{name}_btn", None)
        if legacy is not None:
            legacy.setChecked(checked)

    def _tab_changed(self, idx):
        t = self.current_tab()
        if t and t.document:
            self.setWindowTitle(f"{t.document.file_name()} — {APP_NAME}")
            self._update_status()
            # Use UniqueConnection so each viewer is wired at most once.
            for sig, slot in (
                (t.viewer.current_page_changed, self._on_page_changed),
                (t.viewer.zoom_changed, self._on_zoom_changed),
                (t.viewer.highlight_selected, self._on_highlight_selected),
                (t.viewer.sign_placement_requested, self._on_sign_placement),
                (t.viewer.stamp_placement_requested, self._on_stamp_placement),
                (t.viewer.comment_placement_requested, self._on_comment_placement),
                (t.viewer.field_placement_requested, self._on_field_placement),
                (t.viewer.link_placement_requested, self._on_link_placement),
                (t.viewer.line_clicked, self._on_line_clicked),
                (t.viewer.inline_edit_committed, self._on_inline_edit_committed),
                (t.viewer.text_copied, self._on_text_copied),
                (t.viewer.reference_found, self._on_reference_found),
                (t.viewer.text_selected_for_note, self._on_text_selected_for_note),
                (t.viewer.form_field_clicked, self._on_form_field_clicked),
                (t.viewer.ink_drawn, self._on_ink_drawn),
                (t.viewer.xmark_placed, self._on_xmark_placed),
                (t.viewer.shape_drawn, self._on_shape_drawn),
                (t.viewer.text_placement_requested, self._on_text_placement),
                (t.viewer.image_placement_requested, self._on_image_placement),
                (t.viewer.annot_delete_requested, self._on_annot_delete),
                (t.viewer.open_url_requested, self._on_open_url),
            ):
                try:
                    sig.connect(slot, Qt.UniqueConnection)
                except (RuntimeError, TypeError):
                    pass

            # Wire the per-tab All Tools panel signals
            tp = t.tools_panel
            wires = (
                (tp.undo_requested,           self.action_undo),
                (tp.delete_annot_requested,   self.action_delete_annot_toggle),
                (tp.highlight_requested,      self.action_highlight_toggle),
                (tp.line_highlight_requested, self.action_line_highlight_toggle),
                (tp.note_requested,           self.action_note_hint),
                (tp.comment_requested,        self.action_comment),
                (tp.line_comment_requested,   self.action_line_comment_toggle),
                (tp.stamp_requested,          self.action_stamp),
                (tp.text_color_requested,     self.action_text_color),
                (tp.line_edit_requested,      self.action_line_edit_toggle),
                (tp.edit_mode_requested,      self.action_edit_mode_toggle),
                (tp.select_text_requested,    self.action_select_text_toggle),
                (tp.fill_form_requested,      self.action_fill_form_toggle),
                (tp.line_color_requested,     self.action_line_color_toggle),
                (tp.sign_requested,           self.action_sign),
                (tp.prepare_form_requested,   self.action_prepare_form),
                (tp.fill_form_requested,      self.action_fill_form),
                (tp.media_requested,          self.action_media),
                (tp.send_review_requested,    self.action_send_review),
                (tp.create_pdf_requested,     self.action_create_pdf),
                (tp.organize_requested,       self.action_organize),
                (tp.merge_requested,          self.action_merge),
                (tp.split_requested,          self.action_split),
                (tp.extract_requested,        self.action_extract_pages),
                (tp.compare_requested,        self.action_compare),
                (tp.extract_citations_requested, self.action_extract_citations),
                (tp.reference_collection_requested, self.open_reference_panel),
                (tp.notes_collection_requested, self.open_notes_panel),
                (tp.library_requested, self.open_library_panel),
                (tp.compress_requested,       self.action_compress),
                (tp.encrypt_requested,        self.action_encrypt),
                (tp.decrypt_requested,        self.action_decrypt),
                (tp.properties_requested,     self.action_properties),
                (tp.to_images_requested,      self.action_export_images),
                (tp.images_to_pdf_requested,  self.action_images_to_pdf),
                (tp.to_text_requested,        self.action_extract_text),
                (tp.ocr_requested,            self.action_ocr),
                # NEW edit features
                (tp.add_text_requested,            self.action_add_text_toggle),
                (tp.add_image_requested,           self.action_add_image_toggle),
                (tp.header_footer_requested,       self.action_header_footer),
                (tp.insert_blank_page_requested,   self.action_insert_blank_page),
                (tp.delete_current_page_requested, self.action_delete_current_page),
                (tp.rotate_page_left_requested,    self.action_rotate_page_left),
                (tp.rotate_page_right_requested,   self.action_rotate_page_right),
            )
            for sig, slot in wires:
                try:
                    sig.connect(slot, Qt.UniqueConnection)
                except (RuntimeError, TypeError):
                    pass
        else:
            self.setWindowTitle(APP_NAME)

    def _on_page_changed(self, page_num):
        t = self.current_tab()
        if not t or not t.document:
            return
        self.status_page.setText(f"Page {page_num} / {t.document.page_count}")
        # keep the jump box in sync without firing its signal
        try:
            self.page_jump.blockSignals(True)
            self.page_jump.setMaximum(max(1, t.document.page_count))
            self.page_jump.setValue(page_num)
            self.page_jump.blockSignals(False)
        except Exception:
            pass
        self._refresh_undo_state()

    def _on_zoom_changed(self, zoom):
        self.status_zoom.setText(f"Zoom {int(zoom * 100)}%")
        self.toolbar.set_zoom_label(zoom)

    def _update_status(self):
        t = self.current_tab()
        if not t or not t.document:
            self.status_page.setText("Page —")
            self.status_zoom.setText("Zoom 100%")
            return
        self.status_page.setText(f"Page {t.viewer.canvas.current_page() + 1} / {t.document.page_count}")
        self.status_zoom.setText(f"Zoom {int(t.viewer.canvas.zoom * 100)}%")
        self.toolbar.set_zoom_label(t.viewer.canvas.zoom)

    # ---- welcome tab ----
    def _open_welcome_tab(self):
        if self.tab_widget.count() > 0:
            return
        from ui.home_page import HomePage
        import getpass
        try:
            user = getpass.getuser()
        except Exception:
            user = ""

        def on_action(name):
            if name == "references":
                self.open_reference_panel()
            elif name == "notes":
                self.open_notes_panel()
            elif name == "compare":
                self.action_compare()
            elif name == "ocr":
                self.action_ocr()

        w = HomePage(
            app_name=APP_NAME,
            user_name=user,
            recent_paths=self.settings.recent_files(),
            on_open_dialog=self.action_open,
            on_open_file=self.open_pdf,
            on_action=on_action,
            is_dark=(self.settings.theme() == "dark"),
            parent=self,
        )
        self.tab_widget.addTab(w, "Home")
        if hasattr(self, "_apply_tab_close_icons"):
            self._apply_tab_close_icons()

    # ---- file actions ----
    def action_open(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Open PDFs", "", PDF_FILTER)
        for f in files:
            self.open_pdf(f)

    def open_pdf(self, path: str):
        if not file_exists(path):
            QMessageBox.warning(self, "Not found", f"File not found:\n{path}")
            self.settings.remove_recent_file(path)
            self._rebuild_recent_menu()
            return
        # remove welcome tab on first real open
        if self.tab_widget.count() == 1:
            first = self.tab_widget.widget(0)
            if not isinstance(first, PDFTab):
                self.tab_widget.removeTab(0)

        tab = PDFTab(self.settings)
        if not tab.open(path):
            return
        idx = self.tab_widget.addTab(tab, tab.document.file_name())
        self.tab_widget.setCurrentIndex(idx)
        self.tab_widget.setTabToolTip(idx, path)
        if hasattr(self, "_apply_tab_close_icons"):
            self._apply_tab_close_icons()
        tab.viewer.set_background_color(viewer_background(self.settings.theme()))
        self.settings.add_recent_file(path)
        self._rebuild_recent_menu()
        self._update_status()

    def _close_tab(self, idx):
        w = self.tab_widget.widget(idx)
        if isinstance(w, PDFTab) and w.document and w.document.dirty:
            ret = QMessageBox.question(self, "Unsaved changes",
                                       "You have unsaved changes. Save now?",
                                       QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel)
            if ret == QMessageBox.Cancel:
                return
            if ret == QMessageBox.Save:
                w.save()
        if isinstance(w, PDFTab):
            w.close_document()
        self.tab_widget.removeTab(idx)
        if self.tab_widget.count() == 0:
            self._open_welcome_tab()

    def action_save(self):
        t = self.current_tab()
        if not t or not t.document:
            return
        if not t.path:
            self.action_save_as()
            return
        try:
            t.save()
            self.status_msg.setText(f"Saved {t.path}")
        except Exception as e:
            QMessageBox.critical(self, "Save failed", str(e))

    def action_save_as(self):
        t = self.current_tab()
        if not t or not t.document:
            return
        if t.save_as():
            self.status_msg.setText(f"Saved as {t.path}")

    def action_print(self):
        """Print the current PDF using the system print dialog.

        Renders each page to an image and sends it to the chosen printer,
        so it works for any PDF the app can display (including edits).
        """
        t = self.current_tab()
        if not t or not t.document:
            QMessageBox.information(self, "Print", "Open a PDF first.")
            return

        try:
            from PySide6.QtPrintSupport import (QPrinter, QPrinterInfo)
            from PySide6.QtGui import QPainter, QImage, QPageLayout
            from PySide6.QtCore import QRectF
            import fitz
        except Exception:
            QMessageBox.warning(
                self, "Print",
                "Printing support is not available. Please make sure "
                "PySide6 is fully installed.")
            return

        from ui.dialogs import PrintDialog
        cur_page = t.viewer.canvas.current_page()
        dlg = PrintDialog(t.document, current_page=cur_page, parent=self)
        if dlg.exec() != PrintDialog.Accepted:
            return
        opts = dlg.results()

        # Build the printer from the chosen options
        printer = QPrinter(QPrinter.HighResolution)
        try:
            from PySide6.QtPrintSupport import QPrinterInfo
            for pinfo in QPrinterInfo.availablePrinters():
                if pinfo.printerName() == opts["printer"]:
                    printer.setPrinterName(opts["printer"])
                    break
        except Exception:
            pass
        printer.setDocName(os.path.basename(t.path or "document.pdf"))
        printer.setCopyCount(max(1, opts["copies"]))
        if opts["grayscale"]:
            try:
                printer.setColorMode(QPrinter.GrayScale)
            except Exception:
                pass
        if opts["orientation"] == "portrait":
            printer.setPageOrientation(QPageLayout.Portrait)
        elif opts["orientation"] == "landscape":
            printer.setPageOrientation(QPageLayout.Landscape)
        if opts["duplex"]:
            try:
                printer.setDuplex(QPrinter.DuplexAuto)
            except Exception:
                pass

        # Work out the page list
        pages = self._parse_page_selection(opts["pages"], opts["current_page"],
                                           t.document.page_count)
        if not pages:
            QMessageBox.information(self, "Print", "No pages selected.")
            return

        self.status_msg.setText("Printing…")
        QApplication.setOverrideCursor(Qt.WaitCursor)
        painter = QPainter()
        if not painter.begin(printer):
            QApplication.restoreOverrideCursor()
            QMessageBox.warning(self, "Print", "Could not start the printer.")
            return
        try:
            doc = t.document.doc
            res = printer.resolution()
            for n, pno in enumerate(pages):
                if n > 0:
                    printer.newPage()
                page = doc[pno]
                zoom = max(1.0, res / 72.0)
                pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom),
                                      alpha=False)
                if max(pix.width, pix.height) > 4200:
                    shrink = 4200 / max(pix.width, pix.height)
                    pix = page.get_pixmap(
                        matrix=fitz.Matrix(zoom * shrink, zoom * shrink),
                        alpha=False)
                img = QImage(pix.samples, pix.width, pix.height,
                             pix.stride, QImage.Format_RGB888)
                if opts["grayscale"]:
                    img = img.convertToFormat(QImage.Format_Grayscale8)
                target = QRectF(printer.pageRect(QPrinter.DevicePixel))
                iw, ih = img.width(), img.height()
                if iw and ih:
                    if opts["sizing"] == "actual":
                        scale = res / 72.0 / zoom
                    else:
                        scale = min(target.width() / iw, target.height() / ih)
                        if opts["sizing"] == "shrink":
                            scale = min(scale, 1.0 * target.width() / iw,
                                        1.0 * target.height() / ih)
                    w, h = iw * scale, ih * scale
                    x = target.x() + (target.width() - w) / 2
                    y = target.y() + (target.height() - h) / 2
                    painter.drawImage(QRectF(x, y, w, h), img)
            painter.end()
            self.status_msg.setText(f"Printed {len(pages)} page(s).")
        except Exception as e:
            painter.end()
            QMessageBox.critical(self, "Print failed", str(e))
            self.status_msg.setText("Print failed.")
        finally:
            QApplication.restoreOverrideCursor()

    def _parse_page_selection(self, pages, current_page, total):
        """Turn the dialog's page choice into a list of 0-based page indices."""
        if pages == "all":
            return list(range(total))
        if pages == "current":
            return [max(0, min(current_page, total - 1))]
        # a range like "1-3,5,7-9"
        result = []
        for part in str(pages).replace(" ", "").split(","):
            if not part:
                continue
            if "-" in part:
                try:
                    a, b = part.split("-")
                    a = int(a); b = int(b)
                    for p in range(a, b + 1):
                        if 1 <= p <= total:
                            result.append(p - 1)
                except ValueError:
                    continue
            else:
                try:
                    p = int(part)
                    if 1 <= p <= total:
                        result.append(p - 1)
                except ValueError:
                    continue
        # de-duplicate while keeping order
        seen = set(); out = []
        for p in result:
            if p not in seen:
                seen.add(p); out.append(p)
        return out

    def action_save_flattened(self):
        """Save a copy where annotations are baked into page content."""
        t = self.current_tab()
        if not t or not t.document:
            return
        path, _ = QFileDialog.getSaveFileName(self, "Save flattened copy…",
                                              "flattened.pdf", PDF_FILTER)
        if not path:
            return
        # PyMuPDF flattens by default when saving with garbage collection
        try:
            t.document.doc.save(path, garbage=4, deflate=True, clean=True)
            self.status_msg.setText(f"Saved flattened copy to {path}")
        except Exception as e:
            QMessageBox.critical(self, "Save failed", str(e))

    def action_open_folder(self):
        t = self.current_tab()
        if t and t.path:
            open_containing_folder(t.path)

    # ---- view actions ----
    def _rotate_view(self, deg: int):
        t = self.current_tab()
        if not t or not t.document:
            return
        new_rot = (t.viewer.canvas.rotation + deg) % 360
        t.viewer.set_rotation(new_rot)

    def _set_view_mode(self, mode: str):
        t = self.current_tab()
        if t:
            t.viewer.set_view_mode(mode)

    def _toggle_fullscreen(self):
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()

    # ---- panel collapse / expand ----
    def _toggle_panel(self, which: str):
        t = self.current_tab()
        if not t:
            return
        wrap = {"tools": getattr(t, "tools_wrap", None),
                "left": getattr(t, "left_wrap", None),
                "right": getattr(t, "right_wrap", None)}.get(which)
        if wrap:
            wrap.toggle()

    def _focus_mode(self):
        """Collapse all three side panels for a distraction-free view.
        If they're already all collapsed, expand them again."""
        t = self.current_tab()
        if not t:
            return
        wraps = [getattr(t, "tools_wrap", None),
                 getattr(t, "left_wrap", None),
                 getattr(t, "right_wrap", None)]
        wraps = [w for w in wraps if w]
        all_collapsed = all(w.is_collapsed() for w in wraps)
        for w in wraps:
            if all_collapsed:
                w.expand()
            else:
                w.collapse()
        self.status_msg.setText(
            "Focus mode off." if all_collapsed
            else "Focus mode: panels hidden (Ctrl+Shift+F to bring back).")

    # ---- search ----
    def _search(self, term):
        t = self.current_tab()
        if t:
            t.search(term)

    # ---- annotation actions (hints) ----
    def action_highlight_toggle(self):
        """Toggle the click-drag highlight tool."""
        from ui.pdf_viewer import TOOL_HIGHLIGHT, TOOL_NONE
        t = self.current_tab()
        if not t or not t.document:
            self._set_tool_btn("highlight", False)
            QMessageBox.information(self, "Highlight", "Open a PDF first.")
            return
        # If user just clicked it off, deactivate
        if not self._tool_btn_checked("highlight"):
            t.viewer.set_tool(TOOL_NONE)
            self.status_msg.setText("Highlight tool off.")
            return
        # Turn on highlight: clear other tool buttons
        t.tools_panel.uncheck_all_except("highlight")
        self._set_tool_btn("highlight", True)
        self._pending_signature_path = None
        t.viewer.set_tool(TOOL_HIGHLIGHT)
        self.status_msg.setText(
            "Highlight tool: drag across text to highlight. Click again to stop.")

    def _on_highlight_selected(self, page_index, rect):
        """Called when the user finishes a drag on the highlight tool."""
        t = self.current_tab()
        if not t or not t.document:
            return
        try:
            t.document.push_undo("Highlight")
            color = self.settings.highlight_color()
            # snap to words inside the rect for nicer text highlights
            try:
                word_rects = t.document.doc[page_index].get_text("words")
                # each word: (x0, y0, x1, y1, "word", block, line, word)
                import fitz
                sel = fitz.Rect(rect.x(), rect.y(),
                                rect.x() + rect.width(),
                                rect.y() + rect.height())
                hit_rects = []
                for w in word_rects:
                    wr = fitz.Rect(w[0], w[1], w[2], w[3])
                    if wr.intersects(sel):
                        hit_rects.append(wr)
                if not hit_rects:
                    hit_rects = [sel]
            except Exception:
                hit_rects = [(rect.x(), rect.y(),
                              rect.x() + rect.width(),
                              rect.y() + rect.height())]

            style = getattr(t, "_highlight_style", "highlight")
            if style == "underline":
                t.annotations.add_underline(page_index, hit_rects, color=color)
                label = "Underline"
            elif style == "strikeout":
                t.annotations.add_strikeout(page_index, hit_rects, color=color)
                label = "Strikethrough"
            else:
                t.annotations.add_highlight(page_index, hit_rects, color=color)
                label = "Highlight"
            t.viewer.canvas.invalidate_page(page_index)
            t._refresh_right_sidebar()
            t.document.mark_dirty()
            self.status_msg.setText(
                f"{label} added on page {page_index + 1} (unsaved)")
        except Exception as e:
            QMessageBox.critical(self, "Could not highlight", str(e))

    def action_note_hint(self):
        t = self.current_tab()
        if not t or not t.document:
            return
        page, ok = QInputDialog.getInt(self, "Sticky note", "Page number:",
                                       t.viewer.canvas.current_page() + 1,
                                       1, t.document.page_count)
        if not ok:
            return
        text, ok = QInputDialog.getMultiLineText(self, "Sticky note",
                                                 "Note text:", "")
        if not ok:
            return
        try:
            t.annotations.add_sticky_note(page - 1, (40, 40), text)
            t.viewer.canvas.invalidate_page(page - 1)
            t._refresh_right_sidebar()
            t.document.mark_dirty()
            self.status_msg.setText(f"Added note on page {page}")
        except Exception as e:
            QMessageBox.critical(self, "Could not add note", str(e))

    # ---- properties ----
    def action_properties(self):
        t = self.current_tab()
        if not t or not t.document:
            return
        md = t.document.metadata()
        dlg = PropertiesDialog(md, self)
        if dlg.exec() == PropertiesDialog.Accepted:
            try:
                t.document.set_metadata(dlg.updated_fields())
                t._refresh_right_sidebar()
                self.status_msg.setText("Metadata updated (unsaved)")
            except Exception as e:
                QMessageBox.critical(self, "Could not update metadata", str(e))

    # ---- organize ----
    def action_organize(self):
        t = self.current_tab()
        if not t or not t.document:
            return
        dlg = OrganizeDialog(t.document, self)
        if dlg.exec() != OrganizeDialog.Accepted:
            return
        plan = dlg.get_plan()
        if not plan:
            QMessageBox.warning(self, "Empty", "No pages would remain.")
            return
        try:
            self._apply_organize_plan(t, plan)
            t._refresh_right_sidebar()
            t.left_side.populate(t.document)
            t.viewer.canvas._page_pixmaps.clear()
            t.viewer.canvas._relayout()
            t.viewer.canvas.update()
            self.status_msg.setText("Pages reorganized (unsaved)")
        except Exception as e:
            QMessageBox.critical(self, "Reorganize failed", str(e))

    def _apply_organize_plan(self, tab: PDFTab, plan: list[dict]):
        """Rebuild the document according to the organize dialog's plan."""
        import fitz
        new_doc = fitz.open()
        for entry in plan:
            src_idx = entry["source_index"]
            rot = entry["rotation"]
            new_doc.insert_pdf(tab.document.doc, from_page=src_idx, to_page=src_idx)
            if rot:
                new_doc[-1].set_rotation((new_doc[-1].rotation + rot) % 360)
        # swap docs
        tab.document.close()
        tab.document.doc = new_doc
        tab.document.mark_dirty()
        tab.annotations = AnnotationManager(tab.document)
        tab.viewer.set_document(tab.document)

    # ---- merge ----
    def action_merge(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Pick PDFs to merge "
                                                "(order = selection order)", "", PDF_FILTER)
        if not files or len(files) < 2:
            if files:
                QMessageBox.information(self, "Merge", "Pick at least two PDFs.")
            return
        out, _ = QFileDialog.getSaveFileName(self, "Save merged file as…",
                                             "merged.pdf", PDF_FILTER)
        if not out:
            return
        self._run_worker(MergeWorker(files, out), "Merging PDFs…",
                         lambda result: self._after_merge(result, out))

    def _after_merge(self, result, path):
        self.status_msg.setText(f"Merged to {path}")
        if QMessageBox.question(self, "Open merged file?",
                                f"Done!\n\n{path}\n\nOpen it now?",
                                QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
            self.open_pdf(path)

    # ---- split ----
    def action_split(self):
        t = self.current_tab()
        if not t or not t.document or not t.path:
            QMessageBox.information(self, "Split", "Open a saved PDF first.")
            return
        dlg = SplitDialog(t.document.page_count, self)
        if dlg.exec() != SplitDialog.Accepted:
            return
        out_folder = QFileDialog.getExistingDirectory(self, "Output folder")
        if not out_folder:
            return
        try:
            if dlg.each_page():
                outs = PageManager.split_each_page(t.path, out_folder)
            else:
                outs = PageManager.split_by_ranges(t.path, out_folder, dlg.get_ranges())
            QMessageBox.information(self, "Split", f"Created {len(outs)} files in:\n{out_folder}")
        except Exception as e:
            QMessageBox.critical(self, "Split failed", str(e))

    # ---- extract ----
    def action_extract_pages(self):
        t = self.current_tab()
        if not t or not t.document:
            return
        spec, ok = QInputDialog.getText(self, "Extract pages",
                                        f"Pages to extract (e.g. 1-3,5,9). "
                                        f"Document has {t.document.page_count} pages:")
        if not ok or not spec:
            return
        pages = PageManager.parse_page_range(spec, t.document.page_count)
        if not pages:
            QMessageBox.warning(self, "Extract", "No valid pages in range.")
            return
        out, _ = QFileDialog.getSaveFileName(self, "Save extracted PDF as…",
                                             "extracted.pdf", PDF_FILTER)
        if not out:
            return
        try:
            t.document.extract_pages(pages, out)
            self.status_msg.setText(f"Extracted to {out}")
        except Exception as e:
            QMessageBox.critical(self, "Extract failed", str(e))

    # ---- convert ----
    def action_export_images(self):
        t = self.current_tab()
        if not t or not t.path:
            QMessageBox.information(self, "Export images", "Save the PDF first.")
            return
        out_folder = QFileDialog.getExistingDirectory(self, "Output folder")
        if not out_folder:
            return
        fmt_items = ["PNG", "JPG"]
        fmt, ok = QInputDialog.getItem(self, "Format", "Image format:", fmt_items, 0, False)
        if not ok:
            return
        worker = ImageExportWorker(t.path, out_folder, fmt=fmt.lower(), dpi=150)
        self._run_worker(worker, "Exporting pages…",
                         lambda r: self.status_msg.setText(f"Saved images to {r}"))

    def action_images_to_pdf(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Pick images", "", IMAGE_FILTER)
        if not files:
            return
        out, _ = QFileDialog.getSaveFileName(self, "Save PDF as…", "images.pdf", PDF_FILTER)
        if not out:
            return
        try:
            Converter.images_to_pdf(files, out)
            self.status_msg.setText(f"Built PDF: {out}")
            if QMessageBox.question(self, "Open?", "Open the new PDF?",
                                    QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
                self.open_pdf(out)
        except Exception as e:
            QMessageBox.critical(self, "Image→PDF failed", str(e))

    def action_extract_text(self):
        t = self.current_tab()
        if not t or not t.path:
            return
        out, _ = QFileDialog.getSaveFileName(self, "Save text as…", "text.txt", "Text (*.txt)")
        if not out:
            return
        try:
            Converter.pdf_to_text(t.path, out)
            self.status_msg.setText(f"Text saved to {out}")
        except Exception as e:
            QMessageBox.critical(self, "Extract text failed", str(e))

    # ---- OCR ----
    def action_ocr(self):
        t = self.current_tab()
        if not t or not t.path:
            QMessageBox.information(self, "OCR", "Save the PDF first.")
            return
        engine = OCREngine()
        if not engine.is_available():
            QMessageBox.warning(self, "Tesseract not installed",
                                "OCR requires Tesseract to be installed.\n\n"
                                "Windows: https://github.com/UB-Mannheim/tesseract/wiki\n"
                                "macOS:   brew install tesseract\n"
                                "Linux:   sudo apt install tesseract-ocr")
            return
        dlg = OCRDialog(default_lang=self.settings.ocr_language(), parent=self)
        if dlg.exec() != OCRDialog.Accepted:
            return
        lang = dlg.language_code()

        # Check the chosen language pack(s) are actually installed in Tesseract.
        # Without this, OCR for e.g. Japanese silently produces nothing.
        check = OCREngine(language=lang)
        missing = check.missing_languages()
        if missing:
            pretty = ", ".join(missing)
            ret = QMessageBox.warning(
                self, "Language pack not installed",
                f"Tesseract does not have the language pack(s) for: {pretty}.\n\n"
                "OCR for this language will not work until you install it:\n"
                "  Windows: re-run the Tesseract installer and tick the language\n"
                "  macOS:   brew install tesseract-lang\n"
                "  Linux:   sudo apt install tesseract-ocr-" + missing[0] + "\n\n"
                "Continue with English only?",
                QMessageBox.Yes | QMessageBox.Cancel)
            if ret == QMessageBox.Cancel:
                return
            lang = "eng"

        out, _ = QFileDialog.getSaveFileName(self, "Save searchable PDF…",
                                             "searchable.pdf", PDF_FILTER)
        if not out:
            return
        worker = OCRWorker(t.path, out, language=lang)
        self._run_worker(worker, "Running OCR…",
                         lambda r: self._after_ocr(r))

    def _after_ocr(self, path):
        self.status_msg.setText(f"OCR finished: {path}")
        if QMessageBox.question(self, "Open OCR'd file?", f"OCR done!\n\n{path}\n\nOpen it now?",
                                QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
            self.open_pdf(path)

    # ---- security ----
    def action_encrypt(self):
        t = self.current_tab()
        if not t or not t.path:
            QMessageBox.information(self, "Encrypt", "Save the PDF first.")
            return
        dlg = EncryptDialog(self)
        if dlg.exec() != EncryptDialog.Accepted:
            return
        opts = dlg.options()
        out, _ = QFileDialog.getSaveFileName(self, "Save encrypted copy…",
                                             "encrypted.pdf", PDF_FILTER)
        if not out:
            return
        try:
            SecurityManager.encrypt(t.path, out, opts["password"],
                                    allow_print=opts["allow_print"],
                                    allow_copy=opts["allow_copy"],
                                    allow_modify=opts["allow_modify"])
            QMessageBox.information(self, "Encrypted", f"Saved to:\n{out}")
        except Exception as e:
            QMessageBox.critical(self, "Encrypt failed", str(e))

    def action_decrypt(self):
        path, _ = QFileDialog.getOpenFileName(self, "Pick encrypted PDF", "", PDF_FILTER)
        if not path:
            return
        pw, ok = QInputDialog.getText(self, "Decrypt", "Password:", QLineEdit.Password)
        if not ok:
            return
        out, _ = QFileDialog.getSaveFileName(self, "Save decrypted copy…",
                                             "decrypted.pdf", PDF_FILTER)
        if not out:
            return
        try:
            ok = SecurityManager.decrypt(path, out, pw)
            if not ok:
                QMessageBox.warning(self, "Wrong password", "Could not decrypt with that password.")
                return
            QMessageBox.information(self, "Decrypted", f"Saved to:\n{out}")
        except Exception as e:
            QMessageBox.critical(self, "Decrypt failed", str(e))

    # ---- sign ----
    def action_sign(self):
        """Open the signature dialog, then put the viewer into 'click to place' mode."""
        from ui.pdf_viewer import TOOL_SIGN, TOOL_NONE
        t = self.current_tab()
        if not t or not t.document:
            self._set_tool_btn("sign", False)
            QMessageBox.information(self, "Sign", "Open a PDF first.")
            return

        # If the button was clicked off, cancel pending sign mode
        if not self._tool_btn_checked("sign"):
            t.viewer.set_tool(TOOL_NONE)
            self._pending_signature_path = None
            self.status_msg.setText("Sign cancelled.")
            return

        dlg = SignatureDialog(self)
        if dlg.exec() != SignatureDialog.Accepted:
            self._set_tool_btn("sign", False)
            return
        pix = dlg.signature_pixmap()
        if not pix or pix.isNull():
            self._set_tool_btn("sign", False)
            QMessageBox.warning(self, "Sign", "No signature was produced.")
            return

        # save to a temp file
        import tempfile
        tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
        pix.save(tmp.name, "PNG")
        tmp.close()
        self._pending_signature_path = tmp.name
        self._pending_signature_aspect = (pix.width() / max(1, pix.height()))

        # turn off other tools
        t.tools_panel.uncheck_all_except("sign")
        self._set_tool_btn("sign", True)

        t.viewer.set_tool(TOOL_SIGN)
        self.status_msg.setText(
            "Click on the page where you want the signature. "
            "Press the Sign button again to cancel.")

    def _on_sign_placement(self, page_index, point):
        """User clicked on the page after preparing a signature."""
        from ui.pdf_viewer import TOOL_NONE
        t = self.current_tab()
        if not t or not t.document:
            return
        if not getattr(self, "_pending_signature_path", None):
            return
        try:
            t.document.push_undo("Signature")
            page_w, page_h = t.document.page_size(page_index)
            aspect = getattr(self, "_pending_signature_aspect", 4.0)
            sig_w = min(180, page_w * 0.3)
            sig_h = sig_w / max(0.1, aspect)
            # center the signature on the click point, but clamp inside page
            x0 = max(0, min(page_w - sig_w, point.x() - sig_w / 2))
            y0 = max(0, min(page_h - sig_h, point.y() - sig_h / 2))
            t.annotations.add_signature_image(
                page_index, self._pending_signature_path,
                (x0, y0, x0 + sig_w, y0 + sig_h))
            t.viewer.canvas.invalidate_page(page_index)
            t.document.mark_dirty()
            self.status_msg.setText(
                f"Signed page {page_index + 1} (unsaved). Click again to add more, "
                "or click Sign to stop.")
        except Exception as e:
            QMessageBox.critical(self, "Could not sign", str(e))
            self._set_tool_btn("sign", False)
            t.viewer.set_tool(TOOL_NONE)
            self._pending_signature_path = None

    # ---- compress ----
    def action_compress(self):
        t = self.current_tab()
        if not t or not t.document or not t.path:
            QMessageBox.information(
                self, "Compress",
                "Open and save a PDF first so it has a file on disk to compress.")
            return
        from ui.dialogs import CompressDialog
        from utils.worker_threads import CompressWorker
        size = os.path.getsize(t.path)
        dlg = CompressDialog(size, self)
        if dlg.exec() != CompressDialog.Accepted:
            return
        dpi, quality = dlg.settings()
        out, _ = QFileDialog.getSaveFileName(
            self, "Save compressed PDF as",
            os.path.splitext(t.path)[0] + f"-compressed-{dpi}dpi.pdf",
            "PDF (*.pdf)")
        if not out:
            return
        if not out.lower().endswith(".pdf"):
            out += ".pdf"

        worker = CompressWorker(t.path, out, dpi, quality)

        def on_done(path):
            stats = worker.stats or {}
            old = stats.get("original_size", 0)
            new = stats.get("new_size", 0)
            saved_pct = (1 - new / old) * 100 if old else 0
            QMessageBox.information(
                self, "Compression done",
                f"Saved to:\n{path}\n\n"
                f"Original: {old / 1024 / 1024:.2f} MB\n"
                f"New:      {new / 1024 / 1024:.2f} MB\n"
                f"Saved:    {saved_pct:.1f}%\n\n"
                f"Images downsampled: {stats.get('images_replaced', 0)}\n"
                f"Images left as-is:  {stats.get('images_skipped', 0)}")

        self._run_worker(worker, f"Compressing to {dpi} DPI", on_done)

    # ---- compare ----
    def action_extract_citations(self):
        """Extract in-text citations + reference list and show them. Offline."""
        t = self.current_tab()
        if not t or not t.document:
            QMessageBox.information(self, "Extract Citations",
                                    "Open a PDF first.")
            return
        from core.citation_extractor import extract_all
        from PySide6.QtWidgets import (QDialog, QVBoxLayout, QTextEdit,
                                       QPushButton, QHBoxLayout, QLabel,
                                       QFileDialog)
        try:
            data = extract_all(t.path)
        except Exception as e:
            QMessageBox.critical(self, "Extract Citations", str(e))
            return

        # build a readable text report
        lines = []
        lines.append("IN-TEXT CITATIONS")
        lines.append("-" * 40)
        if data["numeric"]:
            lines.append("Numbered: " + ", ".join(data["numeric"]))
        if data["author_year"]:
            lines.append("Author-year: " + ", ".join(data["author_year"]))
        if not data["numeric"] and not data["author_year"]:
            lines.append("(none found)")
        lines.append("")
        lines.append(f"REFERENCE LIST  ({data['reference_count']} found)")
        lines.append("-" * 40)
        if data["references"]:
            lines.extend(data["references"])
        else:
            lines.append("(no reference section detected)")
        report = "\n".join(lines)

        dlg = QDialog(self)
        dlg.setWindowTitle("Extracted Citations & References")
        dlg.resize(640, 560)
        lay = QVBoxLayout(dlg)
        lay.addWidget(QLabel("Found in this document (you can copy or save):"))
        box = QTextEdit()
        box.setPlainText(report)
        box.setReadOnly(True)
        lay.addWidget(box, 1)
        row = QHBoxLayout()
        copy_btn = QPushButton("Copy all")
        save_btn = QPushButton("Save to .txt")
        close_btn = QPushButton("Close")
        row.addWidget(copy_btn); row.addWidget(save_btn)
        row.addStretch(1); row.addWidget(close_btn)
        lay.addLayout(row)

        from PySide6.QtWidgets import QApplication
        copy_btn.clicked.connect(
            lambda: QApplication.clipboard().setText(report))
        def _save():
            fn, _ = QFileDialog.getSaveFileName(
                dlg, "Save citations", "citations.txt", "Text files (*.txt)")
            if fn:
                try:
                    with open(fn, "w", encoding="utf-8") as f:
                        f.write(report)
                except Exception as e:
                    QMessageBox.critical(dlg, "Save failed", str(e))
        save_btn.clicked.connect(_save)
        close_btn.clicked.connect(dlg.accept)
        dlg.exec()

    def action_compare(self):
        from ui.dialogs import CompareDialog, SelectFilesToCompareDialog
        # Pre-fill the OLD file with the currently open document, if any
        cur = self.current_tab()
        prefill = cur.path if (cur and cur.path) else ""
        picker = SelectFilesToCompareDialog(self, old_path=prefill)
        if picker.exec() != SelectFilesToCompareDialog.Accepted:
            return
        res = picker.results()
        old_path, new_path = res["old_path"], res["new_path"]
        if not old_path or not new_path:
            return
        try:
            dlg = CompareDialog(old_path, new_path, self)
            # carry over the "text only" choice to the report default
            if hasattr(dlg, "report_mode_combo"):
                idx = dlg.report_mode_combo.findData(
                    "changes" if res["text_only"] else "both")
                if idx >= 0:
                    dlg.report_mode_combo.setCurrentIndex(idx)
            dlg.exec()
        except Exception as e:
            QMessageBox.critical(self, "Compare failed", str(e))

    # ---- text color ----
    def action_text_color(self):
        from ui.dialogs import TextColorDialog
        from core.text_editor import change_text_color_on_page
        t = self.current_tab()
        if not t or not t.document or not t.path:
            QMessageBox.information(
                self, "Change text color",
                "Open and save a PDF first so it has a file on disk to edit.")
            return
        current_page = t.viewer.canvas.current_page() + 1
        dlg = TextColorDialog(t.document.page_count, current_page, self)
        if dlg.exec() != TextColorDialog.Accepted:
            return
        out, _ = QFileDialog.getSaveFileName(
            self, "Save recolored PDF as",
            os.path.splitext(t.path)[0] + "-recolored.pdf",
            "PDF (*.pdf)")
        if not out:
            return
        if not out.lower().endswith(".pdf"):
            out += ".pdf"
        try:
            stats = change_text_color_on_page(
                t.path, out, dlg.page_index(), dlg.color_hex())
            QMessageBox.information(
                self, "Text color changed",
                f"Saved to:\n{out}\n\n"
                f"Page {stats['page']}: "
                f"{stats['spans_changed']} text spans recolored, "
                f"{stats['spans_skipped']} skipped.\n\n"
                "Open the new file to see the result.")
        except RuntimeError as e:
            QMessageBox.warning(self, "Cannot change text color", str(e))
        except Exception as e:
            QMessageBox.critical(self, "Failed", str(e))

    # ===== Create PDF =====
    def action_create_pdf(self):
        from ui.dialogs import CreatePDFDialog
        from core.pdf_creator import create_blank_pdf
        dlg = CreatePDFDialog(self)
        if dlg.exec() != CreatePDFDialog.Accepted:
            return
        s = dlg.settings()
        out, _ = QFileDialog.getSaveFileName(
            self, "Save new PDF as", "untitled.pdf", "PDF (*.pdf)")
        if not out:
            return
        if not out.lower().endswith(".pdf"):
            out += ".pdf"
        try:
            create_blank_pdf(out,
                             page_size=s["page_size"],
                             orientation=s["orientation"],
                             page_count=s["page_count"],
                             title=s["title"],
                             author=s["author"])
            # open it in a new tab
            self.open_pdf(out)
            self.status_msg.setText(f"Created {os.path.basename(out)}")
        except Exception as e:
            QMessageBox.critical(self, "Create failed", str(e))

    # ===== Prepare form =====
    def action_prepare_form(self):
        from ui.pdf_viewer import TOOL_FIELD, TOOL_NONE
        from ui.dialogs import PrepareFormDialog
        t = self.current_tab()
        if not t or not t.document:
            self._set_tool_btn("prepare_form", False)
            QMessageBox.information(self, "Prepare form", "Open a PDF first.")
            return
        if not self._tool_btn_checked("prepare_form"):
            t.viewer.set_tool(TOOL_NONE)
            self._pending_field = None
            self.status_msg.setText("Form tool off.")
            return
        dlg = PrepareFormDialog(self)
        if dlg.exec() != PrepareFormDialog.Accepted:
            self._set_tool_btn("prepare_form", False)
            return
        self._pending_field = dlg.settings()
        # turn off other tools
        t.tools_panel.uncheck_all_except("prepare_form")
        self._set_tool_btn("prepare_form", True)
        t.viewer.set_tool(TOOL_FIELD)
        ft = self._pending_field["field_type"]
        self.status_msg.setText(
            f"Drag a rectangle to place a {ft} field. "
            "Press the Prepare Form button again to stop.")

    def _on_field_placement(self, page_index, rect):
        t = self.current_tab()
        if not t or not t.document or not t.forms or not self._pending_field:
            return
        s = self._pending_field
        try:
            t.document.push_undo("Form field")
            name = t.forms.add_field(
                page_index,
                (rect.x(), rect.y(),
                 rect.x() + rect.width(), rect.y() + rect.height()),
                field_type=s["field_type"],
                field_name=s["field_name"],
                field_label=s["field_label"],
                default_value=s["default_value"],
                options=s["options"],
                required=s["required"],
            )
            t.viewer.canvas.invalidate_page(page_index)
            self.status_msg.setText(
                f"Added {s['field_type']} field '{name}' on page {page_index + 1}. "
                "Drag again to place another, or stop the tool.")
        except Exception as e:
            QMessageBox.critical(self, "Could not add field", str(e))

    # ===== Fill and sign =====
    def action_fill_form(self):
        from ui.dialogs import FillFormDialog
        t = self.current_tab()
        if not t or not t.document:
            QMessageBox.information(self, "Fill & sign", "Open a PDF first.")
            return
        fields = t.forms.list_fields() if t.forms else []
        dlg = FillFormDialog(fields, self)
        if dlg.exec() != FillFormDialog.Accepted:
            return
        # apply values to live document
        for page_idx, name, value in dlg.filled_values():
            t.forms.set_field_value(page_idx, name, value)
        t.viewer.canvas._page_pixmaps.clear()
        t.viewer.canvas.update()
        self.status_msg.setText(f"Filled {len(dlg.filled_values())} field(s) (unsaved).")

        if dlg.flatten_requested():
            out, _ = QFileDialog.getSaveFileName(
                self, "Save flattened PDF as",
                os.path.splitext(t.path or "filled.pdf")[0] + "-flat.pdf",
                "PDF (*.pdf)")
            if out:
                if not out.lower().endswith(".pdf"):
                    out += ".pdf"
                try:
                    # first save the current edits in-place
                    if t.path:
                        t.save(t.path)
                    t.forms.flatten_fields(out)
                    QMessageBox.information(self, "Flattened",
                                            f"Flat copy saved:\n{out}")
                except Exception as e:
                    QMessageBox.critical(self, "Flatten failed", str(e))

    # ===== Stamp =====
    def action_stamp(self):
        from ui.pdf_viewer import TOOL_STAMP, TOOL_NONE
        from ui.dialogs import StampDialog
        t = self.current_tab()
        if not t or not t.document:
            self._set_tool_btn("stamp", False)
            QMessageBox.information(self, "Stamp", "Open a PDF first.")
            return
        if not self._tool_btn_checked("stamp"):
            t.viewer.set_tool(TOOL_NONE)
            self._pending_stamp = None
            self.status_msg.setText("Stamp tool off.")
            return
        dlg = StampDialog(self)
        if dlg.exec() != StampDialog.Accepted:
            self._set_tool_btn("stamp", False)
            return
        self._pending_stamp = dlg.settings()
        t.tools_panel.uncheck_all_except("stamp")
        self._set_tool_btn("stamp", True)
        t.viewer.set_tool(TOOL_STAMP)
        self.status_msg.setText("Click on the page to place the stamp. "
                                "Press Stamp again to stop.")

    def _on_stamp_placement(self, page_index, point):
        t = self.current_tab()
        if not t or not t.stamps or not self._pending_stamp:
            return
        s = self._pending_stamp
        try:
            t.document.push_undo("Stamp")
            # center the stamp on the click
            w, h = 180, 50
            x0 = max(0, point.x() - w / 2)
            y0 = max(0, point.y() - h / 2)
            if s["kind"] == "standard":
                t.stamps.add_standard_stamp(page_index, s["name"], (x0, y0), w, h)
                msg = f"Stamp '{s['name']}' on page {page_index + 1}"
            else:
                t.stamps.add_custom_text_stamp(
                    page_index, s["text"], (x0, y0), w, h, s["color"])
                msg = f"Custom stamp '{s['text']}' on page {page_index + 1}"
            t.viewer.canvas.invalidate_page(page_index)
            t._refresh_right_sidebar()
            self.status_msg.setText(msg + " (unsaved)")
            self._refresh_undo_state()
        except Exception as e:
            QMessageBox.critical(self, "Stamp failed", str(e))

    # ===== Comment =====
    def action_comment(self):
        from ui.pdf_viewer import TOOL_COMMENT, TOOL_NONE
        from ui.dialogs import CommentDialog
        t = self.current_tab()
        if not t or not t.document:
            self._set_tool_btn("comment", False)
            QMessageBox.information(self, "Comment", "Open a PDF first.")
            return
        if not self._tool_btn_checked("comment"):
            t.viewer.set_tool(TOOL_NONE)
            self._pending_comment = None
            self.status_msg.setText("Comment tool off.")
            return
        import getpass
        default_author = ""
        try:
            default_author = getpass.getuser()
        except Exception:
            pass
        dlg = CommentDialog(self, default_author)
        if dlg.exec() != CommentDialog.Accepted:
            self._set_tool_btn("comment", False)
            return
        cfg = dlg.settings()
        if not cfg["text"]:
            QMessageBox.warning(self, "Comment", "Comment text is empty.")
            self._set_tool_btn("comment", False)
            return
        self._pending_comment = cfg
        t.tools_panel.uncheck_all_except("comment")
        self._set_tool_btn("comment", True)
        t.viewer.set_tool(TOOL_COMMENT)
        self.status_msg.setText("Click on the page to place the comment.")

    def _on_comment_placement(self, page_index, point):
        t = self.current_tab()
        if not t or not t.annotations:
            return

        # If the media tool routed us here for a file attachment, handle that
        if getattr(self, "_media_via_comment", False) and getattr(
                self, "_pending_media", None):
            s = self._pending_media
            if s.get("kind") == "attachment" and s.get("path"):
                try:
                    t.document.push_undo("Attachment")
                    t.media.add_file_attachment(
                        page_index,
                        (point.x(), point.y()),
                        s["path"],
                        s.get("description", ""))
                    t.viewer.canvas.invalidate_page(page_index)
                    self.status_msg.setText(
                        f"Attached '{os.path.basename(s['path'])}' on page "
                        f"{page_index + 1} (unsaved).")
                except Exception as e:
                    QMessageBox.critical(self, "Attach failed", str(e))
                return  # don't fall through into comment

        if not getattr(self, "_pending_comment", None):
            return
        c = self._pending_comment
        try:
            t.document.push_undo("Comment")
            t.annotations.add_sticky_note(
                page_index, (point.x(), point.y()),
                c["text"], author=c["author"])
            t.viewer.canvas.invalidate_page(page_index)
            t._refresh_right_sidebar()
            self.status_msg.setText(
                f"Comment added on page {page_index + 1} (unsaved).")
            self._refresh_undo_state()
        except Exception as e:
            QMessageBox.critical(self, "Comment failed", str(e))

    # ===== Rich media =====
    def action_media(self):
        from ui.pdf_viewer import TOOL_LINK, TOOL_NONE
        from ui.dialogs import MediaDialog
        t = self.current_tab()
        if not t or not t.document:
            self._set_tool_btn("media", False)
            QMessageBox.information(self, "Link / Media", "Open a PDF first.")
            return
        if not self._tool_btn_checked("media"):
            t.viewer.set_tool(TOOL_NONE)
            self._pending_media = None
            self.status_msg.setText("Link/media tool off.")
            return
        dlg = MediaDialog(t.document.page_count, self)
        if dlg.exec() != MediaDialog.Accepted:
            self._set_tool_btn("media", False)
            return
        s = dlg.settings()
        # validate
        if s["kind"] == "url" and not s.get("url"):
            QMessageBox.warning(self, "Link", "Enter a URL first.")
            self._set_tool_btn("media", False)
            return
        if s["kind"] in ("attachment", "media") and not s.get("path"):
            QMessageBox.warning(self, "Media", "Pick a file first.")
            self._set_tool_btn("media", False)
            return
        self._pending_media = s
        t.tools_panel.uncheck_all_except("media")
        self._set_tool_btn("media", True)
        # attachment uses click-to-place (paperclip icon), others use drag-rect
        if s["kind"] == "attachment":
            from ui.pdf_viewer import TOOL_COMMENT  # reuse click-to-place
            t.viewer.set_tool(TOOL_COMMENT)
            # use a separate flag so comment handler skips
            self._media_via_comment = True
            self.status_msg.setText("Click where to drop the paperclip icon.")
        else:
            t.viewer.set_tool(TOOL_LINK)
            self._media_via_comment = False
            self.status_msg.setText("Drag a rectangle for the clickable area.")

    def _on_link_placement(self, page_index, rect):
        """Drag-rect placement for URL link / internal link / media pointer."""
        t = self.current_tab()
        if not t or not t.media or not getattr(self, "_pending_media", None):
            return
        s = self._pending_media
        r = (rect.x(), rect.y(), rect.x() + rect.width(), rect.y() + rect.height())
        try:
            t.document.push_undo("Link")
            if s["kind"] == "url":
                t.media.add_url_link(page_index, r, s["url"])
                msg = f"Linked rectangle to {s['url']} on page {page_index + 1}"
            elif s["kind"] == "internal":
                t.media.add_internal_link(page_index, r, s["target_page"])
                msg = f"Jump to page {s['target_page'] + 1} on page {page_index + 1}"
            elif s["kind"] == "media":
                t.media.add_media_pointer(page_index, r, s["path"], s["label"])
                msg = f"Media added on page {page_index + 1}"
            else:
                return
            t.viewer.canvas.invalidate_page(page_index)
            self.status_msg.setText(msg + " (unsaved)")
            self._refresh_undo_state()
        except Exception as e:
            QMessageBox.critical(self, "Failed", str(e))

    # ===== Send for review =====
    def action_send_review(self):
        from ui.dialogs import SendCommentsDialog
        t = self.current_tab()
        if not t or not t.document:
            QMessageBox.information(self, "Send for review", "Open a PDF first.")
            return
        comments = t.annotations.list_annotations() if t.annotations else []
        # filter to text-bearing annotations
        comments = [c for c in comments
                    if c.get("type") in ("Text", "FreeText", "Highlight",
                                         "Underline", "StrikeOut")
                    or (c.get("content"))]
        dlg = SendCommentsDialog(comments, t.path, self)
        dlg.exec()

    # ===== Line-level tools (highlight / comment / edit a single line) =====
    def _activate_line_tool(self, tool_const: str, panel_btn_name: str,
                            status_msg: str):
        """Helper: turn on a line tool, off all the others."""
        t = self.current_tab()
        if not t or not t.document:
            t and t.tools_panel.uncheck_all_except()
            QMessageBox.information(self, "Line tool", "Open a PDF first.")
            return False
        btn = t.tools_panel.get(panel_btn_name)
        if btn and not btn.isChecked():
            # button was toggled off
            t.viewer.set_tool("none")
            self.status_msg.setText("Line tool off.")
            return False
        # untoggle every other panel button
        t.tools_panel.uncheck_all_except(panel_btn_name)
        # also clear top-toolbar legacy buttons
        for b in (getattr(self.toolbar, "highlight_btn", None),
                  getattr(self.toolbar, "sign_btn", None)):
            if b: b.setChecked(False)
        t.viewer.set_tool(tool_const)
        self.status_msg.setText(status_msg)
        return True

    def action_line_highlight_toggle(self):
        from ui.pdf_viewer import TOOL_LINE_HIGHLIGHT
        self._activate_line_tool(
            TOOL_LINE_HIGHLIGHT, "line_highlight",
            "Click a line of text to highlight it. Press the button again to stop.")

    def action_line_comment_toggle(self):
        from ui.pdf_viewer import TOOL_LINE_COMMENT
        self._activate_line_tool(
            TOOL_LINE_COMMENT, "line_comment",
            "Click a line of text to comment on it.")

    def _on_ink_drawn(self, page_index, points):
        """Free-hand stroke finished — save it as an ink annotation."""
        t = self.current_tab()
        if not t or not t.document:
            return
        try:
            t.document.push_undo("Free-hand draw")
            color = getattr(self, "_annot_color", "#E53935")
            # ink expects a list of strokes; each stroke is a list of points
            t.annotations.add_ink(page_index, [points], color=color, width=2)
            t.viewer.canvas.invalidate_page(page_index)
            t.viewer.canvas.update()
            self.status_msg.setText("Free-hand drawing added (unsaved).")
        except Exception as e:
            QMessageBox.critical(self, "Draw failed", str(e))

    def _on_shape_drawn(self, page_index, kind, rect):
        """Draw a rectangle or circle annotation from a dragged box."""
        t = self.current_tab()
        if not t or not t.document:
            return
        try:
            color = getattr(t, "_annot_color", "#E53935")
            r = (rect.x(), rect.y(), rect.x() + rect.width(),
                 rect.y() + rect.height())
            if kind == "circle":
                t.document.push_undo("Circle")
                t.annotations.add_circle(page_index, r, color=color, width=2)
                self.status_msg.setText("Circle added (unsaved).")
            else:
                t.document.push_undo("Rectangle")
                t.annotations.add_rectangle(page_index, r, color=color, width=2)
                self.status_msg.setText("Rectangle added (unsaved).")
            t.viewer.canvas.invalidate_page(page_index)
            t.viewer.canvas.update()
            t._refresh_right_sidebar()
            t.document.mark_dirty()
        except Exception as e:
            QMessageBox.critical(self, "Shape failed", str(e))

    def _on_xmark_placed(self, page_index, point):
        """Place a mark (X / check / dot) where the user clicked."""
        t = self.current_tab()
        if not t or not t.document:
            return
        try:
            kind = getattr(t, "_mark_kind", "xmark")
            color = getattr(t, "_annot_color", "#E53935")
            x, y = point.x(), point.y()
            s = 7
            if kind == "check":
                t.document.push_undo("Check mark")
                # a check mark: short down-stroke + long up-stroke
                t.annotations.add_line(page_index, (x - s, y), (x - 1, y + s),
                                       color=color, width=2)
                t.annotations.add_line(page_index, (x - 1, y + s), (x + s, y - s),
                                       color=color, width=2)
                self.status_msg.setText("Check mark added (unsaved).")
            elif kind == "dot":
                t.document.push_undo("Dot")
                t.annotations.add_circle(page_index,
                                         (x - 3, y - 3, x + 3, y + 3),
                                         color=color, width=4)
                self.status_msg.setText("Dot added (unsaved).")
            else:
                t.document.push_undo("X mark")
                t.annotations.add_line(page_index, (x - s, y - s), (x + s, y + s),
                                       color=color, width=2)
                t.annotations.add_line(page_index, (x - s, y + s), (x + s, y - s),
                                       color=color, width=2)
                self.status_msg.setText("X mark added (unsaved).")
            t.viewer.canvas.invalidate_page(page_index)
            t.viewer.canvas.update()
        except Exception as e:
            QMessageBox.critical(self, "Mark failed", str(e))

    def action_fill_form_toggle(self):
        from ui.pdf_viewer import TOOL_FILL_FORM
        t = self.current_tab()
        if not t or not t.document:
            return
        if t.viewer.canvas.current_tool() == TOOL_FILL_FORM:
            t.viewer.canvas.set_tool("none")
            self.status_msg.setText("Fill form: off")
        else:
            t.viewer.canvas.set_tool(TOOL_FILL_FORM)
            self.status_msg.setText(
                "Fill form ON — click a field and type to fill it.")

    def _on_form_field_clicked(self, page_index, rect, name, ftype):
        """User clicked a form field while in Fill Form mode. Let them type a
        value (or toggle a checkbox) and write it into the real field."""
        from core.form_manager import FormManager
        t = self.current_tab()
        if not t or not t.document:
            return
        fm = FormManager(t.document)
        try:
            if ftype == "checkbox":
                # toggle the checkbox
                fields = {f["name"]: f for f in fm.list_fields()}
                cur = fields.get(name, {}).get("value")
                newval = not (cur in (True, "Yes", "On", "1", 1))
                fm.set_field_value(page_index, name, newval)
                self.status_msg.setText(f"Checkbox {'checked' if newval else 'unchecked'}.")
            else:
                from PySide6.QtWidgets import QInputDialog
                # show current value as the starting text
                fields = {f["name"]: f for f in fm.list_fields()}
                cur = fields.get(name, {}).get("value") or ""
                text, ok = QInputDialog.getText(
                    self, "Fill field",
                    f"Enter value for this field:", text=str(cur))
                if not ok:
                    return
                fm.set_field_value(page_index, name, text)
                self.status_msg.setText("Field filled (unsaved).")
            t.viewer.canvas.invalidate_page(page_index)
            t.viewer.canvas.update()
        except Exception as e:
            QMessageBox.critical(self, "Fill form failed", str(e))

    def action_edit_mode_toggle(self):
        from ui.pdf_viewer import TOOL_EDIT_MODE
        self._activate_line_tool(
            TOOL_EDIT_MODE, "edit_mode",
            "Edit mode ON — click any line of text and type to change it. "
            "Press the button again to finish.")

    def action_select_text_toggle(self):
        from ui.pdf_viewer import TOOL_SELECT_TEXT
        t = self.current_tab()
        if not t or not t.document:
            return
        # turning on normal copy mode cancels 'save notes' mode so plain
        # copying always works as expected
        self._save_note_on_select = False
        # toggle the tool on the canvas
        if t.viewer.canvas.current_tool() == TOOL_SELECT_TEXT:
            t.viewer.canvas.set_tool("none")
            self.status_msg.setText("Select text: off")
        else:
            t.viewer.canvas.set_tool(TOOL_SELECT_TEXT)
            self.status_msg.setText(
                "Select text ON — drag a box over text to copy it.")

    def _on_text_copied(self, n_chars):
        if n_chars > 0:
            self.status_msg.setText(
                f"\u2713 Copied {n_chars} characters to clipboard "
                "(paste with Ctrl+V).")
            self._show_copy_toast(f"\u2713  Copied {n_chars} characters")
        else:
            self.status_msg.setText(
                "No text found there. Drag the box right over the words "
                "you want to copy.")
            self._show_copy_toast("No text in that area", ok=False)

    def _show_copy_toast(self, message, ok=True):
        """A brief floating confirmation over the PDF so the user clearly
        knows whether the copy worked (the status bar is easy to miss)."""
        t = self.current_tab()
        if not t:
            return
        from PySide6.QtWidgets import QLabel
        from PySide6.QtCore import QTimer, Qt as _Qt
        lbl = QLabel(message, t.viewer)
        bg = "#2E7D32" if ok else "#C62828"
        lbl.setStyleSheet(
            f"QLabel {{ background: {bg}; color: white; padding: 10px 18px;"
            f" border-radius: 18px; font-size: 14px; font-weight: 600; }}")
        lbl.adjustSize()
        vp = t.viewer
        lbl.move((vp.width() - lbl.width()) // 2, 24)
        lbl.show()
        lbl.raise_()
        QTimer.singleShot(1500, lbl.deleteLater)

    def _on_text_selected_for_note(self, text, page_index):
        """Selecting text can save it as a note OR as a reference, depending
        on which 'collect' mode is on. Otherwise it just copies."""
        t = self.current_tab()
        if not t or not t.document:
            return
        src = os.path.basename(t.path) if t.path else ""

        # Reference-collecting mode: save the selected text as a reference
        if getattr(self, "_save_ref_on_select", False):
            added = self.ref_collection.add(text, src)
            if added:
                self.status_msg.setText(
                    f"Reference collected ({len(self.ref_collection)} total). "
                    "Open Reference Collection to view.")
                if self._ref_panel is not None:
                    self._ref_panel.refresh()
            else:
                self.status_msg.setText("Reference already in your collection.")
            return

        # Notes-collecting mode: save the selected text as a note
        if not getattr(self, "_save_note_on_select", False):
            return
        title, author = self._doc_title_author(t)
        scroll = 0
        try:
            scroll = t.viewer.verticalScrollBar().value()
        except Exception:
            pass
        added = self.text_collection.add(
            snippet=text, paper_title=title, author=author,
            page=page_index + 1, source_file=src, reference="",
            scroll_pos=scroll)
        if added:
            self.status_msg.setText(
                f"Note saved ({len(self.text_collection)} total). "
                "Open Tools \u2192 Text/Notes Collection to review.")
            if self._notes_panel is not None:
                self._notes_panel.refresh()
        else:
            self.status_msg.setText("That snippet is already saved.")

    def _doc_title_author(self, tab):
        """Best-effort paper title + author from the PDF metadata."""
        title, author = "", ""
        try:
            md = tab.document.doc.metadata or {}
            title = (md.get("title") or "").strip()
            author = (md.get("author") or "").strip()
        except Exception:
            pass
        if not title and tab.path:
            title = os.path.splitext(os.path.basename(tab.path))[0]
        return title, author

    def action_save_notes_toggle(self):
        """Turn 'Save selected text as notes' mode on/off."""
        from ui.pdf_viewer import TOOL_SELECT_TEXT
        t = self.current_tab()
        if not t or not t.document:
            self._sync_collect_buttons()
            QMessageBox.information(self, "Text Collection", "Open a PDF first.")
            return
        self._save_ref_on_select = False  # the two modes are exclusive
        self._save_note_on_select = not getattr(self, "_save_note_on_select", False)
        if self._save_note_on_select:
            t.viewer.canvas.set_tool(TOOL_SELECT_TEXT)
            self.status_msg.setText(
                "Save-notes mode ON \u2014 drag over text to save it as a note "
                "with its page and source. Toggle off when done.")
        else:
            t.viewer.canvas.set_tool("none")
            self.status_msg.setText("Save-notes mode off.")
        self._sync_collect_buttons()

    def action_mark_reference_toggle(self):
        """Turn 'Mark & collect references' mode on/off. Drag over a reference
        in the bibliography to save it to your Reference Collection."""
        from ui.pdf_viewer import TOOL_SELECT_TEXT
        t = self.current_tab()
        if not t or not t.document:
            self._sync_collect_buttons()
            QMessageBox.information(self, "Reference Collection", "Open a PDF first.")
            return
        self._save_note_on_select = False  # exclusive with notes mode
        self._save_ref_on_select = not getattr(self, "_save_ref_on_select", False)
        if self._save_ref_on_select:
            t.viewer.canvas.set_tool(TOOL_SELECT_TEXT)
            self.status_msg.setText(
                "Mark-reference mode ON \u2014 drag over a reference in the "
                "bibliography to collect it. Toggle off when done.")
        else:
            t.viewer.canvas.set_tool("none")
            self.status_msg.setText("Mark-reference mode off.")
        self._sync_collect_buttons()

    def _sync_collect_buttons(self):
        """Reflect the current collect modes on the toolbar toggle buttons."""
        tb = getattr(self, "toolbar", None)
        if tb and hasattr(tb, "set_collect_states"):
            tb.set_collect_states(
                getattr(self, "_save_ref_on_select", False),
                getattr(self, "_save_note_on_select", False),
            )

    def open_notes_panel(self):
        from ui.notes_panel import NotesPanel
        if self._notes_panel is None:
            self._notes_panel = NotesPanel(self.text_collection, self)
            self._notes_panel.jump_requested.connect(self._jump_to_note)
        self._notes_panel.refresh()
        self._notes_panel.show()
        self._notes_panel.raise_()
        self._notes_panel.activateWindow()

    def open_library_panel(self):
        from ui.library_panel import LibraryPanel
        if self._library_panel is None:
            self._library_panel = LibraryPanel(self.library, self)
            self._library_panel.open_paper_requested.connect(self._open_from_library)
        self._library_panel.refresh_all()
        self._library_panel.show()
        self._library_panel.raise_()
        self._library_panel.activateWindow()

    def _open_from_library(self, path):
        try:
            self.open_pdf(path)
            self.library.mark_opened(path)
        except Exception as e:
            QMessageBox.critical(self, "Open", str(e))

    def action_add_current_to_library(self):
        """Add the currently open PDF to the research library."""
        t = self.current_tab()
        if not t or not t.path:
            QMessageBox.information(self, "Library", "Open a PDF first.")
            return
        new = self.library.add_paper(t.path)
        QMessageBox.information(
            self, "Library",
            ("Added to your library." if new else "Already in your library.")
            + f"\n\nTotal: {len(self.library.all_papers())} papers.")
        if self._library_panel is not None:
            self._library_panel.refresh_all()

    def _jump_to_note(self, entry):
        """One-click jump back to where a saved snippet came from."""
        src = entry.get("Source file", "")
        page = entry.get("Page", 0)
        scroll = entry.get("_scroll", 0)
        # find the matching open tab (by source file name)
        target_tab = None
        for i in range(self.tab_widget.count()):
            tb = self.tab_widget.widget(i)
            if tb and tb.path and os.path.basename(tb.path) == src:
                target_tab = tb
                self.tab_widget.setCurrentIndex(i)
                break
        if target_tab is None:
            QMessageBox.information(
                self, "Jump to source",
                f"Open '{src}' first, then jump to the note "
                f"(page {page}).")
            return
        try:
            if scroll:
                target_tab.viewer.verticalScrollBar().setValue(int(scroll))
            elif page:
                target_tab.viewer.goto_page(int(page) - 1)
        except Exception:
            pass

    def _on_reference_found(self, ref_text):
        """A citation was clicked; collect the reference it points to."""
        if not getattr(self, "_collect_refs_on", True):
            return
        t = self.current_tab()
        src = os.path.basename(t.path) if (t and t.path) else ""
        added = self.ref_collection.add(ref_text, src)
        if added:
            self.status_msg.setText(
                f"Reference collected ({len(self.ref_collection)} total). "
                "Open Tools \u2192 Reference Collection to view.")
            if self._ref_panel is not None:
                self._ref_panel.refresh()
        else:
            self.status_msg.setText("Reference already in your collection.")

    def open_reference_panel(self):
        """Open (or focus) the reference collection window."""
        from ui.reference_panel import ReferencePanel
        if self._ref_panel is None:
            self._ref_panel = ReferencePanel(self.ref_collection, self)
            self._ref_panel.collection_changed.connect(
                lambda: self.status_msg.setText(
                    f"{len(self.ref_collection)} references collected."))
        self._ref_panel.refresh()
        self._ref_panel.show()
        self._ref_panel.raise_()
        self._ref_panel.activateWindow()

    def action_collect_references_now(self):
        """Extract ALL references from the current PDF into the collection."""
        t = self.current_tab()
        if not t or not t.document:
            QMessageBox.information(self, "Reference Collection",
                                    "Open a PDF first.")
            return
        from core.citation_extractor import extract_reference_list
        try:
            refs = extract_reference_list(t.document.doc)
        except Exception as e:
            QMessageBox.critical(self, "Reference Collection", str(e))
            return
        if not refs:
            QMessageBox.information(
                self, "Reference Collection",
                "No reference list was detected in this PDF.")
            return
        src = os.path.basename(t.path) if t.path else ""
        n = self.ref_collection.add_many(refs, src)
        QMessageBox.information(
            self, "Reference Collection",
            f"Added {n} new reference(s). "
            f"Total collected: {len(self.ref_collection)}.")
        self.open_reference_panel()

    def _on_inline_edit_committed(self, page_index, line_rect, new_text):
        """Called when the user finishes typing in the inline editor on the
        page. Applies the edit in memory (keeps original font), no popup."""
        t = self.current_tab()
        if not t or not t.document:
            return
        try:
            t.document.push_undo("edit text")
            t.document.edit_line_in_memory(
                page_index,
                (line_rect.x(), line_rect.y(),
                 line_rect.x() + line_rect.width(),
                 line_rect.y() + line_rect.height()),
                new_text, color_hex="#000000")
            t.viewer.canvas.invalidate_page(page_index)
            t.viewer.canvas.update()
            self.status_msg.setText(
                "Edited (unsaved). Keep clicking lines, or press the button "
                "again to finish.")
        except Exception as e:
            QMessageBox.critical(self, "Edit failed", str(e))

    def action_line_edit_toggle(self):
        from ui.pdf_viewer import TOOL_LINE_EDIT
        self._activate_line_tool(
            TOOL_LINE_EDIT, "line_edit",
            "Click a line of text to edit it.")

    def action_line_color_toggle(self):
        from ui.pdf_viewer import TOOL_LINE_COLOR
        self._activate_line_tool(
            TOOL_LINE_COLOR, "line_color",
            "Click a line of text to change its color. "
            "Press the button again to stop.")

    def _on_line_clicked(self, page_index, line_rect, line_text):
        """Dispatch a line click to the right line tool."""
        from ui.pdf_viewer import (TOOL_LINE_HIGHLIGHT, TOOL_LINE_COMMENT,
                                   TOOL_LINE_EDIT, TOOL_LINE_COLOR)
        t = self.current_tab()
        if not t or not t.document:
            return
        tool = t.viewer.current_tool()
        if tool == TOOL_LINE_HIGHLIGHT:
            self._do_line_highlight(t, page_index, line_rect)
        elif tool == TOOL_LINE_COMMENT:
            self._do_line_comment(t, page_index, line_rect, line_text)
        elif tool == TOOL_LINE_EDIT:
            self._do_line_edit(t, page_index, line_rect, line_text)
        elif tool == TOOL_LINE_COLOR:
            self._do_line_color(t, page_index, line_rect)

    def _do_line_color(self, t, page_index, line_rect):
        """Change the color of just the clicked line, keeping the same text.
        Edits in memory — only saved when the user saves/closes."""
        from PySide6.QtWidgets import QColorDialog
        try:
            col = QColorDialog.getColor(parent=self,
                                        title="Pick a color for this line")
            if not col.isValid():
                return
            color_hex = col.name()  # like "#RRGGBB"
            t.document.push_undo("color line")
            res = t.document.recolor_line_in_memory(
                page_index,
                (line_rect.x(), line_rect.y(),
                 line_rect.x() + line_rect.width(),
                 line_rect.y() + line_rect.height()),
                color_hex=color_hex)
            if not res.get("changed"):
                self.status_msg.setText("No text found on that line to color.")
                return
            t.viewer.canvas.invalidate_page(page_index)
            t.viewer.canvas.update()
            self.status_msg.setText(
                f"Line colored on page {page_index + 1} (unsaved). "
                "Click another line, or stop the tool.")
        except Exception as e:
            QMessageBox.critical(self, "Color line failed", str(e))

    def _do_line_highlight(self, t, page_index, line_rect):
        try:
            color = self.settings.highlight_color()
            rect_tuple = (line_rect.x(), line_rect.y(),
                          line_rect.x() + line_rect.width(),
                          line_rect.y() + line_rect.height())
            t.annotations.add_highlight(page_index, [rect_tuple], color=color)
            t.viewer.canvas.invalidate_page(page_index)
            t._refresh_right_sidebar()
            t.document.mark_dirty()
            self.status_msg.setText(
                f"Highlighted a line on page {page_index + 1} (unsaved). "
                "Click another line, or press the button to stop.")
        except Exception as e:
            QMessageBox.critical(self, "Highlight failed", str(e))

    def _do_line_comment(self, t, page_index, line_rect, line_text):
        from ui.dialogs import CommentDialog
        import getpass
        try:
            default_author = getpass.getuser()
        except Exception:
            default_author = ""
        dlg = CommentDialog(self, default_author)
        # Pre-fill with the line text as context
        preview = (line_text[:80] + "…") if len(line_text) > 80 else line_text
        dlg.text.setPlainText(f"Re: \"{preview}\"\n\n")
        # put cursor at end so user can just start typing
        from PySide6.QtGui import QTextCursor
        cur = dlg.text.textCursor()
        cur.movePosition(QTextCursor.MoveOperation.End)
        dlg.text.setTextCursor(cur)
        dlg.setWindowTitle(f"Comment on line (page {page_index + 1})")
        if dlg.exec() != CommentDialog.Accepted:
            return
        c = dlg.settings()
        if not c["text"]:
            return
        try:
            # Place the sticky note right at the start of the line
            t.annotations.add_sticky_note(
                page_index, (line_rect.x() + line_rect.width() + 6,
                             line_rect.y()),
                c["text"], author=c["author"])
            t.viewer.canvas.invalidate_page(page_index)
            t._refresh_right_sidebar()
            t.document.mark_dirty()
            self.status_msg.setText(
                f"Comment added to a line on page {page_index + 1} (unsaved).")
        except Exception as e:
            QMessageBox.critical(self, "Comment failed", str(e))

    def _do_line_edit(self, t, page_index, line_rect, line_text):
        from ui.dialogs import EditLineDialog
        from core.text_line_editor import edit_line_text

        # We need the line's font info — fetch it from the viewer cache.
        info = None
        try:
            t.viewer.canvas._ensure_lines_for(page_index)
            cache = t.viewer.canvas._line_cache.get(page_index, [])
            # find the cached line whose bbox is closest to the clicked one,
            # with a generous tolerance (strict matching often failed and left
            # us with no size info, which defaulted headings to 11pt).
            best = None
            best_d = 1e9
            for ln in cache:
                x0, y0, x1, y1 = ln["bbox"]
                d = abs(x0 - line_rect.x()) + abs(y0 - line_rect.y())
                if d < best_d:
                    best_d = d
                    best = ln
            if best is not None and best_d < 8:
                info = best
        except Exception:
            pass

        font_hint = info["font"] if info else ""
        # Only pass an explicit size if we actually found the line. Otherwise
        # pass None so edit_line_in_memory DETECTS the real size from the
        # document (this is what kept shrinking headings to body size).
        font_size = info["size"] if info else None

        # If the clicked line is part of a multi-line block (e.g. a heading
        # that wraps onto 2+ lines), edit the WHOLE block as one unit — erase
        # all of it and replace — so we don't leave leftover old text under
        # the new text. Use the block's bbox and the block's full text.
        edit_rect = line_rect
        prefill = line_text
        if info and info.get("is_multiline") and info.get("block_bbox"):
            from PySide6.QtCore import QRectF
            bx0, by0, bx1, by1 = info["block_bbox"]
            edit_rect = QRectF(bx0, by0, bx1 - bx0, by1 - by0)
            prefill = info.get("block_text", line_text)

        dlg = EditLineDialog(prefill, page_index, font_hint,
                             font_size or 11.0, self)
        if dlg.exec() != EditLineDialog.Accepted:
            return

        # Edit the line IN MEMORY — no save dialog. The change stays in the
        # open document and is only written when the user saves or closes.
        try:
            t.document.push_undo("edit line")
            t.document.edit_line_in_memory(
                page_index,
                (edit_rect.x(), edit_rect.y(),
                 edit_rect.x() + edit_rect.width(),
                 edit_rect.y() + edit_rect.height()),
                dlg.new_text(),
                font_size=font_size,   # None => detect real size from document
                font_hint=font_hint,
                color_hex=dlg.color_hex(),
            )
            # refresh the page so the change shows immediately
            t.viewer.canvas.invalidate_page(page_index)
            t.viewer.canvas.update()
            self.status_msg.setText(
                "Line edited. (Save when you close, or press Ctrl+S.)")
        except Exception as e:
            QMessageBox.critical(self, "Edit failed", str(e))

    # ===== Add text (click on page to drop) =====
    def action_add_text_toggle(self):
        from ui.pdf_viewer import TOOL_ADD_TEXT, TOOL_NONE
        from ui.dialogs import AddTextDialog
        t = self.current_tab()
        if not t or not t.document:
            self._set_tool_btn("add_text", False)
            QMessageBox.information(self, "Add text", "Open a PDF first.")
            return
        if not self._tool_btn_checked("add_text"):
            t.viewer.set_tool(TOOL_NONE)
            self._pending_text = None
            self.status_msg.setText("Add-text tool off.")
            return
        dlg = AddTextDialog(self)
        if dlg.exec() != AddTextDialog.Accepted:
            self._set_tool_btn("add_text", False)
            return
        cfg = dlg.settings()
        if not cfg["text"].strip():
            QMessageBox.warning(self, "Add text", "Type some text first.")
            self._set_tool_btn("add_text", False)
            return
        self._pending_text = cfg
        t.tools_panel.uncheck_all_except("add_text")
        self._set_tool_btn("add_text", True)
        t.viewer.set_tool(TOOL_ADD_TEXT)
        self.status_msg.setText(
            "Click anywhere on the page to place the text. "
            "Click Add Text again to stop.")

    def _on_text_placement(self, page_index, point):
        t = self.current_tab()
        if not t or not t.document:
            return
        if not getattr(self, "_pending_text", None):
            return
        cfg = self._pending_text
        try:
            from core.page_editor import add_text_to_page
            t.document.push_undo("Add text")
            add_text_to_page(
                t.document, page_index, (point.x(), point.y()),
                cfg["text"], font_size=cfg["size"], color_hex=cfg["color"],
                style=cfg["style"])
            t.viewer.canvas.invalidate_page(page_index)
            t.viewer.canvas.invalidate_line_cache(page_index)
            t._refresh_right_sidebar()
            self.status_msg.setText(
                f"Text added on page {page_index + 1} (unsaved).")
            self._refresh_undo_state()
        except Exception as e:
            QMessageBox.critical(self, "Add text failed", str(e))

    # ===== Insert image (drag a rect) =====
    def action_add_image_toggle(self):
        from ui.pdf_viewer import TOOL_ADD_IMAGE, TOOL_NONE
        t = self.current_tab()
        if not t or not t.document:
            self._set_tool_btn("add_image", False)
            QMessageBox.information(self, "Insert image", "Open a PDF first.")
            return
        if not self._tool_btn_checked("add_image"):
            t.viewer.set_tool(TOOL_NONE)
            self._pending_image_path = None
            self.status_msg.setText("Insert-image tool off.")
            return
        path, _ = QFileDialog.getOpenFileName(
            self, "Pick an image", "",
            "Images (*.png *.jpg *.jpeg *.bmp *.gif *.tiff *.webp)")
        if not path:
            self._set_tool_btn("add_image", False)
            return
        self._pending_image_path = path
        t.tools_panel.uncheck_all_except("add_image")
        self._set_tool_btn("add_image", True)
        t.viewer.set_tool(TOOL_ADD_IMAGE)
        self.status_msg.setText(
            "Drag a rectangle on the page where the image should go.")

    def _on_image_placement(self, page_index, rect):
        t = self.current_tab()
        if not t or not t.document or not getattr(self, "_pending_image_path", None):
            return
        try:
            from core.page_editor import insert_image_on_page
            t.document.push_undo("Insert image")
            insert_image_on_page(
                t.document, page_index,
                (rect.x(), rect.y(),
                 rect.x() + rect.width(), rect.y() + rect.height()),
                self._pending_image_path)
            t.viewer.canvas.invalidate_page(page_index)
            self.status_msg.setText(
                f"Image placed on page {page_index + 1} (unsaved).")
            self._refresh_undo_state()
        except Exception as e:
            QMessageBox.critical(self, "Insert image failed", str(e))

    # ===== Delete an edit (eraser tool) =====
    def action_delete_annot_toggle(self):
        from ui.pdf_viewer import TOOL_DELETE_ANNOT, TOOL_NONE
        t = self.current_tab()
        if not t or not t.document:
            self._set_tool_btn("delete_annot", False)
            QMessageBox.information(self, "Delete an Edit", "Open a PDF first.")
            return
        if not self._tool_btn_checked("delete_annot"):
            t.viewer.set_tool(TOOL_NONE)
            self.status_msg.setText("Eraser off.")
            return
        t.tools_panel.uncheck_all_except("delete_annot")
        self._set_tool_btn("delete_annot", True)
        t.viewer.set_tool(TOOL_DELETE_ANNOT)
        self.status_msg.setText(
            "Click an edit (highlight, comment, stamp, added text, "
            "signature) to remove it. Click the tool again to stop.")

    def _on_open_url(self, url: str):
        """A link in the PDF was clicked. Confirm, then open in the browser."""
        if not url:
            return
        from PySide6.QtWidgets import QMessageBox
        r = QMessageBox.question(
            self, "Open link",
            f"This link points to:\n\n{url}\n\nOpen it in your web browser?",
            QMessageBox.Yes | QMessageBox.No)
        if r == QMessageBox.Yes:
            from PySide6.QtGui import QDesktopServices
            from PySide6.QtCore import QUrl
            QDesktopServices.openUrl(QUrl(url))

    def _on_annot_delete(self, page_index, point):
        t = self.current_tab()
        if not t or not t.document:
            return
        # snapshot first so even the deletion itself can be undone
        t.document.push_undo("Delete edit")
        label = t.document.delete_annot_at(page_index, point.x(), point.y())
        if label:
            t.viewer.canvas.invalidate_page(page_index)
            t.viewer.canvas.invalidate_line_cache(page_index)
            t._refresh_right_sidebar()
            self._refresh_undo_state()
            self.status_msg.setText(f"Removed {label} (unsaved).")
        else:
            # nothing was there — discard the snapshot we just made
            if t.document.can_undo():
                t.document._undo_stack.pop()
                t.document._undo_labels.pop()
            self.status_msg.setText(
                "Nothing to delete there. Tip: inserted images aren't "
                "annotations — use Undo (Ctrl+Z) for those.")

    # ===== Undo =====
    def action_undo(self):
        t = self.current_tab()
        if not t or not t.document:
            return
        if not t.document.can_undo():
            self.status_msg.setText("Nothing to undo.")
            return
        label = t.document.last_undo_label()
        if t.document.undo():
            # the underlying fitz doc was replaced — rebuild views
            t.viewer.set_document(t.document)
            t.left_side.populate(t.document)
            t._refresh_right_sidebar()
            cur = min(t.viewer.canvas.current_page(),
                      t.document.page_count - 1)
            t.viewer.goto_page(max(0, cur))
            self._refresh_undo_state()
            self.status_msg.setText(f"Undone: {label}.")
        else:
            self.status_msg.setText("Could not undo.")

    def _refresh_undo_state(self):
        """Enable/label the Undo action based on the current tab."""
        t = self.current_tab()
        can = bool(t and t.document and t.document.can_undo())
        if hasattr(self, "a_undo"):
            self.a_undo.setEnabled(can)
            if can:
                self.a_undo.setText(f"Undo {t.document.last_undo_label()}")
            else:
                self.a_undo.setText("Undo")

    # ===== Header & Footer =====
    def action_header_footer(self):
        from ui.dialogs import HeaderFooterDialog
        from core.page_editor import add_header_footer
        t = self.current_tab()
        if not t or not t.document:
            QMessageBox.information(self, "Header & Footer", "Open a PDF first.")
            return
        dlg = HeaderFooterDialog(t.document.page_count, self)
        if dlg.exec() != HeaderFooterDialog.Accepted:
            return
        s = dlg.settings()
        # At least one slot must have text
        if not any(s[k] for k in ("header_left", "header_center", "header_right",
                                   "footer_left", "footer_center", "footer_right")):
            QMessageBox.warning(self, "Header & Footer",
                                "Enter some text in at least one slot.")
            return
        try:
            import os
            t.document.push_undo("Header & footer")
            count = add_header_footer(
                t.document,
                header_left=s["header_left"],
                header_center=s["header_center"],
                header_right=s["header_right"],
                footer_left=s["footer_left"],
                footer_center=s["footer_center"],
                footer_right=s["footer_right"],
                font_size=s["font_size"],
                color_hex=s["color_hex"],
                style=s["style"],
                page_range=s["page_range"],
                filename=os.path.basename(t.path) if t.path else "",
            )
            t.viewer.canvas._page_pixmaps.clear()
            t.viewer.canvas.invalidate_line_cache()
            t.viewer.canvas.update()
            self.status_msg.setText(
                f"Header / footer added to {count} page(s) (unsaved).")
            self._refresh_undo_state()
        except Exception as e:
            QMessageBox.critical(self, "Header & Footer failed", str(e))

    # ===== Insert blank page =====
    def action_insert_blank_page(self):
        from core.page_editor import insert_blank_page
        t = self.current_tab()
        if not t or not t.document:
            QMessageBox.information(self, "Insert page", "Open a PDF first.")
            return
        cur = t.viewer.canvas.current_page()
        try:
            t.document.push_undo("Insert page")
            new_idx = insert_blank_page(t.document, cur)
            # rebuild thumbnails / outline since page count changed
            t.left_side.populate(t.document)
            t.viewer.set_document(t.document)
            t.viewer.goto_page(new_idx)
            self.status_msg.setText(
                f"Blank page inserted (now page {new_idx + 1}, unsaved).")
            self._refresh_undo_state()
        except Exception as e:
            QMessageBox.critical(self, "Insert failed", str(e))

    # ===== Delete current page =====
    def action_delete_current_page(self):
        t = self.current_tab()
        if not t or not t.document:
            QMessageBox.information(self, "Delete page", "Open a PDF first.")
            return
        if t.document.page_count <= 1:
            QMessageBox.warning(self, "Delete page",
                                "Cannot delete the last remaining page.")
            return
        cur = t.viewer.canvas.current_page()
        r = QMessageBox.question(
            self, "Delete page",
            f"Delete page {cur + 1}? This cannot be undone "
            "until you save (you'll still be able to close without saving).",
            QMessageBox.Yes | QMessageBox.No)
        if r != QMessageBox.Yes:
            return
        try:
            t.document.push_undo("Delete page")
            t.document.delete_page(cur)
            t.left_side.populate(t.document)
            t.viewer.set_document(t.document)
            target = min(cur, t.document.page_count - 1)
            t.viewer.goto_page(target)
            self.status_msg.setText(f"Deleted page {cur + 1} (unsaved).")
            self._refresh_undo_state()
        except Exception as e:
            QMessageBox.critical(self, "Delete failed", str(e))

    # ===== Rotate current page =====
    def _rotate_current_page(self, degrees: int):
        t = self.current_tab()
        if not t or not t.document:
            QMessageBox.information(self, "Rotate page", "Open a PDF first.")
            return
        cur = t.viewer.canvas.current_page()
        try:
            t.document.push_undo("Rotate page")
            t.document.rotate_page(cur, degrees)
            t.viewer.canvas.invalidate_page(cur)
            t.viewer.canvas.invalidate_line_cache(cur)
            t.left_side.populate(t.document)
            self.status_msg.setText(
                f"Rotated page {cur + 1} by {degrees}° (unsaved).")
            self._refresh_undo_state()
        except Exception as e:
            QMessageBox.critical(self, "Rotate failed", str(e))

    def action_rotate_page_left(self):
        self._rotate_current_page(-90)

    def action_rotate_page_right(self):
        self._rotate_current_page(90)

    # ---- settings ----
    def _on_toolbar_language_changed(self, code):
        """User picked a language from the top-bar selector."""
        from utils.i18n import set_language, current_language
        if not code or code == current_language():
            return
        self.settings.set_ui_language(code)
        set_language(code)
        # Rebuild the menus right away so the change is visible immediately.
        try:
            self.menuBar().clear()
            self._build_menus()
        except Exception:
            pass
        QMessageBox.information(
            self, tr("Language changed"),
            tr("The interface language will fully apply after you "
               "restart the app."))

    def action_settings(self):
        from utils.i18n import current_language, set_language
        lang_before = self.settings.ui_language()
        dlg = SettingsDialog(self.settings, self)
        if dlg.exec() == SettingsDialog.Accepted:
            dlg.apply()
            self._apply_theme()
            self._configure_autosave()
            # Apply new render quality to every open tab right away
            new_dpi = self.settings.render_dpi()
            for i in range(self.tab_widget.count()):
                tab = self.tab_widget.widget(i)
                if hasattr(tab, "viewer") and tab.viewer:
                    tab.viewer.set_render_dpi(new_dpi)
            # Interface language changed? Rebuild the menus live and tell the
            # user a restart will refresh anything still in the old language.
            lang_after = self.settings.ui_language()
            if lang_after != lang_before:
                set_language(lang_after)
                try:
                    self.menuBar().clear()
                    self._build_menus()
                except Exception:
                    pass
                QMessageBox.information(
                    self, tr("Language changed"),
                    tr("The interface language will fully apply after you "
                       "restart the app."))

    # ---- about ----
    def action_check_updates(self, manual=False):
        """Check GitHub for a newer version.

        manual=True means the user clicked Help > Check for updates, so we
        also tell them when they're already up to date. On the automatic
        startup check we only speak up if there IS an update.
        """
        try:
            from utils.updater import check_for_update
            from PySide6.QtGui import QDesktopServices
            from PySide6.QtCore import QUrl
        except Exception:
            if manual:
                QMessageBox.information(self, "Check for updates",
                                        "Update check is not available.")
            return

        result = check_for_update()
        if result is None:
            if manual:
                QMessageBox.information(
                    self, "Check for updates",
                    "Could not check right now.\nPlease make sure you have "
                    "an internet connection and try again.")
            return

        if result["update"]:
            box = QMessageBox(self)
            box.setIcon(QMessageBox.Information)
            box.setWindowTitle("Update available")
            box.setText(
                f"A new version of {APP_NAME} is available.\n\n"
                f"You have: {result['current']}\n"
                f"Latest:   {result['latest']}\n\n"
                "Download and install it now?")
            box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
            box.button(QMessageBox.Yes).setText("Download && Install")
            box.button(QMessageBox.No).setText("Later")
            if box.exec() == QMessageBox.Yes:
                self._download_and_install_update(result)
        elif manual:
            QMessageBox.information(
                self, "Check for updates",
                f"You are using the latest version ({result['current']}).")

    def _download_and_install_update(self, result):
        """Launch the SEPARATE updater process, then close this app.

        The updater runs on its own (while the app is closed, so files aren't
        locked), downloads the new version, installs it over this one, and
        restarts the app. This is the safe way to self-update.
        """
        from PySide6.QtGui import QDesktopServices
        from PySide6.QtCore import QUrl
        import os, sys, subprocess

        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        updater = os.path.join(base, "updater_runner.py")
        main_py = os.path.join(base, "main.py")
        python_exe = sys.executable  # the python/pythonw running us
        # The updater should run with the CONSOLE python (python.exe), not the
        # windowless pythonw.exe, so it can actually run and show progress.
        if os.name == "nt" and python_exe.lower().endswith("pythonw.exe"):
            cand = python_exe[:-len("pythonw.exe")] + "python.exe"
            if os.path.exists(cand):
                python_exe = cand

        if not os.path.exists(updater):
            # no updater script — fall back to opening the download page
            QDesktopServices.openUrl(QUrl(result["url"]))
            return

        # tell the user what's about to happen
        QMessageBox.information(
            self, "Updating",
            f"{APP_NAME} will now close and update itself to version "
            f"{result['latest']}.\n\n"
            "It will reopen automatically when the update is done. "
            "Please wait a moment.")

        try:
            # start the updater as an independent process so it keeps running
            # after we exit
            kwargs = {}
            if os.name == "nt":
                # CREATE_NEW_CONSOLE so the updater shows its own window with
                # progress, and survives this app closing.
                kwargs["creationflags"] = 0x00000010  # CREATE_NEW_CONSOLE
            # relaunch with pythonw if available so the restarted app has no console
            relaunch_exe = sys.executable
            subprocess.Popen([python_exe, updater, base, relaunch_exe, main_py],
                             **kwargs)
        except Exception as e:
            QMessageBox.warning(
                self, "Update failed to start",
                f"Could not start the updater: {e}\n\n"
                "Opening the download page instead.")
            QDesktopServices.openUrl(QUrl(result["url"]))
            return

        # close the app so the updater can replace files
        QApplication.quit()

    def action_about(self):
        QMessageBox.about(
            self, f"About {APP_NAME}",
            f"<h2>{APP_NAME}</h2>"
            f"<p><b>Version:</b> {APP_VERSION}</p>"
            f"<p><b>Author:</b> {APP_AUTHOR}</p>"
            f"<p><b>License:</b> {APP_LICENSE} — free and open source.<br>"
            f"You may use, copy, modify, and distribute this software freely. "
            f"See the LICENSE file for the full text.</p>"
            f"<p>An open PDF studio built with Python, PySide6, "
            f"PyMuPDF, pypdf, Pillow, and Tesseract.</p>"
            f"<p>© 2026 {APP_AUTHOR}. The software is provided \"as is\", "
            f"without warranty of any kind.</p>"
        )

    # ---- recent files ----
    def _rebuild_recent_menu(self):
        self.recent_menu.clear()
        recents = self.settings.recent_files()
        if not recents:
            empty = QAction("No recent files", self); empty.setEnabled(False)
            self.recent_menu.addAction(empty)
            return
        for path in recents:
            a = QAction(os.path.basename(path), self)
            a.setToolTip(path)
            a.triggered.connect(lambda _, p=path: self.open_pdf(p))
            self.recent_menu.addAction(a)
        self.recent_menu.addSeparator()
        clear = QAction("Clear", self); clear.triggered.connect(self._clear_recents)
        self.recent_menu.addAction(clear)

    def _clear_recents(self):
        self.settings.clear_recent_files()
        self._rebuild_recent_menu()

    # ---- autosave ----
    def _configure_autosave(self):
        if self.settings.autosave_enabled():
            interval = max(10, self.settings.autosave_interval())
            self._autosave_timer.start(interval * 1000)
        else:
            self._autosave_timer.stop()

    def _on_autosave(self):
        t = self.current_tab()
        if not t or not t.document or not t.path:
            return
        if not t.document.dirty:
            return
        try:
            # Save to .autosave sibling so we don't surprise the user
            tmp = t.path + ".autosave"
            t.document.save(tmp)
            self.status_msg.setText(f"Autosaved at {datetime.now().strftime('%H:%M:%S')}")
        except Exception:
            pass

    # ---- worker management ----
    def _run_worker(self, worker, label: str, on_done):
        self._worker = worker
        self._progress = QProgressBar()
        self._progress.setRange(0, 100)
        self._progress.setFormat(f"{label} %p%")
        self.statusBar().addPermanentWidget(self._progress)
        self.status_msg.setText(label)

        def cleanup():
            try:
                self.statusBar().removeWidget(self._progress)
            except Exception:
                pass
            self._progress = None
            self._worker = None

        worker.progress.connect(self._progress.setValue)
        worker.message.connect(self.status_msg.setText)
        worker.failed.connect(lambda msg: (QMessageBox.critical(self, "Failed", msg), cleanup()))
        worker.finished_ok.connect(lambda result: (on_done(result), cleanup()))
        worker.start()

    # ---- drag and drop ----
    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if path.lower().endswith(".pdf"):
                self.open_pdf(path)

    # ---- close ----
    def closeEvent(self, event):
        # check for unsaved tabs
        for i in range(self.tab_widget.count()):
            w = self.tab_widget.widget(i)
            if isinstance(w, PDFTab) and w.document and w.document.dirty:
                ret = QMessageBox.question(
                    self, "Unsaved changes",
                    f"'{w.document.file_name()}' has unsaved changes. Save before closing?",
                    QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel)
                if ret == QMessageBox.Cancel:
                    event.ignore()
                    return
                if ret == QMessageBox.Save:
                    try:
                        w.save()
                    except Exception:
                        pass
        # save geometry
        self.settings.save_geometry(self.saveGeometry())
        # close docs
        for i in range(self.tab_widget.count()):
            w = self.tab_widget.widget(i)
            if isinstance(w, PDFTab):
                w.close_document()
        event.accept()
