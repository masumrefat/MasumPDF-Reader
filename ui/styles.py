"""Modern Qt stylesheets for MasumPDF Reader.

The goal is a clean researcher-focused UI: high contrast, readable spacing,
large click targets, soft cards, and consistent light/dark themes.
"""

LIGHT_THEME = """
* {
    font-family: 'Segoe UI', 'Noto Sans', 'Helvetica Neue', Arial, sans-serif;
    font-size: 14px;
}
QWidget {
    background-color: #F6F8FC;
    color: #172033;
}
QMainWindow {
    background-color: #F6F8FC;
}
QToolTip {
    background-color: #111827;
    color: #FFFFFF;
    border: 1px solid #111827;
    padding: 8px 10px;
    border-radius: 8px;
}
QMenuBar {
    background-color: #FFFFFF;
    border-bottom: 1px solid #E6EAF2;
    padding: 4px 8px;
}
QMenuBar::item {
    padding: 7px 12px;
    background: transparent;
    border-radius: 8px;
    color: #243047;
}
QMenuBar::item:selected {
    background-color: #EEF4FF;
    color: #174EA6;
}
QMenu {
    background-color: #FFFFFF;
    border: 1px solid #E1E6EF;
    border-radius: 12px;
    padding: 8px;
}
QMenu::item {
    padding: 8px 28px;
    border-radius: 8px;
    color: #243047;
}
QMenu::item:selected {
    background-color: #EEF4FF;
    color: #174EA6;
}
QToolBar {
    background-color: #FFFFFF;
    border: none;
    border-bottom: 1px solid #E6EAF2;
    padding: 8px;
    spacing: 6px;
}
QToolButton {
    background: transparent;
    border: 1px solid transparent;
    border-radius: 10px;
    padding: 8px 11px;
    color: #263248;
    font-weight: 600;
}
QToolButton:hover {
    background-color: #F0F5FF;
    border-color: #D9E6FF;
}
QToolButton:pressed {
    background-color: #E2ECFF;
}
QToolButton:checked {
    background-color: #E8F0FF;
    border-color: #9DBEFF;
    color: #1D4ED8;
}
QPushButton {
    background-color: #FFFFFF;
    border: 1px solid #D5DCE8;
    border-radius: 10px;
    padding: 8px 14px;
    color: #1F2937;
    font-weight: 600;
    min-height: 22px;
}
QPushButton:hover {
    background-color: #F2F6FF;
    border-color: #BFD3FF;
}
QPushButton:pressed {
    background-color: #E6EEFF;
}
QPushButton:disabled {
    background-color: #F1F4F9;
    color: #9AA5B5;
    border-color: #E1E7F0;
}
QPushButton:default, QPushButton#PrimaryButton {
    background-color: #2563EB;
    color: white;
    border-color: #2563EB;
}
QPushButton:default:hover, QPushButton#PrimaryButton:hover {
    background-color: #1D4ED8;
}
QPushButton#DangerButton {
    color: #B42318;
    border-color: #F3C2BD;
    background-color: #FFF8F7;
}
QPushButton#DangerButton:hover {
    background-color: #FFEDEA;
}
QLineEdit, QTextEdit, QPlainTextEdit, QSpinBox, QComboBox {
    background-color: #FFFFFF;
    border: 1px solid #D6DDE9;
    border-radius: 10px;
    padding: 8px 10px;
    color: #172033;
    selection-background-color: #2563EB;
    selection-color: white;
}
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QSpinBox:focus, QComboBox:focus {
    border: 1px solid #2563EB;
    background-color: #FFFFFF;
}
QComboBox::drop-down {
    border: none;
    width: 28px;
}
QListWidget, QListView, QTreeView, QTreeWidget, QTableWidget {
    background-color: #FFFFFF;
    border: 1px solid #E1E6EF;
    border-radius: 12px;
    padding: 4px;
    alternate-background-color: #F8FAFD;
    color: #172033;
}
QListWidget::item, QTreeWidget::item {
    padding: 8px;
    border-radius: 8px;
}
QListWidget::item:hover, QTreeWidget::item:hover {
    background-color: #F2F6FF;
}
QListWidget::item:selected, QTreeWidget::item:selected {
    background-color: #E8F0FF;
    color: #123A75;
}
QTableWidget {
    gridline-color: #EEF2F7;
    selection-background-color: #E8F0FF;
    selection-color: #0F172A;
}
QTableWidget::item {
    padding: 8px;
}
QHeaderView::section {
    background: #F8FAFC;
    color: #475569;
    border: none;
    border-bottom: 1px solid #E1E6EF;
    padding: 9px;
    font-weight: 800;
}
QTabWidget::pane {
    border: 1px solid #E1E6EF;
    background-color: #FFFFFF;
    border-radius: 12px;
    top: -1px;
}
QTabBar::tab {
    background-color: #EEF2F8;
    border: 1px solid #E1E6EF;
    padding: 9px 16px;
    margin-right: 3px;
    border-top-left-radius: 10px;
    border-top-right-radius: 10px;
    color: #475569;
    font-weight: 700;
}
QTabBar::tab:selected {
    background-color: #FFFFFF;
    border-bottom: 1px solid #FFFFFF;
    color: #1D4ED8;
}
QTabBar::tab:hover:!selected {
    background-color: #E8EEF8;
}
QTabBar::close-button {
    subcontrol-position: right;
    margin-left: 6px;
    padding: 2px;
    border-radius: 8px;
    background: #D8DEE9;
}
QTabBar::close-button:hover {
    background: #F2B8B8;
}
QScrollBar:vertical {
    background: transparent;
    width: 14px;
    margin: 2px;
}
QScrollBar::handle:vertical {
    background-color: #C7D0DF;
    min-height: 34px;
    border-radius: 7px;
}
QScrollBar::handle:vertical:hover {
    background-color: #AAB8CC;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}
QScrollBar:horizontal {
    background: transparent;
    height: 14px;
    margin: 2px;
}
QScrollBar::handle:horizontal {
    background-color: #C7D0DF;
    min-width: 34px;
    border-radius: 7px;
}
QStatusBar {
    background-color: #FFFFFF;
    border-top: 1px solid #E6EAF2;
    color: #64748B;
    padding: 3px;
}
QDockWidget {
    border: 1px solid #E1E6EF;
    titlebar-close-icon: none;
    background: #FFFFFF;
}
QDockWidget::title {
    background-color: #F8FAFC;
    padding: 8px;
    border-bottom: 1px solid #E1E6EF;
    font-weight: 800;
}
QSplitter::handle {
    background-color: #E1E6EF;
}
QSplitter::handle:hover {
    background-color: #BFD3FF;
}
QProgressBar {
    border: 1px solid #D6DDE9;
    border-radius: 10px;
    background-color: #FFFFFF;
    text-align: center;
    padding: 2px;
}
QProgressBar::chunk {
    background-color: #2563EB;
    border-radius: 8px;
}
QGroupBox {
    border: 1px solid #E1E6EF;
    border-radius: 12px;
    margin-top: 14px;
    padding-top: 16px;
    background-color: #FFFFFF;
    font-weight: 700;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 14px;
    padding: 0 7px;
    color: #334155;
}
QLabel#LanguageBadge {
    background-color: #DBEAFE;
    color: #1D4ED8;
    border: 1px solid #93C5FD;
    border-radius: 10px;
    padding: 7px 10px;
    font-weight: 900;
}
QComboBox#LanguageCombo {
    background-color: #FFFFFF;
    border: 2px solid #2563EB;
    border-radius: 10px;
    padding: 7px 10px;
    color: #0F172A;
    font-weight: 800;
}
QComboBox#LanguageCombo:hover {
    background-color: #F0F6FF;
}
"""
DARK_THEME = """
* {
    font-family: 'Segoe UI', 'Noto Sans', 'Helvetica Neue', Arial, sans-serif;
    font-size: 14px;
}
QWidget {
    background-color: #101522;
    color: #E7ECF5;
}
QMainWindow {
    background-color: #101522;
}
QToolTip {
    background-color: #F8FAFC;
    color: #0F172A;
    border: 1px solid #CBD5E1;
    padding: 8px 10px;
    border-radius: 8px;
}
QMenuBar {
    background-color: #151B2B;
    border-bottom: 1px solid #263149;
    padding: 4px 8px;
}
QMenuBar::item {
    padding: 7px 12px;
    background: transparent;
    border-radius: 8px;
    color: #E7ECF5;
}
QMenuBar::item:selected {
    background-color: #1E2A44;
    color: #93C5FD;
}
QMenu {
    background-color: #151B2B;
    border: 1px solid #2B3650;
    border-radius: 12px;
    padding: 8px;
}
QMenu::item {
    padding: 8px 28px;
    border-radius: 8px;
    color: #E7ECF5;
}
QMenu::item:selected {
    background-color: #1E2A44;
    color: #93C5FD;
}
QToolBar {
    background-color: #151B2B;
    border: none;
    border-bottom: 1px solid #263149;
    padding: 8px;
    spacing: 6px;
}
QToolButton {
    background: transparent;
    border: 1px solid transparent;
    border-radius: 10px;
    padding: 8px 11px;
    color: #E7ECF5;
    font-weight: 600;
}
QToolButton:hover {
    background-color: #1D2941;
    border-color: #33415F;
}
QToolButton:pressed {
    background-color: #24314D;
}
QToolButton:checked {
    background-color: #1E3A8A;
    border-color: #3B82F6;
    color: #FFFFFF;
}
QPushButton {
    background-color: #182033;
    border: 1px solid #34415F;
    border-radius: 10px;
    padding: 8px 14px;
    color: #F1F5F9;
    font-weight: 600;
    min-height: 22px;
}
QPushButton:hover {
    background-color: #1F2A42;
    border-color: #4B6FB8;
}
QPushButton:pressed {
    background-color: #263553;
}
QPushButton:disabled {
    background-color: #151B2B;
    color: #6B778C;
    border-color: #263149;
}
QPushButton:default, QPushButton#PrimaryButton {
    background-color: #3B82F6;
    color: white;
    border-color: #3B82F6;
}
QPushButton:default:hover, QPushButton#PrimaryButton:hover {
    background-color: #2563EB;
}
QPushButton#DangerButton {
    color: #FCA5A5;
    border-color: #7F1D1D;
    background-color: #2A1416;
}
QPushButton#DangerButton:hover {
    background-color: #3A171A;
}
QLineEdit, QTextEdit, QPlainTextEdit, QSpinBox, QComboBox {
    background-color: #151B2B;
    border: 1px solid #34415F;
    border-radius: 10px;
    padding: 8px 10px;
    color: #E7ECF5;
    selection-background-color: #3B82F6;
    selection-color: white;
}
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QSpinBox:focus, QComboBox:focus {
    border: 1px solid #60A5FA;
    background-color: #151B2B;
}
QComboBox::drop-down {
    border: none;
    width: 28px;
}
QListWidget, QListView, QTreeView, QTreeWidget, QTableWidget {
    background-color: #151B2B;
    border: 1px solid #2B3650;
    border-radius: 12px;
    padding: 4px;
    alternate-background-color: #121A2A;
    color: #E7ECF5;
}
QListWidget::item, QTreeWidget::item {
    padding: 8px;
    border-radius: 8px;
}
QListWidget::item:hover, QTreeWidget::item:hover {
    background-color: #1D2941;
}
QListWidget::item:selected, QTreeWidget::item:selected {
    background-color: #1E3A8A;
    color: #FFFFFF;
}
QTableWidget {
    gridline-color: #24304A;
    selection-background-color: #1E3A8A;
    selection-color: #FFFFFF;
}
QTableWidget::item {
    padding: 8px;
}
QHeaderView::section {
    background: #121A2A;
    color: #C9D4E5;
    border: none;
    border-bottom: 1px solid #2B3650;
    padding: 9px;
    font-weight: 800;
}
QTabWidget::pane {
    border: 1px solid #2B3650;
    background-color: #151B2B;
    border-radius: 12px;
    top: -1px;
}
QTabBar::tab {
    background-color: #121A2A;
    border: 1px solid #2B3650;
    color: #C9D4E5;
    padding: 9px 16px;
    margin-right: 3px;
    border-top-left-radius: 10px;
    border-top-right-radius: 10px;
    font-weight: 700;
}
QTabBar::tab:selected {
    background-color: #151B2B;
    border-bottom: 1px solid #151B2B;
    color: #93C5FD;
}
QTabBar::tab:hover:!selected {
    background-color: #1B2438;
}
QTabBar::close-button {
    subcontrol-position: right;
    margin-left: 6px;
    padding: 2px;
    border-radius: 8px;
    background: #475569;
}
QTabBar::close-button:hover {
    background: #B91C1C;
}
QScrollBar:vertical {
    background: transparent;
    width: 14px;
    margin: 2px;
}
QScrollBar::handle:vertical {
    background-color: #44516B;
    min-height: 34px;
    border-radius: 7px;
}
QScrollBar::handle:vertical:hover {
    background-color: #5A6A88;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}
QScrollBar:horizontal {
    background: transparent;
    height: 14px;
    margin: 2px;
}
QScrollBar::handle:horizontal {
    background-color: #44516B;
    min-width: 34px;
    border-radius: 7px;
}
QStatusBar {
    background-color: #151B2B;
    border-top: 1px solid #263149;
    color: #C9D4E5;
    padding: 3px;
}
QDockWidget {
    border: 1px solid #2B3650;
    color: #E7ECF5;
    background: #151B2B;
}
QDockWidget::title {
    background-color: #121A2A;
    padding: 8px;
    border-bottom: 1px solid #2B3650;
    font-weight: 800;
}
QSplitter::handle {
    background-color: #263149;
}
QSplitter::handle:hover {
    background-color: #3B82F6;
}
QProgressBar {
    border: 1px solid #34415F;
    border-radius: 10px;
    background-color: #151B2B;
    text-align: center;
    padding: 2px;
    color: #E7ECF5;
}
QProgressBar::chunk {
    background-color: #3B82F6;
    border-radius: 8px;
}
QGroupBox {
    border: 1px solid #2B3650;
    border-radius: 12px;
    margin-top: 14px;
    padding-top: 16px;
    background-color: #151B2B;
    font-weight: 700;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 14px;
    padding: 0 7px;
    color: #C9D4E5;
}
"""




