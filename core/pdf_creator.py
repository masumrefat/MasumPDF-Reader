"""Create a new blank PDF from scratch."""

import fitz


# Standard page sizes in points (1 pt = 1/72 inch). PyMuPDF uses points.
PAGE_SIZES = {
    "A4":      (595.276, 841.890),
    "A3":      (841.890, 1190.551),
    "A5":      (419.528, 595.276),
    "Letter":  (612.0, 792.0),
    "Legal":   (612.0, 1008.0),
    "Tabloid": (792.0, 1224.0),
}


def create_blank_pdf(output_path: str,
                     page_size: str = "A4",
                     orientation: str = "portrait",
                     page_count: int = 1,
                     title: str = "",
                     author: str = "") -> str:
    """Create a blank PDF and return its output path."""
    if page_size not in PAGE_SIZES:
        page_size = "A4"
    w, h = PAGE_SIZES[page_size]
    if orientation == "landscape":
        w, h = h, w

    doc = fitz.open()
    for _ in range(max(1, int(page_count))):
        doc.new_page(width=w, height=h)

    if title or author:
        md = doc.metadata or {}
        if title:  md["title"] = title
        if author: md["author"] = author
        doc.set_metadata(md)

    doc.save(output_path, garbage=4, deflate=True)
    doc.close()
    return output_path
