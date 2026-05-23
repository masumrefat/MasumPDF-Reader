"""Top toolbar with primary actions."""

from PySide6.QtWidgets import (
    QToolBar, QToolButton, QLineEdit, QLabel, QComboBox,
    QWidget, QHBoxLayout, QPushButton, QSizePolicy, QFrame,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction, QIcon, QKeySequence


def _make_action(parent, text: str, shortcut: str = "", tooltip: str = ""):
    a = QAction(text, parent)
    if shortcut:
        a.setShortcut(QKeySequence(shortcut))
    a.setToolTip(tooltip or text)
    return a


class MainToolbar(QToolBar):
    """Primary toolbar shown at the top of the main window."""

    # Outgoing signals — keeps the toolbar decoupled from window logic
    open_requested = Signal()
    save_requested = Signal()
    save_as_requested = Signal()
    print_requested = Signal()
    zoom_in_requested = Signal()
    zoom_out_requested = Signal()
    fit_width_requested = Signal()
    fit_page_requested = Signal()
    rotate_requested = Signal(int)
    view_mode_changed = Signal(str)
    search_text_changed = Signal(str)
    search_next_requested = Signal()
    search_prev_requested = Signal()
    organize_requested = Signal()
    merge_requested = Signal()
    split_requested = Signal()
    extract_requested = Signal()
    convert_to_images_requested = Signal()
    images_to_pdf_requested = Signal()
    extract_text_requested = Signal()
    ocr_requested = Signal()
    encrypt_requested = Signal()
    decrypt_requested = Signal()
    sign_requested = Signal()
    annotate_highlight_requested = Signal()
    annotate_note_requested = Signal()
    theme_toggle_requested = Signal()
    properties_requested = Signal()
    compress_requested = Signal()
    compare_requested = Signal()
    text_color_requested = Signal()
    create_pdf_requested = Signal()
    prepare_form_requested = Signal()
    fill_form_requested = Signal()
    stamp_requested = Signal()
    comment_requested = Signal()
    media_requested = Signal()
    send_review_requested = Signal()
    mark_reference_requested = Signal()
    save_note_requested = Signal()
    language_changed = Signal(str)

    def __init__(self, parent=None):
        super().__init__("Main toolbar", parent)
        self.setMovable(False)
        self.setIconSize(self.iconSize())

        self._build()

    def _add_btn(self, text: str, tooltip: str, signal):
        b = QToolButton()
        b.setText(text)
        b.setToolTip(tooltip)
        b.setToolButtonStyle(Qt.ToolButtonTextOnly)
        b.clicked.connect(lambda: signal.emit())
        self.addWidget(b)
        return b

    def _add_sep(self):
        s = QFrame()
        s.setFrameShape(QFrame.VLine)
        s.setStyleSheet("color: #C0C0C6;")
        s.setFixedHeight(22)
        self.addWidget(s)

    def _build(self):
        # File
        self._add_btn("Open", "Open a PDF (Ctrl+O)", self.open_requested)
        self._add_btn("Save", "Save (Ctrl+S)", self.save_requested)
        self._add_btn("Save As", "Save a copy", self.save_as_requested)

        self._add_sep()

        # Zoom
        self._add_btn("−", "Zoom out (Ctrl+−)", self.zoom_out_requested)
        self.zoom_label = QLabel("100%")
        self.zoom_label.setMinimumWidth(48)
        self.zoom_label.setAlignment(Qt.AlignCenter)
        self.addWidget(self.zoom_label)
        self._add_btn("+", "Zoom in (Ctrl++)", self.zoom_in_requested)
        self._add_btn("Fit W", "Fit width", self.fit_width_requested)
        self._add_btn("Fit", "Fit page", self.fit_page_requested)

        self._add_sep()

        # View mode
        self.view_mode_combo = QComboBox()
        self.view_mode_combo.addItems(["Continuous", "Single page", "Two pages"])
        self.view_mode_combo.setToolTip("View mode")
        self.view_mode_combo.currentIndexChanged.connect(self._on_view_mode)
        self.addWidget(self.view_mode_combo)

        # Rotate
        rotate_btn = QToolButton()
        rotate_btn.setText("↻")
        rotate_btn.setToolTip("Rotate view 90°")
        rotate_btn.clicked.connect(lambda: self.rotate_requested.emit(90))
        self.addWidget(rotate_btn)

        self._add_sep()

        # ---- Collect tools (placed in the open band at the top) ----
        # These toggle "modes": when ON, dragging over text on the page
        # saves it (as a reference, or as a note) instead of just copying.
        self.mark_ref_btn = QToolButton()
        self.mark_ref_btn.setText("\u2605  Collect Reference")
        self.mark_ref_btn.setToolTip(
            "Mark & collect references.\n"
            "When ON, drag over a reference in the bibliography to save it "
            "to your Reference Collection.")
        self.mark_ref_btn.setCheckable(True)
        self.mark_ref_btn.setToolButtonStyle(Qt.ToolButtonTextOnly)
        self.mark_ref_btn.clicked.connect(self.mark_reference_requested.emit)
        self.addWidget(self.mark_ref_btn)

        self.save_note_btn = QToolButton()
        self.save_note_btn.setText("\U0001F4DD  Save Text as Note")
        self.save_note_btn.setToolTip(
            "Save selected text as a note.\n"
            "When ON, drag over any text to save it as a note with its "
            "page number and source file.")
        self.save_note_btn.setCheckable(True)
        self.save_note_btn.setToolButtonStyle(Qt.ToolButtonTextOnly)
        self.save_note_btn.clicked.connect(self.save_note_requested.emit)
        self.addWidget(self.save_note_btn)

        # spacer
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.addWidget(spacer)

        # Search
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search in document…")
        self.search_input.setMinimumWidth(150)
        self.search_input.setMaximumWidth(220)
        self.search_input.textChanged.connect(self.search_text_changed.emit)
        self.search_input.returnPressed.connect(self.search_next_requested.emit)
        self.addWidget(self.search_input)
        self._add_btn("↑", "Previous result", self.search_prev_requested)
        self._add_btn("↓", "Next result", self.search_next_requested)

        self._add_sep()

        self._add_btn("Info", "Document properties", self.properties_requested)
        self._add_btn("Theme", "Toggle dark/light theme", self.theme_toggle_requested)

        self._add_sep()

        # ---- Interface language selector (clearly visible on the top bar) ----
        # Kept compact (globe + short name) so it always fits on the bar; the
        # full language name shows in the tooltip and in the dropdown list.
        from utils.i18n import available_languages, current_language, tr
        globe = QLabel(" \U0001F310")   # 🌐
        globe.setToolTip(tr("Interface language"))
        self.addWidget(globe)
        self.lang_combo = QComboBox()
        self.lang_combo.setToolTip(tr("Interface language"))
        # short labels in the closed box, full names in the popup list
        short = {
            "en": "EN", "bn": "বাংলা", "es": "ES", "ar": "العربية",
            "hi": "हिन्दी", "ja": "日本語", "zh": "中文", "de": "DE",
        }
        for code, name in available_languages().items():
            # itemText is the full name (shown in the list); we override the
            # displayed text of the current item via setCurrentText-like trick
            self.lang_combo.addItem(name, code)
        self.lang_combo.setMinimumWidth(96)
        self.lang_combo.setMaximumWidth(150)
        self._lang_short = short
        cur = current_language()
        for i in range(self.lang_combo.count()):
            if self.lang_combo.itemData(i) == cur:
                self.lang_combo.setCurrentIndex(i)
                break
        self.lang_combo.currentIndexChanged.connect(self._on_language)
        self.addWidget(self.lang_combo)

        # ---- Legacy checkable button attributes ----
        # The All Tools panel now owns all editing tools, but some code in
        # main_window still refers to these toolbar buttons via _set_tool_btn /
        # getattr(self.toolbar, f"{name}_btn"). Provide hidden no-op buttons so
        # those references stay valid without cluttering the toolbar.
        from PySide6.QtWidgets import QPushButton as _QPB
        for _name in ("highlight", "comment", "stamp", "sign",
                      "prepare_form", "media"):
            _b = _QPB(self)
            _b.setCheckable(True)
            _b.setVisible(False)
            setattr(self, f"{_name}_btn", _b)

    def _on_view_mode(self, idx):
        mapping = {0: "continuous", 1: "single", 2: "two_page"}
        self.view_mode_changed.emit(mapping.get(idx, "continuous"))

    def _on_language(self, idx):
        code = self.lang_combo.itemData(idx)
        if code:
            self.language_changed.emit(code)

    def set_zoom_label(self, zoom: float):
        self.zoom_label.setText(f"{int(zoom * 100)}%")

    def set_search_text(self, text: str):
        if self.search_input.text() != text:
            self.search_input.blockSignals(True)
            self.search_input.setText(text)
            self.search_input.blockSignals(False)

    def set_collect_states(self, ref_on: bool, note_on: bool):
        """Keep the two toggle buttons in sync with the window's real mode."""
        for btn, on in ((self.mark_ref_btn, ref_on),
                        (self.save_note_btn, note_on)):
            btn.blockSignals(True)
            btn.setChecked(bool(on))
            btn.blockSignals(False)
