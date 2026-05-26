"""Research Library panel — browse, search, organize, and open your papers.

Left side: collections, favorites, recent, tags (click to filter).
Right side: the paper list + search, with import/open/link/tag/favorite actions.
"""

import os
from urllib.parse import quote
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton, QLabel,
    QTableWidget, QTableWidgetItem, QHeaderView, QFileDialog, QMessageBox,
    QAbstractItemView, QListWidget, QSplitter, QWidget, QInputDialog,
    QTextEdit, QFormLayout, QDialogButtonBox, QScrollArea, QSizePolicy,
    QCheckBox, QGroupBox, QGridLayout,
)
from PySide6.QtCore import Qt, Signal, QUrl, QSize
from PySide6.QtGui import QDesktopServices
from ui.icons import make_icon

LIBRARY_ICON_SIZE = 16


class WebResourceDialog(QDialog):
    """Small editor for saving a non-PDF web resource in the Research Library."""

    def __init__(self, parent=None, title="", url="", about="", tags=""):
        super().__init__(parent)
        self.setWindowTitle("Add web resource")
        self.resize(560, 360)
        is_dark = bool(parent and hasattr(parent, "_is_dark_mode") and parent._is_dark_mode())
        self.setStyleSheet("""
            QDialog { background: #111827; color: #F8FAFC; }
            QLabel { font-weight: 700; color: #F8FAFC; }
            QLineEdit, QTextEdit { background: #0E1624; border: 1px solid #263244; border-radius: 10px; padding: 8px; color: #F8FAFC; selection-background-color: #3B82F6; selection-color: white; }
            QLineEdit:focus, QTextEdit:focus { border: 1px solid #3B82F6; }
            QPushButton { background: #151F2F; color: #F8FAFC; border: 1px solid #263244; border-radius: 10px; padding: 8px 12px; font-weight: 700; }
            QPushButton:hover { background: #1B2C47; border-color: #3B82F6; }
        """ if is_dark else """
            QDialog { background: #f8fafc; color: #172033; }
            QLabel { font-weight: 700; color: #334155; }
            QLineEdit, QTextEdit { background: white; border: 1px solid #d5dce8; border-radius: 10px; padding: 8px; color: #172033; }
            QLineEdit:focus, QTextEdit:focus { border: 1px solid #2563eb; }
            QPushButton { background: white; border: 1px solid #d5dce8; border-radius: 10px; padding: 8px 12px; font-weight: 700; }
            QPushButton:hover { background: #f2f6ff; border-color: #bcd0ff; }
        """)
        layout = QVBoxLayout(self)
        header = QLabel("Save any useful web link")
        header.setStyleSheet("font-size: 20px; font-weight: 900;")
        subtitle = QLabel("Not only papers: save datasets, GitHub, project pages, tutorials, videos, lab pages, protocols, or publisher links.")
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet("font-weight: 500;")
        layout.addWidget(header)
        layout.addWidget(subtitle)

        form = QFormLayout()
        self.title_edit = QLineEdit(title)
        self.title_edit.setPlaceholderText("Example: Cyborg insect dataset / Lab GitHub / Useful tutorial")
        self.url_edit = QLineEdit(url)
        self.url_edit.setPlaceholderText("Example: github.com/... or https://... or DOI")
        self.about_edit = QTextEdit()
        self.about_edit.setPlainText(about)
        self.about_edit.setPlaceholderText("Write what this web link is about and why it is useful…")
        self.about_edit.setMinimumHeight(110)
        self.tags_edit = QLineEdit(tags)
        self.tags_edit.setPlaceholderText("Example: dataset, cyborg insect, code, protocol")
        form.addRow("Title / name:", self.title_edit)
        form.addRow("Web link:", self.url_edit)
        form.addRow("What is it about:", self.about_edit)
        form.addRow("Tags:", self.tags_edit)
        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def values(self):
        tags = [t.strip() for t in self.tags_edit.text().split(",") if t.strip()]
        return {
            "title": self.title_edit.text().strip(),
            "url": self.url_edit.text().strip(),
            "about": self.about_edit.toPlainText().strip(),
            "tags": tags,
        }


