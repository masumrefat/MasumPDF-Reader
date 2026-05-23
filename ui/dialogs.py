"""Reusable dialogs for various PDF operations."""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel, QLineEdit,
    QPushButton, QDialogButtonBox, QCheckBox, QSpinBox, QComboBox,
    QListWidget, QListWidgetItem, QFileDialog, QMessageBox, QGroupBox,
    QTabWidget, QWidget, QPlainTextEdit, QInputDialog, QToolButton,
    QColorDialog, QSlider, QSplitter, QTextEdit, QApplication,
    QGridLayout, QFrame, QRadioButton,
)
from PySide6.QtCore import Qt, QSize, QPoint, Signal, QRect
from PySide6.QtGui import QPainter, QPen, QColor, QPixmap, QFont, QImage

import os
from utils.file_utils import human_size
from utils.constants import OCR_LANGUAGES, THEME_LIGHT, THEME_DARK


class PasswordDialog(QDialog):
    def __init__(self, title="Password required", message="This PDF is password-protected.",
                 parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumWidth(360)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(message))
        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.Password)
        self.password.setPlaceholderText("Enter password")
        layout.addWidget(self.password)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        layout.addWidget(bb)

    def value(self) -> str:
        return self.password.text()


class PropertiesDialog(QDialog):
    def __init__(self, metadata: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Document properties")
        self.setMinimumWidth(440)
        layout = QVBoxLayout(self)

        info_box = QGroupBox("File")
        form = QFormLayout(info_box)
        form.addRow("Path:", QLabel(metadata.get("file_path", "—")))
        form.addRow("Size:", QLabel(human_size(metadata.get("file_size", 0))))
        form.addRow("Pages:", QLabel(str(metadata.get("page_count", 0))))
        form.addRow("Encrypted:", QLabel("Yes" if metadata.get("encrypted") else "No"))
        layout.addWidget(info_box)

        meta_box = QGroupBox("Metadata (editable)")
        form2 = QFormLayout(meta_box)
        self.title = QLineEdit(metadata.get("title", "") or "")
        self.author = QLineEdit(metadata.get("author", "") or "")
        self.subject = QLineEdit(metadata.get("subject", "") or "")
        self.keywords = QLineEdit(metadata.get("keywords", "") or "")
        form2.addRow("Title:", self.title)
        form2.addRow("Author:", self.author)
        form2.addRow("Subject:", self.subject)
        form2.addRow("Keywords:", self.keywords)
        layout.addWidget(meta_box)

        dates = QGroupBox("Dates")
        form3 = QFormLayout(dates)
        form3.addRow("Created:", QLabel(metadata.get("creationDate", "—") or "—"))
        form3.addRow("Modified:", QLabel(metadata.get("modDate", "—") or "—"))
        form3.addRow("Producer:", QLabel(metadata.get("producer", "—") or "—"))
        form3.addRow("Creator:", QLabel(metadata.get("creator", "—") or "—"))
        layout.addWidget(dates)

        bb = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        layout.addWidget(bb)

    def updated_fields(self) -> dict:
        return {
            "title": self.title.text(),
            "author": self.author.text(),
            "subject": self.subject.text(),
            "keywords": self.keywords.text(),
        }


class EncryptDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Encrypt PDF")
        self.setMinimumWidth(380)
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.password1 = QLineEdit()
        self.password1.setEchoMode(QLineEdit.Password)
        self.password2 = QLineEdit()
        self.password2.setEchoMode(QLineEdit.Password)
        form.addRow("Password:", self.password1)
        form.addRow("Confirm:", self.password2)
        layout.addLayout(form)

        perms = QGroupBox("Permissions")
        pl = QVBoxLayout(perms)
        self.allow_print = QCheckBox("Allow printing")
        self.allow_print.setChecked(True)
        self.allow_copy = QCheckBox("Allow copying")
        self.allow_copy.setChecked(True)
        self.allow_modify = QCheckBox("Allow editing")
        pl.addWidget(self.allow_print)
        pl.addWidget(self.allow_copy)
        pl.addWidget(self.allow_modify)
        layout.addWidget(perms)

        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self._accept)
        bb.rejected.connect(self.reject)
        layout.addWidget(bb)

    def _accept(self):
        if not self.password1.text():
            QMessageBox.warning(self, "Missing password", "Please enter a password.")
            return
        if self.password1.text() != self.password2.text():
            QMessageBox.warning(self, "Mismatch", "The passwords don't match.")
            return
        self.accept()

    def options(self):
        return {
            "password": self.password1.text(),
            "allow_print": self.allow_print.isChecked(),
            "allow_copy": self.allow_copy.isChecked(),
            "allow_modify": self.allow_modify.isChecked(),
        }


class OrganizeDialog(QDialog):
    """Drag-and-drop to reorder; buttons to delete and rotate."""

    def __init__(self, pdf_document, parent=None):
        super().__init__(parent)
        self.pdf = pdf_document
        self.setWindowTitle("Organize pages")
        self.resize(640, 520)
        layout = QVBoxLayout(self)

        help_label = QLabel("Drag pages to reorder. Use the buttons to rotate or delete.")
        help_label.setStyleSheet("color: #8A8E98;")
        layout.addWidget(help_label)

        self.list_widget = QListWidget()
        self.list_widget.setViewMode(QListWidget.IconMode)
        self.list_widget.setIconSize(QSize(120, 160))
        self.list_widget.setMovement(QListWidget.Snap)
        self.list_widget.setResizeMode(QListWidget.Adjust)
        self.list_widget.setDragDropMode(QListWidget.InternalMove)
        self.list_widget.setSelectionMode(QListWidget.ExtendedSelection)
        self.list_widget.setSpacing(8)
        layout.addWidget(self.list_widget)

        # populate
        for i in range(pdf_document.page_count):
            self._add_page_item(i)

        btn_row = QHBoxLayout()
        for label, fn in (("Rotate left", self._rotate_left),
                          ("Rotate right", self._rotate_right),
                          ("Delete", self._delete_selected),
                          ("Duplicate", self._duplicate_selected),
                          ("Extract…", self._extract_selected)):
            b = QPushButton(label)
            b.clicked.connect(fn)
            btn_row.addWidget(b)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        bb = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        layout.addWidget(bb)

    def _add_page_item(self, page_index, rotation=0):
        item = QListWidgetItem()
        try:
            pix = self.pdf.render_thumbnail(page_index, width=120)
            if rotation:
                pix = pix.transformed(self._rot_transform(rotation))
            item.setIcon(pix)
        except Exception:
            pass
        item.setText(f"Page {page_index + 1}")
        item.setTextAlignment(Qt.AlignHCenter)
        item.setData(Qt.UserRole, {"page_index": page_index, "rotation": rotation,
                                   "deleted": False, "duplicate_of": None})
        self.list_widget.addItem(item)

    def _rot_transform(self, deg):
        from PySide6.QtGui import QTransform
        t = QTransform()
        t.rotate(deg)
        return t

    def _rotate_left(self):
        for it in self.list_widget.selectedItems():
            d = it.data(Qt.UserRole)
            d["rotation"] = (d.get("rotation", 0) - 90) % 360
            it.setData(Qt.UserRole, d)
            # re-render thumb
            try:
                pix = self.pdf.render_thumbnail(d["page_index"], width=120)
                if d["rotation"]:
                    pix = pix.transformed(self._rot_transform(d["rotation"]))
                it.setIcon(pix)
            except Exception:
                pass

    def _rotate_right(self):
        for it in self.list_widget.selectedItems():
            d = it.data(Qt.UserRole)
            d["rotation"] = (d.get("rotation", 0) + 90) % 360
            it.setData(Qt.UserRole, d)
            try:
                pix = self.pdf.render_thumbnail(d["page_index"], width=120)
                if d["rotation"]:
                    pix = pix.transformed(self._rot_transform(d["rotation"]))
                it.setIcon(pix)
            except Exception:
                pass

    def _delete_selected(self):
        for it in list(self.list_widget.selectedItems()):
            row = self.list_widget.row(it)
            self.list_widget.takeItem(row)

    def _duplicate_selected(self):
        new_items = []
        for it in self.list_widget.selectedItems():
            d = dict(it.data(Qt.UserRole))
            row = self.list_widget.row(it)
            new_item = QListWidgetItem(it)
            new_item.setData(Qt.UserRole, d)
            new_items.append((row + 1, new_item))
        # insert in reverse so indices stay valid
        for row, item in reversed(new_items):
            self.list_widget.insertItem(row, item)

    def _extract_selected(self):
        items = self.list_widget.selectedItems()
        if not items:
            QMessageBox.information(self, "No selection", "Select pages first.")
            return
        path, _ = QFileDialog.getSaveFileName(self, "Extract to…", "extracted.pdf",
                                              "PDF files (*.pdf)")
        if not path:
            return
        page_indices = [it.data(Qt.UserRole)["page_index"] for it in items]
        try:
            self.pdf.extract_pages(page_indices, path)
            QMessageBox.information(self, "Extracted",
                                    f"Saved {len(page_indices)} pages to:\n{path}")
        except Exception as e:
            QMessageBox.critical(self, "Extract failed", str(e))

    def get_plan(self) -> list[dict]:
        """Return the planned page list (in display order) with rotations."""
        plan = []
        for i in range(self.list_widget.count()):
            it = self.list_widget.item(i)
            d = it.data(Qt.UserRole)
            plan.append({
                "source_index": d["page_index"],
                "rotation": d.get("rotation", 0),
            })
        return plan


