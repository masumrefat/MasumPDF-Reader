"""Home / Welcome page — an Acrobat-style start screen.

Layout, top to bottom / left to right:
  • a left sidebar with grouped navigation items
  • a greeting line
  • a coloured hero banner
  • a row of "Get inspired" feature cards (these point at THIS app's own
    features, not anyone else's marketing content)
  • a "Recent" files list with Name / Opened / Size columns and a
    list / grid view toggle

Everything that can actually do something is wired through callbacks the
main window passes in; purely decorative items are shown greyed-out so the
user can tell at a glance what is and isn't active.
"""

import os
from datetime import datetime

from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QGridLayout, QLabel, QPushButton,
    QFrame, QScrollArea, QSizePolicy, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView, QButtonGroup,
)
from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QFont

from utils.i18n import tr


# --------------------------------------------------------------------------
# small helpers
# --------------------------------------------------------------------------
def _human_size(num_bytes: int) -> str:
    try:
        n = float(num_bytes)
    except Exception:
        return ""
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            if unit == "B":
                return f"{int(n)} {unit}"
            return f"{n:.0f} {unit}" if n >= 10 else f"{n:.1f} {unit}"
        n /= 1024
    return ""


def _relative_date(ts: float) -> str:
    """Format a timestamp like 'Today, 3:08 AM' / 'Yesterday, 10:43 PM' /
    'May 12, 2026'."""
    try:
        dt = datetime.fromtimestamp(ts)
    except Exception:
        return ""
    now = datetime.now()
    today = now.date()
    d = dt.date()
    delta_days = (today - d).days
    time_str = dt.strftime("%I:%M %p").lstrip("0")
    if delta_days == 0:
        return f"Today, {time_str}"
    if delta_days == 1:
        return f"Yesterday, {time_str}"
    if d.year == today.year:
        return dt.strftime("%b %d").replace(" 0", " ")
    return dt.strftime("%b %d, %Y").replace(" 0", " ")


def _palette(is_dark: bool) -> dict:
    if is_dark:
        return dict(
            page_bg="#1E1E22", panel_bg="#26262B", text="#ECECEF",
            muted="#9A9AA2", sidebar_bg="#202024", sidebar_sel="#34343C",
            line="#34343A", accent="#5B8CFF", card_text="#FFFFFF",
            row_hover="#2C2C32", header="#8A8A92",
        )
    return dict(
        page_bg="#FFFFFF", panel_bg="#FFFFFF", text="#1F1F24",
        muted="#6B6B72", sidebar_bg="#FFFFFF", sidebar_sel="#ECECF1",
        line="#E7E7EB", accent="#2667FF", card_text="#FFFFFF",
        row_hover="#F4F4F7", header="#8A8A92",
    )


# --------------------------------------------------------------------------
# a clickable card
# --------------------------------------------------------------------------
class FeatureCard(QFrame):
    clicked = Signal()

    def __init__(self, title, subtitle, gradient, parent=None):
        super().__init__(parent)
        self.setCursor(Qt.PointingHandCursor)
        self.setMinimumHeight(150)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setStyleSheet(
            f"FeatureCard {{ border-radius: 12px; background: {gradient}; }}")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 16, 18, 16)
        lay.addStretch(1)
        t = QLabel(title)
        t.setWordWrap(True)
        t.setStyleSheet("color:#FFFFFF; font-size:16px; font-weight:700;"
                        " background: transparent;")
        lay.addWidget(t)
        s = QLabel(subtitle)
        s.setWordWrap(True)
        s.setStyleSheet("color:rgba(255,255,255,0.88); font-size:12px;"
                        " background: transparent;")
        lay.addWidget(s)

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(e)


