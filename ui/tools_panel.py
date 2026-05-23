"""Left-side 'All Tools' panel — professional, aligned, icon-based.

Replaces the emoji glyphs (which never aligned) with crisp SVG icons in a
fixed-width column so every label starts at the same x position. Rows have
a consistent height, hover/checked states, and section headers with rules.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QScrollArea,
    QFrame, QSizePolicy, QToolButton, QPushButton,
)
from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QColor

from ui.icons import make_icon


ACCENT = "#2667FF"
ICON_LIGHT = "#42454E"
ICON_DARK = "#C7CAD1"


class ToolButton(QPushButton):
    """A full-width row: [icon]  Label."""

    ROW_HEIGHT = 38
    ICON_SIZE = 19

    def __init__(self, icon_name: str, text: str, tooltip: str = "",
                 checkable: bool = False, dark: bool = False, parent=None):
        super().__init__(parent)
        self._icon_name = icon_name
        self._dark = dark
        # Escape & so QPushButton doesn't treat it as a mnemonic (showing _)
        self.setText("   " + text.replace("&", "&&"))
        self.setToolTip(tooltip or text)
        self.setCheckable(checkable)
        self.setIcon(make_icon(icon_name,
                               ICON_DARK if dark else ICON_LIGHT,
                               self.ICON_SIZE))
        self.setIconSize(QSize(self.ICON_SIZE, self.ICON_SIZE))
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setFixedHeight(self.ROW_HEIGHT)
        self.setCursor(Qt.PointingHandCursor)
        self.setFlat(True)
        self._apply_style()

    def _apply_style(self):
        text_color = "#E6E8EC" if self._dark else "#2B2D33"
        hover_bg = "rgba(255,255,255,0.06)" if self._dark else "rgba(20,30,60,0.05)"
        press_bg = "rgba(255,255,255,0.10)" if self._dark else "rgba(20,30,60,0.09)"
        checked_bg = "rgba(38,103,255,0.16)"
        self.setStyleSheet(f"""
            QPushButton {{
                text-align: left;
                padding: 0 14px;
                border: none;
                border-radius: 8px;
                background: transparent;
                color: {text_color};
                font-size: 13px;
            }}
            QPushButton:hover {{ background: {hover_bg}; }}
            QPushButton:pressed {{ background: {press_bg}; }}
            QPushButton:checked {{
                background: {checked_bg};
                color: {ACCENT};
                font-weight: 600;
            }}
        """)

    def refresh_icon(self, dark: bool):
        self._dark = dark
        color = ACCENT if self.isChecked() else (ICON_DARK if dark else ICON_LIGHT)
        self.setIcon(make_icon(self._icon_name, color, self.ICON_SIZE))
        self._apply_style()

    def nextCheckState(self):
        super().nextCheckState()
        color = ACCENT if self.isChecked() else (ICON_DARK if self._dark else ICON_LIGHT)
        self.setIcon(make_icon(self._icon_name, color, self.ICON_SIZE))


class SectionHeader(QWidget):
    """Group header: clickable, shows a chevron, collapses its tools."""

    clicked = Signal()

    def __init__(self, text: str, dark: bool = False, parent=None):
        super().__init__(parent)
        self._dark = dark
        self._collapsed = False
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(34)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(14, 10, 12, 6)
        lay.setSpacing(8)
        self.chevron = QLabel("\u25BC")  # down arrow = expanded
        self.chevron.setStyleSheet(
            f"color: {'#888C96' if dark else '#9499A6'}; font-size: 9px;")
        lay.addWidget(self.chevron)
        self.lbl = QLabel(text.upper())
        color = "#6E7280" if not dark else "#9499A6"
        self.lbl.setStyleSheet(
            f"color: {color}; font-size: 10px; font-weight: 700; "
            f"letter-spacing: 1.4px; background: transparent;")
        lay.addWidget(self.lbl)
        self.rule = QFrame()
        self.rule.setFrameShape(QFrame.HLine)
        self.rule.setStyleSheet(
            f"color: {'rgba(255,255,255,0.08)' if dark else 'rgba(20,30,60,0.07)'};")
        self.rule.setMaximumHeight(1)
        lay.addWidget(self.rule, 1)
        self._update_hover_style()

    def _update_hover_style(self):
        hover = "rgba(255,255,255,0.05)" if self._dark else "rgba(20,30,60,0.04)"
        self.setStyleSheet(
            f"SectionHeader {{ border-radius: 6px; }}"
            f"SectionHeader:hover {{ background: {hover}; }}")

    def mousePressEvent(self, event):
        self.clicked.emit()
        super().mousePressEvent(event)

    def set_collapsed(self, collapsed: bool):
        self._collapsed = collapsed
        self.chevron.setText("\u25B6" if collapsed else "\u25BC")  # right vs down

    def set_dark(self, dark):
        self._dark = dark
        color = "#6E7280" if not dark else "#9499A6"
        self.lbl.setStyleSheet(
            f"color: {color}; font-size: 10px; font-weight: 700; "
            f"letter-spacing: 1.4px; background: transparent;")
        self.chevron.setStyleSheet(
            f"color: {'#888C96' if dark else '#9499A6'}; font-size: 9px;")
        self.rule.setStyleSheet(
            f"color: {'rgba(255,255,255,0.08)' if dark else 'rgba(20,30,60,0.07)'};")
        self._update_hover_style()


class AllToolsPanel(QWidget):
    """Left sidebar with every tool grouped into sections."""

    highlight_requested = Signal()
    select_text_requested = Signal()
    fill_form_requested = Signal()
    line_highlight_requested = Signal()
    note_requested = Signal()
    comment_requested = Signal()
    line_comment_requested = Signal()
    stamp_requested = Signal()

    undo_requested = Signal()
    delete_annot_requested = Signal()

    text_color_requested = Signal()
    line_edit_requested = Signal()
    line_color_requested = Signal()
    edit_mode_requested = Signal()
    sign_requested = Signal()
    prepare_form_requested = Signal()
    fill_form_requested = Signal()
    add_text_requested = Signal()
    add_image_requested = Signal()
    header_footer_requested = Signal()
    insert_blank_page_requested = Signal()
    delete_current_page_requested = Signal()
    rotate_page_left_requested = Signal()
    rotate_page_right_requested = Signal()

    media_requested = Signal()
    send_review_requested = Signal()

    create_pdf_requested = Signal()
    organize_requested = Signal()
    merge_requested = Signal()
    split_requested = Signal()
    extract_requested = Signal()
    compare_requested = Signal()
    extract_citations_requested = Signal()
    reference_collection_requested = Signal()
    notes_collection_requested = Signal()
    library_requested = Signal()

    compress_requested = Signal()
    encrypt_requested = Signal()
    decrypt_requested = Signal()
    properties_requested = Signal()

    to_images_requested = Signal()
    images_to_pdf_requested = Signal()
    to_text_requested = Signal()
    ocr_requested = Signal()

    def __init__(self, dark: bool = False, parent=None):
        super().__init__(parent)
        self.setObjectName("AllToolsPanel")
        self._dark = dark
        self._checkable = {}
        self._all_buttons = []
        self._headers = []
        self._groups = []          # [(header, [member widgets]), ...]
        self._current_group = None

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Search box — type to filter tools (helps users who feel lost).
        from PySide6.QtWidgets import QLineEdit
        search_wrap = QWidget()
        sw = QVBoxLayout(search_wrap)
        sw.setContentsMargins(10, 10, 10, 6)
        self.search = QLineEdit()
        self.search.setPlaceholderText("\U0001F50D  Search tools…")
        self.search.setClearButtonEnabled(True)
        self.search.setFixedHeight(32)
        _sbg = "#2A2D34" if dark else "#FFFFFF"
        _sbd = "#3A3E47" if dark else "#DCDFE6"
        _stx = "#E6E8EC" if dark else "#2B2D33"
        self.search.setStyleSheet(
            f"QLineEdit {{ background: {_sbg}; border: 1px solid {_sbd};"
            f" border-radius: 8px; padding: 4px 10px; color: {_stx};"
            f" font-size: 13px; }}"
            f"QLineEdit:focus {{ border: 1px solid {ACCENT}; }}")
        sw.addWidget(self.search)
        outer.addWidget(search_wrap)
        self.search.textChanged.connect(self._filter_tools)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        outer.addWidget(scroll, 1)

        inner = QWidget()
        scroll.setWidget(inner)
        self._layout = QVBoxLayout(inner)
        self._layout.setContentsMargins(8, 8, 8, 12)
        self._layout.setSpacing(1)

        self._build()

    def _build(self):
        L = self._layout

        # ---- RESEARCH TOOLS — highlighted at the very top, easy to find ----
        self._research_header(L, "\U0001F393  RESEARCH TOOLS")
        self.library_btn = self._add_feature(
            L, "\U0001F4DA", "Research Library",
            "Organize all your papers — import, tag, search, open",
            self.library_requested)
        self.refcol_btn = self._add_feature(
            L, "\U0001F517", "Reference Collection",
            "Collect references from citations and save them to Excel",
            self.reference_collection_requested)
        self.notescol_btn = self._add_feature(
            L, "\U0001F4DD", "Text / Notes Collection",
            "Save important highlighted text with its source",
            self.notes_collection_requested)
        L.addSpacing(4)

        self._section(L, "Quick Actions")
        self.select_text_btn = self._add(
            L, "highlight", "Select / Copy Text",
            "Drag a box over text to copy it to the clipboard",
            self.select_text_requested, "select_text")
        self.undo_btn = self._add(L, "undo", "Undo",
                                  "Undo the last edit (Ctrl+Z)",
                                  self.undo_requested)
        self.delete_annot_btn = self._add(
            L, "eraser", "Delete an Edit",
            "Click an annotation, comment, stamp, or added text to remove it",
            self.delete_annot_requested, "delete_annot")

        self._section(L, "Annotate")
        self.highlight_btn = self._add(L, "highlight", "Highlight",
                                       "Drag across text to highlight",
                                       self.highlight_requested, "highlight")
        self.line_highlight_btn = self._add(L, "highlight_line", "Highlight a Line",
                                            "Click a line to highlight just that line",
                                            self.line_highlight_requested,
                                            "line_highlight")
        self._add(L, "note", "Sticky Note",
                  "Add a sticky note", self.note_requested)
        self.comment_btn = self._add(L, "comment", "Comment",
                                     "Click on the page to drop a comment",
                                     self.comment_requested, "comment")
        self.line_comment_btn = self._add(L, "comment_line", "Comment on a Line",
                                          "Click a line to comment on it",
                                          self.line_comment_requested,
                                          "line_comment")
        self.stamp_btn = self._add(L, "stamp", "Stamp",
                                   "Add a stamp (Approved, Confidential, …)",
                                   self.stamp_requested, "stamp")

        self._section(L, "Edit")
        self.edit_mode_btn = self._add(L, "edit_line", "Edit Mode (click & type)",
                                       "Turn on edit mode, then click any line and type",
                                       self.edit_mode_requested, "edit_mode")
        self._add(L, "text_color", "Change Text Color",
                  "Recolor all text on a page", self.text_color_requested)
        self.line_edit_btn = self._add(L, "edit_line", "Edit a Line",
                                       "Click a line to edit its text",
                                       self.line_edit_requested, "line_edit")
        self.line_color_btn = self._add(L, "edit_line", "Color a Line",
                                        "Click a line to change its color",
                                        self.line_color_requested, "line_color")

        self._section(L, "Modify Page")
        self._add(L, "rotate_left", "Rotate Page Left",
                  "Rotate current page 90° counter-clockwise",
                  self.rotate_page_left_requested)
        self._add(L, "rotate_right", "Rotate Page Right",
                  "Rotate current page 90° clockwise",
                  self.rotate_page_right_requested)
        self._add(L, "page_add", "Insert Blank Page",
                  "Add a blank page after the current page",
                  self.insert_blank_page_requested)
        self._add(L, "page_delete", "Delete Current Page",
                  "Remove the current page (with confirm)",
                  self.delete_current_page_requested)

        self._section(L, "Add Content")
        self.add_text_btn = self._add(L, "add_text", "Add Text",
                                      "Click on the page to drop text",
                                      self.add_text_requested, "add_text")
        self.add_image_btn = self._add(L, "add_image", "Insert Image",
                                       "Drag a rectangle to place an image",
                                       self.add_image_requested, "add_image")
        self._add(L, "header_footer", "Header & Footer",
                  "Add headers and footers across pages",
                  self.header_footer_requested)

        self._section(L, "Sign & Forms")
        self.sign_btn = self._add(L, "sign", "Sign",
                                  "Sign the document — click to place",
                                  self.sign_requested, "sign")
        self.prepare_form_btn = self._add(L, "form", "Prepare Form",
                                          "Add form fields (text, checkbox, …)",
                                          self.prepare_form_requested,
                                          "prepare_form")
        self.fill_form_btn = self._add(L, "form", "Fill Form",
                                       "Click a form field and type to fill it",
                                       self.fill_form_requested, "fill_form")
        self._add(L, "fill_sign", "Fill & Sign",
                  "Fill existing form fields", self.fill_form_requested)

        self._section(L, "Rich Media")
        self.media_btn = self._add(L, "link", "Link / Media",
                                   "Add web links, attachments, or media",
                                   self.media_requested, "media")
        self._add(L, "review", "Send for Review",
                  "Email a comments summary", self.send_review_requested)

        self._section(L, "Pages")
        self._add(L, "create", "Create Blank PDF",
                  "Make a new empty PDF", self.create_pdf_requested)
        self._add(L, "organize", "Organize Pages",
                  "Reorder, rotate, delete pages", self.organize_requested)
        self._add(L, "merge", "Merge PDFs",
                  "Combine multiple PDFs", self.merge_requested)
        self._add(L, "split", "Split PDF",
                  "Split this PDF apart", self.split_requested)
        self._add(L, "extract", "Extract Pages",
                  "Pull out selected pages", self.extract_requested)
        self._add(L, "compare", "Compare PDFs",
                  "Side-by-side text diff + report", self.compare_requested)
        self._add(L, "extract", "Extract Citations",
                  "Pull out in-text citations and the reference list",
                  self.extract_citations_requested)

        self._section(L, "Document")
        self._add(L, "compress", "Compress",
                  "Reduce file size", self.compress_requested)
        self._add(L, "encrypt", "Encrypt (Password)",
                  "Protect with a password", self.encrypt_requested)
        self._add(L, "decrypt", "Decrypt",
                  "Remove password", self.decrypt_requested)
        self._add(L, "properties", "Properties",
                  "View / edit metadata", self.properties_requested)

        self._section(L, "Convert")
        self._add(L, "to_images", "PDF \u2192 Images",
                  "Export pages as PNG/JPG", self.to_images_requested)
        self._add(L, "images_to_pdf", "Images \u2192 PDF",
                  "Build PDF from images", self.images_to_pdf_requested)
        self._add(L, "to_text", "PDF \u2192 Text",
                  "Extract all text", self.to_text_requested)
        self._add(L, "ocr", "Run OCR",
                  "Make scanned PDF searchable", self.ocr_requested)

        L.addStretch(1)

        # Start with only the most-used groups open, so new users aren't
        # overwhelmed. They can click any header to expand it.
        open_by_default = {"QUICK ACTIONS", "ANNOTATE"}
        for hdr, members in self._groups:
            if hdr.lbl.text() not in open_by_default:
                hdr.set_collapsed(True)
                for w in members:
                    w.setVisible(False)

    def _filter_tools(self, text):
        text = (text or "").strip().lower()
        if not text:
            # restore default: show all, then re-collapse non-default groups
            for hdr, members in self._groups:
                hdr.setVisible(True)
                collapsed = hdr._collapsed
                for w in members:
                    w.setVisible(not collapsed)
            return
        # search mode: show only matching buttons, expand their groups
        for hdr, members in self._groups:
            any_match = False
            for w in members:
                label = w.text().strip().lower()
                match = text in label
                w.setVisible(match)
                if match:
                    any_match = True
            hdr.setVisible(any_match)

    def _research_header(self, layout, text):
        """A bold, colored header for the highlighted research section."""
        h = QLabel(text)
        h.setStyleSheet(
            "color: #2667FF; font-size: 11px; font-weight: 800;"
            " letter-spacing: 1px; padding: 10px 14px 4px 14px;")
        layout.addWidget(h)

    def _add_feature(self, layout, emoji, text, tooltip, signal):
        """A prominent, highlighted button for an important research tool."""
        btn = QPushButton(f"  {emoji}   {text}")
        btn.setToolTip(tooltip)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setFixedHeight(42)
        btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        bg = "rgba(38,103,255,0.10)" if not self._dark else "rgba(38,103,255,0.20)"
        hover = "rgba(38,103,255,0.18)" if not self._dark else "rgba(38,103,255,0.30)"
        txt = "#1B53E0" if not self._dark else "#9DB8FF"
        btn.setStyleSheet(
            f"QPushButton {{ text-align: left; padding: 0 12px; border: none;"
            f" border-radius: 9px; background: {bg}; color: {txt};"
            f" font-size: 13px; font-weight: 600; }}"
            f"QPushButton:hover {{ background: {hover}; }}")
        btn.clicked.connect(lambda checked=False: signal.emit())
        # small left margin wrapper for breathing room
        from PySide6.QtWidgets import QWidget as _QW, QHBoxLayout as _QH
        wrap = _QW()
        h = _QH(wrap); h.setContentsMargins(8, 2, 8, 2); h.addWidget(btn)
        layout.addWidget(wrap)
        return btn

    def _section(self, layout, text):
        sp = QWidget(); sp.setFixedHeight(4)
        layout.addWidget(sp)
        h = SectionHeader(text, self._dark)
        layout.addWidget(h)
        self._headers.append(h)
        # start a new group; tools added after this belong to it
        self._current_group = []
        self._groups.append((h, self._current_group))
        h.clicked.connect(lambda hdr=h: self._toggle_section(hdr))

    def _toggle_section(self, header):
        for hdr, members in self._groups:
            if hdr is header:
                collapsed = not hdr._collapsed
                hdr.set_collapsed(collapsed)
                for w in members:
                    w.setVisible(not collapsed)
                break

    def _add(self, layout, icon_name, text, tooltip, signal, check_key=None):
        btn = ToolButton(icon_name, text, tooltip,
                         checkable=bool(check_key), dark=self._dark)
        btn.clicked.connect(lambda checked=False: signal.emit())
        layout.addWidget(btn)
        self._all_buttons.append(btn)
        # register with the current section group for collapse/expand
        if hasattr(self, "_current_group") and self._current_group is not None:
            self._current_group.append(btn)
        if check_key:
            self._checkable[check_key] = btn
        return btn

    def set_dark(self, dark: bool):
        if dark == self._dark:
            return
        self._dark = dark
        for btn in self._all_buttons:
            btn.refresh_icon(dark)
        for h in self._headers:
            h.set_dark(dark)

    def uncheck_all_except(self, keep_name=None):
        for name, b in self._checkable.items():
            if name != keep_name:
                b.setChecked(False)
                b.refresh_icon(self._dark)

    def get(self, name):
        return self._checkable.get(name)
