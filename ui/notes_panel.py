"""Text / Notes Collection panel — organised full-screen saved snippet manager."""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton, QLabel,
    QTableWidget, QTableWidgetItem, QHeaderView, QFileDialog, QMessageBox,
    QAbstractItemView, QTextEdit, QSplitter, QFrame,
)
from PySide6.QtCore import Qt, Signal


class NotesPanel(QDialog):
    jump_requested = Signal(object)   # emits the entry dict to jump to

    def __init__(self, collection, parent=None):
        super().__init__(parent)
        self.collection = collection
        self._first_show_done = False
        self.setWindowTitle("Text / Notes Collection")
        self.resize(1200, 760)
        self.setMinimumSize(900, 560)
        self.setSizeGripEnabled(True)

        self.setStyleSheet("""
            QDialog { font-size: 11px; }
            QLabel#PageTitle { font-size: 18px; font-weight: 700; }
            QLabel#PageSubtitle { color: #666; font-size: 11px; }
            QLabel#SectionTitle { font-weight: 700; font-size: 12px; }
            QLabel#LogCount { color: #444; font-weight: 600; }
            QLabel#LogHint { color: #777; font-size: 10px; }
            QPushButton { padding: 5px 9px; min-height: 24px; }
            QPushButton#PrimaryButton { font-weight: 600; }
            QLineEdit { padding: 6px; }
            QTextEdit { font-size: 11px; }
            QTableWidget { font-size: 11px; gridline-color: #ddd; }
            QHeaderView::section { font-weight: 600; padding: 5px; }
        """)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 10, 10, 10)
        lay.setSpacing(8)

        # Header.
        header = QFrame()
        h = QHBoxLayout(header)
        h.setContentsMargins(0, 0, 0, 0)
        title_box = QVBoxLayout()
        title = QLabel("Text / Notes Collection")
        title.setObjectName("PageTitle")
        subtitle = QLabel("Saved text snippets from PDFs. Search, preview, jump back to source, export, or merge notes.")
        subtitle.setObjectName("PageSubtitle")
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        h.addLayout(title_box, 1)
        self.count_lbl = QLabel("")
        self.count_lbl.setObjectName("LogCount")
        h.addWidget(self.count_lbl, 0, Qt.AlignRight | Qt.AlignVCenter)
        lay.addWidget(header)

        # Search + primary actions.
        search_row = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search notes by snippet, paper title, author, page, or source file…")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self.refresh)
        search_row.addWidget(self.search, 1)
        self.jump_btn = QPushButton("Jump to source")
        self.jump_btn.setObjectName("PrimaryButton")
        self.scholar_btn = QPushButton("Search Scholar")
        self.save_btn = QPushButton("Export Excel")
        self.load_btn = QPushButton("Import/Merge")
        search_row.addWidget(self.jump_btn)
        search_row.addWidget(self.scholar_btn)
        search_row.addWidget(self.save_btn)
        search_row.addWidget(self.load_btn)
        lay.addLayout(search_row)

        splitter = QSplitter(Qt.Vertical)
        splitter.setChildrenCollapsible(False)

        # Table area.
        table_frame = QFrame()
        table_lay = QVBoxLayout(table_frame)
        table_lay.setContentsMargins(0, 0, 0, 0)
        table_lay.setSpacing(4)
        table_title_row = QHBoxLayout()
        table_title = QLabel("Saved notes")
        table_title.setObjectName("SectionTitle")
        table_title_row.addWidget(table_title)
        table_title_row.addStretch(1)
        hint = QLabel("Tip: select a row to preview; double-click to open full note.")
        hint.setObjectName("LogHint")
        table_title_row.addWidget(hint)
        table_lay.addLayout(table_title_row)

        self.table = QTableWidget()
        cols = ["Snippet", "Paper title", "Author", "Page", "Source file"]
        self.table.setColumnCount(len(cols))
        self.table.setHorizontalHeaderLabels(cols)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setAlternatingRowColors(True)
        self.table.setWordWrap(False)
        self.table.verticalHeader().setDefaultSectionSize(30)
        self.table.verticalHeader().setVisible(False)
        hh = self.table.horizontalHeader()
        hh.setStretchLastSection(False)
        hh.setSectionResizeMode(0, QHeaderView.Stretch)
        hh.setSectionResizeMode(1, QHeaderView.Interactive)
        hh.setSectionResizeMode(2, QHeaderView.Interactive)
        hh.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(4, QHeaderView.Interactive)
        self.table.setColumnWidth(1, 260)
        self.table.setColumnWidth(2, 180)
        self.table.setColumnWidth(4, 260)
        self.table.doubleClicked.connect(self._show_full)
        self.table.itemSelectionChanged.connect(self._update_preview)
        table_lay.addWidget(self.table, 1)
        splitter.addWidget(table_frame)

        # Preview area.
        preview_frame = QFrame()
        preview_lay = QVBoxLayout(preview_frame)
        preview_lay.setContentsMargins(0, 0, 0, 0)
        preview_lay.setSpacing(4)
        preview_title = QLabel("Selected note preview")
        preview_title.setObjectName("SectionTitle")
        preview_lay.addWidget(preview_title)
        self.preview = QTextEdit()
        self.preview.setReadOnly(True)
        self.preview.setPlaceholderText("Select a note to preview full snippet and source information here.")
        preview_lay.addWidget(self.preview, 1)
        splitter.addWidget(preview_frame)
        splitter.setSizes([540, 210])
        lay.addWidget(splitter, 1)

        # Manage row.
        action_row = QHBoxLayout()
        self.remove_btn = QPushButton("Remove selected")
        self.clear_btn = QPushButton("Clear all")
        self.close_btn = QPushButton("Close")
        self.jump_btn.setToolTip("Go back to the page/location where this note was collected.")
        self.scholar_btn.setToolTip("Search the source paper or snippet on Google Scholar.")
        self.remove_btn.setToolTip("Remove only the selected note from this collection.")
        self.clear_btn.setToolTip("Remove every saved note. Export first if you want to keep a copy.")
        action_row.addWidget(QLabel("Manage:"))
        action_row.addWidget(self.remove_btn)
        action_row.addWidget(self.clear_btn)
        action_row.addStretch(1)
        action_row.addWidget(self.close_btn)
        lay.addLayout(action_row)

        self.jump_btn.clicked.connect(self._jump)
        self.scholar_btn.clicked.connect(self._scholar)
        self.save_btn.clicked.connect(self._save)
        self.load_btn.clicked.connect(self._load)
        self.remove_btn.clicked.connect(self._remove)
        self.clear_btn.clicked.connect(self._clear)
        self.close_btn.clicked.connect(self.hide)

        self._filtered = []
        self.refresh()

    def showEvent(self, event):
        super().showEvent(event)
        if not self._first_show_done:
            self._first_show_done = True
            self.showMaximized()

    def refresh(self):
        term = self.search.text() if hasattr(self, "search") else ""
        self._filtered = self.collection.search(term)
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(self._filtered))
        for row, e in enumerate(self._filtered):
            snippet = str(e.get("Snippet", ""))
            disp = snippet if len(snippet) <= 180 else snippet[:180] + "…"
            vals = [disp, str(e.get("Paper title", "")),
                    str(e.get("Author", "")), str(e.get("Page", "")),
                    str(e.get("Source file", ""))]
            for col, v in enumerate(vals):
                item = QTableWidgetItem(v)
                item.setToolTip(v)
                if col == 0:
                    item.setData(Qt.UserRole, row)
                self.table.setItem(row, col, item)
        self.table.setSortingEnabled(True)
        self.count_lbl.setText(f"{len(self.collection)} notes")
        self._update_preview()

    def _selected_entry(self):
        row = self.table.currentRow()
        if row < 0:
            return None
        item = self.table.item(row, 0)
        idx = item.data(Qt.UserRole) if item else row
        try:
            idx = int(idx)
        except (TypeError, ValueError):
            return None
        if 0 <= idx < len(self._filtered):
            return self._filtered[idx]
        return None

    def _note_text(self, e):
        if not e:
            return ""
        parts = []
        snippet = str(e.get("Snippet", "")).strip()
        if snippet:
            parts.append("Saved text:\n" + snippet)
        meta = []
        if e.get("Paper title"):
            meta.append("Paper: " + str(e["Paper title"]))
        if e.get("Author"):
            meta.append("Author: " + str(e["Author"]))
        if e.get("Page"):
            meta.append("Page: " + str(e["Page"]))
        if e.get("Source file"):
            meta.append("File: " + str(e["Source file"]))
        if meta:
            parts.append("Source information:\n" + "\n".join(meta))
        return "\n\n".join(parts)

    def _update_preview(self):
        if not hasattr(self, "preview"):
            return
        e = self._selected_entry()
        self.preview.setPlainText(self._note_text(e) if e else "")

    def _show_full(self):
        e = self._selected_entry()
        if not e:
            return
        QMessageBox.information(self, "Saved note", self._note_text(e))

    def _jump(self):
        e = self._selected_entry()
        if e:
            self.jump_requested.emit(e)
        else:
            QMessageBox.information(self, "Jump to source", "Select a note first.")

    def _scholar(self):
        """Search Google Scholar for the paper this note came from."""
        e = self._selected_entry()
        if not e:
            QMessageBox.information(self, "Google Scholar", "Select a note first.")
            return
        from PySide6.QtGui import QDesktopServices
        from PySide6.QtCore import QUrl
        from urllib.parse import quote_plus
        title = str(e.get("Paper title", "")).strip()
        author = str(e.get("Author", "")).strip()
        if title:
            q = title + ((" " + author) if author else "")
        else:
            q = str(e.get("Snippet", ""))[:200]
        QDesktopServices.openUrl(QUrl("https://scholar.google.com/scholar?q=" + quote_plus(q)))

    def _save(self):
        if len(self.collection) == 0:
            QMessageBox.information(self, "Export Excel", "No notes to export yet.")
            return
        fn, _ = QFileDialog.getSaveFileName(
            self, "Export notes collection", "my_notes.xlsx",
            "Excel files (*.xlsx)")
        if not fn:
            return
        if not fn.lower().endswith(".xlsx"):
            fn += ".xlsx"
        try:
            self.collection.save_xlsx(fn)
            QMessageBox.information(self, "Exported",
                                    f"Exported {len(self.collection)} notes to:\n{fn}")
        except Exception as e:
            QMessageBox.critical(self, "Export failed", str(e))

    def _load(self):
        fn, _ = QFileDialog.getOpenFileName(
            self, "Import / merge notes collection", "", "Excel files (*.xlsx)")
        if not fn:
            return
        try:
            n = self.collection.load_xlsx(fn, merge=True)
            self.refresh()
            QMessageBox.information(
                self, "Imported",
                f"Added {n} note(s). Total: {len(self.collection)}. Duplicates were skipped.")
        except Exception as e:
            QMessageBox.critical(self, "Import failed", str(e))

    def _remove(self):
        e = self._selected_entry()
        if not e:
            QMessageBox.information(self, "Remove selected", "Select a note first.")
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
            self, "Clear all notes",
            "Remove ALL saved notes? Export to Excel first if you want to keep them.")
        if ok == QMessageBox.Yes:
            self.collection.clear()
            self.refresh()
