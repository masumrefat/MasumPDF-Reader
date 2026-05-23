"""Research Library panel — browse, search, organize, and open your papers.

Left side: collections, favorites, recent, tags (click to filter).
Right side: the paper list + search, with import/open/tag/favorite actions.
"""

import os
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton, QLabel,
    QTableWidget, QTableWidgetItem, QHeaderView, QFileDialog, QMessageBox,
    QAbstractItemView, QListWidget, QListWidgetItem, QSplitter, QWidget,
    QInputDialog, QComboBox,
)
from PySide6.QtCore import Qt, Signal


class LibraryPanel(QDialog):
    open_paper_requested = Signal(str)   # emits a pdf path to open

    def __init__(self, library, parent=None):
        super().__init__(parent)
        self.library = library
        self.setWindowTitle("Research Library")
        self.resize(1040, 640)
        self._current_view = ("all", None)  # (kind, value)

        outer = QVBoxLayout(self)

        # top: title + search
        top = QHBoxLayout()
        t = QLabel("My Research Library")
        t.setStyleSheet("font-size: 16px; font-weight: 700;")
        top.addWidget(t)
        top.addStretch(1)
        self.count_lbl = QLabel("")
        self.count_lbl.setStyleSheet("color:#666;")
        top.addWidget(self.count_lbl)
        outer.addLayout(top)

        self.search = QLineEdit()
        self.search.setPlaceholderText(
            "\U0001F50D  Search by title, author, keyword, DOI, or year…")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self.refresh_papers)
        outer.addWidget(self.search)

        split = QSplitter(Qt.Horizontal)
        outer.addWidget(split, 1)

        # ---- left: navigation ----
        left = QWidget()
        lv = QVBoxLayout(left)
        lv.setContentsMargins(0, 0, 0, 0)
        lv.addWidget(self._small_label("LIBRARY"))
        self.nav = QListWidget()
        self.nav.addItem("\U0001F4DA  All papers")
        self.nav.addItem("\u2B50  Favorites")
        self.nav.addItem("\U0001F551  Recent")
        self.nav.currentRowChanged.connect(self._on_nav)
        self.nav.setFixedHeight(96)
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
        self.tag_list.setFixedHeight(130)
        lv.addWidget(self.tag_list)

        split.addWidget(left)

        # ---- right: paper table ----
        right = QWidget()
        rv = QVBoxLayout(right)
        rv.setContentsMargins(0, 0, 0, 0)
        self.view_lbl = QLabel("All papers")
        self.view_lbl.setStyleSheet("font-weight: 600; color:#333;")
        rv.addWidget(self.view_lbl)

        self.table = QTableWidget()
        cols = ["", "Title", "Author", "Year", "Tags"]
        self.table.setColumnCount(len(cols))
        self.table.setHorizontalHeaderLabels(cols)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setAlternatingRowColors(True)
        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(1, QHeaderView.Stretch)
        hh.setSectionResizeMode(2, QHeaderView.Interactive)
        hh.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(4, QHeaderView.Interactive)
        self.table.doubleClicked.connect(self._open_selected)
        rv.addWidget(self.table, 1)

        hint = QLabel("Double-click a paper to open it. "
                      "Select one to tag, favorite, preview, or see related papers.")
        hint.setStyleSheet("color:#888; font-size: 11px;")
        rv.addWidget(hint)

        split.addWidget(right)
        split.setSizes([260, 760])

        # ---- buttons ----
        brow = QHBoxLayout()
        self.import_btn = QPushButton("Import PDFs…")
        self.open_btn = QPushButton("Open")
        self.fav_btn = QPushButton("Toggle favorite")
        self.tag_btn = QPushButton("Edit tags…")
        self.preview_btn = QPushButton("Preview")
        self.related_btn = QPushButton("Related papers")
        self.remove_btn = QPushButton("Remove")
        for b in (self.import_btn, self.open_btn, self.fav_btn, self.tag_btn,
                  self.preview_btn, self.related_btn, self.remove_btn):
            brow.addWidget(b)
        brow.addStretch(1)
        self.close_btn = QPushButton("Close")
        brow.addWidget(self.close_btn)
        outer.addLayout(brow)

        self.import_btn.clicked.connect(self._import)
        self.open_btn.clicked.connect(self._open_selected)
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
        l.setStyleSheet("color:#888; font-size:10px; font-weight:700;"
                        " letter-spacing:1px; margin-top:6px;")
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
            self.coll_list.addItem(f"\U0001F4C1  {name}  ({n})")

    def _refresh_tags(self):
        self.tag_list.clear()
        for tag in self.library.all_tags():
            self.tag_list.addItem(f"\U0001F3F7  {tag}")

    def refresh_papers(self):
        kind, value = self._current_view
        term = self.search.text()
        if kind == "favorites":
            papers = self.library.favorites()
            if term:
                papers = [p for p in papers if term.lower() in
                          (p.get("title", "") + p.get("author", "")).lower()]
            self.view_lbl.setText("\u2B50 Favorites")
        elif kind == "recent":
            papers = self.library.recent(20)
            self.view_lbl.setText("\U0001F551 Recently opened")
        elif kind == "collection":
            papers = self.library.search(term=term, collection=value)
            self.view_lbl.setText(f"\U0001F4C1 {value}")
        elif kind == "tag":
            papers = self.library.search(term=term, tag=value)
            self.view_lbl.setText(f"\U0001F3F7 {value}")
        else:
            papers = self.library.search(term=term)
            self.view_lbl.setText("All papers")

        self._rows = papers
        self.table.setRowCount(len(papers))
        for r, p in enumerate(papers):
            star = "\u2B50" if p.get("favorite") else ""
            vals = [star, p.get("title", ""), p.get("author", ""),
                    str(p.get("year", "")), ", ".join(p.get("tags", []))]
            for c, v in enumerate(vals):
                self.table.setItem(r, c, QTableWidgetItem(str(v)))
        self.count_lbl.setText(f"{len(self.library.all_papers())} papers total")

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
        # strip the count suffix "(n)"
        name = name.rsplit("  (", 1)[0].strip()
        self._current_view = ("collection", name)
        self.refresh_papers()

    def _on_tag(self, item):
        tag = item.text().replace("\U0001F3F7", "").strip()
        self._current_view = ("tag", tag)
        self.refresh_papers()

    # ---------- selection ----------
    def _selected_paper(self):
        r = self.table.currentRow()
        if 0 <= r < len(self._rows):
            return self._rows[r]
        return None

    # ---------- actions ----------
    def _import(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, "Import PDF papers", "", "PDF files (*.pdf)")
        if not files:
            return
        # offer to add to current collection if viewing one
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
        path = p["path"]
        if not os.path.exists(path):
            QMessageBox.warning(self, "Open",
                                "This file no longer exists at:\n" + path)
            return
        self.library.mark_opened(path)
        self.open_paper_requested.emit(path)

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
        text = p.get("preview", "") or "(no preview text available)"
        QMessageBox.information(
            self, "Preview — " + p.get("title", ""),
            f"Title: {p.get('title','')}\n"
            f"Author: {p.get('author','')}\n"
            f"Year: {p.get('year','')}   DOI: {p.get('doi','') or '—'}\n\n"
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
        lines = [f"\u2022 {r.get('title','')}  ({r.get('year','')})"
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
            "(The PDF file itself is NOT deleted.)")
        if ok == QMessageBox.Yes:
            self.library.remove_paper(p["path"])
            self.refresh_all()
