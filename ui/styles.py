"""Qt stylesheets for light and dark themes.

Kept compact and modern; uses CSS-like syntax that Qt supports.
"""

LIGHT_THEME = """
QWidget {
    background-color: #F2EFE9;
    color: #2A2722;
    font-family: 'Segoe UI', 'Helvetica Neue', system-ui, sans-serif;
    font-size: 13px;
}
QToolTip {
    background-color: #2B2D33;
    color: #FFFFFF;
    border: 1px solid #2B2D33;
    padding: 4px 8px;
    border-radius: 4px;
}
QMainWindow {
    background-color: #F2EFE9;
}
QMenuBar {
    background-color: #FBFAF7;
    border-bottom: 1px solid #DAD5CC;
    padding: 4px;
}
QMenuBar::item {
    padding: 4px 12px;
    background: transparent;
    border-radius: 4px;
}
QMenuBar::item:selected {
    background-color: #E8E8EC;
}
QMenu {
    background-color: #FFFFFF;
    border: 1px solid #E5E5E7;
    border-radius: 6px;
    padding: 4px;
}
QMenu::item {
    padding: 6px 24px;
    border-radius: 4px;
}
QMenu::item:selected {
    background-color: #E8E8EC;
}
QToolBar {
    background-color: #FBFAF7;
    border: none;
    border-bottom: 1px solid #DAD5CC;
    padding: 6px;
    spacing: 4px;
}
QToolButton {
    background: transparent;
    border: 1px solid transparent;
    border-radius: 6px;
    padding: 6px 10px;
    color: #2A2722;
}
QToolButton:hover {
    background-color: #ECE8E0;
}
QToolButton:pressed {
    background-color: #DED8CD;
}
QToolButton:checked {
    background-color: #DBE7FF;
    border-color: #B5CCFF;
}
QPushButton {
    background-color: #FBFAF7;
    border: 1px solid #D2CCC1;
    border-radius: 6px;
    padding: 6px 14px;
}
QPushButton:hover {
    background-color: #F5F5F7;
}
QPushButton:pressed {
    background-color: #E5E5E7;
}
QPushButton:default {
    background-color: #2667FF;
    color: white;
    border-color: #2667FF;
}
QPushButton:default:hover {
    background-color: #1E55D6;
}
QLineEdit, QTextEdit, QPlainTextEdit, QSpinBox, QComboBox {
    background-color: #FFFFFF;
    border: 1px solid #D9D9DE;
    border-radius: 6px;
    padding: 5px 8px;
    selection-background-color: #2667FF;
    selection-color: white;
}
QLineEdit:focus, QTextEdit:focus, QSpinBox:focus, QComboBox:focus {
    border-color: #2667FF;
}
QListWidget, QListView, QTreeView, QTreeWidget {
    background-color: #FFFFFF;
    border: 1px solid #E5E5E7;
    border-radius: 8px;
    padding: 4px;
}
QListWidget::item, QTreeWidget::item {
    padding: 6px;
    border-radius: 4px;
}
QListWidget::item:selected, QTreeWidget::item:selected {
    background-color: #DBE7FF;
    color: #1d1d1f;
}
QTabWidget::pane {
    border: 1px solid #E5E5E7;
    background-color: #FFFFFF;
    border-radius: 8px;
    top: -1px;
}
QTabBar::tab {
    background-color: #ECECEF;
    border: 1px solid #E5E5E7;
    padding: 8px 16px;
    margin-right: 2px;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
}
QTabBar::tab:selected {
    background-color: #FFFFFF;
    border-bottom: 1px solid #FFFFFF;
}
QTabBar::tab:hover:!selected {
    background-color: #E5E5E7;
}
QTabBar::close-button {
    subcontrol-position: right;
    margin-left: 6px;
    padding: 2px;
    border-radius: 8px;
    background: #D6D6DB;
}
QTabBar::close-button:hover {
    background: #F2B8B8;
}
QTabBar::close-button:pressed {
    background: #E89090;
}
QScrollBar:vertical {
    background: transparent;
    width: 14px;
    margin: 16px 0 16px 0;
}
QScrollBar::handle:vertical {
    background-color: #C8C8CE;
    min-height: 30px;
    border-radius: 6px;
}
QScrollBar::handle:vertical:hover {
    background-color: #A8A8AE;
}
QScrollBar::sub-line:vertical {
    background: #E5E5E7;
    height: 16px;
    subcontrol-position: top;
    subcontrol-origin: margin;
    border-radius: 3px;
}
QScrollBar::add-line:vertical {
    background: #E5E5E7;
    height: 16px;
    subcontrol-position: bottom;
    subcontrol-origin: margin;
    border-radius: 3px;
}
QScrollBar::up-arrow:vertical {
    width: 8px; height: 8px;
    image: none;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-bottom: 6px solid #707076;
}
QScrollBar::down-arrow:vertical {
    width: 8px; height: 8px;
    image: none;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 6px solid #707076;
}
QScrollBar:horizontal {
    background: transparent;
    height: 12px;
}
QScrollBar::handle:horizontal {
    background-color: #C8C8CE;
    min-width: 30px;
    border-radius: 6px;
}
QStatusBar {
    background-color: #FFFFFF;
    border-top: 1px solid #E5E5E7;
}
QDockWidget {
    border: 1px solid #E5E5E7;
    titlebar-close-icon: none;
}
QDockWidget::title {
    background-color: #ECECEF;
    padding: 6px;
    border-bottom: 1px solid #E5E5E7;
}
QSplitter::handle {
    background-color: #E5E5E7;
}
QProgressBar {
    border: 1px solid #D9D9DE;
    border-radius: 6px;
    background-color: #FFFFFF;
    text-align: center;
}
QProgressBar::chunk {
    background-color: #2667FF;
    border-radius: 5px;
}
QGroupBox {
    border: 1px solid #E5E5E7;
    border-radius: 8px;
    margin-top: 12px;
    padding-top: 12px;
    background-color: #FFFFFF;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 6px;
}
"""

