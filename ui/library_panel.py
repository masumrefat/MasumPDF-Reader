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
)
from PySide6.QtCore import Qt, Signal, QUrl, QSize
from PySide6.QtGui import QDesktopServices
from ui.icons import make_icon

LIBRARY_ICON_SIZE = 18


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


class LibraryPanel(QDialog):
    open_paper_requested = Signal(str)   # emits a pdf path to open

    def __init__(self, library, parent=None):
        super().__init__(parent)
        self.library = library
        self.setWindowTitle("Research Library")
        self.resize(1280, 780)
        self.setMinimumSize(980, 620)
        self._current_view = ("all", None)  # (kind, value)

        is_dark = bool(parent and hasattr(parent, "_is_dark_mode") and parent._is_dark_mode())
        self.setStyleSheet("""
            QDialog { background: #0B101A; color: #F8FAFC; }
            QLabel#LibraryTitle { font-size: 28px; font-weight: 900; color: #F8FAFC; }
            QLabel#LibrarySubtitle { color: #CBD5E1; font-size: 13px; }
            QLabel#StatCard { background: #151F2F; border: 1px solid #263244; border-radius: 16px; padding: 12px 16px; color: #F8FAFC; font-weight: 800; min-width: 110px; }
            QLineEdit { background: #0E1624; border: 1px solid #263244; border-radius: 16px; padding: 12px 14px; font-size: 14px; color: #F8FAFC; selection-background-color: #3B82F6; selection-color: white; }
            QLineEdit:focus { border: 1px solid #3B82F6; }
            QListWidget, QTableWidget, QTextEdit { background: #111827; border: 1px solid #263244; border-radius: 16px; color: #F8FAFC; }
            QListWidget::item { padding: 10px; border-radius: 10px; color: #F8FAFC; }
            QListWidget::item:hover { background: #1B2C47; }
            QListWidget::item:selected { background: #1E3A8A; color: #FFFFFF; font-weight: 700; }
            QTableWidget { gridline-color: #202B3A; selection-background-color: #1E3A8A; selection-color: #FFFFFF; alternate-background-color: #151F2F; }
            QTableWidget::item { padding: 8px; color: #F8FAFC; }
            QHeaderView::section { background: #121B2B; border: 0; border-bottom: 1px solid #263244; padding: 10px; font-weight: 900; color: #E5E7EB; }
            QTextEdit { padding: 10px; line-height: 1.35; }
            QPushButton { background: #151F2F; border: 1px solid #263244; border-radius: 12px; padding: 10px 16px; font-weight: 800; min-height: 30px; color: #F8FAFC; }
            QPushButton:hover { background: #1B2C47; border-color: #3B82F6; }
            QPushButton#PrimaryButton { background: #3B82F6; color: white; border: 1px solid #3B82F6; }
            QPushButton#PrimaryButton:hover { background: #2563EB; }
            QPushButton#DangerButton { color: #FCA5A5; border-color: #7F1D1D; background: #2A1416; }
            QPushButton#DangerButton:hover { background: #3A171A; }
        """ if is_dark else """
            QDialog { background: #f6f8fc; color: #172033; }
            QLabel#LibraryTitle { font-size: 28px; font-weight: 900; color: #0f172a; }
            QLabel#LibrarySubtitle { color: #64748b; font-size: 13px; }
            QLabel#StatCard { background: #ffffff; border: 1px solid #e1e7f0; border-radius: 16px; padding: 12px 16px; color: #334155; font-weight: 800; min-width: 110px; }
            QLineEdit { background: #ffffff; border: 1px solid #d5dce8; border-radius: 16px; padding: 12px 14px; font-size: 14px; color: #172033; }
            QLineEdit:focus { border: 1px solid #2563eb; }
            QListWidget, QTableWidget, QTextEdit { background: #ffffff; border: 1px solid #e1e7f0; border-radius: 16px; color: #172033; }
            QListWidget::item { padding: 10px; border-radius: 10px; }
            QListWidget::item:hover { background: #f2f6ff; }
            QListWidget::item:selected { background: #e8f0ff; color: #123a75; font-weight: 700; }
            QTableWidget { gridline-color: #eef2f7; selection-background-color: #e8f0ff; selection-color: #0f172a; alternate-background-color: #f8fafc; }
            QTableWidget::item { padding: 8px; }
            QHeaderView::section { background: #f8fafc; border: 0; border-bottom: 1px solid #e1e7f0; padding: 10px; font-weight: 900; color: #475569; }
            QTextEdit { padding: 10px; line-height: 1.35; }
            QPushButton { background: #ffffff; border: 1px solid #d5dce8; border-radius: 12px; padding: 10px 16px; font-weight: 800; min-height: 30px; color: #1f2937; }
            QPushButton:hover { background: #f2f6ff; border-color: #bcd0ff; }
            QPushButton#PrimaryButton { background: #2563eb; color: white; border: 1px solid #2563eb; }
            QPushButton#PrimaryButton:hover { background: #1d4ed8; }
            QPushButton#DangerButton { color: #b42318; border-color: #f3c2bd; background: #fff8f7; }
            QPushButton#DangerButton:hover { background: #ffedea; }
        """)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(22, 20, 22, 20)
        outer.setSpacing(14)

        # top: title + useful stats
        top = QHBoxLayout()
        title_box = QVBoxLayout()
        t = QLabel("Research Library")
        t.setObjectName("LibraryTitle")
        sub = QLabel("A clean workspace for papers plus useful web links, DOI/publisher pages, datasets, code, tags, notes, and fast reopening.")
        sub.setObjectName("LibrarySubtitle")
        title_box.addWidget(t)
        title_box.addWidget(sub)
        top.addLayout(title_box)
        top.addStretch(1)
        self.count_lbl = QLabel("")
        self.count_lbl.setObjectName("StatCard")
        self.fav_count_lbl = QLabel("")
        self.fav_count_lbl.setObjectName("StatCard")
        self.link_count_lbl = QLabel("")
        self.link_count_lbl.setObjectName("StatCard")
        top.addWidget(self.count_lbl)
        top.addWidget(self.fav_count_lbl)
        top.addWidget(self.link_count_lbl)
        outer.addLayout(top)

        self.search = QLineEdit()
        self.search.setPlaceholderText(
            "Search papers and web resources by title, about/notes, author, year, tags, DOI, web link, filename, or keyword…")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self.refresh_papers)
        outer.addWidget(self.search)

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
        self.nav.setFixedHeight(138)
        lv.addWidget(self.nav)

        lv.addWidget(self._small_label("COLLECTIONS"))
        self.coll_list = QListWidget()
        self.coll_list.itemClicked.connect(self._on_collection)
        lv.addWidget(self.coll_list, 1)
        crow = QHBoxLayout()
        add_coll = QPushButton("+ New collection")
        add_coll.clicked.connect(self._new_collection)
        crow.addWidget(add_coll)
        lv.addLayout(crow)

        lv.addWidget(self._small_label("TAGS"))
        self.tag_list = QListWidget()
        self.tag_list.itemClicked.connect(self._on_tag)
        self.tag_list.setFixedHeight(160)
        lv.addWidget(self.tag_list)

        split.addWidget(left)

        # ---- right: paper table ----
        right = QWidget()
        rv = QVBoxLayout(right)
        rv.setContentsMargins(0, 0, 0, 0)
        rv.setSpacing(8)
        self.view_lbl = QLabel("All papers")
        self.view_lbl.setStyleSheet("font-weight: 900; font-size: 16px; padding: 2px 0;")
        rv.addWidget(self.view_lbl)

        self.table = QTableWidget()
        cols = ["Fav", "Type", "Title / resource", "Author", "Year", "Tags", "Web"]
        self.table.setColumnCount(len(cols))
        self.table.setHorizontalHeaderLabels(cols)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(42)
        self.table.setWordWrap(False)
        self.table.setSortingEnabled(True)
        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(2, QHeaderView.Stretch)
        hh.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(5, QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(6, QHeaderView.ResizeToContents)
        self.table.doubleClicked.connect(self._open_selected)
        self.table.itemSelectionChanged.connect(self._update_details)
        rv.addWidget(self.table, 1)

        self.details = QTextEdit()
        self.details.setReadOnly(True)
        self.details.setFixedHeight(150)
        self.details.setPlaceholderText(
            "Select an item to see DOI, web link, file path, notes/about, and preview.")
        rv.addWidget(self.details)

        hint = QLabel(
            "Double-click PDFs to open the file. Double-click web resources to open the saved link. Use Add web resource for non-PDF links.")
        hint.setStyleSheet("font-size: 12px; padding: 2px 0;")
        rv.addWidget(hint)

        split.addWidget(right)
        split.setSizes([300, 980])

        # ---- action toolbar ----
        # Keep actions readable on small screens: buttons use clear short labels,
        # full explanations are in tooltips, and the whole row can scroll horizontally
        # instead of squeezing/cutting text.
        action_scroll = QScrollArea()
        action_scroll.setWidgetResizable(True)
        action_scroll.setFrameShape(QScrollArea.NoFrame)
        action_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        action_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        action_scroll.setFixedHeight(66)
        action_scroll.setStyleSheet("QScrollArea { background: transparent; border: 0; }")

        action_bar = QWidget()
        brow = QHBoxLayout(action_bar)
        brow.setContentsMargins(0, 4, 0, 4)
        brow.setSpacing(10)

        self.import_btn = QPushButton("Import PDFs")
        self.import_btn.setIcon(make_icon("import", "#1F2937", LIBRARY_ICON_SIZE))
        self.import_btn.setObjectName("PrimaryButton")
        self.import_btn.setToolTip("Import one or more PDF files into the Research Library")
        self.open_btn = QPushButton("Open PDF")
        self.open_btn.setIcon(make_icon("pdf", "#1F2937", LIBRARY_ICON_SIZE))
        self.open_btn.setToolTip("Open the selected PDF item")
        self.web_btn = QPushButton("Open Link")
        self.web_btn.setIcon(make_icon("web", "#1F2937", LIBRARY_ICON_SIZE))
        self.web_btn.setToolTip("Open the saved web link for the selected item")
        self.add_link_btn = QPushButton("Edit Link")
        self.add_link_btn.setIcon(make_icon("link", "#1F2937", LIBRARY_ICON_SIZE))
        self.add_link_btn.setToolTip("Add or edit a DOI, publisher URL, GitHub URL, dataset URL, or other web link")
        self.add_resource_btn = QPushButton("Add Web")
        self.add_resource_btn.setIcon(make_icon("web", "#1F2937", LIBRARY_ICON_SIZE))
        self.add_resource_btn.setToolTip("Add a web resource that is not a PDF, and describe what the link is about")
        self.fav_btn = QPushButton("Favorite")
        self.fav_btn.setIcon(make_icon("favorite", "#1F2937", LIBRARY_ICON_SIZE))
        self.fav_btn.setToolTip("Mark or unmark the selected item as a favorite")
        self.tag_btn = QPushButton("Tags")
        self.tag_btn.setIcon(make_icon("tag", "#1F2937", LIBRARY_ICON_SIZE))
        self.tag_btn.setToolTip("Add or edit tags for the selected item")
        self.preview_btn = QPushButton("Preview")
        self.preview_btn.setIcon(make_icon("eye", "#1F2937", LIBRARY_ICON_SIZE))
        self.preview_btn.setToolTip("Preview title, DOI, web link, notes/about, path, and extracted text")
        self.related_btn = QPushButton("Related")
        self.related_btn.setIcon(make_icon("related", "#1F2937", LIBRARY_ICON_SIZE))
        self.related_btn.setToolTip("Find items with similar tags or keywords")
        self.remove_btn = QPushButton("Remove")
        self.remove_btn.setIcon(make_icon("remove", "#1F2937", LIBRARY_ICON_SIZE))
        self.remove_btn.setToolTip("Remove the selected item from the library database. The PDF file itself is not deleted.")
        self.remove_btn.setObjectName("DangerButton")
        self.close_btn = QPushButton("Close")
        self.close_btn.setIcon(make_icon("close", "#1F2937", LIBRARY_ICON_SIZE))
        self.close_btn.setToolTip("Close the Research Library window")

        button_widths = {
            self.import_btn: 138,
            self.add_resource_btn: 124,
            self.open_btn: 124,
            self.web_btn: 124,
            self.add_link_btn: 124,
            self.fav_btn: 116,
            self.tag_btn: 96,
            self.preview_btn: 108,
            self.related_btn: 110,
            self.remove_btn: 104,
            self.close_btn: 92,
        }
        for b, w in button_widths.items():
            b.setMinimumWidth(w)
            b.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
            b.setCursor(Qt.PointingHandCursor)
            b.setIconSize(QSize(LIBRARY_ICON_SIZE, LIBRARY_ICON_SIZE))

        for b in (self.import_btn, self.add_resource_btn, self.open_btn, self.web_btn, self.add_link_btn,
                  self.fav_btn, self.tag_btn, self.preview_btn,
                  self.related_btn, self.remove_btn, self.close_btn):
            brow.addWidget(b)
        brow.addStretch(1)
        action_scroll.setWidget(action_bar)
        outer.addWidget(action_scroll)

        self.import_btn.clicked.connect(self._import)
        self.open_btn.clicked.connect(self._open_selected)
        self.web_btn.clicked.connect(self._open_web_link)
        self.add_link_btn.clicked.connect(self._edit_web_link)
        self.add_resource_btn.clicked.connect(self._add_web_resource)
        self.fav_btn.clicked.connect(self._toggle_fav)
        self.tag_btn.clicked.connect(self._edit_tags)
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
            vals = ["", "Web" if self._is_web_resource(p) else "PDF", p.get("title", ""), p.get("author", ""),
                    str(p.get("year", "")), ", ".join(p.get("tags", [])), ""]
            for c, v in enumerate(vals):
                item = QTableWidgetItem(str(v))
                if c == 0 and p.get("favorite"):
                    item.setIcon(make_icon("favorite", "#1F2937", 16))
                if c == 1:
                    item.setIcon(make_icon("web" if self._is_web_resource(p) else "pdf", "#1F2937", 16))
                if c == 6 and self._paper_web_link(p):
                    item.setIcon(make_icon("link", "#1F2937", 16))
                    item.setText("Yes")
                if c in (0, 1, 4, 6):
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
        name = item.text().split("  ")[1] if "  " in item.text() else item.text()
        name = name.rsplit("  (", 1)[0].strip()
        self._current_view = ("collection", name)
        self.refresh_papers()

    def _on_tag(self, item):
        tag = item.text().strip()
        self._current_view = ("tag", tag)
        self.refresh_papers()

    # ---------- selection ----------
    def _selected_paper(self):
        r = self.table.currentRow()
        if 0 <= r < len(self._rows):
            return self._rows[r]
        return None

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
            self.details.setPlainText("Select an item to see DOI, web link, file path, notes/about, and preview.")
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
                f"Tags: {', '.join(p.get('tags', [])) or '—'}\n\n"
                f"What this link is about:\n{about or '—'}"
            )
        else:
            self.details.setPlainText(
                f"Title: {p.get('title','')}\n"
                f"Author: {p.get('author','') or '—'}    Year: {p.get('year','') or '—'}    DOI: {p.get('doi','') or '—'}\n"
                f"Web link: {link}\n"
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
                f"Tags: {', '.join(p.get('tags', [])) or '—'}\n\n"
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

    def _new_collection(self):
        name, ok = QInputDialog.getText(self, "New collection",
                                        "Collection name:")
        if ok and name.strip():
            self.library.create_collection(name.strip())
            self._refresh_collections()

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
