"""Vector icon set for the tool panel.

Each icon is a small, clean, monochrome SVG path drawn on a 24x24 grid
in the style of Lucide / Feather (1.6px stroke, round caps). They render
crisp at any DPI and recolor to match the current theme, which is the key
to a tidy, professional look — emoji glyphs have inconsistent widths and
colors and never line up.
"""

from PySide6.QtCore import QByteArray, Qt, QSize
from PySide6.QtGui import QIcon, QPixmap, QPainter, QColor
from PySide6.QtSvg import QSvgRenderer


# Each entry is the inner SVG markup (paths/shapes) drawn on a 24x24 viewBox.
# Stroke color is set to "currentColor" and substituted at render time.
_ICONS = {
    "highlight": '<path d="M9 11l-4 4v3h3l4-4"/><path d="M13 7l4 4"/><path d="M15 4l5 5-7 7-5-5z"/>',
    "highlight_line": '<path d="M4 7h16"/><path d="M4 12h10"/><rect x="3.5" y="15.5" width="17" height="3" rx="1"/>',
    "note": '<path d="M4 4h16v12h-7l-5 4v-4H4z"/>',
    "comment": '<path d="M21 12a8 8 0 0 1-11.5 7.2L4 21l1.8-5.5A8 8 0 1 1 21 12z"/>',
    "comment_line": '<path d="M20 11a7 7 0 0 1-10 6.3L5 19l1.7-4.8A7 7 0 1 1 20 11z"/><path d="M9 9h6"/><path d="M9 12h4"/>',
    "stamp": '<path d="M5 21h14"/><path d="M9 11V7a3 3 0 0 1 6 0v4"/><path d="M6 18h12v-3a2 2 0 0 0-2-2H8a2 2 0 0 0-2 2z"/>',
    "text_color": '<path d="M5 18L10 6l5 12"/><path d="M6.5 14h7"/><rect x="16" y="16" width="5" height="4" rx="1"/>',
    "edit_line": '<path d="M4 18h7"/><path d="M14 4l4 4-9 9-4 1 1-4z"/>',
    "rotate_left": '<path d="M3 8a8 8 0 1 1-1 4"/><path d="M3 4v4h4"/>',
    "rotate_right": '<path d="M21 8a8 8 0 1 0 1 4"/><path d="M21 4v4h-4"/>',
    "page_add": '<path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h6"/><path d="M14 3v5h5"/><path d="M18 14v6"/><path d="M15 17h6"/>',
    "page_delete": '<path d="M6 7h12l-1 13a2 2 0 0 1-2 2H9a2 2 0 0 1-2-2z"/><path d="M9 7V4h6v3"/><path d="M10 11v6M14 11v6"/>',
    "add_text": '<path d="M4 7V5h16v2"/><path d="M9 5v14"/><path d="M7 19h4"/><path d="M16 13h5M18.5 11v4"/>',
    "add_image": '<rect x="3" y="5" width="14" height="14" rx="2"/><circle cx="8" cy="10" r="1.5"/><path d="M3 16l4-4 4 4 3-3 3 3"/><path d="M19 7h3M20.5 5.5v3"/>',
    "header_footer": '<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M3 8h18"/><path d="M3 16h18"/>',
    "sign": '<path d="M3 18c3 0 3-3 5-3s2 3 4 3 3-6 5-6 2 2 4 2"/><path d="M3 21h18"/>',
    "form": '<rect x="4" y="3" width="16" height="18" rx="2"/><path d="M8 8h8M8 12h8M8 16h5"/>',
    "fill_sign": '<path d="M14 4l4 4-9 9-4 1 1-4z"/><path d="M3 21h7"/>',
    "link": '<path d="M10 13a5 5 0 0 0 7 0l3-3a5 5 0 0 0-7-7l-1 1"/><path d="M14 11a5 5 0 0 0-7 0l-3 3a5 5 0 0 0 7 7l1-1"/>',
    "review": '<path d="M4 4h16v12H8l-4 4z"/><path d="M8 9h8M8 12h5"/>',
    "create": '<path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z"/><path d="M14 3v5h5"/><path d="M12 11v6M9 14h6"/>',
    "organize": '<rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/>',
    "merge": '<path d="M7 3v6a4 4 0 0 0 4 4h6"/><path d="M14 10l3 3-3 3"/><path d="M3 3v18"/>',
    "split": '<path d="M8 3L4 7l4 4"/><path d="M4 7h9a4 4 0 0 1 4 4v10"/><path d="M14 17l3 4 3-4"/>',
    "extract": '<path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-7"/><path d="M14 3v5h5"/><path d="M21 3l-7 7"/><path d="M16 3h5v5"/>',
    "compare": '<path d="M12 3v18"/><path d="M5 7l-2 2 2 2"/><path d="M3 9h6"/><path d="M19 13l2 2-2 2"/><path d="M21 15h-6"/>',
    "compress": '<path d="M4 9V5a1 1 0 0 1 1-1h4"/><path d="M20 9V5a1 1 0 0 0-1-1h-4"/><path d="M4 15v4a1 1 0 0 0 1 1h4"/><path d="M20 15v4a1 1 0 0 1-1 1h-4"/><path d="M8 12h8"/>',
    "encrypt": '<rect x="5" y="11" width="14" height="9" rx="2"/><path d="M8 11V7a4 4 0 0 1 8 0v4"/>',
    "decrypt": '<rect x="5" y="11" width="14" height="9" rx="2"/><path d="M8 11V7a4 4 0 0 1 7.5-2"/>',
    "properties": '<circle cx="12" cy="12" r="9"/><path d="M12 11v5"/><circle cx="12" cy="8" r="0.6" fill="currentColor"/>',
    "to_images": '<rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/><path d="M21 15l-5-5L5 21"/>',
    "images_to_pdf": '<rect x="3" y="5" width="12" height="12" rx="2"/><circle cx="7" cy="9" r="1.2"/><path d="M3 14l4-4 4 4"/><path d="M17 9h4v10a2 2 0 0 1-2 2H9"/>',
    "to_text": '<path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z"/><path d="M14 3v5h5"/><path d="M9 13h6M9 17h6"/>',
    "to_word": '<path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z"/><path d="M14 3v5h5"/><path d="M8 12l1.2 5 1.8-4 1.8 4 1.2-5"/><path d="M16 12h2"/>',
    "ocr": '<path d="M4 8V6a2 2 0 0 1 2-2h2"/><path d="M16 4h2a2 2 0 0 1 2 2v2"/><path d="M20 16v2a2 2 0 0 1-2 2h-2"/><path d="M8 20H6a2 2 0 0 1-2-2v-2"/><path d="M8 12h8"/>',

    # General application / toolbar icons
    "home": '<path d="M3 11l9-8 9 8"/><path d="M5 10v10h5v-6h4v6h5V10"/>',
    "open": '<path d="M4 20h16a2 2 0 0 0 2-2l1-8H9l-2 4H2l2 6z"/><path d="M2 10V6a2 2 0 0 1 2-2h5l2 3h7a2 2 0 0 1 2 2v1"/>',
    "save": '<path d="M5 3h12l2 2v16H5z"/><path d="M8 3v6h8V3"/><path d="M8 21v-7h8v7"/>',
    "save_as": '<path d="M5 3h12l2 2v16H5z"/><path d="M8 3v6h8V3"/><path d="M8 21v-7h5"/><path d="M15 16l4 4"/><path d="M19 16l-4 4"/>',
    "print": '<path d="M7 8V3h10v5"/><path d="M7 17H5a2 2 0 0 1-2-2v-4a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2v4a2 2 0 0 1-2 2h-2"/><path d="M7 14h10v7H7z"/>',
    "search": '<circle cx="11" cy="11" r="7"/><path d="M21 21l-4.3-4.3"/>',
    "zoom_in": '<circle cx="11" cy="11" r="7"/><path d="M11 8v6M8 11h6"/><path d="M21 21l-4.3-4.3"/>',
    "zoom_out": '<circle cx="11" cy="11" r="7"/><path d="M8 11h6"/><path d="M21 21l-4.3-4.3"/>',
    "fit_width": '<path d="M4 6h16v12H4z"/><path d="M8 12h8"/><path d="M8 12l2-2M8 12l2 2M16 12l-2-2M16 12l-2 2"/>',
    "fit_page": '<path d="M7 3h10l3 3v15H7z"/><path d="M17 3v4h4"/><path d="M10 9h7M10 13h7M10 17h4"/>',
    "theme": '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>',
    "language": '<circle cx="12" cy="12" r="9"/><path d="M3 12h18"/><path d="M12 3a14 14 0 0 1 0 18"/><path d="M12 3a14 14 0 0 0 0 18"/>',
    "tools": '<path d="M14.7 6.3a4 4 0 0 0-5 5L3 18v3h3l6.7-6.7a4 4 0 0 0 5-5l-2.4 2.4-3-3z"/>',
    "menu": '<path d="M4 6h16M4 12h16M4 18h16"/>',
    "pages": '<path d="M7 3h9l4 4v14H7z"/><path d="M16 3v5h5"/><path d="M4 7v14h13"/>',
    "comments": '<path d="M4 5h16v11H8l-4 4z"/><path d="M8 9h8M8 12h5"/>',
    "library": '<path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/><path d="M8 6h8"/>',
    "reference": '<path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H19"/><path d="M6.5 2H19v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/><path d="M9 6h6M9 10h6M9 14h4"/>',
    "favorite": '<path d="M12 3l2.8 5.7 6.2.9-4.5 4.4 1.1 6.2L12 17.2 6.4 20.2 7.5 14 3 9.6l6.2-.9z"/>',
    "tag": '<path d="M20 13l-7 7L4 11V4h7z"/><circle cx="8.5" cy="8.5" r="1.5"/>',
    "eye": '<path d="M2 12s4-7 10-7 10 7 10 7-4 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/>',
    "related": '<circle cx="6" cy="12" r="3"/><circle cx="18" cy="6" r="3"/><circle cx="18" cy="18" r="3"/><path d="M8.7 10.7l6.6-3.4M8.7 13.3l6.6 3.4"/>',
    "web": '<circle cx="12" cy="12" r="9"/><path d="M3 12h18"/><path d="M12 3a14 14 0 0 1 0 18"/><path d="M12 3a14 14 0 0 0 0 18"/>',
    "pdf": '<path d="M6 3h9l3 3v15H6z"/><path d="M15 3v4h4"/><path d="M8 16h2a2 2 0 0 0 0-4H8v5"/><path d="M13 12v5h1.5a2.5 2.5 0 0 0 0-5H13"/>',
    "import": '<path d="M12 3v10"/><path d="M8 9l4 4 4-4"/><path d="M4 17v3h16v-3"/>',
    "remove": '<path d="M6 7h12l-1 13a2 2 0 0 1-2 2H9a2 2 0 0 1-2-2z"/><path d="M9 7V4h6v3"/><path d="M10 11v6M14 11v6"/>',
    "close": '<path d="M18 6L6 18M6 6l12 12"/>',
    "arrow_left": '<path d="M19 12H5"/><path d="M12 19l-7-7 7-7"/>',
    "arrow_right": '<path d="M5 12h14"/><path d="M12 5l7 7-7 7"/>',
    "arrow_up": '<path d="M12 19V5"/><path d="M5 12l7-7 7 7"/>',
    "arrow_down": '<path d="M12 5v14"/><path d="M5 12l7 7 7-7"/>',
    "settings": '<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.6 1.6 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.6 1.6 0 0 0-2.7 1.1V21a2 2 0 0 1-4 0v-.1A1.6 1.6 0 0 0 7 19.4a1.6 1.6 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.6 1.6 0 0 0-1.1-2.7H1a2 2 0 0 1 0-4h.1A1.6 1.6 0 0 0 2.6 7a1.6 1.6 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.6 1.6 0 0 0 1.8.3H7a1.6 1.6 0 0 0 1-1.5V1a2 2 0 0 1 4 0v.1a1.6 1.6 0 0 0 2.7 1.1l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.6 1.6 0 0 0-.3 1.8V7a1.6 1.6 0 0 0 1.5 1H23a2 2 0 0 1 0 4h-.1a1.6 1.6 0 0 0-1.5 1z"/>',
    "undo": '<path d="M3 7v6h6"/><path d="M3 13a9 9 0 1 0 3-7L3 9"/>',

    "select": '<path d="M5 3l12 12-5 1.2 3.2 5.2-2.4 1.5-3.1-5.1L6 21z"/>',
    "underline": '<path d="M7 4v6a5 5 0 0 0 10 0V4"/><path d="M5 21h14"/>',
    "strikeout": '<path d="M6 12h12"/><path d="M8 5c1.3-1 3-1.5 5-1.1 2.3.4 3.8 1.7 3.8 3.4 0 1.4-.9 2.4-2.6 3"/><path d="M16 15.5c0 1.9-1.7 3.2-4.1 3.2-2.1 0-3.7-.7-5-2"/>',
    "draw": '<path d="M4 20c3-5 5-7 7-7 1.4 0 2.1 1.1 2.9 2.1.8 1 1.6 1.9 3.1 1.9 1.4 0 2.4-.7 3-1.5"/><path d="M14 4l6 6"/><path d="M16 2l6 6-9 9-6 1 1-6z"/>',
    "shape": '<rect x="4" y="5" width="8" height="8" rx="1.5"/><circle cx="16.5" cy="15.5" r="4.5"/>',
    "mark_x": '<path d="M6 6l12 12M18 6L6 18"/>',
    "mark_check": '<path d="M4 12.5l5 5L20 6"/>',
    "mark_dot": '<circle cx="12" cy="12" r="4" fill="currentColor" stroke="none"/>',
    "line": '<path d="M4 18L20 6"/>',
    "rect": '<rect x="5" y="6" width="14" height="12" rx="2"/>',
    "circle": '<circle cx="12" cy="12" r="7"/>',
    "eraser": '<path d="M4 14l7-7 6 6-7 7H7z"/><path d="M9 19h11"/><path d="M11 9l6 6"/>',
}


def _svg_document(inner: str, color: str, stroke: float = 1.7) -> bytes:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" '
        f'fill="none" stroke="{color}" stroke-width="{stroke}" '
        f'stroke-linecap="round" stroke-linejoin="round">{inner}</svg>'
    ).encode("utf-8")


def make_icon(name: str, color: str = "#3A3A42", size: int = 20) -> QIcon:
    """Render a named icon to a crisp QIcon in the given color."""
    inner = _ICONS.get(name)
    if inner is None:
        return QIcon()
    svg = _svg_document(inner, color)
    renderer = QSvgRenderer(QByteArray(svg))
    # render at 2x for retina crispness
    scale = 2
    pix = QPixmap(size * scale, size * scale)
    pix.fill(Qt.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.Antialiasing, True)
    renderer.render(p)
    p.end()
    pix.setDevicePixelRatio(scale)
    return QIcon(pix)


def has_icon(name: str) -> bool:
    return name in _ICONS