COLOR_THEME_PALETTES = {
    "blue": {
        "name": "Ocean Blue", "accent": "#2563EB", "accent_dark": "#1D4ED8",
        "accent_soft": "#DBEAFE", "accent_hover": "#EFF6FF", "accent_border": "#93C5FD",
        "accent_text": "#1D4ED8",
    },
    "green": {
        "name": "Research Green", "accent": "#059669", "accent_dark": "#047857",
        "accent_soft": "#D1FAE5", "accent_hover": "#ECFDF5", "accent_border": "#6EE7B7",
        "accent_text": "#047857",
    },
    "purple": {
        "name": "Royal Purple", "accent": "#7C3AED", "accent_dark": "#6D28D9",
        "accent_soft": "#EDE9FE", "accent_hover": "#F5F3FF", "accent_border": "#C4B5FD",
        "accent_text": "#6D28D9",
    },
    "orange": {
        "name": "Warm Orange", "accent": "#EA580C", "accent_dark": "#C2410C",
        "accent_soft": "#FFEDD5", "accent_hover": "#FFF7ED", "accent_border": "#FDBA74",
        "accent_text": "#C2410C",
    },
    "rose": {
        "name": "Rose Pink", "accent": "#E11D48", "accent_dark": "#BE123C",
        "accent_soft": "#FFE4E6", "accent_hover": "#FFF1F2", "accent_border": "#FDA4AF",
        "accent_text": "#BE123C",
    },
    "graphite": {
        "name": "Graphite", "accent": "#334155", "accent_dark": "#1E293B",
        "accent_soft": "#E2E8F0", "accent_hover": "#F1F5F9", "accent_border": "#94A3B8",
        "accent_text": "#1E293B",
    },
}


