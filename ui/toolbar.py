"""Top toolbar with primary actions."""

from PySide6.QtWidgets import (
    QToolBar, QToolButton, QLineEdit, QLabel, QComboBox,
    QWidget, QHBoxLayout, QPushButton, QSizePolicy, QFrame,
)
from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QAction, QIcon, QKeySequence
from ui.icons import make_icon

TOOLBAR_ICON_SIZE = 18


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
    color_theme_changed = Signal(str)
    app_theme_changed = Signal(str, str)  # appearance, accent color
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
    home_requested = Signal()
    tools_bar_toggle_requested = Signal()

    def __init__(self, parent=None):
        super().__init__("Main toolbar", parent)
        self.setMovable(False)
        self.setFloatable(False)
        self.setMinimumHeight(34)
        self.setMaximumHeight(38)
        self.setIconSize(QSize(TOOLBAR_ICON_SIZE, TOOLBAR_ICON_SIZE))

        self._build()

    def _add_btn(self, text: str, tooltip: str, signal, min_width: int = 0, icon: str | None = None):
        b = QToolButton()
        b.setObjectName("QuickActionButton")
        b.setText(text)
        b.setToolTip(tooltip)
        if icon:
            b.setIcon(make_icon(icon, "#1F2937", TOOLBAR_ICON_SIZE))
            b.setIconSize(QSize(TOOLBAR_ICON_SIZE, TOOLBAR_ICON_SIZE))
            b.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        else:
            b.setToolButtonStyle(Qt.ToolButtonTextOnly)
        b.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)
        b.setMinimumHeight(28)
        if min_width:
            b.setMinimumWidth(min_width)
        b.clicked.connect(lambda: signal.emit())
        self.addWidget(b)
        return b

    def _add_sep(self):
        s = QFrame()
        s.setObjectName("ToolbarSeparator")
        s.setFrameShape(QFrame.VLine)
        s.setFixedHeight(22)
        self.addWidget(s)

    def _build(self):
        # Navigation / File — compact labels so nothing is clipped.
        self._add_btn("Home", "Go to the Home screen", self.home_requested, 76, "home")
        self._add_btn("Open", "Open a PDF (Ctrl+O)", self.open_requested, 68, "open")
        self._add_btn("Save", "Save (Ctrl+S)", self.save_requested, 66, "save")
        self._add_btn("Save As", "Save a copy", self.save_as_requested, 70)

        self._add_sep()

        # Zoom
        self._add_btn("", "Zoom out (Ctrl+−)", self.zoom_out_requested, 40, "zoom_out")
        self.zoom_label = QLabel("100%")
        self.zoom_label.setObjectName("ZoomLabel")
        self.zoom_label.setMinimumWidth(48)
        self.zoom_label.setAlignment(Qt.AlignCenter)
        self.addWidget(self.zoom_label)
        self._add_btn("", "Zoom in (Ctrl++)", self.zoom_in_requested, 40, "zoom_in")
        self._add_btn("Fit W", "Fit width", self.fit_width_requested, 56)
        self._add_btn("Fit", "Fit page", self.fit_page_requested, 46)

        self._add_sep()

        # View mode
        self.view_mode_combo = QComboBox()
        self.view_mode_combo.setObjectName("ViewModeCombo")
        self.view_mode_combo.addItems(["Continuous", "Single page", "Two pages"])
        self.view_mode_combo.setToolTip("View mode")
        self.view_mode_combo.setMinimumWidth(120)
        self.view_mode_combo.setMaximumWidth(150)
        self.view_mode_combo.currentIndexChanged.connect(self._on_view_mode)
        self.addWidget(self.view_mode_combo)

        # Rotate
        rotate_btn = QToolButton()
        rotate_btn.setText("")
        rotate_btn.setIcon(make_icon("rotate_right", "#1F2937", TOOLBAR_ICON_SIZE))
        rotate_btn.setIconSize(QSize(TOOLBAR_ICON_SIZE, TOOLBAR_ICON_SIZE))
        rotate_btn.setToolTip("Rotate view 90°")
        rotate_btn.clicked.connect(lambda: self.rotate_requested.emit(90))
        self.addWidget(rotate_btn)

        self._add_sep()

        # ---- Collect tools (placed in the open band at the top) ----
        # These toggle "modes": when ON, dragging over text on the page
        # saves it (as a reference, or as a note) instead of just copying.
        self.mark_ref_btn = QToolButton()
        self.mark_ref_btn.setObjectName("CollectButton")
        self.mark_ref_btn.setText("Reference")
        self.mark_ref_btn.setIcon(make_icon("reference", "#1F2937", TOOLBAR_ICON_SIZE))
        self.mark_ref_btn.setIconSize(QSize(TOOLBAR_ICON_SIZE, TOOLBAR_ICON_SIZE))
        self.mark_ref_btn.setToolTip(
            "Mark & collect references.\n"
            "When ON, drag over a reference in the bibliography to save it "
            "to your Reference Collection.")
        self.mark_ref_btn.setCheckable(True)
        self.mark_ref_btn.setToolButtonStyle(Qt.ToolButtonTextOnly)
        self.mark_ref_btn.clicked.connect(self.mark_reference_requested.emit)
        self.addWidget(self.mark_ref_btn)

        self.save_note_btn = QToolButton()
        self.save_note_btn.setObjectName("CollectButton")
        self.save_note_btn.setText("Note")
        self.save_note_btn.setIcon(make_icon("note", "#1F2937", TOOLBAR_ICON_SIZE))
        self.save_note_btn.setIconSize(QSize(TOOLBAR_ICON_SIZE, TOOLBAR_ICON_SIZE))
        self.save_note_btn.setToolTip(
            "Save selected text as a note.\n"
            "When ON, drag over any text to save it as a note with its "
            "page number and source file.")
        self.save_note_btn.setCheckable(True)
        self.save_note_btn.setToolButtonStyle(Qt.ToolButtonTextOnly)
        self.save_note_btn.clicked.connect(self.save_note_requested.emit)
        self.addWidget(self.save_note_btn)

        self._add_sep()

        # ---- Interface language selector: highlighted and always visible ----
        # Keep it before the flexible spacer so it cannot disappear at the far
        # right of the toolbar.
        from utils.i18n import tr
        self.lang_badge = QLabel(" Language ")
        self.lang_badge.setObjectName("LanguageBadge")
        self.lang_badge.setToolTip(tr("Interface language"))
        self.addWidget(self.lang_badge)

        self.lang_combo = QComboBox()
        self.lang_combo.setObjectName("LanguageCombo")
        self.lang_combo.setToolTip(tr("Change interface language immediately"))
        self._populate_language_combo()
        self.lang_combo.currentIndexChanged.connect(self._on_language)
        self.addWidget(self.lang_combo)

        self.hide_tools_btn = QToolButton()
        self.hide_tools_btn.setObjectName("HideToolsButton")
        self.hide_tools_btn.setText("Hide Tools")
        self.hide_tools_btn.setToolTip("Auto-hide the large tools bar and keep a small top bar")
        self.hide_tools_btn.setToolButtonStyle(Qt.ToolButtonTextOnly)
        self.hide_tools_btn.clicked.connect(self.tools_bar_toggle_requested.emit)
        self.addWidget(self.hide_tools_btn)

        # ---- Highlighted theme button ----
        # Click opens Light/Dark + color choices. This is intentionally a big
        # visible top-bar control so users can find customization immediately.
        self.theme_btn = QToolButton()
        self.theme_btn.setObjectName("ThemeButton")
        self.theme_btn.setText("Theme")
        self.theme_btn.setIcon(make_icon("theme", "#1F2937", TOOLBAR_ICON_SIZE))
        self.theme_btn.setIconSize(QSize(TOOLBAR_ICON_SIZE, TOOLBAR_ICON_SIZE))
        self.theme_btn.setToolTip("Choose Light/Dark mode and app color")
        self.theme_btn.setToolButtonStyle(Qt.ToolButtonTextOnly)
        self.theme_btn.setPopupMode(QToolButton.InstantPopup)
        self.addWidget(self.theme_btn)
        self._build_theme_menu()

        # spacer
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.addWidget(spacer)

        # Search
        self.search_input = QLineEdit()
        self.search_input.setObjectName("GlobalSearch")
        self.search_input.setPlaceholderText("Find text, tools, or help")
        self.search_input.setMinimumWidth(190)
        self.search_input.setMaximumWidth(280)
        self.search_input.textChanged.connect(self.search_text_changed.emit)
        self.search_input.returnPressed.connect(self.search_next_requested.emit)
        self.addWidget(self.search_input)
        self._add_btn("", "Previous result", self.search_prev_requested, 36, "arrow_up")
        self._add_btn("", "Next result", self.search_next_requested, 36, "arrow_down")

        self._add_sep()

        self._add_btn("Info", "Document properties", self.properties_requested, 50)

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

    def _populate_language_combo(self):
        """Fill the highlighted language dropdown without emitting changes."""
        from utils.i18n import available_languages, current_language
        self.lang_combo.blockSignals(True)
        self.lang_combo.clear()
        for code, name in available_languages().items():
            # Keep both code and full name visible so users notice it.
            self.lang_combo.addItem(f"{code.upper()} — {name}", code)
        self.lang_combo.setMinimumWidth(132)
        self.lang_combo.setMaximumWidth(178)
        cur = current_language()
        for i in range(self.lang_combo.count()):
            if self.lang_combo.itemData(i) == cur:
                self.lang_combo.setCurrentIndex(i)
                break
        self.lang_combo.blockSignals(False)

    def refresh_language_selector(self):
        """Update the dropdown after language changes are applied live."""
        try:
            from utils.i18n import tr
            self.lang_badge.setToolTip(tr("Interface language"))
            self.lang_combo.setToolTip(tr("Change interface language immediately"))
            self._populate_language_combo()
        except Exception:
            pass

    def _build_theme_menu(self):
        from PySide6.QtWidgets import QMenu
        from utils.constants import COLOR_THEMES, APPEARANCES
        try:
            from utils.settings import AppSettings
            st = AppSettings()
            current_color = st.theme()
            current_appearance = st.appearance()
        except Exception:
            current_color = "blue"
            current_appearance = "light"

        menu = QMenu(self.theme_btn)

        appearance_menu = menu.addMenu("Mode")
        for code, name in APPEARANCES.items():
            act = appearance_menu.addAction(("✓ " if code == current_appearance else "   ") + name)
            act.triggered.connect(lambda checked=False, a=code: self.app_theme_changed.emit(a, current_color))

        color_menu = menu.addMenu("Color")
        swatches = {
            "blue": "●", "green": "●", "purple": "●",
            "orange": "●", "rose": "●", "graphite": "●",
        }
        for code, name in COLOR_THEMES.items():
            label = f"{swatches.get(code, '●')} {name}"
            if code == current_color:
                label = "✓ " + label
            else:
                label = "   " + label
            act = color_menu.addAction(label)
            act.triggered.connect(lambda checked=False, c=code: self.app_theme_changed.emit(current_appearance, c))

        menu.addSeparator()
        for appearance, color, label in (
            ("light", "blue", "Light Ocean Blue"),
            ("dark", "blue", "Dark Ocean Blue"),
            ("light", "green", "Light Research Green"),
            ("dark", "green", "Dark Research Green"),
            ("light", "purple", "Light Royal Purple"),
            ("dark", "purple", "Dark Royal Purple"),
        ):
            act = menu.addAction(label)
            act.triggered.connect(lambda checked=False, a=appearance, c=color: self.app_theme_changed.emit(a, c))

        self.theme_btn.setMenu(menu)
        mode = "Dark" if current_appearance == "dark" else "Light"
        self.theme_btn.setText(f"Theme: {mode}")

    def refresh_color_selector(self):
        try:
            self._build_theme_menu()
        except Exception:
            pass

    def _on_color_theme(self, idx):
        # Backward-compatible no-op hook for older code paths.
        pass

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
