"""Premium fixed sidebars for MasumPDF Reader.

The app uses two clean, non-resizable sidebars:
- left: All Tools
- right: Pages & Outline, Comments & Properties

Each sidebar has a narrow icon rail when collapsed and a standard fixed panel
width when opened.  This keeps the PDF canvas stable and professional.
"""

from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QToolButton, QLabel, QStackedWidget,
    QSizePolicy, QFrame,
)
from PySide6.QtCore import Qt, Signal, QSize, QPropertyAnimation, QEasingCurve
from ui.icons import make_icon

RAIL_ICON_SIZE = 20


class UnifiedSidebar(QWidget):
    """Fixed-width, non-resizable sidebar with an icon rail and stacked pages."""

    collapsed_changed = Signal(bool)

    RAIL_WIDTH = 58
    PANEL_WIDTH = 318

    def __init__(self, tools_panel: QWidget | None = None,
                 pages_panel: QWidget | None = None,
                 comments_panel: QWidget | None = None,
                 parent=None, *, panel_items=None, title="Sidebar"):
        super().__init__(parent)
        self._collapsed = False
        self._animating = False
        self._animation = None
        self.setObjectName("UnifiedSidebar")
        self.setMinimumWidth(self.PANEL_WIDTH)
        self.setMaximumWidth(self.PANEL_WIDTH)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)

        if panel_items is None:
            panel_items = []
            if tools_panel is not None:
                panel_items.append(("All Tools", "tools", tools_panel, "tools"))
            if pages_panel is not None:
                panel_items.append(("Pages & Outline", "pages", pages_panel, "pages"))
            if comments_panel is not None:
                panel_items.append(("Comments & Properties", "comments", comments_panel, "comments"))
        self.panel_items = panel_items
        self._single_tools_mode = (
            len(panel_items) == 1 and len(panel_items[0]) >= 4 and panel_items[0][3] == "tools"
        )
        self._buttons = []
        self._key_to_index = {}

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.rail = QFrame()
        self.rail.setObjectName("UnifiedRail")
        rail_lay = QVBoxLayout(self.rail)
        rail_lay.setContentsMargins(8, 10, 8, 10)
        rail_lay.setSpacing(8)
        self.rail_layout = rail_lay
        self.rail.setFixedWidth(self.RAIL_WIDTH)

        self.expand_btn = None
        if not self._single_tools_mode:
            self.expand_btn = self._rail_button("menu", "Show / hide sidebar", checkable=False)
            self.expand_btn.clicked.connect(self.toggle)
            rail_lay.addWidget(self.expand_btn)
            rail_lay.addSpacing(8)

        self.panel = QWidget()
        self.panel.setObjectName("UnifiedPanel")
        self.panel.setMinimumWidth(max(0, self.PANEL_WIDTH - self.RAIL_WIDTH))
        panel_lay = QVBoxLayout(self.panel)
        panel_lay.setContentsMargins(0, 0, 0, 0)
        panel_lay.setSpacing(0)

        self.header = QFrame()
        self.header.setObjectName("UnifiedHeader")
        hl = QHBoxLayout(self.header)
        hl.setContentsMargins(16, 0, 10, 0)
        self.title_lbl = QLabel(title)
        self.title_lbl.setObjectName("UnifiedTitle")
        hl.addWidget(self.title_lbl)
        hl.addStretch(1)
        self.close_btn = QToolButton()
        self.close_btn.setObjectName("UnifiedCloseButton")
        self.close_btn.setText("")
        self._apply_icon_to_button(self.close_btn, "arrow_left")
        self.close_btn.setToolTip("Collapse sidebar")
        self.close_btn.setFixedSize(QSize(30, 30))
        self.close_btn.clicked.connect(self.collapse)
        hl.addWidget(self.close_btn)
        panel_lay.addWidget(self.header)

        self.stack = QStackedWidget()
        for idx, (ttl, icon, widget, key) in enumerate(self.panel_items):
            btn = self._rail_button(icon, ttl, checkable=True)
            if self._single_tools_mode and key == "tools":
                btn.setObjectName("AllToolsRailButton")
                btn.setText("All\nTools")
                btn.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
                btn.setFixedSize(QSize(50, 66))
                btn.setIconSize(QSize(RAIL_ICON_SIZE, RAIL_ICON_SIZE))
                btn.setToolTip("Open All Tools sidebar")
            if self._single_tools_mode and key == "tools":
                btn.clicked.connect(self.toggle)
            else:
                btn.clicked.connect(lambda checked=False, i=idx: self.show_index(i))
            rail_lay.addWidget(btn)
            self._buttons.append(btn)
            self._key_to_index[key] = idx
            self.stack.addWidget(widget)
        panel_lay.addWidget(self.stack, 1)
        rail_lay.addStretch(1)

        root.addWidget(self.rail)
        root.addWidget(self.panel, 1)
        if self.panel_items:
            self.show_index(0)




    def _default_rail_icon_color(self, is_dark: bool | None = None) -> str:
        """Return a high-contrast vector icon color for the collapsed rail."""
        if is_dark is None:
            # Fallback for initial construction before the main window can pass theme state.
            is_dark = False
        return "#E5E7EB" if is_dark else "#1F2937"

    def _apply_icon_to_button(self, button: QToolButton, icon_name: str, is_dark: bool | None = None):
        button.setProperty("rail_icon_name", icon_name)
        button.setIcon(make_icon(icon_name, self._default_rail_icon_color(is_dark), RAIL_ICON_SIZE))
        button.setIconSize(QSize(RAIL_ICON_SIZE, RAIL_ICON_SIZE))

    def refresh_rail_colors(self, is_dark: bool):
        """Re-render fixed SVG icons and small rail labels for Light/Dark mode.

        QSS can recolor text, but our premium SVG icons are pixmaps. Without
        re-rendering them, the left rail keeps dark icons on a dark background.
        """
        icon_color = self._default_rail_icon_color(is_dark)
        text_color = "#F8FAFC" if is_dark else "#111827"
        muted_color = "#CBD5E1" if is_dark else "#59657A"
        rail_bg = "#0F172A" if is_dark else "#F7F9FC"
        rail_border = "#334155" if is_dark else "#D7DEEA"
        for b in self.findChildren(QToolButton):
            name = b.property("rail_icon_name")
            if name:
                b.setIcon(make_icon(str(name), icon_color, RAIL_ICON_SIZE))
                b.setIconSize(QSize(RAIL_ICON_SIZE, RAIL_ICON_SIZE))
        for lbl in self.findChildren(QLabel, "RailZoomLabel"):
            lbl.setStyleSheet(
                f"QLabel#RailZoomLabel {{ background: transparent; color: {muted_color}; "
                "font-size: 10px; font-weight: 900; border: none; }"
            )
        # Make text-under-icon buttons such as All Tools, W and P readable too.
        self.rail.setStyleSheet(
            f"QFrame#UnifiedRail {{ background: {rail_bg}; border-right: 1px solid {rail_border}; color: {text_color}; }} "
            f"QToolButton#UnifiedRailButton {{ background: transparent; border: none; color: {muted_color}; font-weight: 900; }} "
            f"QToolButton#UnifiedRailButton:hover {{ background: transparent; color: {text_color}; }} "
            f"QToolButton#UnifiedRailButton:checked {{ background: transparent; color: {text_color}; border-left: 3px solid #60A5FA; }} "
            f"QToolButton#AllToolsRailButton {{ background: transparent; border: none; color: {text_color}; font-size: 8.5px; font-weight: 900; }} "
            f"QToolButton#AllToolsRailButton:hover {{ color: {text_color}; }} "
            f"QToolButton#AllToolsRailButton:checked {{ color: {text_color}; border-left: 3px solid #60A5FA; }}"
        )

    def add_rail_action(self, icon_name: str, tooltip: str, callback=None, *, text: str = "", menu=None, size: int = 42, bottom: bool = False):
        """Add a compact vector control to the slim rail.

        Menu buttons intentionally hide the small Qt drop-down indicator. The
        icon itself is enough, and removing the indicator keeps the rail clean.
        """
        b = QToolButton()
        b.setObjectName("UnifiedRailButton")
        self._apply_icon_to_button(b, icon_name)
        b.setToolTip(tooltip)
        b.setCursor(Qt.PointingHandCursor)
        b.setFixedSize(QSize(42, size))
        b.setCheckable(False)
        b.setStyleSheet("QToolButton::menu-indicator { image: none; width: 0px; height: 0px; }")
        if text:
            b.setText(text)
            b.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
            b.setIconSize(QSize(RAIL_ICON_SIZE, RAIL_ICON_SIZE))
        if menu is not None:
            b.setMenu(menu)
            b.setPopupMode(QToolButton.InstantPopup)
        elif callback is not None:
            b.clicked.connect(lambda checked=False: callback())
        insert_at = max(0, self.rail_layout.count() - 1)
        self.rail_layout.insertWidget(insert_at, b)
        return b

    def add_rail_flexible_spacer(self):
        """Push following rail controls down toward the bottom of the sidebar."""
        insert_at = max(0, self.rail_layout.count() - 1)
        self.rail_layout.insertStretch(insert_at, 1)

    def add_rail_label(self, text: str, tooltip: str = ""):
        lbl = QLabel(text)
        lbl.setObjectName("RailZoomLabel")
        lbl.setToolTip(tooltip)
        lbl.setAlignment(Qt.AlignCenter)
        lbl.setFixedSize(QSize(42, 26))
        lbl.setStyleSheet(
            "QLabel#RailZoomLabel { background: transparent; color: #59657A; "
            "font-size: 10px; font-weight: 900; border: none; }"
        )
        insert_at = max(0, self.rail_layout.count() - 1)
        self.rail_layout.insertWidget(insert_at, lbl)
        return lbl

    def set_rail_zoom_label(self, text: str):
        lbl = getattr(self, "rail_zoom_label", None)
        if lbl is not None:
            lbl.setText(text)

    def _rail_button(self, icon_name: str, tooltip: str, checkable: bool = True) -> QToolButton:
        b = QToolButton()
        b.setObjectName("UnifiedRailButton")
        b.setText("")
        self._apply_icon_to_button(b, icon_name)
        b.setToolTip(tooltip)
        b.setCheckable(checkable)
        b.setCursor(Qt.PointingHandCursor)
        b.setFixedSize(QSize(42, 42))
        return b

    def show_index(self, index: int):
        if index < 0 or index >= len(self.panel_items):
            return
        title, _icon, _widget, _key = self.panel_items[index]
        self.stack.setCurrentIndex(index)
        self.title_lbl.setText(title)
        for i, b in enumerate(self._buttons):
            b.setChecked(i == index)
        if self._collapsed:
            self.expand()
        elif self._single_tools_mode:
            # In single-button All Tools mode, clicking the rail button again
            # collapses the panel so the PDF immediately gets the space back.
            pass

    def show_key(self, key: str):
        self.show_index(self._key_to_index.get(key, 0))

    def show_tools(self):
        self.show_key("tools")

    def show_pages(self):
        self.show_key("pages")

    def show_comments(self):
        self.show_key("comments")

    def _set_fixed_width_for_animation(self, width: int):
        """Animate the whole sidebar width while keeping the layout fixed."""
        width = max(self.RAIL_WIDTH, min(self.PANEL_WIDTH, int(width)))
        self.setMinimumWidth(width)
        self.setMaximumWidth(width)
        panel_w = max(0, width - self.RAIL_WIDTH)
        self.panel.setMinimumWidth(panel_w)
        self.panel.setMaximumWidth(panel_w)

    def _animate_to_width(self, target_width: int, collapsed_after: bool):
        """Open/close instantly for a responsive left rail.

        The previous width animation updated layout on every frame. With large PDFs
        open, those repeated splitter/layout changes made the left rail feel slow.
        We now change width once, which makes button clicks immediate.
        """
        target_width = max(self.RAIL_WIDTH, min(self.PANEL_WIDTH, int(target_width)))
        if self._animation is not None:
            try:
                self._animation.stop()
            except Exception:
                pass
            self._animation = None
        self._animating = False
        self.panel.show()
        self._set_fixed_width_for_animation(target_width)
        self._collapsed = collapsed_after
        if collapsed_after:
            self.panel.hide()
            for b in self._buttons:
                b.setChecked(False)
        elif self._single_tools_mode and self._buttons:
            self._buttons[0].setChecked(True)
        self.collapsed_changed.emit(collapsed_after)

    def collapse(self):
        if self._collapsed and not self._animating:
            return
        if self.expand_btn is not None:
            self.expand_btn.setText("")
            self._apply_icon_to_button(self.expand_btn, "menu")
            self.expand_btn.setToolTip("Open sidebar")
        self._animate_to_width(self.RAIL_WIDTH, True)

    def expand(self):
        if not self._collapsed and not self._animating:
            return
        self.panel.show()
        if self.expand_btn is not None:
            self.expand_btn.setText("")
            self._apply_icon_to_button(self.expand_btn, "menu")
            self.expand_btn.setToolTip("Collapse sidebar")
        self._animate_to_width(self.PANEL_WIDTH, False)

    def toggle(self):
        if self._collapsed:
            self.expand()
        else:
            self.collapse()

    def is_collapsed(self):
        return self._collapsed

    def remembered_width(self):
        return self.PANEL_WIDTH