def _palette(theme: str) -> dict:
    if theme in ("light", "dark", "system", None, ""):
        theme = "blue"
    return COLOR_THEME_PALETTES.get(str(theme).lower(), COLOR_THEME_PALETTES["blue"])


def _theme_colors(appearance: str, palette: dict) -> dict:
    """Return full-surface colors for a safe readable light/dark theme."""
    accent = palette["accent"]
    if str(appearance).lower() == "dark":
        return {
            "appearance": "dark",
            "bg": "#0B1220",
            "panel": "#101827",
            "panel2": "#172033",
            "card": "#151F2F",
            "field": "#0E1624",
            "text": "#F8FAFC",
            "muted": "#E5E7EB",
            "subtle": "#CBD5E1",
            "border": "#263244",
            "grid": "#202B3A",
            "header": "#121B2B",
            "tab": "#0F172A",
            "accent": accent,
            "accent_dark": palette["accent_dark"],
            "accent_soft": _dark_soft(accent),
            "accent_hover": _dark_hover(accent),
            "accent_border": palette["accent_border"],
            "accent_text": "#FFFFFF",
            "danger_bg": "#2A1416",
            "danger_border": "#7F1D1D",
            "danger_text": "#FCA5A5",
            "viewer_bg": "#1E293B",
        }
    return {
        "appearance": "light",
        "bg": "#F3F6FB",
        "panel": "#FFFFFF",
        "panel2": "#F8FAFD",
        "card": "#FFFFFF",
        "field": "#FFFFFF",
        "text": "#111827",
        "muted": "#2F3A4A",
        "subtle": "#667085",
        "border": "#D8E0EC",
        "grid": "#EDF1F7",
        "header": "#F7F9FC",
        "tab": "#F5F6F8",
        "accent": accent,
        "accent_dark": palette["accent_dark"],
        "accent_soft": palette["accent_soft"],
        "accent_hover": palette["accent_hover"],
        "accent_border": palette["accent_border"],
        "accent_text": palette["accent_text"],
        "danger_bg": "#FFF8F7",
        "danger_border": "#F3C2BD",
        "danger_text": "#B42318",
        "viewer_bg": "#E8ECF4",
    }


