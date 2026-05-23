"""Sidebars: page thumbnails, document outline, comments list."""

from PySide6.QtWidgets import (
    QWidget, QListWidget, QListWidgetItem, QVBoxLayout, QTabWidget,
    QTreeWidget, QTreeWidgetItem, QLabel, QFrame, QHBoxLayout, QPushButton,
)
from PySide6.QtCore import Qt, Signal, QSize, QThread
from PySide6.QtGui import QIcon, QPixmap

from utils.constants import THUMBNAIL_WIDTH


class ThumbnailListWidget(QListWidget):
    """Vertical list of page thumbnails."""

    page_selected = Signal(int)   # 0-indexed

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setViewMode(QListWidget.IconMode)
        self.setFlow(QListWidget.TopToBottom)
        self.setMovement(QListWidget.Static)
        self.setIconSize(QSize(THUMBNAIL_WIDTH, int(THUMBNAIL_WIDTH * 1.4)))
        self.setSpacing(8)
        self.setUniformItemSizes(False)
        self.setResizeMode(QListWidget.Adjust)
        self.setWordWrap(True)
        self.setSelectionMode(QListWidget.SingleSelection)
        self.itemClicked.connect(self._on_item)

    def populate(self, pdf_document):
        self.clear()
        if not pdf_document:
            return
        for i in range(pdf_document.page_count):
            item = QListWidgetItem()
            item.setText(f"{i + 1}")
            item.setTextAlignment(Qt.AlignHCenter)
            try:
                pix = pdf_document.render_thumbnail(i, width=THUMBNAIL_WIDTH)
                item.setIcon(QIcon(pix))
                item.setSizeHint(QSize(THUMBNAIL_WIDTH + 16,
                                       int(THUMBNAIL_WIDTH * 1.4) + 28))
            except Exception:
                pass
            item.setData(Qt.UserRole, i)
            self.addItem(item)

    def _on_item(self, item):
        idx = item.data(Qt.UserRole)
        if idx is not None:
            self.page_selected.emit(int(idx))

    def highlight_page(self, page_index: int):
        for i in range(self.count()):
            it = self.item(i)
            if int(it.data(Qt.UserRole)) == page_index:
                self.setCurrentItem(it)
                self.scrollToItem(it, QListWidget.PositionAtCenter)
                break


class OutlineTree(QTreeWidget):
    """Document outline (bookmarks)."""

    page_requested = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setHeaderHidden(True)
        self.itemClicked.connect(self._on_item)

    def populate(self, outline):
        self.clear()
        if not outline:
            empty = QTreeWidgetItem(["No bookmarks"])
            empty.setDisabled(True)
            self.addTopLevelItem(empty)
            return
        stack = []  # (level, QTreeWidgetItem)
        for level, title, page in outline:
            item = QTreeWidgetItem([title or f"Page {page + 1}"])
            item.setData(0, Qt.UserRole, page)
            # find parent
            while stack and stack[-1][0] >= level:
                stack.pop()
            if stack:
                stack[-1][1].addChild(item)
            else:
                self.addTopLevelItem(item)
            stack.append((level, item))
        self.expandAll()

    def _on_item(self, item, column):
        page = item.data(0, Qt.UserRole)
        if page is not None:
            self.page_requested.emit(int(page))


class CommentsList(QListWidget):
    """Shows all annotations in the document."""

    comment_selected = Signal(int)  # page index 0-based

    def __init__(self, parent=None):
        super().__init__(parent)
        self.itemClicked.connect(self._on_item)

    def populate(self, annotations: list[dict]):
        self.clear()
        if not annotations:
            empty = QListWidgetItem("No annotations")
            empty.setFlags(Qt.NoItemFlags)
            self.addItem(empty)
            return
        for a in annotations:
            text = f"Page {a['page']} — {a['type']}"
            if a.get("content"):
                text += f"\n{a['content']}"
            elif a.get("author"):
                text += f"\nby {a['author']}"
            item = QListWidgetItem(text)
            item.setData(Qt.UserRole, a["page"] - 1)
            self.addItem(item)

    def _on_item(self, item):
        idx = item.data(Qt.UserRole)
        if idx is not None:
            self.comment_selected.emit(int(idx))


class LeftSidebar(QTabWidget):
    """Tabs: thumbnails, outline."""

    page_requested = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.thumbnails = ThumbnailListWidget()
        self.outline = OutlineTree()
        self.addTab(self.thumbnails, "Pages")
        self.addTab(self.outline, "Outline")
        self.thumbnails.page_selected.connect(self.page_requested.emit)
        self.outline.page_requested.connect(self.page_requested.emit)

    def populate(self, pdf_document):
        self.thumbnails.populate(pdf_document)
        if pdf_document:
            outline = pdf_document.outline()
            self.outline.populate(outline)
            # If the document has a real outline, show it by default —
            # it's the most useful way to navigate a structured document.
            if outline:
                self.setCurrentWidget(self.outline)
            else:
                self.setCurrentWidget(self.thumbnails)
        else:
            self.outline.clear()


class RightSidebar(QTabWidget):
    """Tabs: comments, properties."""

    page_requested = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        # Comments tab
        self.comments_widget = QWidget()
        layout = QVBoxLayout(self.comments_widget)
        layout.setContentsMargins(8, 8, 8, 8)
        self.comments = CommentsList()
        layout.addWidget(self.comments)
        btn_row = QHBoxLayout()
        self.export_btn = QPushButton("Export comments")
        btn_row.addWidget(self.export_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)
        self.addTab(self.comments_widget, "Comments")

        # Properties tab
        self.properties = QLabel("No document open")
        self.properties.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self.properties.setWordWrap(True)
        self.properties.setContentsMargins(10, 10, 10, 10)
        self.addTab(self.properties, "Properties")

        self.comments.comment_selected.connect(self.page_requested.emit)

    def set_comments(self, annotations):
        self.comments.populate(annotations)

    def set_properties_html(self, html):
        self.properties.setText(html)
        self.properties.setTextFormat(Qt.RichText)