class CollectionAssignDialog(QDialog):
    """Assign one library item to user-created collections."""

    def __init__(self, parent=None, item_title="", collections=None, selected=None):
        super().__init__(parent)
        self.setWindowTitle("Choose collection")
        self.resize(520, 420)
        self._checks = []
        collections = sorted(collections or [], key=str.lower)
        selected = set(selected or [])

        is_dark = bool(parent and hasattr(parent, "_is_dark_mode") and parent._is_dark_mode())
        self.setStyleSheet("""
            QDialog { background: #111827; color: #F8FAFC; }
            QLabel { color: #F8FAFC; }
            QLineEdit { background: #0E1624; border: 1px solid #263244; border-radius: 10px; padding: 8px; color: #F8FAFC; }
            QCheckBox { padding: 7px; font-weight: 700; }
            QPushButton { background: #151F2F; color: #F8FAFC; border: 1px solid #263244; border-radius: 10px; padding: 8px 12px; font-weight: 700; }
        """ if is_dark else """
            QDialog { background: #f8fafc; color: #172033; }
            QLabel { color: #334155; }
            QLineEdit { background: white; border: 1px solid #d5dce8; border-radius: 10px; padding: 8px; color: #172033; }
            QCheckBox { padding: 7px; font-weight: 700; }
            QPushButton { background: white; border: 1px solid #d5dce8; border-radius: 10px; padding: 8px 12px; font-weight: 700; }
        """)

        layout = QVBoxLayout(self)
        title = QLabel("Put this item into collection(s)")
        title.setStyleSheet("font-size: 20px; font-weight: 900;")
        layout.addWidget(title)

        subtitle = QLabel(item_title or "Selected library item")
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet("font-weight: 600;")
        layout.addWidget(subtitle)

        info = QLabel("Tick one or more collections. You can also create a new collection below.")
        info.setWordWrap(True)
        layout.addWidget(info)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        container = QWidget()
        box = QVBoxLayout(container)
        box.setContentsMargins(2, 2, 2, 2)
        if collections:
            for name in collections:
                cb = QCheckBox(name)
                cb.setChecked(name in selected)
                self._checks.append(cb)
                box.addWidget(cb)
        else:
            empty = QLabel("No collection yet. Type a new collection name below.")
            empty.setWordWrap(True)
            box.addWidget(empty)
        box.addStretch(1)
        scroll.setWidget(container)
        layout.addWidget(scroll, 1)

        self.new_collection_edit = QLineEdit()
        self.new_collection_edit.setPlaceholderText("New collection name, optional")
        layout.addWidget(self.new_collection_edit)

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def selected_collections(self):
        names = [cb.text().strip() for cb in self._checks if cb.isChecked()]
        new_name = self.new_collection_edit.text().strip()
        if new_name and new_name.lower() not in {n.lower() for n in names}:
            names.append(new_name)
        return names


