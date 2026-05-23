"""Form field management.

Build forms by adding widgets to PDF pages. Fill existing forms by
walking widgets and setting their values.
"""

import fitz


# Friendly field type names mapped to fitz constants
FIELD_TYPES = {
    "text":      fitz.PDF_WIDGET_TYPE_TEXT,
    "checkbox":  fitz.PDF_WIDGET_TYPE_CHECKBOX,
    "dropdown":  fitz.PDF_WIDGET_TYPE_COMBOBOX,
    "listbox":   fitz.PDF_WIDGET_TYPE_LISTBOX,
    "signature": fitz.PDF_WIDGET_TYPE_SIGNATURE,
    "radio":     fitz.PDF_WIDGET_TYPE_RADIOBUTTON,
}

# Reverse map for display
TYPE_TO_NAME = {v: k for k, v in FIELD_TYPES.items()}


def _hex_to_rgb01(hex_str: str):
    h = hex_str.lstrip("#")
    if len(h) != 6:
        return None
    return (int(h[0:2], 16) / 255.0,
            int(h[2:4], 16) / 255.0,
            int(h[4:6], 16) / 255.0)


class FormManager:
    """Helpers for building and filling form fields."""

    def __init__(self, pdf_document):
        self.pdf = pdf_document

    # ---- build ----
    def add_field(self,
                  page_index: int,
                  rect: tuple,
                  field_type: str = "text",
                  field_name: str | None = None,
                  field_label: str = "",
                  default_value: str = "",
                  options: list[str] | None = None,
                  font_size: float = 11.0,
                  border_color: str = "#888888",
                  fill_color: str | None = "#FFFFE0",
                  required: bool = False):
        """Add a new form field widget to a page.

        rect is (x0, y0, x1, y1) in PDF points.
        """
        if not self.pdf or not self.pdf.doc:
            raise RuntimeError("No PDF open")

        page = self.pdf.doc[page_index]
        widget = fitz.Widget()
        widget.rect = fitz.Rect(*rect)
        widget.field_name = field_name or self._unique_name(field_type)
        widget.field_label = field_label or widget.field_name
        widget.field_type = FIELD_TYPES.get(field_type, fitz.PDF_WIDGET_TYPE_TEXT)
        widget.text_fontsize = font_size

        border_rgb = _hex_to_rgb01(border_color)
        if border_rgb:
            widget.border_color = border_rgb
            widget.border_width = 0.8

        if fill_color:
            fill_rgb = _hex_to_rgb01(fill_color)
            if fill_rgb:
                widget.fill_color = fill_rgb

        if required:
            try:
                widget.field_flags = widget.field_flags | 2  # Required flag
            except Exception:
                pass

        if field_type in ("dropdown", "listbox") and options:
            widget.choice_values = list(options)
            if default_value and default_value in options:
                widget.field_value = default_value
            elif options:
                widget.field_value = options[0]
        elif field_type == "checkbox":
            widget.field_value = bool(default_value and default_value.lower()
                                      in ("yes", "true", "on", "1", "checked"))
        else:
            widget.field_value = default_value or ""

        page.add_widget(widget)
        self.pdf.mark_dirty()
        return widget.field_name

    def _unique_name(self, prefix: str) -> str:
        """Generate a field name that doesn't clash with existing widgets."""
        existing = set()
        try:
            for page in self.pdf.doc:
                for w in page.widgets() or []:
                    existing.add(w.field_name or "")
        except Exception:
            pass
        i = 1
        while True:
            name = f"{prefix}_{i}"
            if name not in existing:
                return name
            i += 1

    # ---- read ----
    def list_fields(self) -> list[dict]:
        """Return every form field in the document with its current value."""
        out = []
        if not self.pdf or not self.pdf.doc:
            return out
        for pno, page in enumerate(self.pdf.doc):
            widgets = page.widgets() or []
            for w in widgets:
                ft = TYPE_TO_NAME.get(w.field_type, str(w.field_type))
                rect = w.rect
                out.append({
                    "page": pno,
                    "name": w.field_name or "",
                    "label": w.field_label or w.field_name or "",
                    "type": ft,
                    "value": w.field_value,
                    "options": list(w.choice_values) if w.choice_values else [],
                    "rect": (rect.x0, rect.y0, rect.x1, rect.y1),
                })
        return out

    def has_fields(self) -> bool:
        if not self.pdf or not self.pdf.doc:
            return False
        for page in self.pdf.doc:
            if page.widgets():
                return True
        return False

    # ---- fill ----
    def set_field_value(self, page_index: int, field_name: str, value) -> bool:
        if not self.pdf or not self.pdf.doc:
            return False
        page = self.pdf.doc[page_index]
        for w in page.widgets() or []:
            if w.field_name == field_name:
                if w.field_type == fitz.PDF_WIDGET_TYPE_CHECKBOX:
                    w.field_value = bool(value)
                else:
                    w.field_value = str(value) if value is not None else ""
                w.update()
                self.pdf.mark_dirty()
                return True
        return False

    def flatten_fields(self, output_path: str):
        """Write a copy where form fields are 'frozen' as page content.

        After flattening, fields can't be edited anymore — useful when
        you want to send a filled form as a final document.
        """
        if not self.pdf or not self.pdf.doc:
            raise RuntimeError("No PDF open")
        # Use bake_in_annots/widgets through save with the right flags.
        # PyMuPDF: convert_to_pdf isn't right here; use page.apply_redactions?
        # Best approach: walk widgets, draw their value, then delete widget.
        import io
        # Save current to bytes then re-open so we don't mutate the live doc
        buf = io.BytesIO()
        self.pdf.doc.save(buf)
        buf.seek(0)
        doc = fitz.open(stream=buf.read(), filetype="pdf")
        for page in doc:
            widgets = list(page.widgets() or [])
            for w in widgets:
                try:
                    rect = w.rect
                    val = w.field_value
                    if w.field_type == fitz.PDF_WIDGET_TYPE_CHECKBOX:
                        if val:
                            page.draw_line(
                                fitz.Point(rect.x0 + 2, rect.y0 + rect.height / 2),
                                fitz.Point(rect.x0 + rect.width / 3,
                                           rect.y1 - 2),
                                color=(0, 0, 0), width=1.5)
                            page.draw_line(
                                fitz.Point(rect.x0 + rect.width / 3,
                                           rect.y1 - 2),
                                fitz.Point(rect.x1 - 2, rect.y0 + 2),
                                color=(0, 0, 0), width=1.5)
                    elif val:
                        page.insert_textbox(
                            rect, str(val),
                            fontname="helv",
                            fontsize=max(8, min(14, rect.height - 4)),
                            color=(0, 0, 0), align=0)
                    # remove widget after baking
                    annot = w._annot if hasattr(w, "_annot") else None
                    try:
                        page.delete_widget(w)
                    except Exception:
                        pass
                except Exception:
                    continue
        doc.save(output_path, garbage=4, deflate=True)
        doc.close()