class SplitDialog(QDialog):
    def __init__(self, page_count: int, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Split PDF")
        self.setMinimumWidth(420)
        self.page_count = page_count
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(
            f"This document has {page_count} pages.\n"
            "Enter page ranges to split into separate files.\n"
            "Example:  1-5,  6-10,  11-15"
        ))
        self.ranges = QPlainTextEdit()
        self.ranges.setPlaceholderText("One range per line, e.g.\n1-5\n6-10\n11-end")
        layout.addWidget(self.ranges)
        self.each_page_cb = QCheckBox("Or: save every page as its own PDF")
        layout.addWidget(self.each_page_cb)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        layout.addWidget(bb)

    def get_ranges(self) -> list[str]:
        if self.each_page_cb.isChecked():
            return []  # signal "each page"
        text = self.ranges.toPlainText().strip()
        return [r.replace("end", str(self.page_count)) for r in text.splitlines() if r.strip()]

    def each_page(self) -> bool:
        return self.each_page_cb.isChecked()


class OCRDialog(QDialog):
    def __init__(self, default_lang="eng", parent=None):
        super().__init__(parent)
        self.setWindowTitle("Run OCR")
        self.setMinimumWidth(360)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("OCR will read text from scanned pages and produce a "
                                "searchable copy of this PDF."))
        form = QFormLayout()
        self.lang = QComboBox()
        for name, code in OCR_LANGUAGES.items():
            self.lang.addItem(f"{name} ({code})", code)
            if code == default_lang:
                self.lang.setCurrentIndex(self.lang.count() - 1)
        form.addRow("Language:", self.lang)
        layout.addLayout(form)
        layout.addWidget(QLabel("This requires Tesseract to be installed on your system."))
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        layout.addWidget(bb)

    def language_code(self) -> str:
        return self.lang.currentData()


