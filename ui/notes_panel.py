"""Text / Notes Collection panel — review saved snippets with their source,
jump back to where each came from, export to Excel, and reopen later.
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton, QLabel,
    QTableWidget, QTableWidgetItem, QHeaderView, QFileDialog, QMessageBox,
    QAbstractItemView,
)
from PySide6.QtCore import Qt, Signal


class NotesPanel(QDialog):
    jump_requested = Signal(object)   # emits the entry dict to jump to

    def __init__(self, collection, parent=None):
        super().__init__(parent)
        self.collection = collection
        self.setWindowTitle("Text / Notes Collection")
        self.resize(900, 580)

        lay = QVBoxLayout(self)

        top = QHBoxLayout()
        title = QLabel("Saved text snippets & sources")
        title.setStyleSheet("font-size: 15px; font-weight: 600;")
        top.addWidget(title)
        top.addStretch(1)
        self.count_lbl = QLabel("")
        self.count_lbl.setObjectName("LogCount")
        top.addWidget(self.count_lbl)
        lay.addLayout(top)

        self.search = QLineEdit()
        self.search.setPlaceholderText("Search your notes (text, title, author, page…)")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self.refresh)
        lay.addWidget(self.search)

        self.table = QTableWidget()
        cols = ["Snippet", "Paper title", "Author", "Page", "Source"]
        self.table.setColumnCount(len(cols))
        self.table.setHorizontalHeaderLabels(cols)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.setWordWrap(True)
        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.Stretch)
        hh.setSectionResizeMode(1, QHeaderView.Interactive)
        hh.setSectionResizeMode(2, QHeaderView.Interactive)
        hh.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(4, QHeaderView.Interactive)
        self.table.verticalHeader().setDefaultSectionSize(48)
        self.table.doubleClicked.connect(self._show_full)
        lay.addWidget(self.table, 1)

        hint = QLabel("Double-click a row to see the full text. "
                      "Select a row and click 'Jump to source' to go back to it.")
        hint.setObjectName("LogHint")
        hint.setStyleSheet("font-size: 11px;")
        lay.addWidget(hint)

        brow = QHBoxLayout()
        self.jump_btn = QPushButton("\u2192 Jump to source")
        self.scholar_btn = QPushButton("\U0001F50D  Find paper on Scholar")
        self.save_btn = QPushButton("Save to Excel…")
        self.load_btn = QPushButton("Open / Merge Excel…")
        self.remove_btn = QPushButton("Remove selected")
        self.clear_btn = QPushButton("Clear all")
        for b in (self.jump_btn, self.scholar_btn, self.save_btn, self.load_btn,
                  self.remove_btn, self.clear_btn):
            brow.addWidget(b)
        brow.addStretch(1)
        self.close_btn = QPushButton("Close")
        brow.addWidget(self.close_btn)
        lay.addLayout(brow)

        self.jump_btn.clicked.connect(self._jump)
        self.scholar_btn.clicked.connect(self._scholar)
        self.save_btn.clicked.connect(self._save)
        self.load_btn.clicked.connect(self._load)
        self.remove_btn.clicked.connect(self._remove)
        self.clear_btn.clicked.connect(self._clear)
        self.close_btn.clicked.connect(self.hide)

        self._filtered = []
        self.refresh()

    def refresh(self):
        term = self.search.text() if hasattr(self, "search") else ""
        self._filtered = self.collection.search(term)
        self.table.setRowCount(len(self._filtered))
        for row, e in enumerate(self._filtered):
            snippet = str(e.get("Snippet", ""))
            disp = snippet if len(snippet) <= 140 else snippet[:140] + "…"
            vals = [disp, str(e.get("Paper title", "")),
                    str(e.get("Author", "")), str(e.get("Page", "")),
                    str(e.get("Source file", ""))]
            for col, v in enumerate(vals):
                self.table.setItem(row, col, QTableWidgetItem(v))
        self.count_lbl.setText(f"{len(self.collection)} notes")

    def _selected_entry(self):
        row = self.table.currentRow()
        if 0 <= row < len(self._filtered):
            return self._filtered[row]
        return None

    def _show_full(self):
        e = self._selected_entry()
        if not e:
            return
        msg = e.get("Snippet", "")
        extra = []
        if e.get("Paper title"): extra.append("Paper: " + str(e["Paper title"]))
        if e.get("Author"): extra.append("Author: " + str(e["Author"]))
        if e.get("Page"): extra.append("Page: " + str(e["Page"]))
        if e.get("Source file"): extra.append("File: " + str(e["Source file"]))
        if extra:
            msg += "\n\n" + "\n".join(extra)
        QMessageBox.information(self, "Saved note", msg)

    def _jump(self):
        e = self._selected_entry()
        if e:
            self.jump_requested.emit(e)

    def _scholar(self):
        """Search Google Scholar for the paper this note came from."""
        e = self._selected_entry()
        if not e:
            QMessageBox.information(
                self, "Google Scholar",
                "Select a note first.")
            return
        from PySide6.QtGui import QDesktopServices
        from PySide6.QtCore import QUrl
        from urllib.parse import quote_plus
        # search by paper title (+ author) if we have it, else the snippet
        title = str(e.get("Paper title", "")).strip()
        author = str(e.get("Author", "")).strip()
        if title:
            q = title + ((" " + author) if author else "")
        else:
            q = str(e.get("Snippet", ""))[:200]
        url = "https://scholar.google.com/scholar?q=" + quote_plus(q)
        QDesktopServices.openUrl(QUrl(url))

    def _save(self):
        if len(self.collection) == 0:
            QMessageBox.information(self, "Save", "No notes to save yet.")
            return
        fn, _ = QFileDialog.getSaveFileName(
            self, "Save notes collection", "my_notes.xlsx",
            "Excel files (*.xlsx)")
        if not fn:
            return
        if not fn.lower().endswith(".xlsx"):
            fn += ".xlsx"
        try:
            self.collection.save_xlsx(fn)
            QMessageBox.information(self, "Saved",
                                    f"Saved {len(self.collection)} notes to:\n{fn}")
        except Exception as e:
            QMessageBox.critical(self, "Save failed", str(e))

    def _load(self):
        fn, _ = QFileDialog.getOpenFileName(
            self, "Open a saved notes collection", "", "Excel files (*.xlsx)")
        if not fn:
            return
        try:
            n = self.collection.load_xlsx(fn, merge=True)
            self.refresh()
            QMessageBox.information(
                self, "Loaded",
                f"Added {n} note(s). Total: {len(self.collection)} "
                "(duplicates skipped).")
        except Exception as e:
            QMessageBox.critical(self, "Open failed", str(e))

    def _remove(self):
        e = self._selected_entry()
        if not e:
            return
        for i, item in enumerate(self.collection.entries):
            if item is e:
                self.collection.remove_at(i)
                break
        self.refresh()

    def _clear(self):
        if len(self.collection) == 0:
            return
        ok = QMessageBox.question(
            self, "Clear all",
            "Remove ALL saved notes? Save to Excel first if you want to keep them.")
        if ok == QMessageBox.Yes:
            self.collection.clear()
            self.refresh()
