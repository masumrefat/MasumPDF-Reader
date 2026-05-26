"""Reference Collection panel — organized full-screen literature review database."""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton, QLabel,
    QTableWidget, QTableWidgetItem, QHeaderView, QFileDialog, QMessageBox,
    QAbstractItemView, QTextEdit, QSplitter, QFrame, QSizePolicy,
)
from PySide6.QtCore import Qt, Signal


class ReferencePanel(QDialog):
    collection_changed = Signal()

    def __init__(self, collection, parent=None):
        super().__init__(parent)
        self.collection = collection
        self._first_show_done = False
        self.setWindowTitle("Reference Collection")
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

        # Header: simple purpose + count.
        header = QFrame()
        h = QHBoxLayout(header)
        h.setContentsMargins(0, 0, 0, 0)
        title_box = QVBoxLayout()
        title = QLabel("Reference Collection")
        title.setObjectName("PageTitle")
        subtitle = QLabel("Collected references from PDFs. Search, inspect, export, merge, or remove items.")
        subtitle.setObjectName("PageSubtitle")
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        h.addLayout(title_box, 1)
        self.count_lbl = QLabel("")
        self.count_lbl.setObjectName("LogCount")
        h.addWidget(self.count_lbl, 0, Qt.AlignRight | Qt.AlignVCenter)
        lay.addWidget(header)

        # Search + main action row.
        search_row = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search by author, year, title, reference number, or source paper…")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self.refresh)
        search_row.addWidget(self.search, 1)
        self.scholar_btn = QPushButton("Search Scholar")
        self.scholar_btn.setObjectName("PrimaryButton")
        self.save_btn = QPushButton("Export Excel")
        self.load_btn = QPushButton("Import/Merge")
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
        table_title = QLabel("References")
        table_title.setObjectName("SectionTitle")
        table_title_row.addWidget(table_title)
        table_title_row.addStretch(1)
        hint = QLabel("Tip: select a row to preview; double-click to open full text.")
        hint.setObjectName("LogHint")
        table_title_row.addWidget(hint)
        table_lay.addLayout(table_title_row)

        self.table = QTableWidget()
        cols = ["No.", "Authors", "Year", "Title", "Source paper"]
        self.table.setColumnCount(len(cols))
        self.table.setHorizontalHeaderLabels(cols)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setAlternatingRowColors(True)
        self.table.setWordWrap(False)
        self.table.verticalHeader().setDefaultSectionSize(26)
        self.table.verticalHeader().setVisible(False)
        hh = self.table.horizontalHeader()
        hh.setStretchLastSection(False)
        hh.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(1, QHeaderView.Interactive)
        hh.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(3, QHeaderView.Stretch)
        hh.setSectionResizeMode(4, QHeaderView.Interactive)
        self.table.setColumnWidth(1, 220)
        self.table.setColumnWidth(4, 260)
        self.table.doubleClicked.connect(self._show_full)
        self.table.itemSelectionChanged.connect(self._update_preview)
        table_lay.addWidget(self.table, 1)
        splitter.addWidget(table_frame)

        # Preview area for selected reference.
        preview_frame = QFrame()
        preview_lay = QVBoxLayout(preview_frame)
        preview_lay.setContentsMargins(0, 0, 0, 0)
        preview_lay.setSpacing(4)
        preview_title = QLabel("Selected reference preview")
        preview_title.setObjectName("SectionTitle")
        preview_lay.addWidget(preview_title)
        self.preview = QTextEdit()
        self.preview.setReadOnly(True)
        self.preview.setPlaceholderText("Select a reference to preview full reference text here.")
        preview_lay.addWidget(self.preview, 1)
        splitter.addWidget(preview_frame)
        splitter.setSizes([560, 180])
        lay.addWidget(splitter, 1)

        # Organised action bar.
        action_row = QHBoxLayout()
        self.remove_btn = QPushButton("Remove selected")
        self.clear_btn = QPushButton("Clear all")
        self.close_btn = QPushButton("Close")
        self.remove_btn.setToolTip("Remove only the selected reference from this collection.")
        self.clear_btn.setToolTip("Remove every collected reference. Export first if you want to keep a copy.")
        action_row.addWidget(QLabel("Manage:"))
        action_row.addWidget(self.remove_btn)
        action_row.addWidget(self.clear_btn)
        action_row.addStretch(1)
        action_row.addWidget(self.close_btn)
        lay.addLayout(action_row)

        self.scholar_btn.clicked.connect(self._search_scholar)
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
            vals = [e.get("Number", ""), e.get("Authors", ""),
                    e.get("Year", ""), e.get("Title", ""),
                    e.get("Source paper", "")]
            for col, v in enumerate(vals):
                item = QTableWidgetItem(str(v))
                item.setToolTip(str(v))
                if col == 0:
                    item.setData(Qt.UserRole, row)
                self.table.setItem(row, col, item)
        self.table.setSortingEnabled(True)
        self.count_lbl.setText(f"{len(self.collection)} references")
        self._update_preview()
        self.collection_changed.emit()

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

    def _reference_text(self, e):
        if not e:
            return ""
        parts = []
        if e.get("Number"):
            parts.append(f"Reference no.: {e.get('Number')}")
        if e.get("Title"):
            parts.append(f"Title: {e.get('Title')}")
        if e.get("Authors"):
            parts.append(f"Authors: {e.get('Authors')}")
        if e.get("Year"):
            parts.append(f"Year: {e.get('Year')}")
        if e.get("Source paper"):
            parts.append(f"Source paper: {e.get('Source paper')}")
        full = str(e.get("Full reference", "")).strip()
        if full:
            parts.append("\nFull reference:\n" + full)
        return "\n".join(parts)

    def _update_preview(self):
        if not hasattr(self, "preview"):
            return
        e = self._selected_entry()
        self.preview.setPlainText(self._reference_text(e) if e else "")

    def _show_full(self):
        e = self._selected_entry()
        if e:
            box = QMessageBox(self)
            box.setWindowTitle("Reference")
            box.setText(self._reference_text(e))
            scholar = box.addButton("Search on Google Scholar", QMessageBox.ActionRole)
            box.addButton("Close", QMessageBox.RejectRole)
            box.exec()
            if box.clickedButton() is scholar:
                self._open_scholar_for(e)

    def _search_scholar(self):
        e = self._selected_entry()
        if not e:
            QMessageBox.information(
                self, "Google Scholar",
                "Select a reference first, then click Search Scholar.")
            return
        self._open_scholar_for(e)

    def _open_scholar_for(self, entry):
        from core.reference_collection import scholar_url
        from PySide6.QtGui import QDesktopServices
        from PySide6.QtCore import QUrl
        QDesktopServices.openUrl(QUrl(scholar_url(entry)))

    def _save(self):
        if len(self.collection) == 0:
            QMessageBox.information(self, "Export Excel", "No references to export yet.")
            return
        fn, _ = QFileDialog.getSaveFileName(
            self, "Export reference collection", "my_references.xlsx",
            "Excel files (*.xlsx)")
        if not fn:
            return
        if not fn.lower().endswith(".xlsx"):
            fn += ".xlsx"
        try:
            self.collection.save_xlsx(fn)
            QMessageBox.information(self, "Exported",
                                    f"Exported {len(self.collection)} references to:\n{fn}")
        except Exception as e:
            QMessageBox.critical(self, "Export failed", str(e))

    def _load(self):
        fn, _ = QFileDialog.getOpenFileName(
            self, "Import / merge reference collection", "",
            "Excel files (*.xlsx)")
        if not fn:
            return
        try:
            n = self.collection.load_xlsx(fn, merge=True)
            self.refresh()
            QMessageBox.information(
                self, "Imported",
                f"Added {n} reference(s). Total: {len(self.collection)}. Duplicates were skipped.")
        except Exception as e:
            QMessageBox.critical(self, "Import failed", str(e))

    def _remove(self):
        target = self._selected_entry()
        if not target:
            QMessageBox.information(self, "Remove selected", "Select a reference first.")
            return
        for i, e in enumerate(self.collection.entries):
            if e is target:
                self.collection.remove_at(i)
                break
        self.refresh()

    def _clear(self):
        if len(self.collection) == 0:
            return
        ok = QMessageBox.question(
            self, "Clear all references",
            "Remove ALL collected references? Export to Excel first if you want to keep them.")
        if ok == QMessageBox.Yes:
            self.collection.clear()
            self.refresh()
