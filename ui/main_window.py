"""Main application window.

Hosts: menu, toolbar, tab widget (for multiple PDFs), left sidebar
(thumbnails / outline), right sidebar (comments / properties), and
the central PDF viewer for the active tab.
"""

from PySide6.QtWidgets import (
    QMainWindow, QTabWidget, QSplitter, QFileDialog, QMessageBox,
    QDockWidget, QStatusBar, QLabel, QInputDialog, QMenuBar, QMenu,
    QApplication, QProgressBar, QWidget, QVBoxLayout, QPushButton,
    QToolBar, QToolButton, QLineEdit, QComboBox, QSizePolicy,
)
from PySide6.QtCore import Qt, QPoint, QTimer
from PySide6.QtGui import QAction, QKeySequence, QPixmap, QColor, QCursor, QIcon, QShortcut

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
    human_size, open_containing_folder, safe_unique_path, file_exists
)
from utils.settings import AppSettings
from utils.worker_threads import OCRWorker, MergeWorker, ImageExportWorker, PdfToWordWorker
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
from .unified_sidebar import UnifiedSidebar
from .icons import make_icon
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
        self._citation_link_summary: dict | None = None
        self._search_hits: dict = {}
        self._flat_hits: list = []  # [(page, hit_index), ...]
        self._active_hit_idx: int = -1
        self._last_search_term: str = ""
        self._last_search_case_sensitive: bool = False
        self._last_search_whole_word: bool = False
        self._pending_search_text: str = ""
        self._auto_fit_after_layout = True
        self._auto_fit_timer_active = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        from ui.tools_panel import AllToolsPanel

        self.splitter = QSplitter(Qt.Horizontal)
        self.splitter.setChildrenCollapsible(False)
        self.splitter.setHandleWidth(0)  # fixed premium layout; users do not resize sidebars

        # Premium fixed sidebars.  Tools stay on the left.  Pages/Outline and
        # Comments/Properties live on the right, each opened from one clear rail
        # icon.  Both sidebars are fixed-width so users cannot accidentally
        # resize them and break the reading layout.
        is_dark = False
        self.tools_panel = AllToolsPanel(dark=is_dark)
        self.left_side = LeftSidebar()
        self.right_side = RightSidebar()
        self.tools_sidebar = UnifiedSidebar(
            panel_items=[("All Tools", "tools", self.tools_panel, "tools")],
            title="All Tools",
        )
        # Pages/Outline and Comments/Properties now live in the same slim
        # right-side reading rail as the page controls.  This removes the extra
        # separate sidebar and uses the space the user already sees.
        self.info_sidebar = None
        # Compatibility names used by existing menu actions.
        self.unified_sidebar = self.tools_sidebar
        self.tools_wrap = self.tools_sidebar
        self.left_wrap = None
        self.right_wrap = None
        self._install_left_rail_view_controls()

        # Center: the viewer (never collapsible)
        self.viewer = PDFViewer()

        # Thin vertical annotation bar beside the PDF (self-contained per tab).
        self._annot_color = "#FFD54F"
        self.annot_bar = self._build_annot_bar()
        self.annot_bar_wrap = self._wrap_annot_bar(self.annot_bar)
        # Right-side navigation rail (page number, prev/next, zoom, refresh).
        self.nav_rail = self._build_nav_rail()
        self.right_info_panel = self._build_right_info_panel()
        self.right_info_panel.hide()

        # Per-PDF text search bar. It stays hidden until the user clicks Search
        # on the right rail or presses Ctrl+F. This gives the app a clear,
        # normal PDF-reader search option even though the large top toolbar is hidden.
        self.search_bar = self._build_search_bar()
        self.search_bar.hide()

        from PySide6.QtWidgets import QWidget as _QW, QHBoxLayout as _QHB, QVBoxLayout as _QVB
        self.viewer_wrap = _QW()
        _root = _QVB(self.viewer_wrap)
        _root.setContentsMargins(0, 0, 0, 0)
        _root.setSpacing(0)
        _root.addWidget(self.search_bar)

        _row = _QW()
        _vh = _QHB(_row)
        _vh.setContentsMargins(0, 0, 0, 0)
        _vh.setSpacing(0)
        _vh.addWidget(self.annot_bar_wrap)
        _vh.addWidget(self.viewer, 1)
        _vh.addWidget(self.right_info_panel)
        _vh.addWidget(self.nav_rail)
        _root.addWidget(_row, 1)

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

        self.splitter.addWidget(self.tools_sidebar)
        self.splitter.addWidget(self.viewer_wrap)
        self.splitter.setStretchFactor(0, 0)
        self.splitter.setStretchFactor(1, 1)
        self.splitter.setSizes([UnifiedSidebar.RAIL_WIDTH, 1000])
        layout.addWidget(self.splitter)

        # Fast PDF search: do not rescan every keystroke.  The user can type
        # normally, then the actual document search runs once after a short
        # pause.  This removes the lag that happened when every typed letter
        # triggered a full-page PyMuPDF search across the whole document.
        self._pdf_search_timer = QTimer(self)
        self._pdf_search_timer.setSingleShot(True)
        self._pdf_search_timer.setInterval(180)
        self._pdf_search_timer.timeout.connect(self._run_pending_pdf_search)

        # Start in clean reading mode: All Tools is icon-only.  Pages/Outline
        # and Comments are opened from the right rail only when needed.
        self.tools_sidebar.collapse()
        QTimer.singleShot(0, self._rebalance_splitter)
        self.tools_sidebar.collapsed_changed.connect(self._rebalance_splitter)

        # Connect signals
        self.left_side.page_requested.connect(self.viewer.goto_page)
        self.right_side.page_requested.connect(self.viewer.goto_page)
        self.viewer.current_page_changed.connect(self._sync_thumbnails)
        self.viewer.current_page_changed.connect(lambda _: self._nav_sync())
        self.right_side.export_btn.clicked.connect(self._export_annotations)

        # accept drops on the tab too — but the window already handles them


    def _build_search_bar(self):
        """Compact in-document text search bar shown above the PDF."""
        from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel, QLineEdit, QToolButton
        from PySide6.QtCore import QSize
        bar = QWidget()
        bar.setObjectName("PdfSearchBar")
        bar.setFixedHeight(38)
        is_dark = self._is_dark_mode()
        bg = "#0F172A" if is_dark else "#F8FAFC"
        border = "#334155" if is_dark else "#D7DEEA"
        text = "#F8FAFC" if is_dark else "#172033"
        muted = "#CBD5E1" if is_dark else "#64748B"
        field_bg = "#111827" if is_dark else "#FFFFFF"
        hover = "#1E293B" if is_dark else "#E8EEF8"
        accent = "#93C5FD" if is_dark else "#2563EB"
        bar.setStyleSheet(
            f"QWidget#PdfSearchBar {{ background: {bg}; border-bottom: 1px solid {border}; color: {text}; }}"
            f"QLabel {{ color: {text}; background: transparent; }}"
            f"QLabel#SearchCountLabel {{ color: {muted}; font-size: 12px; min-width: 54px; }}"
            f"QLineEdit {{ background: {field_bg}; color: {text}; border: 1px solid {border};"
            " border-radius: 13px; padding: 4px 10px; selection-background-color: #2563EB; }"
            f"QLineEdit:focus {{ border: 1px solid {accent}; }}"
            f"QToolButton {{ border: none; border-radius: 12px; padding: 3px 8px; color: {text}; background: transparent; }}"
            f"QToolButton:hover {{ background: {hover}; color: {accent}; }}"
        )
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(10, 4, 8, 4)
        lay.setSpacing(7)
        title = QLabel("Find")
        title.setStyleSheet("font-weight: 700;")
        lay.addWidget(title)

        self.search_input = QLineEdit()
        self.search_input.setObjectName("PdfSearchInput")
        self.search_input.setPlaceholderText("Type text to find in this PDF")
        self.search_input.setClearButtonEnabled(True)
        self.search_input.textChanged.connect(self._on_pdf_search_text_changed)
        self.search_input.returnPressed.connect(self.search_next)
        try:
            self.search_input.installEventFilter(self)
        except Exception:
            pass
        lay.addWidget(self.search_input, 1)

        self.search_count_label = QLabel("0 / 0")
        self.search_count_label.setObjectName("SearchCountLabel")
        self.search_count_label.setAlignment(Qt.AlignCenter)
        lay.addWidget(self.search_count_label)

        def small_btn(text, tip, fn, width=32):
            b = QToolButton()
            b.setText(text)
            b.setToolTip(tip)
            b.setFixedSize(QSize(width, 26))
            b.clicked.connect(fn)
            lay.addWidget(b)
            return b

        self.search_prev_btn = small_btn("↑", "Previous search result", self.search_prev)
        self.search_next_btn = small_btn("↓", "Next search result", self.search_next)
        small_btn("×", "Close search", self.hide_search_bar)
        return bar

    def show_search_bar(self):
        """Open the in-PDF search bar and focus the text field.

        Ctrl+F should feel like a normal PDF reader: the find box appears
        inside the PDF area, the current text is selected, and typing starts
        searching the open PDF immediately.
        """
        if not hasattr(self, "search_bar"):
            return
        self.search_bar.show()
        try:
            self.search_bar.raise_()
        except Exception:
            pass
        self.search_input.setFocus(Qt.ShortcutFocusReason)
        self.search_input.selectAll()
        # Opening Ctrl+F must be instant.  If text already exists, reuse the
        # cached result when possible and only schedule a delayed refresh.
        try:
            if self.search_input.text() and self.search_input.text() != self._last_search_term:
                self._pending_search_text = self.search_input.text()
                self._pdf_search_timer.start()
        except Exception:
            pass
        self._update_search_count()

    def hide_search_bar(self):
        """Close search and clear temporary search highlights."""
        if hasattr(self, "search_bar"):
            self.search_bar.hide()
        try:
            self._pdf_search_timer.stop()
        except Exception:
            pass
        if hasattr(self, "search_input"):
            self.search_input.blockSignals(True)
            self.search_input.clear()
            self.search_input.blockSignals(False)
        self.search("")
        try:
            self.viewer.setFocus(Qt.ShortcutFocusReason)
        except Exception:
            pass

    def _on_pdf_search_text_changed(self, text: str):
        # Debounced search keeps Ctrl+F responsive on large research PDFs.
        self._pending_search_text = text
        if not text:
            try:
                self._pdf_search_timer.stop()
            except Exception:
                pass
            self.search("")
            return
        if text == self._last_search_term:
            self._update_search_count()
            return
        if hasattr(self, "search_count_label"):
            self.search_count_label.setText("Searching…")
        try:
            self._pdf_search_timer.start()
        except Exception:
            self.search(text)

    def _run_pending_pdf_search(self):
        text = getattr(self, "_pending_search_text", "")
        self.search(text)

    def eventFilter(self, obj, event):
        """Keyboard polish for the PDF search field."""
        try:
            from PySide6.QtCore import QEvent
            if obj is getattr(self, "search_input", None) and event.type() == QEvent.KeyPress:
                if event.key() == Qt.Key_Escape:
                    self.hide_search_bar()
                    return True
                if event.key() in (Qt.Key_Return, Qt.Key_Enter) and (event.modifiers() & Qt.ShiftModifier):
                    self.search_prev()
                    return True
        except Exception:
            pass
        return super().eventFilter(obj, event)

    def _update_search_count(self):
        total = len(getattr(self, "_flat_hits", []))
        current = (getattr(self, "_active_hit_idx", -1) + 1) if total else 0
        if hasattr(self, "search_count_label"):
            self.search_count_label.setText(f"{current} / {total}")
        no_hits = bool(hasattr(self, "search_input") and self.search_input.text() and total == 0)
        if hasattr(self, "search_count_label"):
            self.search_count_label.setToolTip("No results found" if no_hits else "Search result count")

    def _install_left_rail_view_controls(self):
        """Place view/app controls directly in the slim left rail.

        Order requested by user:
        All Tools first, then page/view options, zoom controls lower down,
        then Language and Theme after zoom near the bottom of the sidebar.
        """
        try:
            from PySide6.QtWidgets import QMenu, QApplication
            from utils.i18n import available_languages, current_language
            from utils.constants import COLOR_THEMES, APPEARANCES

            rail = self.tools_sidebar

            def apply_view_mode(mode: str):
                # Change the page-view mode immediately, then auto-fit after the
                # canvas relayout is complete.  Two short queued fits make the
                # result reliable without blocking the UI.
                try:
                    viewer = getattr(self, "viewer", None)
                    if viewer:
                        viewer.set_view_mode(mode)
                        QTimer.singleShot(0, viewer.fit_width)
                        QTimer.singleShot(60, viewer.fit_width)
                except Exception:
                    pass

            def apply_language(code: str):
                try:
                    win = self.window()
                    if hasattr(win, "_on_toolbar_language_changed"):
                        win._on_toolbar_language_changed(code)
                except Exception:
                    pass

            def apply_theme(appearance: str | None = None, color_code: str | None = None):
                try:
                    win = self.window()
                    if hasattr(win, "_on_toolbar_app_theme_changed"):
                        win._on_toolbar_app_theme_changed(
                            appearance or self.settings.appearance(),
                            color_code or self.settings.theme(),
                        )
                except Exception:
                    pass

            # View controls near the top, directly after All Tools.
            rail.add_rail_action("fit_width", "Fit width", lambda: self.viewer.fit_width(), text="W", size=48)
            rail.add_rail_action("fit_page", "Fit page", lambda: self.viewer.fit_page(), text="P", size=48)

            view_menu = QMenu(rail)
            for label, mode in (("Continuous", "continuous"), ("Single page", "single"), ("Two pages", "two_page")):
                act = view_menu.addAction(label)
                act.triggered.connect(lambda checked=False, m=mode: apply_view_mode(m))
            rail.add_rail_action("pages", "Page view", menu=view_menu)

            # Keep the reading/research shortcuts directly before zoom.
            # These are icon-only vector buttons: no text on the rail.
            rail.add_rail_flexible_spacer()

            def mark_reference_from_rail():
                win = self.window()
                if hasattr(win, "action_mark_reference_toggle"):
                    win.action_mark_reference_toggle()

            def save_note_from_rail():
                win = self.window()
                if hasattr(win, "action_save_notes_toggle"):
                    win.action_save_notes_toggle()

            rail.add_rail_action(
                "reference",
                "Mark collected references",
                mark_reference_from_rail,
            )
            rail.add_rail_action(
                "note",
                "Save selected text as note",
                save_note_from_rail,
            )

            rail.add_rail_action("zoom_out", "Zoom out", lambda: self.viewer.zoom_out())
            rail.rail_zoom_label = rail.add_rail_label("100%", "Current zoom")
            rail.add_rail_action("zoom_in", "Zoom in", lambda: self.viewer.zoom_in())

            # Language and Theme now appear after the zoom controls, as requested.
            lang_menu = QMenu(rail)
            cur_lang = current_language()
            for code, name in available_languages().items():
                act = lang_menu.addAction(("✓ " if code == cur_lang else "   ") + f"{code.upper()} — {name}")
                act.triggered.connect(lambda checked=False, c=code: apply_language(c))
            rail.add_rail_action("language", "Language", menu=lang_menu)

            # Flat theme menu: no sub-branches, no visible drop-down arrow on the rail.
            theme_menu = QMenu(rail)
            cur_app = self.settings.appearance()
            cur_color = self.settings.theme()
            for code, name in APPEARANCES.items():
                act = theme_menu.addAction(("✓ " if code == cur_app else "   ") + name)
                act.triggered.connect(lambda checked=False, a=code: apply_theme(appearance=a))
            theme_menu.addSeparator()
            for code, name in COLOR_THEMES.items():
                act = theme_menu.addAction(("✓ " if code == cur_color else "   ") + name)
                act.triggered.connect(lambda checked=False, c=code: apply_theme(color_code=c))
            rail.add_rail_action("theme", "Theme", menu=theme_menu)
            try:
                rail.refresh_rail_colors(self._is_dark_mode())
            except Exception:
                pass
        except Exception:
            pass

    def _wrap_annot_bar(self, annot_bar):
        """Keep annotation tools as a compact floating rail, not a full-height app sidebar."""
        from PySide6.QtWidgets import QWidget, QVBoxLayout
        wrap = QWidget()
        wrap.setObjectName("AnnotBarWrap")
        wrap.setFixedWidth(84)
        wrap.setStyleSheet("QWidget#AnnotBarWrap { background: transparent; border: none; }")
        lay = QVBoxLayout(wrap)
        lay.setContentsMargins(5, 10, 3, 0)
        lay.setSpacing(0)
        lay.addWidget(annot_bar, 0, Qt.AlignTop)
        lay.addStretch(1)
        return wrap

    def _is_dark_mode(self) -> bool:
        """Return current app dark-mode state for hand-styled widgets."""
        try:
            return self.settings.appearance() == "dark"
        except Exception:
            return False

    def _refresh_local_dark_widgets(self):
        """Rebuild small hand-styled rails so their text/icons remain readable in dark mode."""
        try:
            if hasattr(self, "tools_sidebar") and hasattr(self.tools_sidebar, "refresh_rail_colors"):
                self.tools_sidebar.refresh_rail_colors(self._is_dark_mode())
        except Exception:
            pass
        try:
            parent = self.annot_bar_wrap.parentWidget() if hasattr(self, "annot_bar_wrap") else None
            layout = parent.layout() if parent is not None else None
            if layout is not None:
                old_wrap = self.annot_bar_wrap
                old_bar = self.annot_bar
                idx = layout.indexOf(old_wrap)
                layout.removeWidget(old_wrap)
                old_wrap.deleteLater()
                old_bar.deleteLater()
                self.annot_bar = self._build_annot_bar()
                self.annot_bar_wrap = self._wrap_annot_bar(self.annot_bar)
                layout.insertWidget(max(0, idx), self.annot_bar_wrap)
        except Exception:
            pass
        try:
            parent = self.nav_rail.parentWidget() if hasattr(self, "nav_rail") else None
            layout = parent.layout() if parent is not None else None
            if layout is not None:
                old = self.nav_rail
                idx = layout.indexOf(old)
                layout.removeWidget(old)
                old.deleteLater()
                self.nav_rail = self._build_nav_rail()
                layout.insertWidget(max(0, idx), self.nav_rail)
                self._nav_sync()
        except Exception:
            pass
        try:
            if hasattr(self, "right_info_panel"):
                visible = self.right_info_panel.isVisible()
                old = self.right_info_panel
                parent = old.parentWidget()
                layout = parent.layout() if parent is not None else None
                idx = layout.indexOf(old) if layout is not None else -1
                if layout is not None:
                    layout.removeWidget(old)
                    old.deleteLater()
                    self.right_info_panel = self._build_right_info_panel()
                    if not visible:
                        self.right_info_panel.hide()
                    layout.insertWidget(max(0, idx), self.right_info_panel)
        except Exception:
            pass
        try:
            if hasattr(self, "search_bar"):
                visible = self.search_bar.isVisible()
                old_text = self.search_input.text() if hasattr(self, "search_input") else ""
                parent = self.search_bar.parentWidget()
                layout = parent.layout() if parent is not None else None
                idx = layout.indexOf(self.search_bar) if layout is not None else -1
                if layout is not None:
                    layout.removeWidget(self.search_bar)
                    self.search_bar.deleteLater()
                    self.search_bar = self._build_search_bar()
                    self.search_input.setText(old_text)
                    if not visible:
                        self.search_bar.hide()
                    layout.insertWidget(max(0, idx), self.search_bar)
                    self._update_search_count()
        except Exception:
            pass

    def _build_annot_bar(self):
        """Easy markup toolbar beside the PDF.

        The previous rail was very compact and hid common tools inside small
        drop-down buttons.  For normal users that made marking feel difficult.
        This version shows the most-used actions as direct one-click buttons:
        Select, Highlight, Underline, Pen, Text, Box, Circle, X, Check, Erase,
        and Color.
        """
        from PySide6.QtWidgets import QWidget, QVBoxLayout, QToolButton, QLabel, QFrame
        from PySide6.QtCore import QSize, Qt

        bar = QWidget()
        bar.setObjectName("AnnotBar")
        bar.setFixedWidth(76)
        bar.setFixedHeight(430)
        bar.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        is_dark = self._is_dark_mode()
        bg = "rgba(17,24,39,0.97)" if is_dark else "rgba(248,250,252,0.98)"
        border = "#334155" if is_dark else "#DDE3ED"
        text = "#E5E7EB" if is_dark else "#334155"
        sub_text = "#CBD5E1" if is_dark else "#64748B"
        hover = "rgba(96,165,250,0.18)" if is_dark else "rgba(37,99,235,0.08)"
        checked = "rgba(96,165,250,0.30)" if is_dark else "rgba(37,99,235,0.14)"
        accent = "#93C5FD" if is_dark else "#2563EB"
        bar.setStyleSheet(
            f"QWidget#AnnotBar {{ background: {bg}; border: 1px solid {border}; border-radius: 16px; }}"
            f"QLabel#AnnotTitle {{ color: {sub_text}; font-size: 10px; font-weight: 700; padding: 0px; }}"
            f"QToolButton {{ border: none; padding: 2px; border-radius: 10px; color: {text}; background: transparent; font-size: 10px; }}"
            f"QToolButton:hover {{ background: {hover}; color: {accent}; }}"
            f"QToolButton:checked {{ background: {checked}; color: {accent}; font-weight: 700; }}"
            "QToolButton::menu-indicator { image: none; width: 0px; height: 0px; }")

        v = QVBoxLayout(bar)
        v.setContentsMargins(5, 8, 5, 8)
        v.setSpacing(3)
        self._annot_buttons = []
        annot_icon_size = 15

        title = QLabel("MARK")
        title.setObjectName("AnnotTitle")
        title.setAlignment(Qt.AlignCenter)
        v.addWidget(title)

        def _apply_icon(button, icon_name):
            button.setIcon(make_icon(icon_name, "#E5E7EB" if self._is_dark_mode() else "#475569", annot_icon_size))
            button.setIconSize(QSize(annot_icon_size, annot_icon_size))
            button.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)

        def add_btn(label, tip, tool=None, icon_name=None, callback=None):
            b = QToolButton()
            b.setText(label)
            b.setToolTip(tip)
            b.setCheckable(True)
            b.setFixedSize(QSize(64, 34))
            if icon_name:
                _apply_icon(b, icon_name)
            if callback is not None:
                b.clicked.connect(lambda checked=False, btn=b: callback(btn))
            else:
                b.clicked.connect(lambda checked=False, btn=b, tl=tool: self._annot_pick_tool(tl, btn))
            v.addWidget(b)
            self._annot_buttons.append(b)
            return b

        add_btn("Select", "Normal select mode", "none", "select")
        add_btn("High", "Highlight text: drag across words", callback=lambda btn: self._set_highlight_style("highlight", btn))
        add_btn("Under", "Underline text: drag across words", callback=lambda btn: self._set_highlight_style("underline", btn))
        add_btn("Pen", "Free-hand pen: draw on the page", "ink", "draw")
        add_btn("Text", "Add text box: click on the page", "add_text")
        add_btn("Box", "Draw rectangle: drag a box", "rect")
        add_btn("Circle", "Draw circle/ellipse: drag a box", "circle")
        add_btn("X", "Place X mark: click on the page", callback=lambda btn: self._set_mark_kind("xmark", btn))
        add_btn("✓", "Place check mark: click on the page", callback=lambda btn: self._set_mark_kind("check", btn))
        add_btn("Erase", "Delete annotation: click an annotation", "delete_annot")

        div = QFrame()
        div.setFrameShape(QFrame.HLine)
        div.setStyleSheet("color: #334155; background: #334155; max-height: 1px;" if self._is_dark_mode() else "color: #D5D8DF; background: #D5D8DF; max-height: 1px;")
        div.setFixedHeight(1)
        v.addSpacing(2)
        v.addWidget(div)
        v.addSpacing(2)

        self.annot_color_btn = QToolButton()
        self.annot_color_btn.setText("Color")
        self.annot_color_btn.setToolTip("Annotation color — click to change")
        self.annot_color_btn.setFixedSize(QSize(64, 34))
        self._style_color_dot()
        self.annot_color_btn.clicked.connect(self._annot_pick_color)
        v.addWidget(self.annot_color_btn)
        return bar

    def _add_annot_menu_btn(self, layout, symbol, tip, options, icon_name=None):
        """A toolbar button that opens a small popup menu of sub-tools without a visible arrow."""
        from PySide6.QtWidgets import QToolButton, QMenu
        from PySide6.QtCore import QSize
        b = QToolButton()
        b.setToolTip(tip)
        b.setCheckable(True)
        b.setFixedSize(QSize(31, 31))
        if icon_name:
            b.setIcon(make_icon(icon_name, "#E5E7EB" if self._is_dark_mode() else "#475569", 18))
            b.setIconSize(QSize(18, 18))
            b.setText("")
        else:
            b.setText(symbol)
        b.setStyleSheet("QToolButton::menu-indicator { image: none; width: 0px; height: 0px; }")
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

    def _set_highlight_style(self, style, btn=None):
        """Choose highlight / underline / strikeout, then arm the markup tool."""
        self._highlight_style = style
        for bb in self._annot_buttons:
            bb.setChecked(btn is not None and bb is btn)
        self.viewer.set_tool("highlight")
        self.viewer.set_annot_color(self._annot_color)

    def _set_mark_kind(self, kind, btn=None):
        """Choose which mark to place (X / check / dot), then arm the tool."""
        self._mark_kind = kind
        for bb in self._annot_buttons:
            bb.setChecked(btn is not None and bb is btn)
        self.viewer.set_tool("xmark")
        self.viewer.set_annot_color(self._annot_color)

    def _style_color_dot(self):
        """Render the color picker as a small round dot inside the button,
        not a big bright rectangle."""
        ring = "#64748B" if self._is_dark_mode() else "#C9CDD6"
        hover = "rgba(96,165,250,0.18)" if self._is_dark_mode() else "rgba(37,99,235,0.08)"
        self.annot_color_btn.setStyleSheet(
            "QToolButton {"
            "  border: none; border-radius: 10px; padding-left: 19px; text-align: left;"
            f" color: {'#E5E7EB' if self._is_dark_mode() else '#334155'};"
            f" background: qradialgradient(cx:0.14, cy:0.50, radius:0.16,"
            f"   fx:0.14, fy:0.50, stop:0 {self._annot_color},"
            f"   stop:0.72 {self._annot_color}, stop:0.76 {ring},"
            f"   stop:0.82 transparent, stop:1 transparent);"
            "}"
            f"QToolButton:hover {{ background-color: {hover}; }}")

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
        """Right reading rail: page navigation + Pages/Outline + Comments.

        The rail uses the vertical space that was previously mostly empty, so
        users do not need a second right sidebar.  Clicking a rail button opens
        a fixed-width premium panel beside the PDF.
        """
        from PySide6.QtWidgets import (QWidget, QVBoxLayout, QToolButton,
                                       QSpinBox, QLabel, QFrame)
        from PySide6.QtCore import QSize, Qt
        rail = QWidget()
        rail.setObjectName("ReadingRail")
        rail.setFixedWidth(56)
        is_dark = self._is_dark_mode()
        rail_bg = "#0F172A" if is_dark else "#F7F9FC"
        rail_border = "#334155" if is_dark else "#D7DEEA"
        rail_text = "#F8FAFC" if is_dark else "#172033"
        rail_hover = "#1E293B" if is_dark else "#E8EEF8"
        rail_checked = "#1E3A8A" if is_dark else "#DDE8FF"
        rail_accent = "#BFDBFE" if is_dark else "#0B56D0"
        rail.setStyleSheet(
            f"QWidget#ReadingRail {{ background: {rail_bg}; border-left: 1px solid {rail_border}; color: {rail_text}; }}"
            f"QToolButton {{ border: none; padding: 5px; border-radius: 8px; font-size: 16px; color: {rail_text}; background: transparent; }}"
            f"QToolButton:hover {{ background: {rail_hover}; color: {rail_accent}; }}"
            f"QToolButton:checked {{ background: {rail_checked}; color: {rail_accent}; }}"
            f"QSpinBox {{ border: 1px solid {rail_border}; border-radius: 6px; padding: 2px; background: {rail_bg}; color: {rail_text}; }}")
        v = QVBoxLayout(rail)
        v.setContentsMargins(6, 10, 6, 10)
        v.setSpacing(7)
        v.setAlignment(Qt.AlignHCenter)

        # current page box
        self.nav_page_box = QSpinBox()
        self.nav_page_box.setMinimum(1)
        self.nav_page_box.setMaximum(1)
        self.nav_page_box.setButtonSymbols(QSpinBox.NoButtons)
        self.nav_page_box.setAlignment(Qt.AlignCenter)
        self.nav_page_box.setFixedWidth(42)
        self.nav_page_box.setToolTip("Current page — type a number and press Enter")
        self.nav_page_box.editingFinished.connect(self._nav_go_to_typed_page)
        v.addWidget(self.nav_page_box, 0, Qt.AlignHCenter)

        # total pages label
        self.nav_total_lbl = QLabel("—")
        self.nav_total_lbl.setStyleSheet("color:#CBD5E1; font-size: 12px;" if self._is_dark_mode() else "color:#59657A; font-size: 12px;")
        self.nav_total_lbl.setAlignment(Qt.AlignCenter)
        v.addWidget(self.nav_total_lbl, 0, Qt.AlignHCenter)

        def divider():
            line = QFrame(); line.setFrameShape(QFrame.HLine)
            line.setStyleSheet("color:#334155; background:#334155; max-height:1px;" if self._is_dark_mode() else "color:#DDE3EC; background:#DDE3EC; max-height:1px;")
            v.addWidget(line)

        def btn(symbol, tip, fn, checkable=False):
            b = QToolButton()
            b.setText(symbol)
            b.setToolTip(tip)
            b.setCheckable(checkable)
            b.setFixedSize(QSize(42, 36))
            b.clicked.connect(fn)
            v.addWidget(b, 0, Qt.AlignHCenter)
            return b

        btn("\u25B2", "Previous page", self._nav_prev)
        btn("\u25BC", "Next page", self._nav_next)
        divider()

        # Text search option, always visible in the reading rail.
        self.nav_search_btn = btn("⌕", "Search text in this PDF (Ctrl+F)", self.show_search_bar)
        divider()

        # Integrated side-panel openers.  These replace the old separate right
        # sidebar rail and make the available vertical space useful.
        self.nav_pages_btn = btn("\u2630", "Open Pages & Outline",
                                 lambda: self._toggle_right_info_panel("pages"), True)
        self.nav_comments_btn = btn("\u25A1", "Open Comments & Properties",
                                    lambda: self._toggle_right_info_panel("comments"), True)
        divider()

        # Back / Forward — jump to where you were before clicking a link
        self.nav_back_btn = btn("\u2190", "Go back (after clicking a link)",
                                self._nav_back)
        self.nav_fwd_btn = btn("\u2192", "Go forward", self._nav_forward)
        divider()

        btn("\u21BB", "Reload / refresh the page", self._nav_refresh)
        btn("\u2398", "Fit page to width", self._nav_fit)
        # Zoom + / − were removed from the right rail.  Zoom now lives only
        # in the left rail so the right side stays clean and reading-focused.
        v.addStretch(1)
        return rail


    def _build_right_info_panel(self):
        """Fixed premium panel opened from the right reading rail."""
        from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QToolButton, QStackedWidget
        from PySide6.QtCore import QSize
        panel = QWidget()
        panel.setObjectName("RightInfoPanel")
        panel.setFixedWidth(318)
        is_dark = self._is_dark_mode()
        panel_bg = "#111827" if is_dark else "#FFFFFF"
        panel_border = "#334155" if is_dark else "#D7DEEA"
        panel_text = "#F8FAFC" if is_dark else "#172033"
        panel_hover = "#1E293B" if is_dark else "#EEF3FA"
        panel.setStyleSheet(
            f"QWidget#RightInfoPanel {{ background: {panel_bg}; border-left: 1px solid {panel_border}; color: {panel_text}; }}"
            f"QLabel#RightInfoTitle {{ font-size: 13px; font-weight: 700; color: {panel_text}; background: transparent; }}"
            f"QToolButton#RightInfoClose {{ border: none; border-radius: 8px; padding: 4px; color: {panel_text}; background: transparent; }}"
            f"QToolButton#RightInfoClose:hover {{ background: {panel_hover}; }}"
        )
        root = QVBoxLayout(panel)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        header = QWidget()
        header.setFixedHeight(44)
        hl = QHBoxLayout(header)
        hl.setContentsMargins(14, 0, 8, 0)
        self.right_info_title = QLabel("Pages & Outline")
        self.right_info_title.setObjectName("RightInfoTitle")
        hl.addWidget(self.right_info_title)
        hl.addStretch(1)
        close = QToolButton()
        close.setObjectName("RightInfoClose")
        close.setText("\u00D7")
        close.setToolTip("Close panel")
        close.setFixedSize(QSize(30, 30))
        close.clicked.connect(self._hide_right_info_panel)
        hl.addWidget(close)
        root.addWidget(header)

        self.right_info_stack = QStackedWidget()
        self.right_info_stack.addWidget(self.left_side)
        self.right_info_stack.addWidget(self.right_side)
        root.addWidget(self.right_info_stack, 1)
        return panel

    def _toggle_right_info_panel(self, which: str):
        """Open/close Pages/Outline or Comments inside the right reading rail."""
        target = 0 if which == "pages" else 1
        title = "Pages & Outline" if which == "pages" else "Comments & Properties"
        already_open = self.right_info_panel.isVisible() and self.right_info_stack.currentIndex() == target
        if already_open:
            self._hide_right_info_panel()
            return
        self.right_info_stack.setCurrentIndex(target)
        self.right_info_title.setText(title)
        self.right_info_panel.show()
        self.nav_pages_btn.setChecked(target == 0)
        self.nav_comments_btn.setChecked(target == 1)
        self._schedule_auto_fit_width(80)

    def _hide_right_info_panel(self):
        self.right_info_panel.hide()
        if hasattr(self, "nav_pages_btn"):
            self.nav_pages_btn.setChecked(False)
        if hasattr(self, "nav_comments_btn"):
            self.nav_comments_btn.setChecked(False)
        self._schedule_auto_fit_width(80)

    def show_pages_panel(self):
        self._toggle_right_info_panel("pages")

    def show_comments_panel(self):
        self._toggle_right_info_panel("comments")

    def _nav_sync(self):
        """Keep the rail's page box + total in sync with the document."""
        if not self.document:
            self._search_hits = {}
            self._flat_hits = []
            self._active_hit_idx = -1
            self._update_search_count()
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
        self._auto_build_citation_links()
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

    def _auto_build_citation_links(self):
        """Best-effort: make non-clickable numbered citations clickable on open.

        Some publisher PDFs already contain citation links; those are left
        untouched. For PDFs without citation links, this scans numbered
        citations such as [1], [2,3], [4-6] and links them to the matching
        numbered reference entry. The links are added in memory so they work
        immediately; pressing Ctrl+S or Save As will preserve them in the PDF.
        """
        self._citation_link_summary = None
        if not self.document or not self.document.doc:
            return
        try:
            from core.citation_extractor import build_missing_citation_links
            summary = build_missing_citation_links(self.document.doc)
            self._citation_link_summary = summary
            if summary.get("created", 0) > 0:
                # The document content changed in memory, but do not annoy the
                # user with an unsaved-changes warning just because the reader
                # improved navigation automatically. If the user saves later,
                # the links are written into the PDF.
                self.document.mark_dirty(False)
                try:
                    self.viewer.canvas.update()
                except Exception:
                    pass
        except Exception as e:
            self._citation_link_summary = {
                "created": 0, "references": 0, "skipped_existing": 0,
                "reason": str(e),
            }

    def rebuild_citation_links(self, show_message: bool = True):
        """Manual command for the Tools menu."""
        if not self.document or not self.document.doc:
            return False
        try:
            from core.citation_extractor import build_missing_citation_links
            summary = build_missing_citation_links(self.document.doc)
            self._citation_link_summary = summary
            if summary.get("created", 0) > 0:
                self.document.mark_dirty(True)
                try:
                    self.viewer.canvas.update()
                except Exception:
                    pass
            if show_message:
                QMessageBox.information(
                    self,
                    "Citation links",
                    f"Created {summary.get('created', 0)} clickable citation link(s).\n"
                    f"Detected {summary.get('references', 0)} numbered reference(s).\n\n"
                    "Works best with numbered citations like [1], [2,3], [4-6].\n"
                    "Author-year citation linking is not automatic yet."
                )
            return True
        except Exception as e:
            if show_message:
                QMessageBox.critical(self, "Citation links", str(e))
            return False

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
            return False
        target = output_path or self.path
        if not target:
            return self.save_as()
        # Ctrl+S saves directly to the existing file. Save As uses a new path.
        # No .bak backup file is created.
        self.document.save(target)
        self.path = self.document.path
        try:
            self.viewer.canvas._page_pixmaps.clear()
            self.viewer.canvas.invalidate_line_cache()
            self.viewer.canvas.update()
        except Exception:
            pass
        if hasattr(self, "status_msg"):
            self.status_msg.setText(f"Saved: {os.path.basename(self.path)}")
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
        self.path = self.document.path
        try:
            self.viewer.canvas._page_pixmaps.clear()
            self.viewer.canvas.invalidate_line_cache()
            self.viewer.canvas.update()
        except Exception:
            pass
        if hasattr(self, "status_msg"):
            self.status_msg.setText(f"Saved as: {os.path.basename(self.path)}")
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
        """Keep fixed sidebars stable and give all remaining space to PDF.

        When a sidebar opens/collapses, the PDF viewport width changes.  We
        immediately refit the current page/pair to the new space so the user
        does not need to click Fit W manually.
        """
        sizes = self.splitter.sizes()
        if len(sizes) != 2:
            return
        total = max(760, sum(sizes))
        left_w = (UnifiedSidebar.RAIL_WIDTH if self.tools_sidebar.is_collapsed()
                  else UnifiedSidebar.PANEL_WIDTH)
        self.splitter.setSizes([left_w, max(420, total - left_w)])
        # Do not auto-render Fit Width on every sidebar open/close.  Re-rendering
        # large PDF pages here caused the left sidebar buttons to feel laggy.
        # Users can still use the Fit W rail button when they want refitting.

    def _schedule_auto_fit_width(self, delay_ms: int = 80):
        """Debounced automatic Fit Width after layout/sidebar changes."""
        if not self._auto_fit_after_layout or not self.document:
            return
        if self._auto_fit_timer_active:
            return
        self._auto_fit_timer_active = True

        def _run():
            self._auto_fit_timer_active = False
            if self.document:
                try:
                    self.viewer.fit_width()
                except Exception:
                    pass

        QTimer.singleShot(delay_ms, _run)

    def resizeEvent(self, event):
        # Do not auto-fit on every resize.  Re-rendering PDF pages during
        # resizing/sidebar changes makes the interface feel laggy.  The user
        # can still press Fit W instantly from the left rail.
        super().resizeEvent(event)

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
        term = term or ""
        if not term:
            self._search_hits = {}
            self._flat_hits = []
            self._active_hit_idx = -1
            self._last_search_term = ""
            self.viewer.set_search_highlights({}, None)
            self._update_search_count()
            return

        # Reuse the last full-document result when the user presses Ctrl+F,
        # Enter, or clicks around without changing the query.
        if (term == self._last_search_term and
                case_sensitive == self._last_search_case_sensitive and
                whole_word == self._last_search_whole_word):
            active = self._flat_hits[self._active_hit_idx] if self._flat_hits and self._active_hit_idx >= 0 else None
            self.viewer.set_search_highlights(self._search_hits, active)
            self._update_search_count()
            return

        self._search_hits = self.document.search_text(term, case_sensitive, whole_word)
        self._last_search_term = term
        self._last_search_case_sensitive = case_sensitive
        self._last_search_whole_word = whole_word
        # flatten
        self._flat_hits = []
        for page in sorted(self._search_hits.keys()):
            for i in range(len(self._search_hits[page])):
                self._flat_hits.append((page, i))
        self._active_hit_idx = 0 if self._flat_hits else -1
        active = self._flat_hits[0] if self._flat_hits else None
        self.viewer.set_search_highlights(self._search_hits, active)
        self._update_search_count()

    def search_next(self):
        if not self._flat_hits:
            self._update_search_count()
            return
        self._active_hit_idx = (self._active_hit_idx + 1) % len(self._flat_hits)
        active = self._flat_hits[self._active_hit_idx]
        self.viewer.set_search_highlights(self._search_hits, active)
        self._update_search_count()

    def search_prev(self):
        if not self._flat_hits:
            self._update_search_count()
            return
        self._active_hit_idx = (self._active_hit_idx - 1) % len(self._flat_hits)
        active = self._flat_hits[self._active_hit_idx]
        self.viewer.set_search_highlights(self._search_hits, active)
        self._update_search_count()


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

        # Reading chrome auto-hide state.  When a PDF is open, the menu bar,
        # toolbars, and tab strip stay hidden for a distraction-free reading
        # area.  Moving the cursor to the top edge temporarily reveals them.
        self._reading_auto_hide_enabled = False
        self._top_chrome_revealed = True
        self._top_chrome_timer = QTimer(self)
        self._top_chrome_timer.setInterval(180)
        self._top_chrome_timer.timeout.connect(self._update_top_chrome_visibility)

        self._build_central()
        self._build_toolbar()
        self._build_compact_toolbar()
        self._build_menus()
        self._build_statusbar()
        self.optional_panel_dock = None

        self.setAcceptDrops(True)
        self._apply_theme()
        self._configure_autosave()
        self._install_pdf_search_shortcuts()

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

    def _install_pdf_search_shortcuts(self):
        """Reliable PDF find shortcuts independent of menu focus.

        Some Windows/PySide focus paths can swallow QAction shortcuts when the
        PDF canvas or a side panel has focus. Dedicated QShortcut objects make
        Ctrl+F, Enter, Shift+Enter, and Esc work consistently.
        """
        try:
            find_shortcut = QShortcut(QKeySequence.Find, self)
            find_shortcut.setContext(Qt.ApplicationShortcut)
            find_shortcut.activated.connect(self._focus_pdf_search)
            self._find_shortcut = find_shortcut

            esc_shortcut = QShortcut(QKeySequence(Qt.Key_Escape), self)
            esc_shortcut.setContext(Qt.ApplicationShortcut)
            esc_shortcut.activated.connect(self._escape_from_pdf_search)
            self._search_escape_shortcut = esc_shortcut
        except Exception:
            pass

    def _escape_from_pdf_search(self):
        t = self.current_tab()
        if t and hasattr(t, "search_bar") and t.search_bar.isVisible():
            t.hide_search_bar()

    # ---- UI construction ----
    def _build_central(self):
        self.tab_widget = QTabWidget()
        self.tab_widget.setTabsClosable(True)
        self.tab_widget.setMovable(True)
        self.tab_widget.setDocumentMode(True)
        self.tab_widget.tabCloseRequested.connect(self._close_tab)
        self.tab_widget.currentChanged.connect(self._tab_changed)
        self.tab_pdf_count_label = QLabel("PDFs: 0")
        self.tab_pdf_count_label.setObjectName("OpenPdfCountBadge")
        self.tab_pdf_count_label.setToolTip("Number of PDF files currently open")
        self.tab_widget.setCornerWidget(self.tab_pdf_count_label, Qt.TopRightCorner)
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
        # Keep MainToolbar as a hidden compatibility object for existing signal/state code.
        # The visible top area is now only the menu bar + PDF tabs.
        self.toolbar = MainToolbar(self)
        self.toolbar.hide()
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
        if hasattr(tb, "pdf_to_word_requested"):
            tb.pdf_to_word_requested.connect(self.action_pdf_to_word)
        tb.ocr_requested.connect(self.action_ocr)
        tb.encrypt_requested.connect(self.action_encrypt)
        tb.decrypt_requested.connect(self.action_decrypt)
        tb.sign_requested.connect(self.action_sign)
        tb.annotate_highlight_requested.connect(self.action_highlight_toggle)
        tb.annotate_note_requested.connect(self.action_note_hint)
        tb.theme_toggle_requested.connect(self.action_toggle_theme)
        tb.color_theme_changed.connect(self._on_toolbar_color_theme_changed)
        tb.app_theme_changed.connect(self._on_toolbar_app_theme_changed)
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
        tb.home_requested.connect(self.action_home)
        tb.tools_bar_toggle_requested.connect(self._toggle_top_tools_bar)

    def _build_compact_toolbar(self):
        """No visible compact toolbar. Top bar remains menu + PDF tabs only."""
        self.compact_toolbar = QToolBar("Compact toolbar", self)
        self.compact_toolbar.setObjectName("CompactToolbar")
        self.compact_toolbar.hide()
        self.compact_pdf_count_label = QLabel("PDFs: 0")
        self.compact_lang = None
        self.compact_theme_btn = None

    def _toggle_top_tools_bar(self):
        """Top toolbar hiding was removed; open the left tools sidebar instead."""
        try:
            t = self.current_tab()
            if isinstance(t, PDFTab):
                t.tools_sidebar.expand()
                self.status_msg.setText("View controls are in the All Tools sidebar.")
        except Exception:
            pass

    def _auto_hide_top_tools_for_pdf(self):
        """Auto-hide removed: keep menu bar and PDF tabs visible."""
        self._reading_auto_hide_enabled = False
        try:
            self._top_chrome_timer.stop()
        except Exception:
            pass
        self._set_top_chrome_visible(True)

    def _set_top_chrome_visible(self, visible: bool):
        """Top chrome no longer auto-hides. Keep menu bar and PDF tabs visible."""
        self._top_chrome_revealed = True
        try:
            self.menuBar().setVisible(True)
        except Exception:
            pass
        try:
            self.toolbar.hide()
            self.compact_toolbar.hide()
        except Exception:
            pass
        try:
            self.tab_widget.tabBar().setVisible(True)
        except Exception:
            pass

    def _update_top_chrome_visibility(self):
        """Disabled because topbar hiding was removed."""
        return

    def _leave_reading_auto_hide(self):
        """Restore normal chrome, used for Home/non-PDF tabs."""
        self._reading_auto_hide_enabled = False
        try:
            self._top_chrome_timer.stop()
        except Exception:
            pass
        self._set_top_chrome_visible(True)

    def action_home(self):
        """Open or switch to the Home tab."""
        for i in range(self.tab_widget.count()):
            w = self.tab_widget.widget(i)
            if getattr(w, "_is_home_page", False):
                self.tab_widget.setCurrentIndex(i)
                return
        self._open_welcome_tab(force=True)

    def _update_context_state(self):
        """Refresh optional context-dependent UI state."""
        return

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
        a_find.triggered.connect(self._focus_pdf_search)
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
            (tr("Build clickable citation links…"), self.action_build_citation_links),
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
            (tr("PDF to Word (.docx)…"), self.action_pdf_to_word),
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
        # PDF Side panel disabled by user request.
        a_about = QAction(tr("About {app}").replace("{app}", APP_NAME), self); a_about.triggered.connect(self.action_about)
        help_menu.addAction(a_about)
        a_update = QAction(tr("Check for updates…"), self)
        a_update.triggered.connect(lambda: self.action_check_updates(manual=True))
        help_menu.addAction(a_update)

    def _open_pdf_count(self) -> int:
        """Number of real PDF documents currently open (Home tab excluded)."""
        try:
            return sum(1 for i in range(self.tab_widget.count())
                       if isinstance(self.tab_widget.widget(i), PDFTab))
        except Exception:
            return 0

    def _update_open_pdf_count_badge(self):
        """Refresh all places that show how many PDFs are open."""
        count = self._open_pdf_count()
        text = f"PDFs: {count}" if count != 1 else "PDF: 1"
        try:
            self.open_pdf_count_label.setText(text)
        except Exception:
            pass
        try:
            self.compact_pdf_count_label.setText(text)
        except Exception:
            pass
        try:
            self.tab_widget.setToolTip(f"{count} PDF file(s) open")
        except Exception:
            pass
        try:
            self.tab_pdf_count_label.setText(text)
        except Exception:
            pass

    def _build_statusbar(self):
        from PySide6.QtWidgets import QSpinBox
        sb = QStatusBar()
        self.setStatusBar(sb)
        self.status_page = QLabel("Page —")
        self.status_page.setObjectName("StatusPage")
        self.status_zoom = QLabel("Zoom 100%")
        self.status_zoom.setObjectName("StatusZoom")
        self.status_msg = QLabel("Ready")
        self.status_msg.setObjectName("StatusMessage")
        self.open_pdf_count_label = QLabel("PDFs: 0")
        self.open_pdf_count_label.setObjectName("OpenPdfCountBadge")
        self.open_pdf_count_label.setToolTip("Number of PDF files currently open")

        # Jump-to-page box: type a page number and press Enter to go there.
        self.page_jump = QSpinBox()
        self.page_jump.setMinimum(1)
        self.page_jump.setMaximum(1)
        self.page_jump.setPrefix("Go to ")
        self.page_jump.setToolTip("Type a page number and press Enter to jump")
        self.page_jump.setFixedWidth(110)
        self.page_jump.editingFinished.connect(self._on_page_jump)

        # Bottom status bar removed for distraction-free reading.
        # Keep the widgets created so existing page/zoom/status update code remains safe,
        # but do not show a bottom bar in the main window. Page/zoom/open-PDF info
        # is available from the compact/top controls instead.
        sb.addWidget(self.status_msg, 1)
        sb.addPermanentWidget(self.open_pdf_count_label)
        sb.addPermanentWidget(self.page_jump)
        sb.addPermanentWidget(self.status_page)
        sb.addPermanentWidget(self.status_zoom)
        sb.hide()
        sb.setMaximumHeight(0)

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
        appearance = self.settings.appearance()
        QApplication.instance().setStyleSheet(get_stylesheet(theme, appearance))
        is_dark = (appearance == "dark")
        for i in range(self.tab_widget.count()):
            w = self.tab_widget.widget(i)
            if isinstance(w, PDFTab):
                w.viewer.set_background_color(viewer_background(theme, appearance))
                if hasattr(w, "tools_panel"):
                    w.tools_panel.set_dark(is_dark)
                if hasattr(w, "_refresh_local_dark_widgets"):
                    w._refresh_local_dark_widgets()
        try:
            self.toolbar.refresh_color_selector()
            if hasattr(self, "compact_theme_btn"):
                self.toolbar._build_theme_menu()
                self.compact_theme_btn.setMenu(self.toolbar.theme_btn.menu())
        except Exception:
            pass

    def _on_toolbar_app_theme_changed(self, appearance: str, color_code: str):
        old = (self.settings.appearance(), self.settings.theme())
        if appearance not in ("light", "dark"):
            appearance = old[0]
        self.settings.set_app_theme(appearance, color_code)
        if old == (self.settings.appearance(), self.settings.theme()):
            return
        self._apply_theme()
        try:
            from utils.constants import COLOR_THEMES, APPEARANCES
            self.status_msg.setText(
                f"Theme applied: {APPEARANCES.get(self.settings.appearance())} / "
                f"{COLOR_THEMES.get(self.settings.theme(), self.settings.theme())}")
        except Exception:
            pass

    def _on_toolbar_color_theme_changed(self, code: str):
        # Backward-compatible path: change color while keeping Light/Dark mode.
        if not code or code == self.settings.theme():
            return
        self.settings.set_theme(code)
        self._apply_theme()
        try:
            from utils.constants import COLOR_THEMES
            self.status_msg.setText(f"Color theme applied: {COLOR_THEMES.get(code, code)}")
        except Exception:
            pass

    def action_toggle_theme(self):
        # Legacy shortcut/action: toggle Light/Dark quickly.
        self.settings.set_appearance("dark" if self.settings.appearance() == "light" else "light")
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
            self.setWindowTitle(APP_NAME)
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
                (t.viewer.figure_area_save_requested, self._on_figure_area_save_requested),
                (t.viewer.figure_extract_mode_started, self._on_figure_extract_mode_started),
                (t.viewer.annot_delete_requested, self._on_annot_delete),
                (t.viewer.open_url_requested, self._on_open_url),
            ):
                try:
                    sig.connect(slot, Qt.UniqueConnection)
                except (RuntimeError, TypeError):
                    pass

            # Wire the per-tab All Tools panel signals once. Qt.UniqueConnection
            # cannot be used reliably with lambdas, and repeating these
            # connections can cause duplicated actions and sluggish UI.
            if getattr(t, "_tools_panel_wired", False):
                self._update_context_state()
                return
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
                (tp.fill_sign_requested,      self.action_fill_form),
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
                (tp.pdf_to_word_requested,    self.action_pdf_to_word),
                (tp.ocr_requested,            self.action_ocr),
                (tp.zoom_in_requested,         lambda: self._with_tab(lambda t: t.viewer.zoom_in())),
                (tp.zoom_out_requested,        lambda: self._with_tab(lambda t: t.viewer.zoom_out())),
                (tp.fit_width_requested,       lambda: self._with_tab(lambda t: t.viewer.fit_width())),
                (tp.fit_page_requested,        lambda: self._with_tab(lambda t: t.viewer.fit_page())),
                (tp.view_mode_changed,         self._set_view_mode),
                (tp.language_changed,          self._on_toolbar_language_changed),
                (tp.app_theme_changed,         self._on_toolbar_app_theme_changed),
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
                    sig.connect(slot)
                except (RuntimeError, TypeError):
                    pass
            t._tools_panel_wired = True
        else:
            self.setWindowTitle(APP_NAME)
            self._leave_reading_auto_hide()
        self._update_context_state()

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
        try:
            t = self.current_tab()
            if t and hasattr(t, "tools_panel"):
                t.tools_panel.set_zoom_label(zoom)
            if t and hasattr(t, "tools_sidebar"):
                t.tools_sidebar.set_rail_zoom_label(f"{int(zoom * 100)}%")
        except Exception:
            pass

    def _update_status(self):
        self._update_open_pdf_count_badge()
        t = self.current_tab()
        if not t or not t.document:
            self.status_page.setText("Page —")
            self.status_zoom.setText("Zoom 100%")
            return
        self.status_page.setText(f"Page {t.viewer.canvas.current_page() + 1} / {t.document.page_count}")
        self.status_zoom.setText(f"Zoom {int(t.viewer.canvas.zoom * 100)}%")
        self.toolbar.set_zoom_label(t.viewer.canvas.zoom)
        try:
            if hasattr(t, "tools_panel"):
                t.tools_panel.set_zoom_label(t.viewer.canvas.zoom)
            if hasattr(t, "tools_sidebar"):
                t.tools_sidebar.set_rail_zoom_label(f"{int(t.viewer.canvas.zoom * 100)}%")
        except Exception:
            pass
        self._update_context_state()

    # ---- welcome tab ----
    def _open_welcome_tab(self, force: bool = False):
        if self.tab_widget.count() > 0 and not force:
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
            is_dark=(self.settings.appearance() == "dark"),
            parent=self,
        )
        w._is_home_page = True
        self.tab_widget.addTab(w, "Home")
        self.tab_widget.setCurrentWidget(w)
        self._update_open_pdf_count_badge()
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
        self._update_open_pdf_count_badge()
        tab.viewer.set_background_color(viewer_background(self.settings.theme(), self.settings.appearance()))
        self._auto_hide_top_tools_for_pdf()
        self.settings.add_recent_file(path)
        self._rebuild_recent_menu()
        self._update_status()
        try:
            summary = getattr(tab, "_citation_link_summary", None) or {}
            created = int(summary.get("created", 0) or 0)
            refs = int(summary.get("references", 0) or 0)
            if created > 0:
                self.status_msg.setText(
                    f"Opened PDF. Auto-created {created} citation link(s) to {refs} reference(s)."
                )
        except Exception:
            pass

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
        self._update_open_pdf_count_badge()
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
            idx = self.tab_widget.currentIndex()
            if idx >= 0:
                self.tab_widget.setTabText(idx, t.document.file_name())
            self.status_msg.setText(f"Saved {t.path}")
        except Exception as e:
            QMessageBox.critical(self, "Save failed", str(e))

    def action_save_as(self):
        t = self.current_tab()
        if not t or not t.document:
            return
        if t.save_as():
            idx = self.tab_widget.currentIndex()
            if idx >= 0:
                self.tab_widget.setTabText(idx, t.document.file_name())
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
            # Automatically refit the PDF whenever page view changes
            # (continuous / single page / two pages).  Queue the fit so it
            # runs after the new layout is calculated, keeping the response
            # smooth and avoiding a half-fitted page.
            QTimer.singleShot(0, t.viewer.fit_width)
            QTimer.singleShot(60, t.viewer.fit_width)

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
        if which == "tools" and getattr(t, "tools_sidebar", None):
            t.tools_sidebar.show_tools()
        elif which == "left" and hasattr(t, "show_pages_panel"):
            t.show_pages_panel()
        elif which == "right" and hasattr(t, "show_comments_panel"):
            t.show_comments_panel()
        else:
            if getattr(t, "tools_sidebar", None):
                t.tools_sidebar.toggle()

    def _focus_mode(self):
        """Collapse/expand both fixed sidebars for distraction-free reading."""
        t = self.current_tab()
        if not t:
            return
        left = getattr(t, "tools_sidebar", None)
        if not left:
            return
        right_visible = getattr(t, "right_info_panel", None) and t.right_info_panel.isVisible()
        if left.is_collapsed() and not right_visible:
            left.expand()
            self.status_msg.setText("Focus mode off.")
        else:
            left.collapse()
            if hasattr(t, "_hide_right_info_panel"):
                t._hide_right_info_panel()
            self.status_msg.setText("Focus mode: sidebars hidden (Ctrl+Shift+F to bring back).")

    def eventFilter(self, obj, event):
        """Keyboard polish for the PDF find box: Esc closes, Shift+Enter goes back."""
        try:
            from PySide6.QtCore import QEvent
            if event.type() == QEvent.KeyPress:
                t = self.current_tab()
                if t and hasattr(t, "search_input") and obj is t.search_input:
                    if event.key() == Qt.Key_Escape:
                        t.hide_search_bar()
                        return True
                    if event.key() in (Qt.Key_Return, Qt.Key_Enter) and (event.modifiers() & Qt.ShiftModifier):
                        t.search_prev()
                        return True
        except Exception:
            pass
        return super().eventFilter(obj, event)

    # ---- search ----
    def _focus_pdf_search(self):
        t = self.current_tab()
        if t and t.document:
            t.show_search_bar()
            self.status_msg.setText("Search is open. Type text, Enter = next, Shift+Enter = previous, Esc = close.")
        else:
            self.status_msg.setText("Open a PDF first to search text.")

    def _search(self, term):
        t = self.current_tab()
        if t:
            t.show_search_bar()
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
        """Called when the user finishes a drag on the highlight tool.

        The new behavior follows the text's reading order from drag-start word
        to drag-end word, so highlighting feels like using a real marker pen.
        It no longer treats the drag as a big box that catches unrelated text.
        """
        t = self.current_tab()
        if not t or not t.document:
            return
        try:
            t.document.push_undo("Highlight")
            color = self.settings.highlight_color()
            import fitz

            payload = rect if isinstance(rect, dict) else {"rect": rect}
            base_rect = payload.get("rect")
            start = payload.get("start")
            end = payload.get("end")

            def fallback_rects():
                sel = fitz.Rect(base_rect.x(), base_rect.y(),
                                base_rect.x() + base_rect.width(),
                                base_rect.y() + base_rect.height())
                hits = []
                for w in t.document.doc[page_index].get_text("words") or []:
                    wr = fitz.Rect(w[0], w[1], w[2], w[3])
                    if wr.intersects(sel):
                        hits.append(wr)
                return hits or [sel]

            hit_rects = []
            try:
                words = list(t.document.doc[page_index].get_text("words") or [])
                if start and end and words:
                    words.sort(key=lambda w: (int(w[5]), int(w[6]), int(w[7]), float(w[1]), float(w[0])))
                    sp = fitz.Point(float(start[0]), float(start[1]))
                    ep = fitz.Point(float(end[0]), float(end[1]))

                    def score(pt, w):
                        wr = fitz.Rect(w[0], w[1], w[2], w[3])
                        if wr.contains(pt):
                            return -1.0
                        cx = (wr.x0 + wr.x1) / 2.0
                        cy = (wr.y0 + wr.y1) / 2.0
                        return (cx - pt.x) * (cx - pt.x) + (cy - pt.y) * (cy - pt.y)

                    i0 = min(range(len(words)), key=lambda i: score(sp, words[i]))
                    i1 = min(range(len(words)), key=lambda i: score(ep, words[i]))
                    if i0 > i1:
                        i0, i1 = i1, i0
                    hit_rects = [fitz.Rect(w[0], w[1], w[2], w[3])
                                 for w in words[i0:i1 + 1]]
                if not hit_rects:
                    hit_rects = fallback_rects()
            except Exception:
                hit_rects = fallback_rects()

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

    def action_pdf_to_word(self):
        t = self.current_tab()
        if not t or not t.path:
            QMessageBox.information(self, "PDF to Word", "Open and save a PDF first.")
            return
        default_name = os.path.splitext(os.path.basename(t.path))[0] + ".docx"
        out, _ = QFileDialog.getSaveFileName(
            self, "Save Word document as…", default_name, "Word Document (*.docx)"
        )
        if not out:
            return
        if not out.lower().endswith(".docx"):
            out += ".docx"

        worker = PdfToWordWorker(t.path, out)

        def _done(path):
            self.status_msg.setText(f"Word document saved: {path}")
            QMessageBox.information(
                self,
                "PDF to Word complete",
                "Saved Word document:\n" + path +
                "\n\nNote: scanned PDFs need OCR first before Word can contain editable text."
            )

        self._run_worker(worker, "Converting PDF to Word…", _done)

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
        comp_options = dlg.settings()
        dpi = int(comp_options.get("target_dpi", 100))
        quality = int(comp_options.get("jpeg_quality", 70))
        out, _ = QFileDialog.getSaveFileName(
            self, "Save compressed PDF as",
            os.path.splitext(t.path)[0] + f"-compressed-{dpi}dpi.pdf",
            "PDF (*.pdf)")
        if not out:
            return
        if not out.lower().endswith(".pdf"):
            out += ".pdf"

        worker = CompressWorker(t.path, out, dpi, quality, options=comp_options)

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
    def action_build_citation_links(self):
        """Manually add clickable links from citations to reference entries."""
        t = self.current_tab()
        if not t or not t.document:
            QMessageBox.information(self, "Citation links", "Open a PDF first.")
            return
        ok = t.rebuild_citation_links(show_message=True)
        if ok:
            try:
                summary = getattr(t, "_citation_link_summary", None) or {}
                created = int(summary.get("created", 0) or 0)
                refs = int(summary.get("references", 0) or 0)
                if created > 0:
                    self.status_msg.setText(
                        f"Created {created} clickable citation link(s) to {refs} reference(s). Press Ctrl+S to save them."
                    )
                else:
                    self.status_msg.setText("No new missing numbered citation links found.")
            except Exception:
                pass

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
        box.setObjectName("ReportText")
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
            color = getattr(t, "_annot_color", "#E53935")
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
        # Notes collection is data-heavy, so open it maximized by default.
        self._notes_panel.showMaximized()
        self._notes_panel.raise_()
        self._notes_panel.activateWindow()

    def open_library_panel(self):
        from ui.library_panel import LibraryPanel
        if self._library_panel is None:
            self._library_panel = LibraryPanel(self.library, self)
            self._library_panel.open_paper_requested.connect(self._open_from_library)
        self._library_panel.refresh_all()
        # Research Library is data-heavy, so open it maximized by default.
        # Users can still restore/resize the window from the title bar.
        self._library_panel.showMaximized()
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
        self._update_context_state()

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
        # Reference collection is data-heavy, so open it maximized by default.
        self._ref_panel.showMaximized()
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
            t.viewer.canvas.invalidate_line_cache(page_index)
            t.viewer.canvas.update()
            self._refresh_undo_state()
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
            t.viewer.canvas.invalidate_line_cache(page_index)
            t.viewer.canvas.update()
            self._refresh_undo_state()
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

        # Edit only the clicked visual line. The previous version sometimes
        # expanded a click into the whole text block. That looked messy on
        # research papers because a heading/paragraph block could cover two or
        # more lines, leaving a large white patch.
        edit_rect = line_rect
        prefill = line_text

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
            # refresh the page so the change shows immediately, and rebuild
            # line hit-testing so the next edit uses the new text/bounding box.
            t.viewer.canvas.invalidate_page(page_index)
            t.viewer.canvas.invalidate_line_cache(page_index)
            t.viewer.canvas.update()
            self._refresh_undo_state()
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


    def _on_figure_extract_mode_started(self, page_index):
        """User chose right-click > Save figure area. Tell them the next step."""
        try:
            self.status_msg.setText(
                f"Figure export: drag a rectangle around the figure on page {page_index + 1}.")
        except Exception:
            pass

    def _on_figure_area_save_requested(self, page_index, rect):
        """Render a selected PDF page area to a separate image file.

        This intentionally crops the visible page area instead of trying only to
        extract embedded raster images. Research figures often combine vector
        graphics, text labels, plots, and multiple image layers; cropping the
        rendered page area preserves exactly what the user sees.
        """
        t = self.current_tab()
        if not t or not t.document or not t.document.doc:
            QMessageBox.information(self, "Save figure", "Open a PDF first.")
            return
        try:
            import fitz
            page = t.document.doc[page_index]
            page_rect = page.rect

            # Convert QRectF-like object to a PyMuPDF Rect.
            try:
                clip = fitz.Rect(float(rect.x()), float(rect.y()),
                                 float(rect.x() + rect.width()),
                                 float(rect.y() + rect.height()))
            except Exception:
                clip = fitz.Rect(rect)
            clip = clip & page_rect
            if clip.is_empty or clip.width < 3 or clip.height < 3:
                QMessageBox.information(
                    self, "Save figure",
                    "The selected area is too small. Right-click the page again and drag around the figure.")
                return

            base = "figure"
            if t.path:
                base = os.path.splitext(os.path.basename(t.path))[0]
            default_name = f"{base}_page{page_index + 1}_figure.png"
            start_dir = os.path.dirname(t.path) if t.path else os.path.expanduser("~")
            default_path = os.path.join(start_dir, default_name)
            out, selected_filter = QFileDialog.getSaveFileName(
                self,
                "Save selected figure as image",
                default_path,
                "PNG image (*.png);;JPEG image (*.jpg);;All files (*)")
            if not out:
                self.status_msg.setText("Figure export cancelled.")
                return
            root, ext = os.path.splitext(out)
            if not ext:
                out = root + (".jpg" if "JPEG" in selected_filter else ".png")

            # 3x page scale gives good quality for publication figures without
            # making normal crops huge.  It is independent of the current zoom.
            matrix = fitz.Matrix(3.0, 3.0)
            pix = page.get_pixmap(matrix=matrix, clip=clip, alpha=False)
            pix.save(out)
            self.status_msg.setText(f"Figure image saved: {out}")
            try:
                QMessageBox.information(self, "Save figure", f"Figure saved:\n{out}")
            except Exception:
                pass
        except Exception as e:
            QMessageBox.critical(self, "Could not save figure", str(e))

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
        """Apply the selected interface language immediately.

        Older builds showed a restart popup. That felt confusing, so this now
        updates the active top-level UI live: menus, toolbar language selector,
        layout direction, and status message. New dialogs also open in the
        selected language.
        """
        from utils.i18n import set_language, current_language, is_rtl
        if not code or code == current_language():
            return
        self.settings.set_ui_language(code)
        set_language(code)
        try:
            QApplication.instance().setLayoutDirection(
                Qt.RightToLeft if is_rtl() else Qt.LeftToRight)
        except Exception:
            pass
        try:
            self.menuBar().clear()
            self._build_menus()
        except Exception:
            pass
        try:
            self.toolbar.refresh_language_selector()
            t = self.current_tab()
            if t and hasattr(t, "tools_panel"):
                t.tools_panel.refresh_language_selector()
            if getattr(self, "compact_lang", None) is not None:
                self.compact_lang.blockSignals(True)
                for i in range(self.compact_lang.count()):
                    if self.compact_lang.itemData(i) == code:
                        self.compact_lang.setCurrentIndex(i)
                        break
                self.compact_lang.blockSignals(False)
        except Exception:
            pass
        try:
            self.status_msg.setText(tr("Language applied automatically."))
        except Exception:
            pass

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
            # Interface language changed? Apply it immediately without a
            # restart popup. New dialogs will also use the selected language.
            lang_after = self.settings.ui_language()
            if lang_after != lang_before:
                self._on_toolbar_language_changed(lang_after)

    # ---- about ----
    def action_check_updates(self, manual=False):
        """Check GitHub Releases for a newer version.

        Automatic startup check: silent if no update or internet problem, but
        shows the update popup every time the app opens when a newer release
        exists. The user can choose Update now or Later.
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
                    "Could not check right now. Please check your internet "
                    "connection and make sure the GitHub repository is correct.")
            return

        if result.get("update"):
            box = QMessageBox(self)
            box.setIcon(QMessageBox.Information)
            box.setWindowTitle("Update available")
            asset = result.get("asset_name") or "latest release package"
            latest_tag = result.get("latest_tag") or result.get("latest")
            current_tag = result.get("current_tag") or f"v{result.get('current')}"
            box.setText(
                f"A new release of {APP_NAME} is available.\n\n"
                f"Current version: {result.get('current')} ({current_tag})\n"
                f"Latest release:  {result.get('latest')} ({latest_tag})\n\n"
                f"Package: {asset}\n\n"
                "Do you want to download and install the update now?"
            )
            if not result.get("asset_url"):
                box.setInformativeText(
                    "Automatic install needs a .zip asset in the GitHub release. "
                    "I can open the release page for manual download."
                )
            update_now = box.addButton("Update now", QMessageBox.AcceptRole)
            later = box.addButton("Later", QMessageBox.RejectRole)
            release_page = box.addButton("Open release page", QMessageBox.HelpRole)
            box.setDefaultButton(update_now)
            box.exec()
            clicked = box.clickedButton()
            if clicked == update_now:
                if result.get("asset_url"):
                    self._download_and_install_update(result)
                else:
                    QDesktopServices.openUrl(QUrl(result.get("url", "")))
            elif clicked == release_page:
                QDesktopServices.openUrl(QUrl(result.get("url", "")))
            else:
                # No suppression is saved. Because you requested it, the same
                # update will be shown again the next time the app opens.
                return
        elif manual:
            tag = result.get("current_tag") or f"v{result.get('current')}"
            QMessageBox.information(
                self, "Check for updates",
                f"You are using the latest version ({result.get('current')}).\n\n"
                f"Current release tag: {tag}\n"
                f"Repository checked: {result.get('repo', '')}")

    def _download_and_install_update(self, result):
        """Start the separate updater, close this app, and reopen after update.

        Works for both source/Python installs and PyInstaller onedir exe builds.
        For exe builds, developer/build-exe.bat creates UpdaterRunner.exe and
        copies it into the same app folder.
        """
        from PySide6.QtGui import QDesktopServices
        from PySide6.QtCore import QUrl
        import os, sys, subprocess

        frozen = bool(getattr(sys, "frozen", False))
        if frozen:
            base = os.path.dirname(os.path.abspath(sys.executable))
            updater_exe = os.path.join(base, "UpdaterRunner.exe")
            relaunch_exe = sys.executable
            main_py = ""
            if not os.path.exists(updater_exe):
                QMessageBox.warning(
                    self, "Updater missing",
                    "UpdaterRunner.exe is missing from the app folder.\n\n"
                    "Please rebuild the app with developer\\build-exe.bat, "
                    "or download the update manually from GitHub."
                )
                QDesktopServices.openUrl(QUrl(result.get("url", "")))
                return
            command = [updater_exe, base, relaunch_exe, main_py, result.get("asset_url", "")]
        else:
            base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            updater_py = os.path.join(base, "updater_runner.py")
            main_py = os.path.join(base, "main.py")
            python_exe = sys.executable
            if os.name == "nt" and python_exe.lower().endswith("pythonw.exe"):
                cand = python_exe[:-len("pythonw.exe")] + "python.exe"
                if os.path.exists(cand):
                    python_exe = cand
            if not os.path.exists(updater_py):
                QMessageBox.warning(
                    self, "Updater missing",
                    "updater_runner.py is missing. Opening the GitHub release page instead."
                )
                QDesktopServices.openUrl(QUrl(result.get("url", "")))
                return
            command = [python_exe, updater_py, base, sys.executable, main_py, result.get("asset_url", "")]

        QMessageBox.information(
            self, "Updating",
            f"{APP_NAME} will now close and update itself to version "
            f"{result.get('latest')}.\n\n"
            "The updater will download the GitHub release, install it, "
            "and reopen the app automatically. Please wait."
        )

        try:
            kwargs = {}
            if os.name == "nt":
                kwargs["creationflags"] = 0x00000010  # CREATE_NEW_CONSOLE
            subprocess.Popen(command, **kwargs)
        except Exception as e:
            QMessageBox.warning(
                self, "Update failed to start",
                f"Could not start the updater: {e}\n\n"
                "Opening the GitHub release page instead."
            )
            QDesktopServices.openUrl(QUrl(result.get("url", "")))
            return

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
