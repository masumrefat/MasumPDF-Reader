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
    "ocr": '<path d="M4 8V6a2 2 0 0 1 2-2h2"/><path d="M16 4h2a2 2 0 0 1 2 2v2"/><path d="M20 16v2a2 2 0 0 1-2 2h-2"/><path d="M8 20H6a2 2 0 0 1-2-2v-2"/><path d="M8 12h8"/>',
    "settings": '<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.6 1.6 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.6 1.6 0 0 0-2.7 1.1V21a2 2 0 0 1-4 0v-.1A1.6 1.6 0 0 0 7 19.4a1.6 1.6 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.6 1.6 0 0 0-1.1-2.7H1a2 2 0 0 1 0-4h.1A1.6 1.6 0 0 0 2.6 7a1.6 1.6 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.6 1.6 0 0 0 1.8.3H7a1.6 1.6 0 0 0 1-1.5V1a2 2 0 0 1 4 0v.1a1.6 1.6 0 0 0 2.7 1.1l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.6 1.6 0 0 0-.3 1.8V7a1.6 1.6 0 0 0 1.5 1H23a2 2 0 0 1 0 4h-.1a1.6 1.6 0 0 0-1.5 1z"/>',
    "undo": '<path d="M3 7v6h6"/><path d="M3 13a9 9 0 1 0 3-7L3 9"/>',
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