class LibraryPanel(QDialog):
    open_paper_requested = Signal(str)   # emits a pdf path to open

    def __init__(self, library, parent=None):
        super().__init__(parent)
        self.library = library
        self.setWindowTitle("Research Library")
        # Start large and allow maximize/full-screen use, but do not force a
        # width that can exceed small laptop screens.
        self.resize(1280, 820)
        self.setMinimumSize(720, 500)
        self.setWindowFlag(Qt.WindowMaximizeButtonHint, True)
        self._current_view = ("all", None)  # (kind, value)

        is_dark = bool(parent and hasattr(parent, "_is_dark_mode") and parent._is_dark_mode())
        self.setStyleSheet("""
            QDialog { background: #0B101A; color: #F8FAFC; font-size: 12px; }
            QLabel#LibraryTitle { font-size: 21px; font-weight: 900; color: #F8FAFC; }
            QLabel#LibrarySubtitle { color: #CBD5E1; font-size: 12px; }
            QLabel#StatCard { background: #151F2F; border: 1px solid #263244; border-radius: 10px; padding: 5px 8px; color: #F8FAFC; font-weight: 800; }
            QLineEdit { background: #0E1624; border: 1px solid #263244; border-radius: 12px; padding: 8px 10px; font-size: 12px; color: #F8FAFC; selection-background-color: #3B82F6; selection-color: white; }
            QLineEdit:focus { border: 1px solid #3B82F6; }
            QListWidget, QTableWidget, QTextEdit { background: #111827; border: 1px solid #263244; border-radius: 16px; color: #F8FAFC; }
            QListWidget::item { padding: 6px; border-radius: 10px; color: #F8FAFC; }
            QListWidget::item:hover { background: #1B2C47; }
            QListWidget::item:selected { background: #1E3A8A; color: #FFFFFF; font-weight: 700; }
            QTableWidget { gridline-color: #202B3A; selection-background-color: #1E3A8A; selection-color: #FFFFFF; alternate-background-color: #151F2F; }
            QTableWidget::item { padding: 4px; color: #F8FAFC; }
            QHeaderView::section { background: #121B2B; border: 0; border-bottom: 1px solid #263244; padding: 6px; font-weight: 900; color: #E5E7EB; }
            QTextEdit { padding: 7px; line-height: 1.25; }
            QGroupBox { background: #111827; border: 1px solid #263244; border-radius: 12px; margin-top: 8px; padding: 10px 8px 8px 8px; font-weight: 900; color: #E5E7EB; }
            QGroupBox::title { subcontrol-origin: margin; left: 14px; padding: 0 6px; }
            QPushButton { background: #151F2F; border: 1px solid #263244; border-radius: 9px; padding: 5px 8px; font-weight: 800; min-height: 22px; font-size: 12px; color: #F8FAFC; }
            QPushButton:hover { background: #1B2C47; border-color: #3B82F6; }
            QPushButton#PrimaryButton { background: #3B82F6; color: white; border: 1px solid #3B82F6; }
            QPushButton#PrimaryButton:hover { background: #2563EB; }
            QPushButton#DangerButton { color: #FCA5A5; border-color: #7F1D1D; background: #2A1416; }
            QPushButton#DangerButton:hover { background: #3A171A; }
        """ if is_dark else """
            QDialog { background: #f6f8fc; color: #172033; font-size: 12px; }
            QLabel#LibraryTitle { font-size: 21px; font-weight: 900; color: #0f172a; }
            QLabel#LibrarySubtitle { color: #64748b; font-size: 12px; }
            QLabel#StatCard { background: #ffffff; border: 1px solid #e1e7f0; border-radius: 10px; padding: 5px 8px; color: #334155; font-weight: 800; }
            QLineEdit { background: #ffffff; border: 1px solid #d5dce8; border-radius: 12px; padding: 8px 10px; font-size: 12px; color: #172033; }
            QLineEdit:focus { border: 1px solid #2563eb; }
            QListWidget, QTableWidget, QTextEdit { background: #ffffff; border: 1px solid #e1e7f0; border-radius: 16px; color: #172033; }
            QListWidget::item { padding: 6px; border-radius: 10px; }
            QListWidget::item:hover { background: #f2f6ff; }
            QListWidget::item:selected { background: #e8f0ff; color: #123a75; font-weight: 700; }
            QTableWidget { gridline-color: #eef2f7; selection-background-color: #e8f0ff; selection-color: #0f172a; alternate-background-color: #f8fafc; }
            QTableWidget::item { padding: 4px; }
            QHeaderView::section { background: #f8fafc; border: 0; border-bottom: 1px solid #e1e7f0; padding: 6px; font-weight: 900; color: #475569; }
            QTextEdit { padding: 7px; line-height: 1.25; }
            QGroupBox { background: #ffffff; border: 1px solid #e1e7f0; border-radius: 12px; margin-top: 8px; padding: 10px 8px 8px 8px; font-weight: 900; color: #334155; }
            QGroupBox::title { subcontrol-origin: margin; left: 14px; padding: 0 6px; }
            QPushButton { background: #ffffff; border: 1px solid #d5dce8; border-radius: 9px; padding: 5px 8px; font-weight: 800; min-height: 22px; font-size: 12px; color: #1f2937; }
            QPushButton:hover { background: #f2f6ff; border-color: #bcd0ff; }
            QPushButton#PrimaryButton { background: #2563eb; color: white; border: 1px solid #2563eb; }
            QPushButton#PrimaryButton:hover { background: #1d4ed8; }
            QPushButton#DangerButton { color: #b42318; border-color: #f3c2bd; background: #fff8f7; }
            QPushButton#DangerButton:hover { background: #ffedea; }
        """)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 6, 8, 6)
        outer.setSpacing(6)

        # top: title first, stats underneath. This avoids a wide header that
        # can push the right side of the window outside small screens.
        t = QLabel("Research Library")
        t.setObjectName("LibraryTitle")
        outer.addWidget(t)
        sub = QLabel("Organize PDFs and useful web links by your own collections.")
        sub.setObjectName("LibrarySubtitle")
        sub.setWordWrap(True)
        outer.addWidget(sub)

        stats = QHBoxLayout()
        stats.setSpacing(8)
        self.count_lbl = QLabel("")
        self.count_lbl.setObjectName("StatCard")
        self.fav_count_lbl = QLabel("")
        self.fav_count_lbl.setObjectName("StatCard")
        self.link_count_lbl = QLabel("")
        self.link_count_lbl.setObjectName("StatCard")
        for lbl in (self.count_lbl, self.fav_count_lbl, self.link_count_lbl):
            lbl.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            stats.addWidget(lbl)
        outer.addLayout(stats)

        self.search = QLineEdit()
        self.search.setPlaceholderText(
            "Search title, author, year, tags, DOI, web link, filename, or keyword…")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self.refresh_papers)
        outer.addWidget(self.search)

        guide = QLabel("Workflow: Import/Add Web → Select item → Open, Collection, Tags, Favorite, or Remove")
        guide.setWordWrap(True)
        guide.setStyleSheet("font-weight: 800; font-size: 12px; padding: 6px 10px; border-radius: 10px; background: rgba(37, 99, 235, 0.10);")
        outer.addWidget(guide)

        split = QSplitter(Qt.Horizontal)
        outer.addWidget(split, 1)

        # ---- left: navigation ----
        left = QWidget()
        lv = QVBoxLayout(left)
        lv.setContentsMargins(0, 0, 0, 0)
        lv.setSpacing(8)
        lv.addWidget(self._small_label("LIBRARY"))
        self.nav = QListWidget()
        self.nav.addItem("All items")
        self.nav.addItem("Favorites")
        self.nav.addItem("Recent")
        self.nav.currentRowChanged.connect(self._on_nav)
        self.nav.setMaximumHeight(88)
        lv.addWidget(self.nav)

        lv.addWidget(self._small_label("COLLECTIONS"))
        collection_hint = QLabel("Click a collection to filter.")
        collection_hint.setWordWrap(True)
        collection_hint.setStyleSheet("font-size: 11px; font-weight: 600; color: #64748b; padding-bottom: 4px;")
        lv.addWidget(collection_hint)
        self.coll_list = QListWidget()
        self.coll_list.itemClicked.connect(self._on_collection)
        lv.addWidget(self.coll_list, 1)

        add_coll = QPushButton("+ New collection")
        add_coll.setObjectName("PrimaryButton")
        add_coll.setToolTip("Create a new collection/folder made by the user")
        self.add_to_coll_btn = QPushButton("Put selected item here")
        self.add_to_coll_btn.setToolTip("Add the selected paper or web resource to the currently selected collection")
        self.remove_from_coll_btn = QPushButton("Remove from here")
        self.remove_from_coll_btn.setToolTip("Remove selected item from this collection. The item stays in the library.")
        self.delete_coll_btn = QPushButton("Delete collection")
        self.delete_coll_btn.setToolTip("Delete the selected collection. Items stay in the library.")
        self.delete_coll_btn.setObjectName("DangerButton")
        add_coll.clicked.connect(self._new_collection)
        self.add_to_coll_btn.clicked.connect(self._add_selected_to_collection)
        self.remove_from_coll_btn.clicked.connect(self._remove_selected_from_collection)
        self.delete_coll_btn.clicked.connect(self._delete_collection)
        lv.addWidget(add_coll)
        lv.addWidget(self.add_to_coll_btn)
        lv.addWidget(self.remove_from_coll_btn)
        lv.addWidget(self.delete_coll_btn)

        lv.addWidget(self._small_label("TAGS"))
        self.tag_list = QListWidget()
        self.tag_list.itemClicked.connect(self._on_tag)
        self.tag_list.setMaximumHeight(90)
        lv.addWidget(self.tag_list)

        split.addWidget(left)

        # ---- right: paper table ----
        right = QWidget()
        rv = QVBoxLayout(right)
        rv.setContentsMargins(0, 0, 0, 0)
        rv.setSpacing(8)
        self.view_lbl = QLabel("All items")
        self.view_lbl.setStyleSheet("font-weight: 900; font-size: 14px; padding: 1px 0;")
        rv.addWidget(self.view_lbl)

        self.table = QTableWidget()
        cols = ["★", "Kind", "Title", "Author", "Year", "Collections", "Tags", "Link"]
        self.table.setColumnCount(len(cols))
        self.table.setHorizontalHeaderLabels(cols)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(30)
        self.table.setWordWrap(False)
        self.table.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.table.setSortingEnabled(True)
        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(2, QHeaderView.Stretch)
        hh.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(5, QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(6, QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(7, QHeaderView.ResizeToContents)
        self.table.doubleClicked.connect(self._open_selected)
        self.table.itemSelectionChanged.connect(self._update_details)
        rv.addWidget(self.table, 1)

        self.details = QTextEdit()
        self.details.setReadOnly(True)
        self.details.setMaximumHeight(95)
        self.details.setPlaceholderText(
            "Select one row to see details. Then use the bottom buttons: Open, Collection, Tags, Favorite, or Remove.")
        rv.addWidget(self.details)

        hint = QLabel(
            "Double-click PDFs to open the file. Double-click web resources to open the saved link. Use Add web resource for non-PDF links.")
        hint.setStyleSheet("font-size: 11px; padding: 1px 0;")
        rv.addWidget(hint)

        split.addWidget(right)
        left.setMinimumWidth(170)
        left.setMaximumWidth(250)
        split.setChildrenCollapsible(False)
        split.setSizes([210, 1040])

        # ---- compact action toolbar ----
        # Use a small grid instead of one very long row. This prevents the
        # Research Library from going outside the screen on smaller displays.
        action_bar = QWidget()
        action_grid = QGridLayout(action_bar)
        action_grid.setContentsMargins(0, 2, 0, 2)
        action_grid.setHorizontalSpacing(6)
        action_grid.setVerticalSpacing(6)

        self.import_btn = QPushButton("Import PDF")
        self.import_btn.setIcon(make_icon("import", "#1F2937", LIBRARY_ICON_SIZE))
        self.import_btn.setObjectName("PrimaryButton")
        self.import_btn.setToolTip("Add one or more PDF papers")
        self.add_resource_btn = QPushButton("Add Web")
        self.add_resource_btn.setIcon(make_icon("web", "#1F2937", LIBRARY_ICON_SIZE))
        self.add_resource_btn.setToolTip("Save a website, DOI page, GitHub, dataset, video, or project link")

        self.open_btn = QPushButton("Open")
        self.open_btn.setIcon(make_icon("pdf", "#1F2937", LIBRARY_ICON_SIZE))
        self.open_btn.setToolTip("Open the selected PDF, or open the web link if the item is a web resource")
        self.web_btn = QPushButton("Web")
        self.web_btn.setIcon(make_icon("web", "#1F2937", LIBRARY_ICON_SIZE))
        self.web_btn.setToolTip("Open the saved DOI, publisher page, GitHub, dataset, or other web link")
        self.preview_btn = QPushButton("Details")
        self.preview_btn.setIcon(make_icon("eye", "#1F2937", LIBRARY_ICON_SIZE))
        self.preview_btn.setToolTip("Show full details and preview text for the selected item")

        self.assign_collection_btn = QPushButton("Collection")
        self.assign_collection_btn.setIcon(make_icon("library", "#1F2937", LIBRARY_ICON_SIZE))
        self.assign_collection_btn.setToolTip("Put selected item into one or more user-created collections")
        self.tag_btn = QPushButton("Tags")
        self.tag_btn.setIcon(make_icon("tag", "#1F2937", LIBRARY_ICON_SIZE))
        self.tag_btn.setToolTip("Add or edit tags for the selected item")
        self.fav_btn = QPushButton("Favorite")
        self.fav_btn.setIcon(make_icon("favorite", "#1F2937", LIBRARY_ICON_SIZE))
        self.fav_btn.setToolTip("Mark or unmark the selected item as a favorite")
        self.add_link_btn = QPushButton("Link")
        self.add_link_btn.setIcon(make_icon("link", "#1F2937", LIBRARY_ICON_SIZE))
        self.add_link_btn.setToolTip("Add or edit DOI, publisher URL, GitHub URL, dataset URL, or other web link")

        self.related_btn = QPushButton("Related")
        self.related_btn.setIcon(make_icon("related", "#1F2937", LIBRARY_ICON_SIZE))
        self.related_btn.setToolTip("Find items with similar tags or authors")
        self.remove_btn = QPushButton("Remove")
        self.remove_btn.setIcon(make_icon("remove", "#1F2937", LIBRARY_ICON_SIZE))
        self.remove_btn.setToolTip("Remove selected item from the library database. The PDF file itself is not deleted.")
        self.remove_btn.setObjectName("DangerButton")
        self.close_btn = QPushButton("Close")
        self.close_btn.setIcon(make_icon("close", "#1F2937", LIBRARY_ICON_SIZE))
        self.close_btn.setToolTip("Close the Research Library window")

        buttons = [
            self.import_btn, self.add_resource_btn, self.open_btn, self.web_btn,
            self.preview_btn, self.assign_collection_btn, self.tag_btn, self.fav_btn,
            self.add_link_btn, self.related_btn, self.remove_btn, self.close_btn,
        ]
        for i, b in enumerate(buttons):
            b.setMinimumWidth(68)
            b.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            b.setCursor(Qt.PointingHandCursor)
            b.setIconSize(QSize(LIBRARY_ICON_SIZE, LIBRARY_ICON_SIZE))
            action_grid.addWidget(b, i // 6, i % 6)
        outer.addWidget(action_bar)

        self.import_btn.clicked.connect(self._import)
        self.open_btn.clicked.connect(self._open_selected)
        self.web_btn.clicked.connect(self._open_web_link)
        self.add_link_btn.clicked.connect(self._edit_web_link)
        self.add_resource_btn.clicked.connect(self._add_web_resource)
        self.fav_btn.clicked.connect(self._toggle_fav)
        self.tag_btn.clicked.connect(self._edit_tags)
        self.assign_collection_btn.clicked.connect(self._assign_collection)
        self.preview_btn.clicked.connect(self._preview)
        self.related_btn.clicked.connect(self._related)
        self.remove_btn.clicked.connect(self._remove)
        self.close_btn.clicked.connect(self.hide)

        self._rows = []
        self.refresh_all()

    def _small_label(self, text):
        l = QLabel(text)
        l.setStyleSheet("font-size:11px; font-weight:900;"
                        " letter-spacing:1.2px; margin-top:8px;")
        return l

    def _action_group(self, title, buttons):
        group = QGroupBox(title)
        row = QHBoxLayout(group)
        row.setContentsMargins(8, 8, 8, 8)
        row.setSpacing(8)
        for button in buttons:
            row.addWidget(button)
        return group

    # ---------- refresh ----------
    def refresh_all(self):
        self._refresh_collections()
        self._refresh_tags()
        self.refresh_papers()

    def _refresh_collections(self):
        self.coll_list.clear()
        for name in sorted(self.library.collections.keys()):
            n = len(self.library.collections[name])
            self.coll_list.addItem(f"{name}  ({n})")

    def _refresh_tags(self):
        self.tag_list.clear()
        for tag in self.library.all_tags():
            self.tag_list.addItem(f"{tag}")

    def refresh_papers(self):
        kind, value = self._current_view
        term = self.search.text()
        if kind == "favorites":
            papers = self.library.favorites()
            if term:
                papers = [p for p in papers if term.lower() in
                          self._search_blob(p).lower()]
            self.view_lbl.setText("Favorites")
        elif kind == "recent":
            papers = self.library.recent(20)
            if term:
                papers = [p for p in papers if term.lower() in
                          self._search_blob(p).lower()]
            self.view_lbl.setText("Recently opened")
        elif kind == "collection":
            papers = self.library.search(term=term, collection=value)
            self.view_lbl.setText(f"{value}")
        elif kind == "tag":
            papers = self.library.search(term=term, tag=value)
            self.view_lbl.setText(f"{value}")
        else:
            papers = self.library.search(term=term)
            self.view_lbl.setText("All items")

        self._rows = papers
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(papers))
        for r, p in enumerate(papers):
            collections = ", ".join(self._item_collections(p))
            vals = ["", "Web" if self._is_web_resource(p) else "PDF", p.get("title", ""), p.get("author", ""),
                    str(p.get("year", "")), collections, ", ".join(p.get("tags", [])), ""]
            for c, v in enumerate(vals):
                item = QTableWidgetItem(str(v))
                if c == 0 and p.get("favorite"):
                    item.setIcon(make_icon("favorite", "#1F2937", 16))
                if c == 1:
                    item.setIcon(make_icon("web" if self._is_web_resource(p) else "pdf", "#1F2937", 16))
                if c == 7 and self._paper_web_link(p):
                    item.setIcon(make_icon("link", "#1F2937", 16))
                    item.setText("Yes")
                item.setData(Qt.UserRole, p.get("path", ""))
                if c in (0, 1, 4, 7):
                    item.setTextAlignment(Qt.AlignCenter)
                self.table.setItem(r, c, item)

        self.table.resizeRowsToContents()
        self.table.setSortingEnabled(True)

        all_papers = self.library.all_papers()
        web_count = len([p for p in all_papers if self._is_web_resource(p)])
        pdf_count = len(all_papers) - web_count
        self.count_lbl.setText(f"{pdf_count} PDFs / {web_count} web")
        self.fav_count_lbl.setText(f"{len(self.library.favorites())} favorites")
        linked = len([p for p in all_papers if self._paper_web_link(p)])
        self.link_count_lbl.setText(f"{linked} links")
        self._update_details()

    # ---------- nav handlers ----------
    def _on_nav(self, row):
        if row == 0:
            self._current_view = ("all", None)
        elif row == 1:
            self._current_view = ("favorites", None)
        elif row == 2:
            self._current_view = ("recent", None)
        self.refresh_papers()

    def _on_collection(self, item):
        # Items are displayed as "Collection name  (count)".  The previous
        # parser accidentally kept only the count part for many names, so
        # clicking a collection showed an empty list.  Strip only the trailing
        # counter and keep the full collection name.
        text = item.text().strip()
        name = text.rsplit("  (", 1)[0].strip() if "  (" in text else text
        self._current_view = ("collection", name)
        self.refresh_papers()

    def _on_tag(self, item):
        tag = item.text().strip()
        self._current_view = ("tag", tag)
        self.refresh_papers()

    # ---------- selection ----------
    def _selected_paper(self):
        r = self.table.currentRow()
        if r < 0:
            return None
        item = self.table.item(r, 2) or self.table.item(r, 0)
        path = item.data(Qt.UserRole) if item else ""
        if path and path in getattr(self.library, "papers", {}):
            return self.library.papers[path]
        if 0 <= r < len(self._rows):
            return self._rows[r]
        return None

    def _item_collections(self, paper):
        if not paper:
            return []
        path = paper.get("path", "")
        if hasattr(self.library, "collections_for_item"):
            return self.library.collections_for_item(path)
        return sorted([name for name, paths in getattr(self.library, "collections", {}).items()
                       if path in paths], key=str.lower)

    # ---------- actions ----------
    def _search_blob(self, paper):
        return " ".join([
            str(paper.get("title", "")), str(paper.get("author", "")),
            str(paper.get("keywords", "")), str(paper.get("doi", "")),
            str(paper.get("url", "")), str(paper.get("about", "")),
            str(paper.get("entry_type", "")), str(paper.get("year", "")),
            " ".join(paper.get("tags", [])), str(paper.get("filename", "")),
        ])

    def _is_web_resource(self, paper):
        if not paper:
            return False
        if hasattr(self.library, "is_web_resource"):
            return self.library.is_web_resource(paper)
        return paper.get("entry_type") == "web" or str(paper.get("path", "")).startswith("weblink::")

    def _paper_web_link(self, paper):
        if not paper:
            return ""
        url = (paper.get("url") or "").strip()
        if url:
            return self._normalize_web_link(url)
        doi = (paper.get("doi") or "").strip()
        if doi:
            if doi.startswith("http://") or doi.startswith("https://"):
                return doi
            return "https://doi.org/" + quote(doi, safe="/._;():-")
        return ""

    def _normalize_web_link(self, url):
        url = (url or "").strip()
        if not url:
            return ""
        if url.startswith("doi:"):
            url = url[4:].strip()
        if url.startswith("10."):
            return "https://doi.org/" + quote(url, safe="/._;():-")
        if not (url.startswith("http://") or url.startswith("https://")):
            return "https://" + url
        return url

    def _update_details(self):
        p = self._selected_paper()
        if not hasattr(self, "details"):
            return
        if not p:
            self.details.setPlainText("Select one row to see details. Then use the bottom buttons: Open, Collection, Tags, Favorite, or Remove.")
            return
        link = self._paper_web_link(p) or "—"
        preview = p.get("preview", "") or "No preview text available."
        if len(preview) > 520:
            preview = preview[:520].rstrip() + "…"
        if self._is_web_resource(p):
            about = p.get("about", "") or preview
            self.details.setPlainText(
                f"Web resource: {p.get('title','')}\n"
                f"Link: {link}\n"
                f"Tags: {', '.join(p.get('tags', [])) or '—'}\n"
                f"Collections: {', '.join(self._item_collections(p)) or '—'}\n\n"
                f"What this link is about:\n{about or '—'}"
            )
        else:
            self.details.setPlainText(
                f"Title: {p.get('title','')}\n"
                f"Author: {p.get('author','') or '—'}    Year: {p.get('year','') or '—'}    DOI: {p.get('doi','') or '—'}\n"
                f"Web link: {link}\n"
                f"Collections: {', '.join(self._item_collections(p)) or '—'}\n"
                f"File: {p.get('path','')}\n\n"
                f"Preview: {preview}"
            )

    def _import(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, "Import PDF papers", "", "PDF files (*.pdf)")
        if not files:
            return
        coll = None
        if self._current_view[0] == "collection":
            coll = self._current_view[1]
        added = 0
        for f in files:
            if self.library.add_paper(f, collection=coll):
                added += 1
        self.refresh_all()
        QMessageBox.information(
            self, "Import",
            f"Imported {added} new paper(s). "
            f"({len(files) - added} already in library.)")

    def _open_selected(self):
        p = self._selected_paper()
        if not p:
            return
        if self._is_web_resource(p):
            self._open_web_link()
            return
        path = p["path"]
        if not os.path.exists(path):
            QMessageBox.warning(self, "Open",
                                "This file no longer exists at:\n" + path)
            return
        self.library.mark_opened(path)
        self.open_paper_requested.emit(path)

    def _open_web_link(self):
        p = self._selected_paper()
        if not p:
            return
        url = self._paper_web_link(p)
        if not url:
            QMessageBox.information(
                self, "Open web link",
                "No web link or DOI is saved for this item.\n\n"
                "Click 'Add/edit link…' for a PDF, or 'Add web resource…' to save a non-PDF link.")
            return
        QDesktopServices.openUrl(QUrl(url))

    def _edit_web_link(self):
        p = self._selected_paper()
        if not p:
            return
        if self._is_web_resource(p):
            dlg = WebResourceDialog(
                self,
                title=p.get("title", ""),
                url=p.get("url", ""),
                about=p.get("about", "") or p.get("preview", ""),
                tags=", ".join(p.get("tags", [])),
            )
            dlg.setWindowTitle("Edit web resource")
            if dlg.exec() == QDialog.Accepted:
                data = dlg.values()
                if not data["url"]:
                    QMessageBox.warning(self, "Web resource", "Please enter a web link.")
                    return
                if hasattr(self.library, "update_web_resource"):
                    self.library.update_web_resource(
                        p["path"], data["title"], data["url"], data["about"], data["tags"])
                self.refresh_all()
            return
        cur = p.get("url", "") or self._paper_web_link(p)
        text, ok = QInputDialog.getText(
            self, "Add/edit PDF web link",
            "Web link / DOI / publisher page / arXiv / GitHub URL:", text=cur)
        if ok:
            text = text.strip()
            if hasattr(self.library, "set_web_link"):
                self.library.set_web_link(p["path"], text)
            else:
                self.library.update_field(p["path"], "url", self._normalize_web_link(text))
            self.refresh_papers()

    def _add_web_resource(self):
        dlg = WebResourceDialog(self)
        if dlg.exec() != QDialog.Accepted:
            return
        data = dlg.values()
        if not data["url"]:
            QMessageBox.warning(self, "Web resource", "Please enter a web link.")
            return
        coll = self._current_view[1] if self._current_view[0] == "collection" else None
        if hasattr(self.library, "add_web_resource"):
            self.library.add_web_resource(
                data["title"], data["url"], data["about"], data["tags"], collection=coll)
        self.refresh_all()

    def _toggle_fav(self):
        p = self._selected_paper()
        if p:
            self.library.set_favorite(p["path"], not p.get("favorite"))
            self.refresh_papers()

    def _edit_tags(self):
        p = self._selected_paper()
        if not p:
            return
        cur = ", ".join(p.get("tags", []))
        text, ok = QInputDialog.getText(
            self, "Edit tags",
            "Tags (comma-separated):", text=cur)
        if ok:
            self.library.set_tags(p["path"],
                                  [t.strip() for t in text.split(",")])
            self.refresh_all()

    def _preview(self):
        p = self._selected_paper()
        if not p:
            return
        if self._is_web_resource(p):
            QMessageBox.information(
                self, "Web resource — " + p.get("title", ""),
                f"Title: {p.get('title','')}\n"
                f"Web link: {self._paper_web_link(p) or '—'}\n"
                f"Tags: {', '.join(p.get('tags', [])) or '—'}\n"
                f"Collections: {', '.join(self._item_collections(p)) or '—'}\n\n"
                f"What this link is about:\n\n{p.get('about','') or '—'}")
            return
        text = p.get("preview", "") or "(no preview text available)"
        QMessageBox.information(
            self, "Preview — " + p.get("title", ""),
            f"Title: {p.get('title','')}\n"
            f"Author: {p.get('author','')}\n"
            f"Year: {p.get('year','')}   DOI: {p.get('doi','') or '—'}\n"
            f"Web link: {self._paper_web_link(p) or '—'}\n\n"
            f"First-page text:\n\n{text}")

    def _related(self):
        p = self._selected_paper()
        if not p:
            return
        rel = self.library.related(p["path"])
        if not rel:
            QMessageBox.information(
                self, "Related papers",
                "No related papers found.\n\n"
                "Papers are related when they share a tag or an author. "
                "Add tags to your papers to link them.")
            return
        lines = [f"• {r.get('title','')}  ({r.get('year','')})"
                 for r in rel]
        QMessageBox.information(
            self, "Related papers",
            f"{len(rel)} related (shared tag or author):\n\n" + "\n".join(lines))

    def _assign_collection(self):
        p = self._selected_paper()
        if not p:
            QMessageBox.information(self, "Collection", "Please select an item first.")
            return
        dlg = CollectionAssignDialog(
            self,
            item_title=p.get("title", "Selected item"),
            collections=self._collection_names(),
            selected=self._item_collections(p),
        )
        if dlg.exec() != QDialog.Accepted:
            return
        names = dlg.selected_collections()
        if hasattr(self.library, "set_item_collections"):
            self.library.set_item_collections(p["path"], names)
        else:
            # Compatibility fallback for older ResearchLibrary implementations.
            for name in list(getattr(self.library, "collections", {}).keys()):
                self.library.remove_from_collection(name, p["path"])
            for name in names:
                self.library.add_to_collection(name, p["path"])
        if names:
            self._current_view = ("collection", names[0])
        self.refresh_all()

    def _collection_names(self):
        return sorted(getattr(self.library, "collections", {}).keys(), key=str.lower)

    def _choose_collection(self, title="Choose collection", prompt="Collection:"):
        names = self._collection_names()
        if not names:
            QMessageBox.information(self, title, "Please create a collection first.")
            return ""
        current = self._current_view[1] if self._current_view[0] == "collection" else names[0]
        idx = names.index(current) if current in names else 0
        name, ok = QInputDialog.getItem(self, title, prompt, names, idx, False)
        return name.strip() if ok and name else ""

    def _add_selected_to_collection(self):
        p = self._selected_paper()
        if not p:
            QMessageBox.information(self, "Add to collection", "Please select an item first.")
            return
        if self._current_view[0] == "collection":
            coll = self._current_view[1]
        else:
            coll = self._choose_collection("Add to collection", "Add selected item to:")
        if not coll:
            return
        self.library.add_to_collection(coll, p["path"])
        self._current_view = ("collection", coll)
        self.refresh_all()

    def _remove_selected_from_collection(self):
        p = self._selected_paper()
        if not p:
            QMessageBox.information(self, "Remove from collection", "Please select an item first.")
            return
        if self._current_view[0] == "collection":
            coll = self._current_view[1]
        else:
            coll = self._choose_collection("Remove from collection", "Remove selected item from:")
        if not coll:
            return
        self.library.remove_from_collection(coll, p["path"])
        self.refresh_all()

    def _new_collection(self):
        name, ok = QInputDialog.getText(self, "New collection",
                                        "Collection name:")
        if ok and name.strip():
            name = name.strip()
            self.library.create_collection(name)
            self._current_view = ("collection", name)
            self.refresh_all()

    def _selected_collection_name(self):
        item = self.coll_list.currentItem()
        if item is not None:
            text = item.text().strip()
            return text.rsplit("  (", 1)[0].strip() if "  (" in text else text
        if self._current_view[0] == "collection":
            return self._current_view[1]
        return ""

    def _delete_collection(self):
        name = self._selected_collection_name()
        if not name:
            QMessageBox.information(self, "Delete collection", "Please select a collection first.")
            return
        ok = QMessageBox.question(
            self, "Delete collection",
            f"Delete collection '{name}'?\n\nItems stay in the library; only the collection is removed.")
        if ok == QMessageBox.Yes:
            self.library.delete_collection(name)
            self._current_view = ("all", None)
            self.refresh_all()

    def _remove(self):
        p = self._selected_paper()
        if not p:
            return
        ok = QMessageBox.question(
            self, "Remove",
            f"Remove '{p.get('title','')}' from the library?\n"
            "(The original PDF file or web page is NOT deleted.)")
        if ok == QMessageBox.Yes:
            self.library.remove_paper(p["path"])
            self.refresh_all()
