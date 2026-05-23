"""Stamp annotations.

PDF supports a set of standard stamps (Approved, Confidential, Draft, …).
We also offer custom text stamps drawn as a colored box with the text
inside.
"""

import fitz


# Friendly name -> fitz constant
STANDARD_STAMPS = {
    "Approved":              fitz.STAMP_Approved,
    "As Is":                 fitz.STAMP_AsIs,
    "Confidential":          fitz.STAMP_Confidential,
    "Departmental":          fitz.STAMP_Departmental,
    "Draft":                 fitz.STAMP_Draft,
    "Experimental":          fitz.STAMP_Experimental,
    "Expired":               fitz.STAMP_Expired,
    "Final":                 fitz.STAMP_Final,
    "For Comment":           fitz.STAMP_ForComment,
    "For Public Release":    fitz.STAMP_ForPublicRelease,
    "Not Approved":          fitz.STAMP_NotApproved,
    "Not For Public":        fitz.STAMP_NotForPublicRelease,
    "Sold":                  fitz.STAMP_Sold,
    "Top Secret":            fitz.STAMP_TopSecret,
}


def _hex_to_rgb01(hex_str: str):
    h = hex_str.lstrip("#")
    if len(h) != 6:
        return (0.8, 0.1, 0.1)
    return (int(h[0:2], 16) / 255.0,
            int(h[2:4], 16) / 255.0,
            int(h[4:6], 16) / 255.0)


class StampManager:
    """Add stamps to a PDF."""

    DEFAULT_WIDTH = 180   # default stamp box width in PDF points
    DEFAULT_HEIGHT = 50

    def __init__(self, pdf_document):
        self.pdf = pdf_document

    def add_standard_stamp(self, page_index: int, kind: str,
                           top_left: tuple[float, float],
                           width: float = DEFAULT_WIDTH,
                           height: float = DEFAULT_HEIGHT):
        """Add one of the built-in PDF stamps."""
        if kind not in STANDARD_STAMPS:
            raise ValueError(f"Unknown stamp: {kind}")
        x, y = top_left
        rect = fitz.Rect(x, y, x + width, y + height)
        page = self.pdf.doc[page_index]
        page.add_stamp_annot(rect, stamp=STANDARD_STAMPS[kind])
        self.pdf.mark_dirty()

    def add_custom_text_stamp(self, page_index: int,
                              text: str,
                              top_left: tuple[float, float],
                              width: float = DEFAULT_WIDTH,
                              height: float = DEFAULT_HEIGHT,
                              color_hex: str = "#CC0000",
                              border_width: float = 2.0,
                              opacity: float = 0.95):
        """Draw a custom text stamp.

        Looks like: a colored bordered rounded box with the text in the
        same color. Stays as page content (not an annotation), so it
        cannot be removed by recipients.
        """
        if not text.strip():
            raise ValueError("Stamp text is empty")
        page = self.pdf.doc[page_index]
        rgb = _hex_to_rgb01(color_hex)
        x, y = top_left
        rect = fitz.Rect(x, y, x + width, y + height)

        # outer border
        page.draw_rect(rect, color=rgb, width=border_width, fill=None,
                       overlay=True)
        # inner border, smaller, gives the double-line stamp look
        page.draw_rect(rect + (3, 3, -3, -3), color=rgb,
                       width=border_width * 0.5, fill=None, overlay=True)
        # text
        fontsize = min(height * 0.55, width / max(4, len(text)) * 1.4)
        fontsize = max(10, min(48, fontsize))
        # tight rect so the text is centered. Use a Unicode font when the
        # stamp text isn't plain Latin, so Bangla/CJK/etc. don't become "????".
        from utils.fonts import font_for_page
        stamp_text = text.upper()
        fn, ff = font_for_page(page, stamp_text, "hebo")
        page.insert_textbox(rect, stamp_text,
                            fontname=fn, fontfile=ff,
                            fontsize=fontsize,
                            color=rgb,
                            align=1,           # center
                            render_mode=0)
        self.pdf.mark_dirty()

    @staticmethod
    def list_stamp_names() -> list[str]:
        return list(STANDARD_STAMPS.keys())
