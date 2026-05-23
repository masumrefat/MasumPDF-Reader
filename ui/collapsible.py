"""A collapsible side-panel wrapper.

Wraps any widget with:
  - a header bar showing the title + a collapse (◀ / ▶) button
  - a thin vertical 'rail' shown when collapsed, with a rotated title and
    an expand button, so the panel can be brought back

Used to make every sidebar (Tools, Pages/Outline, Comments/Properties)
minimizable, giving more room to the PDF viewer.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QToolButton, QFrame,
    QStackedWidget, QSizePolicy,
)
from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QPainter, QColor, QFont


class _VerticalLabel(QWidget):
    """A label drawn rotated 90° for the collapsed rail."""

    def __init__(self, text="", parent=None):
        super().__init__(parent)
        self._text = text
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
        self.setMinimumWidth(20)

    def setText(self, text):
        self._text = text
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.TextAntialiasing, True)
        painter.translate(self.width() / 2, self.height() / 2)
        painter.rotate(-90)
        f = QFont()
        f.setPointSize(10)
        f.setBold(True)
        painter.setFont(f)
        painter.setPen(QColor(120, 120, 130))
        painter.drawText(
            int(-self.height() / 2), int(-self.width() / 2),
            self.height(), self.width(),
            Qt.AlignCenter, self._text)


class CollapsiblePanel(QWidget):
    """Wraps a content widget with a collapsible header + rail.

    Signals:
        collapsed_changed(bool)  - emitted when collapsed state changes
    """

    collapsed_changed = Signal(bool)

    RAIL_WIDTH = 26

    def __init__(self, title: str, content: QWidget,
                 side: str = "left", parent=None):
        """side: 'left' or 'right' — controls which way the arrow points
        and where the rail sits."""
        super().__init__(parent)
        self._title = title
        self._side = side
        self._collapsed = False
        self._expanded_width = None   # remembered width before collapse

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ----- expanded view (header + content) -----
        self._expanded = QWidget()
        ev = QVBoxLayout(self._expanded)
        ev.setContentsMargins(0, 0, 0, 0)
        ev.setSpacing(0)

        header = QFrame()
        header.setObjectName("PanelHeader")
        header.setFixedHeight(38)
        header.setStyleSheet(
            "#PanelHeader { background: transparent; "
            "border-bottom: 1px solid rgba(127,127,127,0.18); }")
        hl = QHBoxLayout(header)
        hl.setContentsMargins(14, 0, 8, 0)
        title_lbl = QLabel(title)
        title_lbl.setStyleSheet(
            "font-weight: 700; font-size: 12px; letter-spacing: 0.3px; "
            "color: palette(text);")
        self._collapse_btn = QToolButton()
        self._collapse_btn.setText("‹" if side == "left" else "›")
        self._collapse_btn.setToolTip(f"Hide {title} panel")
        self._collapse_btn.setCursor(Qt.PointingHandCursor)
        self._collapse_btn.setFixedSize(26, 26)
        self._collapse_btn.setStyleSheet(
            "QToolButton { border: 1px solid #C4C8D2; border-radius: 13px;"
            " font-size: 17px; font-weight: 700; color: #4A4E58;"
            " background: #EDEFF3; }"
            "QToolButton:hover { background: #2667FF; color: white;"
            " border: 1px solid #2667FF; }")
        self._collapse_btn.clicked.connect(self.collapse)
        if side == "left":
            hl.addWidget(title_lbl)
            hl.addStretch(1)
            hl.addWidget(self._collapse_btn)
        else:
            hl.addWidget(self._collapse_btn)
            hl.addStretch(1)
            hl.addWidget(title_lbl)
        ev.addWidget(header)
        ev.addWidget(content, 1)

        # ----- collapsed view (thin rail) -----
        self._rail = QFrame()
        self._rail.setObjectName("PanelRail")
        self._rail.setStyleSheet(
            "#PanelRail { background: rgba(127,127,127,14); }")
        self._rail.setFixedWidth(self.RAIL_WIDTH)
        self._rail.setCursor(Qt.PointingHandCursor)
        rv = QVBoxLayout(self._rail)
        rv.setContentsMargins(0, 6, 0, 6)
        rv.setSpacing(4)
        self._expand_btn = QToolButton()
        self._expand_btn.setText("›" if side == "left" else "‹")
        self._expand_btn.setToolTip(f"Show {title} panel")
        self._expand_btn.setCursor(Qt.PointingHandCursor)
        self._expand_btn.setFixedSize(24, 24)
        self._expand_btn.setStyleSheet(
            "QToolButton { border: 1px solid #C4C8D2; border-radius: 12px;"
            " font-size: 16px; font-weight: 700; color: #4A4E58;"
            " background: #EDEFF3; }"
            "QToolButton:hover { background: #2667FF; color: white;"
            " border: 1px solid #2667FF; }")
        self._expand_btn.clicked.connect(self.expand)
        rv.addWidget(self._expand_btn, 0, Qt.AlignHCenter)
        vlabel = _VerticalLabel(title)
        rv.addWidget(vlabel, 1)

        # Stacked: 0 = expanded, 1 = rail
        self._stack = QStackedWidget()
        self._stack.addWidget(self._expanded)
        self._stack.addWidget(self._rail)
        root.addWidget(self._stack)

        self.content = content

    # ---- collapse / expand ----
    def is_collapsed(self) -> bool:
        return self._collapsed

    def collapse(self):
        if self._collapsed:
            return
        # remember our current width so we can restore it later
        self._expanded_width = self.width()
        self._collapsed = True
        self._stack.setCurrentIndex(1)
        self.setFixedWidth(self.RAIL_WIDTH)
        self.collapsed_changed.emit(True)

    def expand(self):
        if not self._collapsed:
            return
        self._collapsed = False
        self._stack.setCurrentIndex(0)
        # release the fixed width so the splitter can size it again
        self.setMinimumWidth(0)
        self.setMaximumWidth(16777215)
        self.collapsed_changed.emit(False)

    def toggle(self):
        if self._collapsed:
            self.expand()
        else:
            self.collapse()

    def remembered_width(self) -> int:
        return self._expanded_width or 240