DARK_THEME = """
QWidget {
    background-color: #1E1E22;
    color: #E5E5E7;
    font-family: 'Segoe UI', 'Helvetica Neue', system-ui, sans-serif;
    font-size: 13px;
}
QToolTip {
    background-color: #3A3D44;
    color: #FFFFFF;
    border: 1px solid #4A4D55;
    padding: 4px 8px;
    border-radius: 4px;
}
QMainWindow {
    background-color: #1E1E22;
}
QMenuBar {
    background-color: #25252A;
    border-bottom: 1px solid #303036;
    padding: 4px;
}
QMenuBar::item {
    padding: 4px 12px;
    background: transparent;
    border-radius: 4px;
}
QMenuBar::item:selected {
    background-color: #34343A;
}
QMenu {
    background-color: #2A2A30;
    border: 1px solid #3A3A42;
    border-radius: 6px;
    padding: 4px;
}
QMenu::item {
    padding: 6px 24px;
    border-radius: 4px;
}
QMenu::item:selected {
    background-color: #3A3A42;
}
QToolBar {
    background-color: #25252A;
    border: none;
    border-bottom: 1px solid #303036;
    padding: 6px;
    spacing: 4px;
}
QToolButton {
    background: transparent;
    border: 1px solid transparent;
    border-radius: 6px;
    padding: 6px 10px;
    color: #E5E5E7;
}
QToolButton:hover {
    background-color: #34343A;
}
QToolButton:pressed {
    background-color: #44444A;
}
QToolButton:checked {
    background-color: #2A4A8C;
    border-color: #3868C0;
}
QPushButton {
    background-color: #2A2A30;
    border: 1px solid #44444A;
    border-radius: 6px;
    padding: 6px 14px;
    color: #E5E5E7;
}
QPushButton:hover {
    background-color: #34343A;
}
QPushButton:pressed {
    background-color: #44444A;
}
QPushButton:default {
    background-color: #2667FF;
    color: white;
    border-color: #2667FF;
}
QPushButton:default:hover {
    background-color: #4A82FF;
}
QLineEdit, QTextEdit, QPlainTextEdit, QSpinBox, QComboBox {
    background-color: #25252A;
    border: 1px solid #3A3A42;
    border-radius: 6px;
    padding: 5px 8px;
    color: #E5E5E7;
    selection-background-color: #2667FF;
    selection-color: white;
}
QLineEdit:focus, QTextEdit:focus, QSpinBox:focus, QComboBox:focus {
    border-color: #2667FF;
}
QListWidget, QListView, QTreeView, QTreeWidget {
    background-color: #25252A;
    border: 1px solid #3A3A42;
    border-radius: 8px;
    padding: 4px;
    color: #E5E5E7;
}
QListWidget::item, QTreeWidget::item {
    padding: 6px;
    border-radius: 4px;
}
QListWidget::item:selected, QTreeWidget::item:selected {
    background-color: #2A4A8C;
    color: #FFFFFF;
}
QTabWidget::pane {
    border: 1px solid #3A3A42;
    background-color: #25252A;
    border-radius: 8px;
    top: -1px;
}
QTabBar::tab {
    background-color: #2A2A30;
    border: 1px solid #3A3A42;
    color: #E5E5E7;
    padding: 8px 16px;
    margin-right: 2px;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
}
QTabBar::tab:selected {
    background-color: #25252A;
    border-bottom: 1px solid #25252A;
}
QTabBar::tab:hover:!selected {
    background-color: #34343A;
}
QTabBar::close-button {
    subcontrol-position: right;
    margin-left: 6px;
    padding: 2px;
    border-radius: 8px;
    background: #C8C8CE;
}
QTabBar::close-button:hover {
    background: #F2B8B8;
}
QTabBar::close-button:pressed {
    background: #E89090;
}
QScrollBar:vertical {
    background: transparent;
    width: 12px;
}
QScrollBar::handle:vertical {
    background-color: #44444A;
    min-height: 30px;
    border-radius: 6px;
}
QScrollBar::handle:vertical:hover {
    background-color: #54545A;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}
QScrollBar:horizontal {
    background: transparent;
    height: 12px;
}
QScrollBar::handle:horizontal {
    background-color: #44444A;
    min-width: 30px;
    border-radius: 6px;
}
QStatusBar {
    background-color: #25252A;
    border-top: 1px solid #303036;
    color: #B5B5B9;
}
QDockWidget {
    border: 1px solid #3A3A42;
    color: #E5E5E7;
}
QDockWidget::title {
    background-color: #2A2A30;
    padding: 6px;
    border-bottom: 1px solid #3A3A42;
}
QSplitter::handle {
    background-color: #3A3A42;
}
QProgressBar {
    border: 1px solid #3A3A42;
    border-radius: 6px;
    background-color: #25252A;
    text-align: center;
    color: #E5E5E7;
}
QProgressBar::chunk {
    background-color: #2667FF;
    border-radius: 5px;
}
QGroupBox {
    border: 1px solid #3A3A42;
    border-radius: 8px;
    margin-top: 12px;
    padding-top: 12px;
    background-color: #25252A;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 6px;
}
"""


def get_stylesheet(theme: str) -> str:
    return DARK_THEME if theme == "dark" else LIGHT_THEME


# colors for the PDF viewer background that follow the theme
def viewer_background(theme: str) -> str:
    return "#1A1A1E" if theme == "dark" else "#D8D8DE"