# --------------------------------------------------------------------------
# the home page
# --------------------------------------------------------------------------
class HomePage(QWidget):
    def __init__(self, app_name, user_name, recent_paths,
                 on_open_dialog, on_open_file, on_action, is_dark=False,
                 parent=None):
        super().__init__(parent)
        self._app_name = app_name
        self._user = user_name
        self._recents = list(recent_paths or [])
        self._on_open_dialog = on_open_dialog
        self._on_open_file = on_open_file
        self._on_action = on_action
        self._pal = _palette(is_dark)

        self.setStyleSheet(f"background:{self._pal['page_bg']};")
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._build_sidebar())
        root.addWidget(self._build_main(), 1)

    # ---- sidebar ----------------------------------------------------------
    def _side_item(self, text, handler=None, selected=False, indent=14):
        p = self._pal
        b = QPushButton(text)
        b.setCursor(Qt.PointingHandCursor if handler else Qt.ArrowCursor)
        b.setFlat(True)
        b.setEnabled(handler is not None)
        bg = p["sidebar_sel"] if selected else "transparent"
        weight = "600" if selected else "500"
        color = p["text"] if handler else p["muted"]
        b.setStyleSheet(
            f"QPushButton {{ text-align:left; padding:8px {indent}px;"
            f" border:none; border-radius:8px; background:{bg};"
            f" color:{color}; font-size:13px; font-weight:{weight}; }}"
            f"QPushButton:hover {{ background:{p['sidebar_sel']}; }}"
            f"QPushButton:disabled {{ color:{p['muted']}; }}")
        if handler:
            b.clicked.connect(lambda: handler())
        return b

    def _side_header(self, text):
        l = QLabel(text)
        l.setStyleSheet(
            f"color:{self._pal['text']}; font-size:12px; font-weight:700;"
            " padding:14px 14px 4px 14px;")
        return l

    def _build_sidebar(self):
        p = self._pal
        wrap = QFrame()
        wrap.setFixedWidth(212)
        wrap.setStyleSheet(
            f"background:{p['sidebar_bg']}; border-right:1px solid {p['line']};")
        lay = QVBoxLayout(wrap)
        lay.setContentsMargins(8, 12, 8, 12)
        lay.setSpacing(2)

        lay.addWidget(self._side_item(tr("Recent"), self._noop, selected=True))
        lay.addWidget(self._side_item(tr("Starred")))            # decorative
        lay.addWidget(self._side_item(tr("Notes"),
                                      lambda: self._on_action("notes")))

        lay.addWidget(self._side_header(tr("Files")))
        lay.addWidget(self._side_item(tr("Your documents"), self._on_open_dialog))
        lay.addWidget(self._side_item(tr("References"),
                                      lambda: self._on_action("references")))
        lay.addWidget(self._side_item(tr("Scans")))              # decorative
        lay.addWidget(self._side_item(tr("Shared by you")))      # decorative
        lay.addWidget(self._side_item(tr("Shared by others")))   # decorative

        lay.addWidget(self._side_header(tr("Other file storage")))
        lay.addWidget(self._side_item(tr("Your computer"), self._on_open_dialog))
        lay.addWidget(self._side_item(tr("Add file storage")))   # decorative

        lay.addStretch(1)
        return wrap

    # ---- main content -----------------------------------------------------
    def _build_main(self):
        p = self._pal
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet(f"background:{p['page_bg']};")

        inner = QWidget()
        inner.setStyleSheet(f"background:{p['page_bg']};")
        col = QVBoxLayout(inner)
        col.setContentsMargins(32, 24, 32, 24)
        col.setSpacing(18)

        # greeting
        who = f", {self._user}" if self._user else ""
        greet = QLabel(tr("Welcome to {app}").replace("{app}", self._app_name) + who)
        greet.setStyleSheet(
            f"color:{p['text']}; font-size:22px; font-weight:700;")
        col.addWidget(greet)

        # hero banner
        col.addWidget(self._build_hero())

        # cards
        cards_lbl = QLabel(tr("Get inspired by what you can do"))
        cards_lbl.setStyleSheet(
            f"color:{p['text']}; font-size:16px; font-weight:700;")
        col.addWidget(cards_lbl)
        col.addLayout(self._build_cards())

        # recent header + view toggle
        col.addLayout(self._build_recent_header())
        col.addWidget(self._build_recent_list(), 1)

        scroll.setWidget(inner)
        return scroll

    def _build_hero(self):
        p = self._pal
        hero = QFrame()
        hero.setMinimumHeight(120)
        hero.setStyleSheet(
            "QFrame { border-radius:14px; background:"
            " qlineargradient(x1:0, y1:0, x2:1, y2:1,"
            " stop:0 #5468FF, stop:0.6 #8A4FFF, stop:1 #C04BD8); }")
        lay = QHBoxLayout(hero)
        lay.setContentsMargins(24, 18, 24, 18)
        textcol = QVBoxLayout()
        h = QLabel("All your reading and research in one place")
        h.setStyleSheet("color:#FFFFFF; font-size:18px; font-weight:700;"
                        " background:transparent;")
        sub = QLabel("Open a PDF, then collect references and save notes as "
                     "you read — your sources build up automatically.")
        sub.setWordWrap(True)
        sub.setStyleSheet("color:rgba(255,255,255,0.9); font-size:12px;"
                          " background:transparent;")
        textcol.addStretch(1)
        textcol.addWidget(h)
        textcol.addWidget(sub)
        textcol.addStretch(1)
        lay.addLayout(textcol, 1)

        btn = QPushButton(tr("Open a PDF"))
        btn.setCursor(Qt.PointingHandCursor)
        btn.setFixedHeight(38)
        btn.setStyleSheet(
            "QPushButton { background:#FFFFFF; color:#3B3B7A; font-weight:700;"
            " border:none; border-radius:19px; padding:0 22px; }"
            "QPushButton:hover { background:#F0F0FF; }")
        btn.clicked.connect(lambda: self._on_open_dialog())
        lay.addWidget(btn, 0, Qt.AlignVCenter)
        return hero

    def _build_cards(self):
        grid = QGridLayout()
        grid.setSpacing(14)
        cards = [
            ("Collect references while you read",
             "Turn on Collect Reference, drag over a citation, and it's saved.",
             "qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 #1FA2FF, stop:1 #12D8B0)",
             "references"),
            ("Save any text as a note",
             "Keep snippets with their page number and source file.",
             "qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 #FF7E5F, stop:1 #FEB47B)",
             "notes"),
            ("Compare two PDFs",
             "Spot what changed between two versions side by side.",
             "qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 #7F53AC, stop:1 #647DEE)",
             "compare"),
            ("Make a scan searchable",
             "Run OCR so you can search and select text in scanned pages.",
             "qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 #11998E, stop:1 #38EF7D)",
             "ocr"),
        ]
        for i, (title, sub, grad, action) in enumerate(cards):
            card = FeatureCard(title, sub, grad)
            card.clicked.connect(lambda a=action: self._on_action(a))
            grid.addWidget(card, 0, i)
            grid.setColumnStretch(i, 1)
        return grid

    def _build_recent_header(self):
        p = self._pal
        row = QHBoxLayout()
        lbl = QLabel(tr("Recent"))
        lbl.setStyleSheet(
            f"color:{p['text']}; font-size:16px; font-weight:700;")
        row.addWidget(lbl)
        row.addStretch(1)

        self.list_btn = QPushButton(tr("List"))
        self.grid_btn = QPushButton(tr("Grid"))
        grp = QButtonGroup(self)
        for b in (self.list_btn, self.grid_btn):
            b.setCheckable(True)
            b.setCursor(Qt.PointingHandCursor)
            b.setFixedHeight(30)
            b.setStyleSheet(
                "QPushButton { border:1px solid %s; background:transparent;"
                " color:%s; padding:0 14px; border-radius:6px; font-size:12px; }"
                "QPushButton:checked { background:%s; color:#FFFFFF;"
                " border:1px solid %s; }"
                % (p["line"], p["muted"], p["accent"], p["accent"]))
            grp.addButton(b)
        self.list_btn.setChecked(True)
        self.list_btn.clicked.connect(lambda: self._set_view("list"))
        self.grid_btn.clicked.connect(lambda: self._set_view("grid"))
        row.addWidget(self.list_btn)
        row.addWidget(self.grid_btn)
        return row

    def _recent_rows(self):
        rows = []
        for path in self._recents:
            try:
                exists = os.path.exists(path)
                size = _human_size(os.path.getsize(path)) if exists else ""
                opened = _relative_date(os.path.getmtime(path)) if exists else ""
            except Exception:
                size, opened, exists = "", "", False
            rows.append(dict(path=path, name=os.path.basename(path),
                             size=size, opened=opened, exists=exists))
        return rows

    def _build_recent_list(self):
        p = self._pal
        self._rows_data = self._recent_rows()

        if not self._rows_data:
            empty = QLabel(tr("No recent files yet. Open a PDF to get started."))
            empty.setStyleSheet(f"color:{p['muted']}; padding:20px 4px;")
            self._recent_container = empty
            return empty

        table = QTableWidget()
        table.setColumnCount(3)
        table.setHorizontalHeaderLabels([tr("Name"), tr("Opened"), tr("Size")])
        table.setRowCount(len(self._rows_data))
        table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        table.setSelectionBehavior(QAbstractItemView.SelectRows)
        table.setSelectionMode(QAbstractItemView.SingleSelection)
        table.verticalHeader().setVisible(False)
        table.setShowGrid(False)
        table.verticalHeader().setDefaultSectionSize(44)
        hh = table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.Stretch)
        hh.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        table.setStyleSheet(
            "QTableWidget { background:%s; border:none; color:%s;"
            " font-size:13px; }"
            "QHeaderView::section { background:%s; color:%s; border:none;"
            " border-bottom:1px solid %s; padding:6px 8px; font-size:11px;"
            " font-weight:700; text-transform:uppercase; }"
            "QTableWidget::item { padding:6px 8px; border-bottom:1px solid %s; }"
            "QTableWidget::item:selected { background:%s; color:%s; }"
            % (p["page_bg"], p["text"], p["page_bg"], p["header"], p["line"],
               p["line"], p["sidebar_sel"], p["text"]))

        for r, row in enumerate(self._rows_data):
            name = row["name"] + ("" if row["exists"] else "  (missing)")
            it = QTableWidgetItem(name)
            it.setToolTip(row["path"])
            table.setItem(r, 0, it)
            table.setItem(r, 1, QTableWidgetItem(row["opened"]))
            table.setItem(r, 2, QTableWidgetItem(row["size"]))

        table.doubleClicked.connect(self._on_row_open)
        self._recent_table = table
        self._recent_container = table
        return table

    def _on_row_open(self, index):
        r = index.row()
        if 0 <= r < len(self._rows_data):
            row = self._rows_data[r]
            if row["exists"]:
                self._on_open_file(row["path"])

    def _set_view(self, mode):
        # Grid view is a light extra: it just widens rows / hides columns.
        # Kept simple and honest — the data is identical either way.
        if not hasattr(self, "_recent_table"):
            return
        t = self._recent_table
        if mode == "grid":
            t.setColumnHidden(1, True)
            t.setColumnHidden(2, True)
            t.verticalHeader().setDefaultSectionSize(64)
        else:
            t.setColumnHidden(1, False)
            t.setColumnHidden(2, False)
            t.verticalHeader().setDefaultSectionSize(44)

    def _noop(self):
        pass
