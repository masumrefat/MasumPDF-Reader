"""Reference Collection panel — view, search, save, and load the literature
review database that grows as the user clicks citations while reading.
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton, QLabel,
    QTableWidget, QTableWidgetItem, QHeaderView, QFileDialog, QMessageBox,
    QAbstractItemView, QCheckBox,
)
from PySide6.QtCore import Qt, Signal


class ReferencePanel(QDialog):
    collection_changed = Signal()

    def __init__(self, collection, parent=None):
        super().__init__(parent)
        self.collection = collection
        self.setWindowTitle("Reference Collection")
        self.resize(880, 560)

        lay = QVBoxLayout(self)

        # top bar: title + count + auto-collect toggle
        top = QHBoxLayout()
        self.title_lbl = QLabel("Your collected references")
        self.title_lbl.setStyleSheet("font-size: 15px; font-weight: 600;")
        top.addWidget(self.title_lbl)
        top.addStretch(1)
        self.count_lbl = QLabel("")
        self.count_lbl.setObjectName("LogCount")
        top.addWidget(self.count_lbl)
        lay.addLayout(top)

        # search row
        srow = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search references (author, title, year…)")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self.refresh)
        srow.addWidget(self.search)
        lay.addLayout(srow)

        # table
        self.table = QTableWidget()
        cols = ["#", "Authors", "Year", "Title", "Source paper"]
        self.table.setColumnCount(len(cols))
        self.table.setHorizontalHeaderLabels(cols)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setAlternatingRowColors(True)
        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(1, QHeaderView.Interactive)
        hh.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(3, QHeaderView.Stretch)
        hh.setSectionResizeMode(4, QHeaderView.Interactive)
        self.table.doubleClicked.connect(self._show_full)
        lay.addWidget(self.table, 1)

        hint = QLabel("Double-click a row to see the full reference text.")
        hint.setObjectName("LogHint")
        hint.setStyleSheet("font-size: 11px;")
        lay.addWidget(hint)

        # buttons
        brow = QHBoxLayout()
        self.scholar_btn = QPushButton("\U0001F50D  Search on Google Scholar")
        self.save_btn = QPushButton("Save to Excel…")
        self.load_btn = QPushButton("Open / Merge Excel…")
        self.remove_btn = QPushButton("Remove selected")
        self.clear_btn = QPushButton("Clear all")
        for b in (self.scholar_btn, self.save_btn, self.load_btn,
                  self.remove_btn, self.clear_btn):
            brow.addWidget(b)
        brow.addStretch(1)
        self.close_btn = QPushButton("Close")
        brow.addWidget(self.close_btn)
        lay.addLayout(brow)

        self.scholar_btn.clicked.connect(self._search_scholar)
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
            vals = [e.get("Number", ""), e.get("Authors", ""),
                    e.get("Year", ""), e.get("Title", ""),
                    e.get("Source paper", "")]
            for col, v in enumerate(vals):
                self.table.setItem(row, col, QTableWidgetItem(str(v)))
        self.count_lbl.setText(f"{len(self.collection)} references")
        self.collection_changed.emit()

    def _show_full(self):
        row = self.table.currentRow()
        if 0 <= row < len(self._filtered):
            e = self._filtered[row]
            from PySide6.QtWidgets import QMessageBox as _MB
            box = _MB(self)
            box.setWindowTitle("Reference")
            box.setText(e.get("Full reference", "") +
                        (f"\n\nFrom: {e.get('Source paper','')}"
                         if e.get("Source paper") else ""))
            scholar = box.addButton("Search on Google Scholar",
                                    _MB.ActionRole)
            box.addButton("Close", _MB.RejectRole)
            box.exec()
            if box.clickedButton() is scholar:
                self._open_scholar_for(e)

    def _search_scholar(self):
        row = self.table.currentRow()
        if row < 0 or row >= len(self._filtered):
            QMessageBox.information(
                self, "Google Scholar",
                "Select a reference first, then click Search on Google Scholar.")
            return
        self._open_scholar_for(self._filtered[row])

    def _open_scholar_for(self, entry):
        from core.reference_collection import scholar_url
        from PySide6.QtGui import QDesktopServices
        from PySide6.QtCore import QUrl
        url = scholar_url(entry)
        QDesktopServices.openUrl(QUrl(url))

    def _save(self):
        if len(self.collection) == 0:
            QMessageBox.information(self, "Save", "No references to save yet.")
            return
        fn, _ = QFileDialog.getSaveFileName(
            self, "Save reference collection", "my_references.xlsx",
            "Excel files (*.xlsx)")
        if not fn:
            return
        if not fn.lower().endswith(".xlsx"):
            fn += ".xlsx"
        try:
            self.collection.save_xlsx(fn)
            QMessageBox.information(self, "Saved",
                                    f"Saved {len(self.collection)} references to:\n{fn}")
        except Exception as e:
            QMessageBox.critical(self, "Save failed", str(e))

    def _load(self):
        fn, _ = QFileDialog.getOpenFileName(
            self, "Open a saved reference collection", "",
            "Excel files (*.xlsx)")
        if not fn:
            return
        try:
            n = self.collection.load_xlsx(fn, merge=True)
            self.refresh()
            QMessageBox.information(
                self, "Loaded",
                f"Added {n} reference(s) from the file. "
                f"Total: {len(self.collection)} (duplicates skipped).")
        except Exception as e:
            QMessageBox.critical(self, "Open failed", str(e))

    def _remove(self):
        row = self.table.currentRow()
        if row < 0 or row >= len(self._filtered):
            return
        target = self._filtered[row]
        # find its real index in the collection
        for i, e in enumerate(self.collection.entries):
            if e is target:
                self.collection.remove_at(i)
                break
        self.refresh()

    def _clear(self):
        if len(self.collection) == 0:
            return
        ok = QMessageBox.question(
            self, "Clear all",
            "Remove ALL collected references? This cannot be undone "
            "(save to Excel first if you want to keep them).")
        if ok == QMessageBox.Yes:
            self.collection.clear()
            self.refresh()