def _dark_soft(accent: str) -> str:
    # Qt stylesheets do not support alpha in all controls consistently, so use
    # a readable dark surface that works for every accent.
    return "#1E3A5F" if accent == "#2563EB" else "#26334A"


def _dark_hover(accent: str) -> str:
    return "#1B2C47" if accent == "#2563EB" else "#202B40"


def get_stylesheet(theme: str, appearance: str = "light") -> str:
    """Return a full GUI stylesheet with readable Light/Dark + accent color.

    Accent color changes the whole app color family, not only push buttons:
    menu selection, toolbar badges, focus rings, tabs, tables, dock titles,
    progress bars, side rails, and selected rows all update.
    """
    c = _theme_colors(appearance, _palette(theme))
    return f"""
* {{
    font-family: 'Segoe UI', 'Noto Sans', 'Helvetica Neue', Arial, sans-serif;
    font-size: 14px;
}}
QWidget {{ background-color: {c['bg']}; color: {c['text']}; }}
QMainWindow {{ background-color: {c['bg']}; }}
QToolTip {{ background-color: {c['text']}; color: {c['panel']}; border: 1px solid {c['border']}; padding: 8px 10px; border-radius: 8px; }}

/* Dark-mode readability hardening: every label, item, menu and popup uses explicit foregrounds. */
QLabel, QCheckBox, QRadioButton, QCommandLinkButton {{ color: {c['text']}; background: transparent; }}
QAbstractItemView {{ background-color: {c['panel']}; color: {c['text']}; selection-background-color: {c['accent_soft']}; selection-color: {c['accent_text']}; outline: none; }}
QAbstractItemView::item {{ color: {c['text']}; }}
QAbstractItemView::item:hover {{ background: {c['accent_hover']}; color: {c['accent_text']}; }}
QAbstractItemView::item:selected {{ background: {c['accent_soft']}; color: {c['accent_text']}; }}
QMenu::separator {{ height: 1px; background: {c['border']}; margin: 6px 8px; }}
QMenu::indicator {{ width: 14px; height: 14px; }}
QComboBox:disabled, QLineEdit:disabled, QTextEdit:disabled, QPlainTextEdit:disabled, QSpinBox:disabled {{ color: {c['subtle']}; background: {c['panel2']}; border-color: {c['border']}; }}
QToolButton:disabled {{ color: {c['subtle']}; }}
QMenuBar {{ background-color: {c['panel']}; border-bottom: 1px solid {c['border']}; padding: 1px 6px; }}
QMenuBar::item {{ padding: 4px 9px; background: transparent; border: none; border-radius: 0; color: {c['muted']}; }}
QMenuBar::item:selected {{ background-color: transparent; color: {c['accent_text']}; }}
QMenu {{ background-color: {c['panel']}; border: 1px solid {c['border']}; border-radius: 12px; padding: 8px; color: {c['text']}; }}
QMenu::item {{ padding: 8px 28px; border-radius: 8px; color: {c['text']}; }}
QMenu::item:selected {{ background-color: {c['accent_hover']}; color: {c['accent_text']}; }}
QToolBar {{ background-color: {c['panel']}; border: none; border-bottom: 1px solid {c['border']}; padding: 1px 6px; spacing: 2px; min-height: 32px; }}
QToolButton {{ background: transparent; border: none; border-radius: 0; padding: 3px 7px; color: {c['text']}; font-weight: 700; min-height: 20px; }}
QToolButton:hover {{ background-color: transparent; color: {c['accent_text']}; }}
QToolButton:pressed {{ background-color: transparent; color: {c['accent_text']}; }}
QToolButton:checked {{ background-color: transparent; color: {c['accent_text']}; border-bottom: 2px solid {c['accent']}; }}
QPushButton {{ background-color: {c['card']}; border: 1px solid {c['border']}; border-radius: 9px; padding: 8px 14px; color: {c['text']}; font-weight: 700; min-height: 22px; }}
QPushButton:hover {{ background-color: {c['accent_hover']}; border-color: {c['accent_border']}; }}
QPushButton:pressed {{ background-color: {c['accent_soft']}; }}
QPushButton:disabled {{ background-color: {c['panel2']}; color: {c['subtle']}; border-color: {c['border']}; }}
QPushButton:default, QPushButton#PrimaryButton {{ background-color: {c['accent']}; color: white; border-color: {c['accent']}; }}
QPushButton:default:hover, QPushButton#PrimaryButton:hover {{ background-color: {c['accent_dark']}; }}
QPushButton#DangerButton {{ color: {c['danger_text']}; border-color: {c['danger_border']}; background-color: {c['danger_bg']}; }}
QPushButton#DangerButton:hover {{ background-color: {c['danger_bg']}; border-color: {c['danger_text']}; }}
QLineEdit, QTextEdit, QPlainTextEdit, QSpinBox, QComboBox {{ background-color: {c['field']}; border: 1px solid {c['border']}; border-radius: 8px; padding: 6px 9px; color: {c['text']}; selection-background-color: {c['accent']}; selection-color: white; }}
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QSpinBox:focus, QComboBox:focus {{ border: 1px solid {c['accent']}; background-color: {c['field']}; }}
QComboBox::drop-down {{ border: none; width: 28px; }}
QComboBox QAbstractItemView {{ background: {c['panel']}; color: {c['text']}; selection-background-color: {c['accent_soft']}; selection-color: {c['accent_text']}; border: 1px solid {c['border']}; }}
QListWidget, QListView, QTreeView, QTreeWidget, QTableWidget {{ background-color: {c['card']}; border: 1px solid {c['border']}; border-radius: 12px; padding: 4px; alternate-background-color: {c['panel2']}; color: {c['text']}; }}
QListWidget::item, QTreeWidget::item {{ padding: 8px; border-radius: 8px; color: {c['text']}; }}
QListWidget::item:hover, QTreeWidget::item:hover {{ background-color: {c['accent_hover']}; }}
QListWidget::item:selected, QTreeWidget::item:selected {{ background-color: {c['accent_soft']}; color: {c['accent_text']}; }}
QTableWidget {{ gridline-color: {c['grid']}; selection-background-color: {c['accent_soft']}; selection-color: {c['accent_text']}; }}
QTableWidget::item {{ padding: 8px; color: {c['text']}; }}
QHeaderView::section {{ background: {c['header']}; color: {c['muted']}; border: none; border-bottom: 1px solid {c['border']}; padding: 9px; font-weight: 900; }}
QTabWidget::pane {{ border: 1px solid {c['border']}; background-color: {c['panel']}; border-radius: 0; top: -1px; }}
QTabBar::tab {{ background-color: transparent; border: none; border-bottom: 2px solid transparent; padding: 5px 12px; margin-right: 2px; color: {c['subtle']}; font-weight: 700; }}
QTabBar::tab:selected {{ background-color: transparent; border-bottom: 2px solid {c['accent']}; color: {c['accent_text']}; }}
QTabBar::tab:hover:!selected {{ background-color: transparent; color: {c['accent_text']}; }}
QTabBar::close-button {{ subcontrol-position: right; margin-left: 5px; padding: 1px; border-radius: 0; background: transparent; }}
QTabBar::close-button:hover {{ background: #F2B8B8; }}
QScrollBar:vertical {{ background: transparent; width: 14px; margin: 2px; }}
QScrollBar::handle:vertical {{ background-color: {c['accent_border']}; min-height: 34px; border-radius: 7px; }}
QScrollBar::handle:vertical:hover {{ background-color: {c['accent']}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar:horizontal {{ background: transparent; height: 14px; margin: 2px; }}
QScrollBar::handle:horizontal {{ background-color: {c['accent_border']}; min-width: 34px; border-radius: 7px; }}
QScrollBar::handle:horizontal:hover {{ background-color: {c['accent']}; }}
QStatusBar {{ background-color: {c['panel']}; border-top: 1px solid {c['border']}; color: {c['text']}; padding: 3px; }}
QStatusBar QLabel {{ color: {c['text']}; background: transparent; }}
QLabel#StatusMessage, QLabel#StatusPage, QLabel#StatusZoom {{ color: {c['text']}; font-weight: 700; background: transparent; }}
QLabel#LogLabel, QLabel#LogCount, QLabel#LogHint {{ color: {c['subtle']}; background: transparent; }}
QTextEdit#LogText, QTextEdit#ReportText, QTextEdit#DiffView, QPlainTextEdit#LogText {{ background-color: {c['field']}; color: {c['text']}; border: 1px solid {c['border']}; border-radius: 12px; padding: 10px; selection-background-color: {c['accent']}; selection-color: white; }}
QTextEdit#DiffView {{ font-family: Consolas, 'Courier New', monospace; font-size: 12px; }}
QDockWidget {{ border: 1px solid {c['border']}; titlebar-close-icon: none; background: {c['panel']}; color: {c['text']}; }}
QDockWidget::title {{ background-color: {c['header']}; padding: 8px; border-bottom: 1px solid {c['border']}; font-weight: 900; color: {c['text']}; }}
QSplitter::handle {{ background-color: {c['border']}; }}
QSplitter::handle:hover {{ background-color: {c['accent_border']}; }}
QProgressBar {{ border: 1px solid {c['border']}; border-radius: 10px; background-color: {c['field']}; text-align: center; padding: 2px; color: {c['text']}; }}
QProgressBar::chunk {{ background-color: {c['accent']}; border-radius: 8px; }}
QGroupBox {{ border: 1px solid {c['border']}; border-radius: 12px; margin-top: 14px; padding-top: 16px; background-color: {c['card']}; font-weight: 800; color: {c['text']}; }}
QGroupBox::title {{ subcontrol-origin: margin; left: 14px; padding: 0 7px; color: {c['muted']}; background-color: {c['card']}; }}
QLabel#LanguageBadge, QLabel#ThemeBadge {{ background-color: transparent; color: {c['accent_text']}; border: none; border-radius: 0; padding: 3px 6px; font-weight: 900; }}
QToolButton#ThemeButton {{ background-color: transparent; color: {c['accent_text']}; border: none; border-radius: 0; padding: 3px 7px; font-weight: 900; }}
QToolButton#ThemeButton:hover {{ background-color: transparent; color: {c['accent']}; }}
QComboBox#LanguageCombo {{ background-color: {c['field']}; border: 1px solid {c['border']}; border-radius: 6px; padding: 3px 8px; color: {c['text']}; font-weight: 800; min-width: 116px; }}
QComboBox#LanguageCombo:hover {{ background-color: {c['accent_hover']}; }}
QFrame#ThemeSwatch {{ background: {c['accent']}; border-radius: 8px; border: 1px solid {c['accent_dark']}; }}
QFrame#PanelHeader {{ background: {c['panel']}; border-bottom: 1px solid {c['border']}; }}
QFrame#PanelRail {{ background: {c['accent_soft']}; border-left: 1px solid {c['accent_border']}; border-right: 1px solid {c['accent_border']}; }}
QToolButton#PanelCollapseButton {{ border: 1px solid {c['border']}; border-radius: 13px; font-size: 17px; font-weight: 900; color: {c['muted']}; background: {c['panel2']}; }}
QToolButton#PanelCollapseButton:hover {{ background: {c['accent']}; color: white; border: 1px solid {c['accent']}; }}
QToolButton#PanelExpandButton {{ border: 2px solid {c['accent']}; border-radius: 17px; font-size: 18px; font-weight: 900; color: white; background: {c['accent']}; }}
QToolButton#PanelExpandButton:hover {{ background: {c['accent_dark']}; color: white; border: 2px solid {c['accent_dark']}; }}

QToolBar#CompactToolbar {{ background-color: {c['panel']}; border-bottom: 1px solid {c['border']}; padding: 2px 8px; spacing: 5px; min-height: 34px; }}
QToolButton#CompactTopButton, QToolButton#CompactHomeButton, QToolButton#ShowToolsButton {{ border-radius: 7px; padding: 4px 10px; font-size: 13px; font-weight: 800; color: {c['muted']}; }}
QToolButton#CompactHomeButton {{ color: {c['accent_text']}; background: {c['accent_soft']}; border: 1px solid {c['accent_border']}; }}
QToolButton#ShowToolsButton {{ color: #FFFFFF; background: {c['accent']}; border: 1px solid {c['accent_dark']}; }}
QToolButton#ShowToolsButton:hover {{ background: {c['accent_dark']}; }}
QComboBox#CompactLanguageCombo {{ border-radius: 12px; padding: 4px 8px; min-width: 118px; max-width: 160px; font-size: 13px; font-weight: 800; }}
QToolButton#CompactThemeButton {{ border-radius: 12px; padding: 4px 10px; font-size: 13px; font-weight: 900; color: #FFFFFF; background: {c['accent']}; border: 1px solid {c['accent_dark']}; }}

QLabel#OpenPdfCountBadge {{ background: transparent; border: none; border-radius: 0; color: {c['accent_text']}; padding: 2px 8px; font-size: 11px; font-weight: 900; min-width: 54px; }}
QToolButton#HideToolsButton {{ color: {c['accent_text']}; background: transparent; border: none; border-radius: 0; padding: 3px 7px; font-weight: 900; }}
QToolButton#HideToolsButton:hover {{ color: {c['accent']}; background: transparent; }}

/* Professional top bar / Acrobat-like polish */
QFrame#ToolbarSeparator {{ background: {c['border']}; min-width: 1px; max-width: 1px; margin: 4px 4px; }}
QLabel#ZoomLabel {{ color: {c['muted']}; font-weight: 800; padding: 0 6px; min-width: 48px; }}
QComboBox#ViewModeCombo {{ border-radius: 6px; padding: 3px 8px; min-width: 110px; font-weight: 700; }}
QLineEdit#GlobalSearch {{ border-radius: 12px; padding: 4px 10px; min-width: 180px; font-weight: 500; background: {c['panel2']}; }}
QLineEdit#GlobalSearch:focus {{ background: {c['field']}; border: 1px solid {c['accent']}; }}
QLabel#LanguageBadge {{ border-radius: 0; padding: 3px 6px; }}
QComboBox#LanguageCombo {{ border-radius: 6px; min-width: 116px; padding: 3px 8px; }}
QToolButton#ThemeButton {{ border-radius: 0; padding: 3px 7px; margin-left: 2px; }}
QToolButton#QuickActionButton {{ color: {c['muted']}; font-weight: 700; }}
QToolButton#QuickActionButton:hover {{ color: {c['accent_text']}; }}
QToolButton#CollectButton {{ background: transparent; border: none; color: {c['muted']}; font-weight: 800; }}
QToolButton#CollectButton:hover {{ background: transparent; color: {c['accent_text']}; }}
QToolButton#CollectButton:checked {{ background: transparent; border-bottom: 2px solid {c['accent']}; color: {c['accent_text']}; }}

/* Unified premium sidebar */
QWidget#UnifiedSidebar {{ background: {c['panel']}; border-right: 1px solid {c['border']}; }}
QFrame#UnifiedRail {{ background: {c['header']}; border-right: 1px solid {c['border']}; }}
QFrame#UnifiedPanel {{ background: {c['panel']}; }}
QFrame#UnifiedHeader {{ background: {c['panel']}; border-bottom: 1px solid {c['border']}; min-height: 36px; max-height: 36px; }}
QLabel#UnifiedTitle {{ color: {c['text']}; font-size: 14px; font-weight: 900; letter-spacing: 0.2px; background: transparent; }}
QToolButton#UnifiedRailButton {{ background: transparent; border: none; border-radius: 0; font-size: 20px; padding: 0; color: {c['muted']}; }}
QToolButton#UnifiedRailButton:hover {{ background: transparent; color: {c['accent_text']}; }}
QToolButton#UnifiedRailButton:checked {{ background: transparent; color: {c['accent_text']}; border-left: 3px solid {c['accent']}; }}
QToolButton#AllToolsRailButton {{ background: transparent; border: none; border-radius: 0; font-size: 8.5px; font-weight: 900; padding: 3px 0; color: {c['text']}; }}
QToolButton#AllToolsRailButton:hover {{ background: transparent; color: {c['accent_text']}; }}
QToolButton#AllToolsRailButton:checked {{ background: transparent; color: {c['accent_text']}; border-left: 3px solid {c['accent']}; }}
QToolButton#UnifiedCloseButton {{ background: transparent; border: none; border-radius: 0; font-size: 18px; font-weight: 900; color: {c['muted']}; }}
QToolButton#UnifiedCloseButton:hover {{ background: transparent; color: {c['accent_text']}; }}


/* Final professional polish override: compact, aligned, premium PDF-reader UI */
QMainWindow, QWidget#CentralWidget {{ background: {c['bg']}; }}
QToolBar#CompactToolbar {{ min-height: 38px; padding: 4px 10px; border-bottom: 1px solid {c['border']}; }}
QToolButton#CompactTopButton, QToolButton#QuickActionButton, QToolButton#CompactHomeButton {{
    min-width: 28px; min-height: 28px; border-radius: 8px; padding: 4px 8px;
    color: {c['muted']}; background: transparent; border: 1px solid transparent;
}}
QToolButton#CompactTopButton:hover, QToolButton#QuickActionButton:hover {{
    color: {c['accent_text']}; background: {c['accent_hover']}; border-color: {c['accent_border']};
}}
QToolButton#CompactTopButton:checked, QToolButton#QuickActionButton:checked {{
    color: {c['accent_text']}; background: {c['accent_soft']}; border-color: {c['accent_border']}; border-bottom: 2px solid {c['accent']};
}}
QLineEdit#GlobalSearch {{ min-height: 25px; border-radius: 13px; padding: 4px 12px; }}
QComboBox#ViewModeCombo, QComboBox#LanguageCombo, QComboBox#CompactLanguageCombo {{ min-height: 25px; border-radius: 8px; }}
QLabel#ZoomLabel {{ color: {c['muted']}; font-size: 12px; font-weight: 900; }}
QWidget#UnifiedSidebar {{ background: {c['panel']}; border-right: 1px solid {c['border']}; }}
QFrame#UnifiedRail {{ background: {c['header']}; border-right: 1px solid {c['border']}; }}
QFrame#UnifiedHeader {{ background: {c['panel']}; min-height: 42px; max-height: 42px; border-bottom: 1px solid {c['border']}; }}
QLabel#UnifiedTitle {{ font-size: 13px; font-weight: 900; color: {c['text']}; }}
QToolButton#UnifiedRailButton, QToolButton#AllToolsRailButton {{
    border-radius: 10px; border: 1px solid transparent; background: transparent; color: {c['muted']};
}}
QToolButton#UnifiedRailButton:hover, QToolButton#AllToolsRailButton:hover {{
    background: {c['accent_hover']}; border-color: {c['accent_border']}; color: {c['accent_text']};
}}
QToolButton#UnifiedRailButton:checked, QToolButton#AllToolsRailButton:checked {{
    background: {c['accent_soft']}; border: 1px solid {c['accent_border']}; color: {c['accent_text']};
}}
QWidget#AllToolsPanel, QWidget#ToolsPanel {{ background: {c['panel']}; }}
QToolButton#PanelIconButton {{ border-radius: 9px; border: 1px solid {c['border']}; background: {c['panel2']}; }}
QToolButton#PanelIconButton:hover {{ background: {c['accent_hover']}; border-color: {c['accent_border']}; }}
QListWidget, QListView, QTreeView, QTreeWidget, QTableWidget {{ border-radius: 14px; }}
QStatusBar {{ min-height: 24px; }}

QDialog {{ background-color: {c['bg']}; color: {c['text']}; }}
QMessageBox {{ background-color: {c['panel']}; color: {c['text']}; }}
QScrollArea {{ background: transparent; border: none; }}
QSplitter::handle:horizontal {{ width: 1px; }}
QSplitter::handle:vertical {{ height: 1px; }}
"""


def viewer_background(theme: str, appearance: str = "light") -> str:
    return _theme_colors(appearance, _palette(theme))["viewer_bg"]