class SignatureDialog(QDialog):
    """Type, draw, or import a signature image."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Create signature")
        self.resize(520, 380)
        self._image_path = None
        self._signature_pixmap: QPixmap | None = None

        layout = QVBoxLayout(self)
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)

        # Typed tab
        typed = QWidget()
        tl = QVBoxLayout(typed)
        tl.addWidget(QLabel("Type your name:"))
        self.typed_input = QLineEdit()
        tl.addWidget(self.typed_input)
        self.typed_preview = QLabel("Your signature will appear here")
        self.typed_preview.setStyleSheet("background:white; color:black; padding:18px;"
                                         "font-family:'Brush Script MT','Segoe Script',cursive;"
                                         "font-size:32px; border:1px solid #ccc;")
        self.typed_preview.setAlignment(Qt.AlignCenter)
        tl.addWidget(self.typed_preview)
        self.typed_input.textChanged.connect(self.typed_preview.setText)
        self.tabs.addTab(typed, "Type")

        # Draw tab
        self.draw_widget = SignatureCanvas()
        clear_btn = QPushButton("Clear")
        clear_btn.clicked.connect(self.draw_widget.clear)
        draw_container = QWidget()
        dl = QVBoxLayout(draw_container)
        dl.addWidget(QLabel("Draw your signature below:"))
        dl.addWidget(self.draw_widget, 1)
        dl.addWidget(clear_btn)
        self.tabs.addTab(draw_container, "Draw")

        # Image tab
        img = QWidget()
        il = QVBoxLayout(img)
        self.image_preview = QLabel("No image selected")
        self.image_preview.setAlignment(Qt.AlignCenter)
        self.image_preview.setStyleSheet("background:white; min-height:160px;"
                                         "border:1px solid #ccc;")
        pick_btn = QPushButton("Choose image…")
        pick_btn.clicked.connect(self._pick_image)
        il.addWidget(pick_btn)
        il.addWidget(self.image_preview, 1)
        self.tabs.addTab(img, "Image")

        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        layout.addWidget(bb)

    def _pick_image(self):
        p, _ = QFileDialog.getOpenFileName(self, "Signature image", "",
                                           "Images (*.png *.jpg *.jpeg *.bmp)")
        if p:
            self._image_path = p
            self.image_preview.setPixmap(QPixmap(p).scaled(360, 160, Qt.KeepAspectRatio,
                                                           Qt.SmoothTransformation))

    def signature_pixmap(self) -> QPixmap | None:
        """Build a QPixmap based on the selected tab."""
        idx = self.tabs.currentIndex()
        if idx == 0:
            text = self.typed_input.text().strip()
            if not text:
                return None
            pix = QPixmap(420, 100)
            pix.fill(Qt.transparent)
            painter = QPainter(pix)
            painter.setRenderHint(QPainter.Antialiasing)
            font = QFont("Brush Script MT")
            font.setPointSize(36)
            painter.setFont(font)
            painter.setPen(QColor("#0E1B3D"))
            painter.drawText(pix.rect(), Qt.AlignCenter, text)
            painter.end()
            return pix
        if idx == 1:
            return self.draw_widget.pixmap()
        if idx == 2 and self._image_path:
            return QPixmap(self._image_path)
        return None


class SignatureCanvas(QWidget):
    """A simple QWidget you can finger-paint on with the mouse."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(160)
        self.setStyleSheet("background:white; border:1px solid #ccc;")
        self._pixmap = QPixmap(640, 200)
        self._pixmap.fill(Qt.white)
        self._last: QPoint | None = None

    def clear(self):
        self._pixmap.fill(Qt.white)
        self.update()

    def pixmap(self) -> QPixmap:
        return self._pixmap

    def paintEvent(self, event):
        painter = QPainter(self)
        # paint the stored pixmap stretched to widget
        painter.drawPixmap(self.rect(), self._pixmap, self._pixmap.rect())
        painter.end()

    def mousePressEvent(self, event):
        self._last = event.position().toPoint()

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.LeftButton and self._last:
            painter = QPainter(self._pixmap)
            painter.setRenderHint(QPainter.Antialiasing)
            painter.setPen(QPen(QColor("#0E1B3D"), 3, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            # convert widget coords to pixmap coords
            scale_x = self._pixmap.width() / self.width()
            scale_y = self._pixmap.height() / self.height()
            p1 = QPoint(int(self._last.x() * scale_x), int(self._last.y() * scale_y))
            now = event.position().toPoint()
            p2 = QPoint(int(now.x() * scale_x), int(now.y() * scale_y))
            painter.drawLine(p1, p2)
            painter.end()
            self._last = now
            self.update()

    def mouseReleaseEvent(self, event):
        self._last = None


class SettingsDialog(QDialog):
    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.setWindowTitle("Settings")
        self.setMinimumWidth(420)
        layout = QVBoxLayout(self)
        form = QFormLayout()

        # Theme
        self.theme = QComboBox()
        self.theme.addItems(["Light", "Dark"])
        self.theme.setCurrentIndex(1 if settings.theme() == THEME_DARK else 0)
        form.addRow("Theme:", self.theme)

        # Default zoom
        self.default_zoom = QSpinBox()
        self.default_zoom.setRange(25, 400)
        self.default_zoom.setSuffix(" %")
        self.default_zoom.setValue(int(settings.default_zoom() * 100))
        form.addRow("Default zoom:", self.default_zoom)

        # Render quality
        from utils.constants import RENDER_QUALITY_PRESETS
        self.render_quality = QComboBox()
        for name in RENDER_QUALITY_PRESETS.keys():
            self.render_quality.addItem(name)
        current_q = settings.render_quality()
        idx = self.render_quality.findText(current_q)
        if idx >= 0:
            self.render_quality.setCurrentIndex(idx)
        self.render_quality.setToolTip(
            "Higher quality means sharper pages but uses more memory and CPU. "
            "Pick Ultra if your screen is 4K / Retina and pages still look soft.")
        form.addRow("Render quality:", self.render_quality)

        # Auto fit on open
        self.auto_fit = QCheckBox("Fit page width when opening a PDF")
        self.auto_fit.setChecked(settings.auto_fit_on_open())
        self.auto_fit.setToolTip(
            "When on, every PDF opens with the page filling the window width — "
            "so text is at its most readable size.")
        form.addRow("", self.auto_fit)

        # View mode
        self.view_mode = QComboBox()
        self.view_mode.addItems(["Continuous", "Single page", "Two pages"])
        mode_map = {"continuous": 0, "single": 1, "two_page": 2}
        self.view_mode.setCurrentIndex(mode_map.get(settings.view_mode(), 0))
        form.addRow("Default view:", self.view_mode)

        # Interface (GUI) language
        from utils.i18n import available_languages
        self.ui_lang = QComboBox()
        for code, name in available_languages().items():
            self.ui_lang.addItem(name, code)
            if code == settings.ui_language():
                self.ui_lang.setCurrentIndex(self.ui_lang.count() - 1)
        self.ui_lang.setToolTip(
            "Language of the app's menus and buttons. Takes full effect after "
            "you restart the app.")
        form.addRow("Interface language:", self.ui_lang)

        # OCR language
        self.ocr_lang = QComboBox()
        for name, code in OCR_LANGUAGES.items():
            self.ocr_lang.addItem(f"{name} ({code})", code)
            if code == settings.ocr_language():
                self.ocr_lang.setCurrentIndex(self.ocr_lang.count() - 1)
        form.addRow("OCR language:", self.ocr_lang)

        # Autosave
        self.autosave = QCheckBox("Enable autosave for annotations")
        self.autosave.setChecked(settings.autosave_enabled())
        form.addRow("", self.autosave)

        self.autosave_interval = QSpinBox()
        self.autosave_interval.setRange(10, 600)
        self.autosave_interval.setSuffix(" s")
        self.autosave_interval.setValue(settings.autosave_interval())
        form.addRow("Autosave interval:", self.autosave_interval)

        # Highlight color
        self.highlight_color_btn = QPushButton(settings.highlight_color())
        self.highlight_color_btn.setStyleSheet(
            f"background-color: {settings.highlight_color()};")
        self.highlight_color_btn.clicked.connect(self._pick_color)
        form.addRow("Highlight color:", self.highlight_color_btn)

        layout.addLayout(form)
        bb = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        layout.addWidget(bb)

    def _pick_color(self):
        color = QColorDialog.getColor(QColor(self.highlight_color_btn.text()), self,
                                      "Pick a highlight color")
        if color.isValid():
            hex_c = color.name()
            self.highlight_color_btn.setText(hex_c)
            self.highlight_color_btn.setStyleSheet(f"background-color: {hex_c};")

    def apply(self):
        self.settings.set_theme(THEME_DARK if self.theme.currentIndex() == 1 else THEME_LIGHT)
        self.settings.set_default_zoom(self.default_zoom.value() / 100.0)
        self.settings.set_render_quality(self.render_quality.currentText())
        self.settings.set_auto_fit_on_open(self.auto_fit.isChecked())
        mode_map = {0: "continuous", 1: "single", 2: "two_page"}
        self.settings.set_view_mode(mode_map.get(self.view_mode.currentIndex(), "continuous"))
        self.settings.set_ocr_language(self.ocr_lang.currentData())
        self.settings.set_ui_language(self.ui_lang.currentData())
        self.settings.set_autosave_enabled(self.autosave.isChecked())
        self.settings.set_autosave_interval(self.autosave_interval.value())
        self.settings.set_highlight_color(self.highlight_color_btn.text())


# =============================================================================
# Compress dialog
# =============================================================================
class CompressDialog(QDialog):
    """Pick a target DPI and JPEG quality for compression."""

    def __init__(self, original_size_bytes: int = 0, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Compress PDF")
        self.setMinimumWidth(440)
        from core.compressor import DPI_PRESETS

        layout = QVBoxLayout(self)

        if original_size_bytes > 0:
            mb = original_size_bytes / (1024 * 1024)
            layout.addWidget(QLabel(f"Original size: <b>{mb:.2f} MB</b>"))

        layout.addWidget(QLabel("Choose a target quality. Lower DPI = smaller file."))

        self.preset_combo = QComboBox()
        for label, dpi, q in DPI_PRESETS:
            self.preset_combo.addItem(label, (dpi, q))
        self.preset_combo.setCurrentIndex(2)  # Medium (100 DPI) default
        layout.addWidget(self.preset_combo)

        # Custom DPI + quality, in case the user wants finer control
        custom_group = QGroupBox("Custom (overrides the preset)")
        cl = QVBoxLayout(custom_group)
        self.custom_check = QCheckBox("Use custom DPI and quality")
        cl.addWidget(self.custom_check)

        row1 = QHBoxLayout()
        row1.addWidget(QLabel("Target DPI:"))
        self.dpi_spin = QSpinBox()
        self.dpi_spin.setRange(30, 600)
        self.dpi_spin.setValue(100)
        self.dpi_spin.setSingleStep(10)
        self.dpi_spin.setSuffix(" dpi")
        row1.addWidget(self.dpi_spin)
        row1.addStretch(1)
        cl.addLayout(row1)

        row2 = QHBoxLayout()
        row2.addWidget(QLabel("JPEG quality:"))
        self.quality_spin = QSpinBox()
        self.quality_spin.setRange(20, 95)
        self.quality_spin.setValue(70)
        self.quality_spin.setSuffix(" %")
        row2.addWidget(self.quality_spin)
        row2.addStretch(1)
        cl.addLayout(row2)

        layout.addWidget(custom_group)

        layout.addWidget(QLabel(
            "<small>Images already smaller than the target are left alone. "
            "Text and vector content is never lost.</small>"))

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def settings(self) -> tuple[int, int]:
        if self.custom_check.isChecked():
            return self.dpi_spin.value(), self.quality_spin.value()
        dpi, q = self.preset_combo.currentData()
        return dpi, q




# =============================================================================
# Select Files to Compare — Adobe-style picker screen
# =============================================================================
class _FileDropBox(QFrame):
    """A large clickable file box showing a doc icon or the chosen filename."""

    clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("FileDropBox")
        self.setFixedSize(150, 200)
        self.setCursor(Qt.PointingHandCursor)
        self._has_file = False
        self.setStyleSheet(
            "#FileDropBox { background: rgba(127,127,127,0.16);"
            " border: 1px solid rgba(127,127,127,0.30); border-radius: 6px; }"
            "#FileDropBox:hover { background: rgba(127,127,127,0.24); }")
        lay = QVBoxLayout(self)
        lay.setAlignment(Qt.AlignCenter)
        self.icon = QLabel()
        self.icon.setAlignment(Qt.AlignCenter)
        from ui.icons import make_icon
        self.icon.setPixmap(make_icon("to_text", "#9AA0AC", 46).pixmap(46, 46))
        lay.addWidget(self.icon)
        self.name = QLabel("")
        self.name.setAlignment(Qt.AlignCenter)
        self.name.setWordWrap(True)
        self.name.setStyleSheet("color: palette(text); font-size: 11px;")
        lay.addWidget(self.name)

    def set_file(self, path):
        self._has_file = bool(path)
        if path:
            self.icon.hide()
            self.name.setText(os.path.basename(path))
        else:
            self.icon.show()
            self.name.setText("")

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)


class PrintDialog(QDialog):
    """Custom print window, styled after Adobe's: a controls column on the
    left and a live page preview on the right with page navigation.

    Renders the preview at low resolution (fast, cached) and returns the
    chosen options; the actual high-quality print is done by the caller.
    """

    def __init__(self, document, current_page: int = 0, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Print")
        self.setMinimumSize(900, 640)
        self._doc = document
        self._page_count = document.page_count
        self._preview_page = max(0, min(current_page, self._page_count - 1))
        self._current_page = self._preview_page
        self._cache = {}            # page index -> QPixmap (preview)

        root = QHBoxLayout(self)
        root.setSpacing(18)

        # ---------------- left column: controls ----------------
        left = QVBoxLayout()
        left.setSpacing(12)

        # Printer
        left.addWidget(self._label("Printer"))
        self.printer_combo = QComboBox()
        try:
            from PySide6.QtPrintSupport import QPrinterInfo
            names = [p.printerName() for p in QPrinterInfo.availablePrinters()]
            default = QPrinterInfo.defaultPrinter().printerName()
        except Exception:
            names, default = [], ""
        if not names:
            names = ["(default printer)"]
        self.printer_combo.addItems(names)
        if default in names:
            self.printer_combo.setCurrentText(default)
        left.addWidget(self.printer_combo)

        # Copies + grayscale
        row = QHBoxLayout()
        row.addWidget(self._label("Copies"))
        self.copies_spin = QSpinBox()
        self.copies_spin.setRange(1, 99)
        self.copies_spin.setValue(1)
        row.addWidget(self.copies_spin)
        row.addStretch(1)
        left.addLayout(row)
        self.grayscale_chk = QCheckBox("Print in grayscale (black and white)")
        left.addWidget(self.grayscale_chk)

        # Pages to print
        left.addWidget(self._label("Pages to Print"))
        self.pages_all = QRadioButton("All")
        self.pages_current = QRadioButton("Current page")
        self.pages_range = QRadioButton("Pages:")
        self.pages_all.setChecked(True)
        self.range_edit = QLineEdit()
        self.range_edit.setPlaceholderText(f"e.g. 1-{self._page_count}")
        self.range_edit.setEnabled(False)
        self.pages_range.toggled.connect(self.range_edit.setEnabled)
        pr1 = QHBoxLayout(); pr1.addWidget(self.pages_all); pr1.addWidget(self.pages_current); pr1.addStretch(1)
        pr2 = QHBoxLayout(); pr2.addWidget(self.pages_range); pr2.addWidget(self.range_edit, 1)
        left.addLayout(pr1); left.addLayout(pr2)

        # Page sizing
        left.addWidget(self._label("Page Sizing & Handling"))
        self.size_combo = QComboBox()
        self.size_combo.addItem("Fit to printable area", "fit")
        self.size_combo.addItem("Shrink oversized pages", "shrink")
        self.size_combo.addItem("Actual size", "actual")
        self.size_combo.setCurrentIndex(1)
        left.addWidget(self.size_combo)

        # Orientation
        left.addWidget(self._label("Orientation"))
        self.orient_combo = QComboBox()
        self.orient_combo.addItem("Auto", "auto")
        self.orient_combo.addItem("Portrait", "portrait")
        self.orient_combo.addItem("Landscape", "landscape")
        left.addWidget(self.orient_combo)

        # Two-sided
        self.duplex_chk = QCheckBox("Print on both sides of paper")
        left.addWidget(self.duplex_chk)

        left.addStretch(1)

        # buttons
        btns = QHBoxLayout()
        btns.addStretch(1)
        self.print_btn = QPushButton("Print")
        self.print_btn.setDefault(True)
        self.print_btn.clicked.connect(self.accept)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        self.print_btn.setStyleSheet(
            "QPushButton { background:#2667FF; color:white; font-weight:600;"
            " border:none; border-radius:5px; padding:7px 22px; }"
            "QPushButton:hover { background:#1B57E0; }")
        btns.addWidget(self.print_btn)
        btns.addWidget(cancel_btn)
        left.addLayout(btns)

        # ---------------- right column: preview ----------------
        right = QVBoxLayout()
        self.scale_lbl = QLabel("Preview")
        self.scale_lbl.setStyleSheet("color:#8A8E98;")
        right.addWidget(self.scale_lbl)
        self.preview_lbl = QLabel()
        self.preview_lbl.setAlignment(Qt.AlignCenter)
        self.preview_lbl.setMinimumSize(380, 480)
        self.preview_lbl.setStyleSheet(
            "background:#3a3a3a; border:1px solid rgba(127,127,127,0.4);")
        right.addWidget(self.preview_lbl, 1)
        navr = QHBoxLayout()
        self.prev_btn = QPushButton("<")
        self.next_btn = QPushButton(">")
        self.prev_btn.setFixedWidth(44)
        self.next_btn.setFixedWidth(44)
        self.prev_btn.clicked.connect(lambda: self._step(-1))
        self.next_btn.clicked.connect(lambda: self._step(+1))
        self.page_lbl = QLabel("")
        self.page_lbl.setAlignment(Qt.AlignCenter)
        navr.addStretch(1)
        navr.addWidget(self.prev_btn)
        navr.addWidget(self.page_lbl)
        navr.addWidget(self.next_btn)
        navr.addStretch(1)
        right.addLayout(navr)

        root.addLayout(left, 0)
        root.addLayout(right, 1)

        self._update_preview()

    def _label(self, text):
        lbl = QLabel(text)
        lbl.setStyleSheet("font-weight:600;")
        return lbl

    def _step(self, d):
        self._preview_page = max(0, min(self._page_count - 1,
                                        self._preview_page + d))
        self._update_preview()

    def _update_preview(self):
        self.page_lbl.setText(f"Page {self._preview_page + 1} of {self._page_count}")
        pno = self._preview_page
        if pno not in self._cache:
            try:
                import fitz
                page = self._doc.doc[pno]
                pix = page.get_pixmap(matrix=fitz.Matrix(1.2, 1.2), alpha=False)
                img = QImage(pix.samples, pix.width, pix.height,
                             pix.stride, QImage.Format_RGB888).copy()
                self._cache[pno] = QPixmap.fromImage(img)
            except Exception:
                self._cache[pno] = QPixmap()
        pm = self._cache[pno]
        if not pm.isNull():
            target = self.preview_lbl.size()
            self.preview_lbl.setPixmap(pm.scaled(
                target.width() - 8, target.height() - 8,
                Qt.KeepAspectRatio, Qt.SmoothTransformation))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_preview()

    def results(self) -> dict:
        if self.pages_all.isChecked():
            pages = "all"
        elif self.pages_current.isChecked():
            pages = "current"
        else:
            pages = self.range_edit.text().strip() or "all"
        return {
            "printer": self.printer_combo.currentText(),
            "copies": self.copies_spin.value(),
            "grayscale": self.grayscale_chk.isChecked(),
            "pages": pages,
            "current_page": self._current_page,
            "sizing": self.size_combo.currentData(),
            "orientation": self.orient_combo.currentData(),
            "duplex": self.duplex_chk.isChecked(),
        }


class SelectFilesToCompareDialog(QDialog):
    """Adobe-style 'Select Files to Compare' screen.

    Lets the user pick an OLD and NEW file, swap them, toggle text-only
    compare, then continue to the side-by-side comparison view.
    """

    def __init__(self, parent=None, old_path: str = "", new_path: str = ""):
        super().__init__(parent)
        self.setWindowTitle("Select Files to Compare")
        self.setMinimumWidth(640)
        self._old_path = old_path
        self._new_path = new_path

        root = QVBoxLayout(self)
        root.setContentsMargins(40, 30, 40, 30)
        root.setSpacing(18)

        title = QLabel("Select Files to Compare")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size: 20px; font-weight: 700;")
        root.addWidget(title)

        # Two file boxes with a swap arrow between
        grid = QHBoxLayout()
        grid.setSpacing(20)
        grid.addStretch(1)

        # OLD column
        old_col = QVBoxLayout()
        old_col.setAlignment(Qt.AlignHCenter)
        old_lbl = QLabel("Old File")
        old_lbl.setAlignment(Qt.AlignCenter)
        old_lbl.setStyleSheet("color: palette(text); font-size: 12px;")
        old_col.addWidget(old_lbl)
        self.old_box = _FileDropBox()
        self.old_box.clicked.connect(self._pick_old)
        old_col.addWidget(self.old_box)
        old_btn_row = QHBoxLayout()
        old_btn_row.setAlignment(Qt.AlignCenter)
        self.old_select_btn = QPushButton("Select File")
        self.old_select_btn.clicked.connect(self._pick_old)
        old_btn_row.addWidget(self.old_select_btn)
        old_col.addLayout(old_btn_row)
        grid.addLayout(old_col)

        # Swap arrow
        swap_col = QVBoxLayout()
        swap_col.addStretch(1)
        self.swap_btn = QToolButton()
        self.swap_btn.setText("\u21c4")
        self.swap_btn.setToolTip("Swap Old and New")
        self.swap_btn.setCursor(Qt.PointingHandCursor)
        self.swap_btn.setAutoRaise(True)
        self.swap_btn.setStyleSheet("QToolButton { font-size: 22px; border: none; }"
                                    "QToolButton:hover { color: #2667FF; }")
        self.swap_btn.clicked.connect(self._swap)
        swap_col.addWidget(self.swap_btn)
        swap_col.addStretch(1)
        grid.addLayout(swap_col)

        # NEW column
        new_col = QVBoxLayout()
        new_col.setAlignment(Qt.AlignHCenter)
        new_lbl = QLabel("New File")
        new_lbl.setAlignment(Qt.AlignCenter)
        new_lbl.setStyleSheet("color: palette(text); font-size: 12px;")
        new_col.addWidget(new_lbl)
        self.new_box = _FileDropBox()
        self.new_box.clicked.connect(self._pick_new)
        new_col.addWidget(self.new_box)
        new_btn_row = QHBoxLayout()
        new_btn_row.setAlignment(Qt.AlignCenter)
        self.new_select_btn = QPushButton("Select File")
        self.new_select_btn.clicked.connect(self._pick_new)
        new_btn_row.addWidget(self.new_select_btn)
        new_col.addLayout(new_btn_row)
        grid.addLayout(new_col)

        grid.addStretch(1)
        root.addLayout(grid)

        # Options
        self.text_only_chk = QCheckBox("Compare text only")
        self.text_only_chk.setChecked(True)
        self.text_only_chk.setToolTip(
            "On: produce a clean list of exactly what text changed "
            "(best for review). Off: also include side-by-side page images.")
        opt_row = QHBoxLayout()
        opt_row.setAlignment(Qt.AlignCenter)
        opt_row.addWidget(self.text_only_chk)
        root.addLayout(opt_row)

        # Compare button
        self.compare_btn = QPushButton("Compare")
        self.compare_btn.setEnabled(False)
        self.compare_btn.setCursor(Qt.PointingHandCursor)
        self.compare_btn.setFixedWidth(150)
        self.compare_btn.setStyleSheet(
            "QPushButton {"
            "  background: #2667FF; color: white; font-weight: 600;"
            "  border: none; border-radius: 16px; padding: 8px 18px;"
            "  font-size: 13px; }"
            "QPushButton:hover { background: #1B57E0; }"
            "QPushButton:disabled { background: rgba(127,127,127,0.35);"
            "  color: rgba(255,255,255,0.6); }")
        self.compare_btn.clicked.connect(self.accept)
        cmp_row = QHBoxLayout()
        cmp_row.setAlignment(Qt.AlignCenter)
        cmp_row.addWidget(self.compare_btn)
        root.addLayout(cmp_row)

        # initialise any pre-supplied paths
        self.old_box.set_file(old_path)
        self.new_box.set_file(new_path)
        self._refresh()

    def _pick_old(self):
        p, _ = QFileDialog.getOpenFileName(self, "Pick the OLD PDF", "",
                                           "PDF (*.pdf)")
        if p:
            self._old_path = p
            self.old_box.set_file(p)
            self._refresh()

    def _pick_new(self):
        p, _ = QFileDialog.getOpenFileName(self, "Pick the NEW PDF", "",
                                           "PDF (*.pdf)")
        if p:
            self._new_path = p
            self.new_box.set_file(p)
            self._refresh()

    def _swap(self):
        self._old_path, self._new_path = self._new_path, self._old_path
        self.old_box.set_file(self._old_path)
        self.new_box.set_file(self._new_path)
        self._refresh()

    def _refresh(self):
        self.compare_btn.setEnabled(bool(self._old_path and self._new_path))

    def results(self):
        return {
            "old_path": self._old_path,
            "new_path": self._new_path,
            "text_only": self.text_only_chk.isChecked(),
        }


# =============================================================================
# Compare dialog (side-by-side viewer + text diff)
# =============================================================================
class CompareDialog(QDialog):
    """Side-by-side comparison of two PDFs with a per-page text diff."""

    def __init__(self, old_path: str, new_path: str, parent=None):
        super().__init__(parent)
        from core.pdf_document import PDFDocument
        from ui.pdf_viewer import PDFViewer
        from core.comparer import compare_pdfs

        self.setWindowTitle("Compare PDFs")
        self.resize(1100, 760)

        self._old_doc = PDFDocument(old_path)
        self._new_doc = PDFDocument(new_path)
        self._old_doc.doc  # open
        self._new_doc.doc

        layout = QVBoxLayout(self)

        # top: side-by-side viewers
        viewers_row = QHBoxLayout()
        left_box = QVBoxLayout()
        left_box.addWidget(QLabel(f"<b>Old:</b> {os.path.basename(old_path)}"))
        self.old_viewer = PDFViewer()
        self.old_viewer.set_document(self._old_doc)
        left_box.addWidget(self.old_viewer, 1)

        right_box = QVBoxLayout()
        right_box.addWidget(QLabel(f"<b>New:</b> {os.path.basename(new_path)}"))
        self.new_viewer = PDFViewer()
        self.new_viewer.set_document(self._new_doc)
        right_box.addWidget(self.new_viewer, 1)

        left_w = QWidget(); left_w.setLayout(left_box)
        right_w = QWidget(); right_w.setLayout(right_box)
        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(left_w)
        splitter.addWidget(right_w)
        splitter.setSizes([500, 500])
        layout.addWidget(splitter, 3)

        # synchronized vertical scroll
        self.old_viewer.verticalScrollBar().valueChanged.connect(
            self._sync_from_old)
        self.new_viewer.verticalScrollBar().valueChanged.connect(
            self._sync_from_new)
        self._suppress_sync = False

        # bottom: page picker + diff
        bottom = QVBoxLayout()
        nav = QHBoxLayout()
        nav.addWidget(QLabel("Jump to page:"))
        self.page_combo = QComboBox()
        nav.addWidget(self.page_combo)
        # change-to-change navigation
        self.prev_change_btn = QPushButton("\u25c0  Prev change")
        self.next_change_btn = QPushButton("Next change  \u25b6")
        self.prev_change_btn.setToolTip("Jump to the previous changed page (Alt+Up)")
        self.next_change_btn.setToolTip("Jump to the next changed page (Alt+Down)")
        self.prev_change_btn.setShortcut("Alt+Up")
        self.next_change_btn.setShortcut("Alt+Down")
        self.prev_change_btn.clicked.connect(lambda: self._goto_change(-1))
        self.next_change_btn.clicked.connect(lambda: self._goto_change(+1))
        nav.addWidget(self.prev_change_btn)
        nav.addWidget(self.next_change_btn)
        self.summary_label = QLabel("")
        nav.addWidget(self.summary_label, 1)
        bottom.addLayout(nav)

        self.diff_view = QTextEdit()
        self.diff_view.setReadOnly(True)
        bottom.addWidget(self.diff_view, 1)

        bottom_w = QWidget(); bottom_w.setLayout(bottom)
        layout.addWidget(bottom_w, 2)

        # Bottom button bar: options + prominent download + close
        btn_row = QHBoxLayout()
        self.ignore_case_chk = QCheckBox("Ignore case")
        self.ignore_quotes_chk = QCheckBox("Ignore quote style")
        self.show_moved_chk = QCheckBox("Show moved text (blue)")
        self.show_moved_chk.setChecked(True)
        self.show_moved_chk.setToolTip(
            "On: mark text that only shifted position (reflow) in blue.\n"
            "Off: hide it — only show real additions (green) and "
            "removals (red).")
        self.compare_images_chk = QCheckBox("Detect figure/image changes")
        self.compare_images_chk.setChecked(True)
        self.compare_images_chk.setToolTip(
            "Also detect changed figures, charts, photos and logos "
            "(marked with a dashed orange box). Slightly slower.")
        btn_row.addWidget(self.ignore_case_chk)
        btn_row.addWidget(self.ignore_quotes_chk)
        btn_row.addWidget(self.show_moved_chk)
        btn_row.addWidget(self.compare_images_chk)

        btn_row.addSpacing(14)
        btn_row.addWidget(QLabel("Report:"))
        self.report_mode_combo = QComboBox()
        self.report_mode_combo.addItem("Changes list only (best for review)", "changes")
        self.report_mode_combo.addItem("Side-by-side visual (all pages)", "visual")
        self.report_mode_combo.addItem("Both: changes list + all pages", "both")
        self.report_mode_combo.setCurrentIndex(0)
        self.report_mode_combo.setToolTip(
            "Changes list: a clean list of exactly what text was added, "
            "removed, or replaced — easy to show someone.\n"
            "Side-by-side: page images with changes highlighted.\n"
            "Both: everything.")
        btn_row.addWidget(self.report_mode_combo)

        btn_row.addStretch(1)

        self.export_report_btn = QPushButton("  \u2193  Download Comparison Report (PDF)  ")
        self.export_report_btn.clicked.connect(self._export_report)
        self.export_report_btn.setCursor(Qt.PointingHandCursor)
        self.export_report_btn.setStyleSheet(
            "QPushButton {"
            "  background: #2667FF; color: white; font-weight: 600;"
            "  border: none; border-radius: 8px; padding: 9px 18px;"
            "  font-size: 13px; }"
            "QPushButton:hover { background: #1B57E0; }"
            "QPushButton:pressed { background: #1648C0; }"
            "QPushButton:disabled { background: #9DB4F0; }")
        btn_row.addWidget(self.export_report_btn)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

        # store paths for the export
        self._old_path = old_path
        self._new_path = new_path

        # run the diff
        self._results = compare_pdfs(old_path, new_path)
        added_total = sum(r["added_lines"] for r in self._results)
        removed_total = sum(r["removed_lines"] for r in self._results)
        changed_pages = sum(1 for r in self._results if r["status"] == "changed")
        only_old = sum(1 for r in self._results if r["status"] == "old_only")
        only_new = sum(1 for r in self._results if r["status"] == "new_only")
        self.summary_label.setText(
            f"  {changed_pages} changed pages, "
            f"+{added_total} / −{removed_total} lines, "
            f"{only_old} only in old, {only_new} only in new")

        for r in self._results:
            tag = {"same": "=", "changed": "≠",
                   "old_only": "← only old", "new_only": "→ only new"}[r["status"]]
            self.page_combo.addItem(f"Page {r['page']}  {tag}")
        self.page_combo.currentIndexChanged.connect(self._show_page_diff)
        # jump to first changed page
        first_changed = next((i for i, r in enumerate(self._results)
                              if r["status"] != "same"), 0)
        self.page_combo.setCurrentIndex(first_changed)
        self._show_page_diff(first_changed)

    def _goto_change(self, direction: int):
        """Jump the page picker to the next/previous changed page.
        direction: +1 = next, -1 = previous."""
        if not getattr(self, "_results", None):
            return
        changed_idx = [i for i, r in enumerate(self._results)
                       if r["status"] != "same"]
        if not changed_idx:
            self.summary_label.setText("  No changes to navigate.")
            return
        cur = self.page_combo.currentIndex()
        if direction > 0:
            nxt = next((i for i in changed_idx if i > cur), changed_idx[0])
        else:
            prevs = [i for i in changed_idx if i < cur]
            nxt = prevs[-1] if prevs else changed_idx[-1]
        self.page_combo.setCurrentIndex(nxt)

    def _show_page_diff(self, idx: int):
        if idx < 0 or idx >= len(self._results):
            return
        r = self._results[idx]
        self.diff_view.setHtml(r["diff_html"])
        if r["status"] in ("same", "changed", "old_only"):
            self.old_viewer.goto_page(idx)
        if r["status"] in ("same", "changed", "new_only"):
            self.new_viewer.goto_page(idx)

    def _sync_from_old(self, value):
        if self._suppress_sync: return
        self._suppress_sync = True
        try:
            old_bar = self.old_viewer.verticalScrollBar()
            new_bar = self.new_viewer.verticalScrollBar()
            ratio = value / max(1, old_bar.maximum())
            new_bar.setValue(int(ratio * new_bar.maximum()))
        finally:
            self._suppress_sync = False

    def _sync_from_new(self, value):
        if self._suppress_sync: return
        self._suppress_sync = True
        try:
            old_bar = self.old_viewer.verticalScrollBar()
            new_bar = self.new_viewer.verticalScrollBar()
            ratio = value / max(1, new_bar.maximum())
            old_bar.setValue(int(ratio * old_bar.maximum()))
        finally:
            self._suppress_sync = False

    def closeEvent(self, event):
        try:
            self._old_doc.close()
            self._new_doc.close()
        except Exception:
            pass
        super().closeEvent(event)

    def _export_report(self):
        """Generate an Adobe-style PDF comparison report."""
        from core.comparer import generate_compare_report
        # Suggest a filename next to the new file
        base = os.path.splitext(os.path.basename(self._new_path))[0]
        default = os.path.join(os.path.dirname(self._new_path),
                               f"{base}-comparison-report.pdf")
        out, _ = QFileDialog.getSaveFileName(
            self, "Save comparison report PDF",
            default, "PDF (*.pdf)")
        if not out:
            return
        if not out.lower().endswith(".pdf"):
            out += ".pdf"

        # Get author from app settings if available
        author = ""
        try:
            from utils.settings import AppSettings
            from utils.constants import APP_AUTHOR
            author = APP_AUTHOR
        except Exception:
            pass

        self.export_report_btn.setEnabled(False)
        self.export_report_btn.setText("  Generating report…  ")
        QApplication.processEvents()
        try:
            stats = generate_compare_report(
                self._old_path, self._new_path, out,
                render_dpi=110, author=author,
                ignore_case=self.ignore_case_chk.isChecked(),
                ignore_quotes=self.ignore_quotes_chk.isChecked(),
                include_changelog=True,
                report_mode=self.report_mode_combo.currentData(),
                all_pages=True,
                show_moved=self.show_moved_chk.isChecked(),
                compare_images=self.compare_images_chk.isChecked())
            QMessageBox.information(
                self, "Report saved",
                f"Comparison report saved to:\n{out}\n\n"
                f"Report pages: {stats['pages']}\n"
                f"Changed source pages: {stats['changed']}\n\n"
                f"Phrases replaced: {stats.get('replaced', 0)}\n"
                f"Text inserted:    {stats.get('inserted', 0)}\n"
                f"Text deleted:     {stats.get('deleted', 0)}\n\n"
                f"Words added (+):   {stats['added_words']}\n"
                f"Words removed (\u2212): {stats['removed_words']}")
            # Offer to open it
            r = QMessageBox.question(
                self, "Open report?",
                "Open the report PDF now in MasumPDF Reader?",
                QMessageBox.Yes | QMessageBox.No)
            if r == QMessageBox.Yes and self.parent() is not None:
                par = self.parent()
                if hasattr(par, "open_pdf"):
                    par.open_pdf(out)
                    self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Report failed", str(e))
        finally:
            self.export_report_btn.setEnabled(True)
            self.export_report_btn.setText(
                "  \u2193  Download Comparison Report (PDF)  ")


# =============================================================================
# Text color change dialog
# =============================================================================
class TextColorDialog(QDialog):
    """Pick a page and a new color for all text on that page."""

    def __init__(self, page_count: int, current_page: int = 1, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Change text color")
        self.setMinimumWidth(380)
        self._color_hex = "#0066CC"

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(
            "Change the color of text on one page.\n"
            "Works best on PDFs with selectable text. Pages that are\n"
            "scanned images need OCR first."))

        row1 = QHBoxLayout()
        row1.addWidget(QLabel("Page:"))
        self.page_spin = QSpinBox()
        self.page_spin.setRange(1, max(1, page_count))
        self.page_spin.setValue(max(1, min(current_page, page_count)))
        row1.addWidget(self.page_spin)
        row1.addStretch(1)
        layout.addLayout(row1)

        row2 = QHBoxLayout()
        row2.addWidget(QLabel("Color:"))
        self.color_btn = QPushButton(self._color_hex)
        self.color_btn.clicked.connect(self._pick_color)
        self._update_color_btn()
        row2.addWidget(self.color_btn)
        row2.addStretch(1)
        layout.addLayout(row2)

        layout.addWidget(QLabel(
            "<small>Note: the original text is replaced with the same\n"
            "characters drawn in a built-in font. Layout is preserved,\n"
            "but unusual fonts may look slightly different.</small>"))

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _pick_color(self):
        col = QColorDialog.getColor(QColor(self._color_hex), self,
                                    "Pick a text color")
        if col.isValid():
            self._color_hex = col.name().upper()
            self._update_color_btn()

    def _update_color_btn(self):
        self.color_btn.setText(self._color_hex)
        # show the color as the button background
        self.color_btn.setStyleSheet(
            f"QPushButton {{ background: {self._color_hex}; "
            f"color: {'white' if self._is_dark(self._color_hex) else 'black'}; "
            f"padding: 6px 14px; }}")

    @staticmethod
    def _is_dark(hex_str):
        h = hex_str.lstrip("#")
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        return (r * 0.299 + g * 0.587 + b * 0.114) < 140

    def page_index(self) -> int:
        return self.page_spin.value() - 1

    def color_hex(self) -> str:
        return self._color_hex


# =============================================================================
# Create blank PDF
# =============================================================================
class CreatePDFDialog(QDialog):
    """Create a new blank PDF."""

    def __init__(self, parent=None):
        super().__init__(parent)
        from core.pdf_creator import PAGE_SIZES
        self.setWindowTitle("Create blank PDF")
        self.setMinimumWidth(380)

        layout = QFormLayout(self)

        self.size_combo = QComboBox()
        for name in PAGE_SIZES.keys():
            self.size_combo.addItem(name)
        self.size_combo.setCurrentText("A4")
        layout.addRow("Page size:", self.size_combo)

        self.orient_combo = QComboBox()
        self.orient_combo.addItems(["Portrait", "Landscape"])
        layout.addRow("Orientation:", self.orient_combo)

        self.page_count = QSpinBox()
        self.page_count.setRange(1, 500)
        self.page_count.setValue(1)
        layout.addRow("Number of pages:", self.page_count)

        self.title_input = QLineEdit()
        layout.addRow("Title (optional):", self.title_input)

        self.author_input = QLineEdit()
        layout.addRow("Author (optional):", self.author_input)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addRow(btns)

    def settings(self) -> dict:
        return {
            "page_size": self.size_combo.currentText(),
            "orientation": self.orient_combo.currentText().lower(),
            "page_count": self.page_count.value(),
            "title": self.title_input.text().strip(),
            "author": self.author_input.text().strip(),
        }


# =============================================================================
# Prepare a form — pick a field type before placing it on the page
# =============================================================================
class PrepareFormDialog(QDialog):
    """Pick the type and properties of a new form field."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Prepare a form field")
        self.setMinimumWidth(420)

        layout = QFormLayout(self)
        layout.addRow(QLabel("Pick a field type, then drag a rectangle on the page."))

        self.type_combo = QComboBox()
        for name in ("Text", "Checkbox", "Dropdown", "Listbox", "Signature"):
            self.type_combo.addItem(name)
        layout.addRow("Field type:", self.type_combo)

        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Auto if blank")
        layout.addRow("Field name:", self.name_input)

        self.label_input = QLineEdit()
        layout.addRow("Label / tooltip:", self.label_input)

        self.default_input = QLineEdit()
        self.default_input.setPlaceholderText("Default value")
        layout.addRow("Default value:", self.default_input)

        self.options_input = QPlainTextEdit()
        self.options_input.setPlaceholderText("One option per line (Dropdown / Listbox)")
        self.options_input.setMaximumHeight(80)
        layout.addRow("Options:", self.options_input)

        self.required_check = QCheckBox("Required field")
        layout.addRow("", self.required_check)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addRow(btns)

    def settings(self) -> dict:
        opts_text = self.options_input.toPlainText().strip()
        options = [o.strip() for o in opts_text.splitlines() if o.strip()]
        return {
            "field_type": self.type_combo.currentText().lower(),
            "field_name": self.name_input.text().strip() or None,
            "field_label": self.label_input.text().strip(),
            "default_value": self.default_input.text(),
            "options": options or None,
            "required": self.required_check.isChecked(),
        }


# =============================================================================
# Fill & sign — list all form fields with editable values
# =============================================================================
class FillFormDialog(QDialog):
    """Show every form field in the document; let the user fill it."""

    def __init__(self, fields: list[dict], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Fill and sign")
        self.resize(640, 520)

        layout = QVBoxLayout(self)
        if not fields:
            layout.addWidget(QLabel(
                "<b>This PDF has no form fields.</b><br>"
                "Use the <i>Prepare Form</i> tool to add fields first."))
            btns = QDialogButtonBox(QDialogButtonBox.Close)
            btns.rejected.connect(self.reject)
            btns.accepted.connect(self.accept)
            btns.button(QDialogButtonBox.Close).clicked.connect(self.reject)
            layout.addWidget(btns)
            self._editors = []
            self._fields = []
            return

        layout.addWidget(QLabel(f"Found <b>{len(fields)}</b> form field(s)."))

        # scroll area for many fields
        from PySide6.QtWidgets import QScrollArea, QFrame
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        inner = QWidget()
        form_layout = QFormLayout(inner)

        self._editors: list[tuple[dict, object]] = []
        for f in fields:
            label_text = f"<b>{f['label'] or f['name']}</b>  " \
                         f"<small>(page {f['page'] + 1}, {f['type']})</small>"
            label = QLabel(label_text)

            ftype = f["type"]
            if ftype == "checkbox":
                editor = QCheckBox()
                val = f["value"]
                editor.setChecked(bool(val) and str(val).lower()
                                  not in ("", "false", "off", "no", "0"))
            elif ftype in ("dropdown", "listbox"):
                editor = QComboBox()
                editor.addItems(f["options"] or [])
                if f["value"] and f["value"] in (f["options"] or []):
                    editor.setCurrentText(f["value"])
            elif ftype == "signature":
                editor = QLabel("<i>Signature — use the Sign tool to place</i>")
            else:
                editor = QLineEdit()
                editor.setText(str(f["value"]) if f["value"] else "")

            form_layout.addRow(label, editor)
            self._editors.append((f, editor))

        scroll.setWidget(inner)
        layout.addWidget(scroll, 1)

        self._fields = fields

        # buttons
        btn_row = QHBoxLayout()
        self.flatten_check = QCheckBox("After saving, also save a flattened copy "
                                       "(values become part of the page, no longer editable)")
        btn_row.addWidget(self.flatten_check, 1)
        layout.addLayout(btn_row)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.button(QDialogButtonBox.Ok).setText("Save values")
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def filled_values(self) -> list[tuple[int, str, object]]:
        """Return list of (page_index, field_name, value)."""
        out = []
        for f, editor in self._editors:
            if isinstance(editor, QCheckBox):
                v = editor.isChecked()
            elif isinstance(editor, QComboBox):
                v = editor.currentText()
            elif isinstance(editor, QLineEdit):
                v = editor.text()
            else:
                continue
            out.append((f["page"], f["name"], v))
        return out

    def flatten_requested(self) -> bool:
        return self.flatten_check.isChecked()


# =============================================================================
# Stamp dialog
# =============================================================================
class StampDialog(QDialog):
    """Pick a stamp to place on the page."""

    def __init__(self, parent=None):
        super().__init__(parent)
        from core.stamp_manager import StampManager
        self.setWindowTitle("Add stamp")
        self.setMinimumWidth(420)
        self._custom_color = "#CC0000"

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Choose a stamp, then click on the page to place it."))

        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)

        # ---- standard stamps tab ----
        std_tab = QWidget()
        std_layout = QVBoxLayout(std_tab)
        self.std_combo = QComboBox()
        for n in StampManager.list_stamp_names():
            self.std_combo.addItem(n)
        std_layout.addWidget(QLabel("Standard PDF stamps:"))
        std_layout.addWidget(self.std_combo)
        std_layout.addStretch(1)
        self.tabs.addTab(std_tab, "Standard")

        # ---- custom text stamp tab ----
        cus_tab = QWidget()
        cus_layout = QFormLayout(cus_tab)
        self.custom_text = QLineEdit()
        self.custom_text.setText("REVIEWED")
        cus_layout.addRow("Text:", self.custom_text)
        self.color_btn = QPushButton(self._custom_color)
        self.color_btn.clicked.connect(self._pick_color)
        self._update_color_btn()
        cus_layout.addRow("Color:", self.color_btn)
        self.tabs.addTab(cus_tab, "Custom text")

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.button(QDialogButtonBox.Ok).setText("Pick spot on page")
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _pick_color(self):
        c = QColorDialog.getColor(QColor(self._custom_color), self, "Stamp color")
        if c.isValid():
            self._custom_color = c.name().upper()
            self._update_color_btn()

    def _update_color_btn(self):
        h = self._custom_color
        self.color_btn.setText(h)
        self.color_btn.setStyleSheet(
            f"QPushButton {{ background: {h}; padding: 6px 14px; color: white; }}")

    def settings(self) -> dict:
        if self.tabs.currentIndex() == 0:
            return {"kind": "standard", "name": self.std_combo.currentText()}
        return {"kind": "custom",
                "text": self.custom_text.text().strip(),
                "color": self._custom_color}


# =============================================================================
# Comment dialog — text + author for a click-to-place comment
# =============================================================================
class CommentDialog(QDialog):
    """Ask for a comment text + optional author."""

    def __init__(self, parent=None, default_author: str = ""):
        super().__init__(parent)
        self.setWindowTitle("Add comment")
        self.setMinimumWidth(420)

        layout = QFormLayout(self)
        self.author = QLineEdit()
        self.author.setText(default_author)
        layout.addRow("Author:", self.author)

        self.text = QPlainTextEdit()
        self.text.setMinimumHeight(120)
        layout.addRow("Comment:", self.text)

        layout.addRow(QLabel(
            "<small>Click on the page where you want this comment to appear.</small>"))

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.button(QDialogButtonBox.Ok).setText("Pick spot on page")
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addRow(btns)

    def settings(self) -> dict:
        return {
            "author": self.author.text().strip(),
            "text": self.text.toPlainText().strip(),
        }


# =============================================================================
# Rich media dialog — URL link, internal jump, or file attachment
# =============================================================================
class MediaDialog(QDialog):
    """Add a link or media to the page."""

    def __init__(self, page_count: int, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add link or media")
        self.setMinimumWidth(480)
        self._file_path = None
        self._page_count = page_count

        layout = QVBoxLayout(self)
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)

        # ---- URL ----
        url_tab = QWidget()
        ul = QFormLayout(url_tab)
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("https://example.com")
        ul.addRow("URL:", self.url_input)
        ul.addRow(QLabel(
            "<small>Drag a rectangle on the page where the link should be clickable.</small>"))
        self.tabs.addTab(url_tab, "Web URL")

        # ---- internal page link ----
        jump_tab = QWidget()
        jl = QFormLayout(jump_tab)
        self.jump_target = QSpinBox()
        self.jump_target.setRange(1, max(1, page_count))
        jl.addRow("Jump to page:", self.jump_target)
        jl.addRow(QLabel(
            "<small>Drag a rectangle for the clickable area.</small>"))
        self.tabs.addTab(jump_tab, "Jump to page")

        # ---- file attachment ----
        att_tab = QWidget()
        al = QVBoxLayout(att_tab)
        row = QHBoxLayout()
        self.att_path = QLineEdit()
        self.att_path.setReadOnly(True)
        self.att_path.setPlaceholderText("Pick a file…")
        row.addWidget(self.att_path, 1)
        pick = QPushButton("Browse…")
        pick.clicked.connect(self._pick_file)
        row.addWidget(pick)
        al.addLayout(row)
        self.att_desc = QLineEdit()
        self.att_desc.setPlaceholderText("Description (optional)")
        al.addWidget(self.att_desc)
        al.addWidget(QLabel(
            "<small>A paperclip icon will be placed where you click on the page.\n"
            "Any file type works.</small>"))
        al.addStretch(1)
        self.tabs.addTab(att_tab, "File attachment")

        # ---- media pointer (audio/video) ----
        med_tab = QWidget()
        ml = QVBoxLayout(med_tab)
        ml.addWidget(QLabel(
            "<b>Honest note:</b> PDF supports embedded audio/video,\n"
            "but most viewers won't play them. The most portable option is\n"
            "to embed the media file as an attachment with a clickable\n"
            "labelled area — that's what this tool does.\n"))
        row2 = QHBoxLayout()
        self.med_path = QLineEdit()
        self.med_path.setReadOnly(True)
        self.med_path.setPlaceholderText("Pick an audio or video file…")
        row2.addWidget(self.med_path, 1)
        pick2 = QPushButton("Browse…")
        pick2.clicked.connect(self._pick_media)
        row2.addWidget(pick2)
        ml.addLayout(row2)
        self.med_label = QLineEdit("Click to play media")
        ml.addWidget(self.med_label)
        ml.addWidget(QLabel("<small>Drag a rectangle for the play button area.</small>"))
        ml.addStretch(1)
        self.tabs.addTab(med_tab, "Audio / Video")

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.button(QDialogButtonBox.Ok).setText("Pick spot on page")
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _pick_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Pick a file to attach",
                                              "", "All files (*)")
        if path:
            self.att_path.setText(path)

    def _pick_media(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Pick an audio or video file", "",
            "Media (*.mp3 *.mp4 *.wav *.m4a *.mov *.avi *.webm *.ogg);;All files (*)")
        if path:
            self.med_path.setText(path)

    def settings(self) -> dict:
        idx = self.tabs.currentIndex()
        if idx == 0:
            return {"kind": "url", "url": self.url_input.text().strip()}
        if idx == 1:
            return {"kind": "internal", "target_page": self.jump_target.value() - 1}
        if idx == 2:
            return {"kind": "attachment",
                    "path": self.att_path.text().strip(),
                    "description": self.att_desc.text().strip()}
        return {"kind": "media",
                "path": self.med_path.text().strip(),
                "label": self.med_label.text().strip() or "Click to play"}


# =============================================================================
# Send for review / export comments
# =============================================================================
class SendCommentsDialog(QDialog):
    """Compose an email summary with the document's comments."""

    def __init__(self, comments: list[dict], pdf_path: str | None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Send for review")
        self.resize(540, 520)
        self._pdf_path = pdf_path

        layout = QVBoxLayout(self)

        # Build a comments summary string
        if comments:
            lines = [f"Comments on {os.path.basename(pdf_path) if pdf_path else 'this PDF'}:\n"]
            for c in comments:
                page = c.get("page", "?")
                author = c.get("author", "")
                text = c.get("content", "") or ""
                ctype = c.get("type", "Note")
                lines.append(f"— Page {int(page) + 1 if isinstance(page, int) else page}: "
                             f"[{ctype}] {author}: {text}".rstrip())
            summary = "\n".join(lines)
        else:
            summary = "(No comments in this document yet.)\n"

        layout.addWidget(QLabel("Recipient email (optional):"))
        self.to_input = QLineEdit()
        self.to_input.setPlaceholderText("name@example.com")
        layout.addWidget(self.to_input)

        layout.addWidget(QLabel("Subject:"))
        self.subj_input = QLineEdit()
        name = os.path.basename(pdf_path) if pdf_path else "PDF document"
        self.subj_input.setText(f"Review request: {name}")
        layout.addWidget(self.subj_input)

        layout.addWidget(QLabel("Message:"))
        self.body_input = QPlainTextEdit()
        self.body_input.setPlainText(
            f"Hi,\n\nPlease review the attached PDF and respond with any feedback.\n\n"
            f"{summary}\n\nThanks!")
        layout.addWidget(self.body_input, 1)

        layout.addWidget(QLabel(
            "<small>Clicking <b>Open in mail client</b> will launch your default email "
            "program with these fields pre-filled. You'll need to attach the PDF "
            "file yourself.<br>"
            "Use <b>Save as text</b> to export the comments to a .txt file instead."
            "</small>"))

        btn_row = QHBoxLayout()
        self.save_btn = QPushButton("Save comments as text…")
        self.save_btn.clicked.connect(self._save_text)
        btn_row.addWidget(self.save_btn)
        btn_row.addStretch(1)
        self.mail_btn = QPushButton("Open in mail client")
        self.mail_btn.setDefault(True)
        self.mail_btn.clicked.connect(self._open_mail)
        btn_row.addWidget(self.mail_btn)
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.reject)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

    def _save_text(self):
        path, _ = QFileDialog.getSaveFileName(self, "Save comments as text",
                                              "comments.txt", "Text (*.txt)")
        if not path:
            return
        if not path.lower().endswith(".txt"):
            path += ".txt"
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(self.body_input.toPlainText())
            QMessageBox.information(self, "Saved", f"Comments saved to:\n{path}")
        except Exception as e:
            QMessageBox.critical(self, "Save failed", str(e))

    def _open_mail(self):
        from urllib.parse import quote
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices
        to = quote(self.to_input.text().strip())
        subj = quote(self.subj_input.text().strip())
        body = quote(self.body_input.toPlainText())
        url = f"mailto:{to}?subject={subj}&body={body}"
        # Some mail clients have URL length limits, mention this if very long
        if len(url) > 8000:
            QMessageBox.information(self, "Long message",
                                    "Your message is very long. Some mail "
                                    "clients may truncate it. Consider saving "
                                    "it as a text file instead.")
        QDesktopServices.openUrl(QUrl(url))
        self.accept()


# =============================================================================
# Edit a single line of text
# =============================================================================
class EditLineDialog(QDialog):
    """Edit the text of one line on a PDF page."""

    def __init__(self, current_text: str, page_index: int,
                 font_hint: str = "", font_size: float = 11.0, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Edit line text")
        self.setMinimumWidth(540)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(
            f"<b>Page {page_index + 1}</b>  •  "
            f"<small>Original font hint: {font_hint or 'unknown'}, "
            f"size {font_size:.1f}pt</small>"
        ))
        layout.addWidget(QLabel("Edit the line, then click Save:"))

        self.text_edit = QPlainTextEdit()
        self.text_edit.setPlainText(current_text)
        self.text_edit.setMinimumHeight(70)
        layout.addWidget(self.text_edit)

        # Color
        self._color_hex = "#000000"
        color_row = QHBoxLayout()
        color_row.addWidget(QLabel("Text color:"))
        self.color_btn = QPushButton(self._color_hex)
        self.color_btn.clicked.connect(self._pick_color)
        self._update_color_btn()
        color_row.addWidget(self.color_btn)
        color_row.addStretch(1)
        layout.addLayout(color_row)

        layout.addWidget(QLabel(
            "<small>The original characters are whited out and the new text is "
            "redrawn using a built-in font that matches the style. "
            "Best results on plain text PDFs — heavy layouts may shift slightly. "
            "The original file is not changed; you'll be asked where to save.</small>"))

        btns = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _pick_color(self):
        c = QColorDialog.getColor(QColor(self._color_hex), self, "Text color")
        if c.isValid():
            self._color_hex = c.name().upper()
            self._update_color_btn()

    def _update_color_btn(self):
        self.color_btn.setText(self._color_hex)
        dark = TextColorDialog._is_dark(self._color_hex)
        self.color_btn.setStyleSheet(
            f"QPushButton {{ background: {self._color_hex}; "
            f"color: {'white' if dark else 'black'}; padding: 6px 14px; }}")

    def new_text(self) -> str:
        return self.text_edit.toPlainText()

    def color_hex(self) -> str:
        return self._color_hex


# =============================================================================
# Add text dialog (click-to-place workflow)
# =============================================================================
class AddTextDialog(QDialog):
    """Pick text content + style before placing it on the page."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add text")
        self.setMinimumWidth(440)
        self._color_hex = "#000000"

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Enter the text, then click on the page to place it."))

        self.text = QPlainTextEdit()
        self.text.setMinimumHeight(80)
        self.text.setPlaceholderText("Your text here…")
        layout.addWidget(self.text)

        row = QHBoxLayout()
        row.addWidget(QLabel("Size:"))
        self.size_spin = QSpinBox()
        self.size_spin.setRange(6, 96)
        self.size_spin.setValue(12)
        self.size_spin.setSuffix(" pt")
        row.addWidget(self.size_spin)
        row.addSpacing(16)
        row.addWidget(QLabel("Style:"))
        self.style_combo = QComboBox()
        self.style_combo.addItems(["Regular", "Bold", "Italic", "Bold Italic",
                                   "Serif", "Monospace"])
        row.addWidget(self.style_combo)
        row.addStretch(1)
        layout.addLayout(row)

        row2 = QHBoxLayout()
        row2.addWidget(QLabel("Color:"))
        self.color_btn = QPushButton(self._color_hex)
        self.color_btn.clicked.connect(self._pick_color)
        self._update_color_btn()
        row2.addWidget(self.color_btn)
        row2.addStretch(1)
        layout.addLayout(row2)

        layout.addWidget(QLabel(
            "<small>Added text becomes an editable annotation on the page "
            "and is saved into the PDF when you save the file.</small>"))

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.button(QDialogButtonBox.Ok).setText("Place on page")
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _pick_color(self):
        c = QColorDialog.getColor(QColor(self._color_hex), self, "Text color")
        if c.isValid():
            self._color_hex = c.name().upper()
            self._update_color_btn()

    def _update_color_btn(self):
        self.color_btn.setText(self._color_hex)
        dark = TextColorDialog._is_dark(self._color_hex)
        self.color_btn.setStyleSheet(
            f"QPushButton {{ background: {self._color_hex}; "
            f"color: {'white' if dark else 'black'}; padding: 6px 14px; }}")

    def settings(self) -> dict:
        return {
            "text": self.text.toPlainText(),
            "size": float(self.size_spin.value()),
            "style": self.style_combo.currentText(),
            "color": self._color_hex,
        }


# =============================================================================
# Header & Footer dialog
# =============================================================================
class HeaderFooterDialog(QDialog):
    """Configure left/center/right header & footer text for a page range."""

    def __init__(self, page_count: int, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Header & Footer")
        self.setMinimumWidth(620)
        self._color_hex = "#444444"
        self._page_count = page_count

        layout = QVBoxLayout(self)

        layout.addWidget(QLabel(
            "Add headers and footers to your pages. You can use these tokens:"))
        tok = QLabel(
            "<small><code>{page}</code> page number  •  "
            "<code>{total}</code> total pages  •  "
            "<code>{date}</code> today's date  •  "
            "<code>{time}</code>  •  "
            "<code>{filename}</code></small>")
        tok.setWordWrap(True)
        layout.addWidget(tok)

        # Header row: left / center / right
        h_group = QGroupBox("Header")
        hl = QFormLayout(h_group)
        self.h_left = QLineEdit()
        self.h_center = QLineEdit()
        self.h_right = QLineEdit()
        hl.addRow("Left:", self.h_left)
        hl.addRow("Center:", self.h_center)
        hl.addRow("Right:", self.h_right)
        layout.addWidget(h_group)

        # Footer row
        f_group = QGroupBox("Footer")
        fl = QFormLayout(f_group)
        self.f_left = QLineEdit()
        self.f_center = QLineEdit("Page {page} of {total}")
        self.f_right = QLineEdit()
        fl.addRow("Left:", self.f_left)
        fl.addRow("Center:", self.f_center)
        fl.addRow("Right:", self.f_right)
        layout.addWidget(f_group)

        # Style row
        style_group = QGroupBox("Style")
        sl = QFormLayout(style_group)
        self.size_spin = QSpinBox()
        self.size_spin.setRange(6, 24); self.size_spin.setValue(10)
        self.size_spin.setSuffix(" pt")
        sl.addRow("Font size:", self.size_spin)

        self.style_combo = QComboBox()
        self.style_combo.addItems(["Regular", "Bold", "Italic", "Bold Italic",
                                   "Serif", "Monospace"])
        sl.addRow("Style:", self.style_combo)

        self.color_btn = QPushButton(self._color_hex)
        self.color_btn.clicked.connect(self._pick_color)
        self._update_color_btn()
        sl.addRow("Color:", self.color_btn)

        layout.addWidget(style_group)

        # Page range
        range_group = QGroupBox("Page range")
        rl = QHBoxLayout(range_group)
        self.range_all = QCheckBox("All pages")
        self.range_all.setChecked(True)
        rl.addWidget(self.range_all)
        rl.addWidget(QLabel("From:"))
        self.from_spin = QSpinBox()
        self.from_spin.setRange(1, max(1, page_count)); self.from_spin.setValue(1)
        self.from_spin.setEnabled(False)
        rl.addWidget(self.from_spin)
        rl.addWidget(QLabel("To:"))
        self.to_spin = QSpinBox()
        self.to_spin.setRange(1, max(1, page_count)); self.to_spin.setValue(page_count)
        self.to_spin.setEnabled(False)
        rl.addWidget(self.to_spin)
        self.range_all.toggled.connect(lambda on: self.from_spin.setEnabled(not on))
        self.range_all.toggled.connect(lambda on: self.to_spin.setEnabled(not on))
        layout.addWidget(range_group)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _pick_color(self):
        c = QColorDialog.getColor(QColor(self._color_hex), self, "Color")
        if c.isValid():
            self._color_hex = c.name().upper()
            self._update_color_btn()

    def _update_color_btn(self):
        self.color_btn.setText(self._color_hex)
        dark = TextColorDialog._is_dark(self._color_hex)
        self.color_btn.setStyleSheet(
            f"QPushButton {{ background: {self._color_hex}; "
            f"color: {'white' if dark else 'black'}; padding: 6px 14px; }}")

    def settings(self) -> dict:
        if self.range_all.isChecked():
            rng = None
        else:
            rng = (self.from_spin.value() - 1, self.to_spin.value() - 1)
        return {
            "header_left":   self.h_left.text(),
            "header_center": self.h_center.text(),
            "header_right":  self.h_right.text(),
            "footer_left":   self.f_left.text(),
            "footer_center": self.f_center.text(),
            "footer_right":  self.f_right.text(),
            "font_size": float(self.size_spin.value()),
            "style": self.style_combo.currentText(),
            "color_hex": self._color_hex,
            "page_range": rng,
        }
