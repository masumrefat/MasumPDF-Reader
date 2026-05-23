"""Rich media in PDFs: web links, file attachments, audio/video notes.

Honest scope:
  - URL links: well supported, work in every PDF viewer.
  - File attachments: well supported, opens in viewers that understand
    embedded files (Acrobat, Foxit, most modern readers).
  - Audio/video: PDF supports these via "screen" / "movie" / "rich media"
    annotations but playback compatibility is poor outside Acrobat. We
    embed the file as an attachment and add a link annotation that says
    'Click to open media' — this is the most portable option.
"""

import os
import fitz


class MediaManager:
    """Add links and media to PDF pages."""

    def __init__(self, pdf_document):
        self.pdf = pdf_document

    def add_url_link(self, page_index: int, rect: tuple, url: str):
        """Add a clickable URL link on a region of a page."""
        if not url:
            raise ValueError("URL is empty")
        page = self.pdf.doc[page_index]
        link = {
            "kind": fitz.LINK_URI,
            "from": fitz.Rect(*rect),
            "uri": url,
        }
        page.insert_link(link)
        self.pdf.mark_dirty()

    def add_internal_link(self, page_index: int, rect: tuple,
                          target_page: int):
        """Add a clickable link that jumps to another page."""
        page = self.pdf.doc[page_index]
        link = {
            "kind": fitz.LINK_GOTO,
            "from": fitz.Rect(*rect),
            "page": target_page,
            "to": fitz.Point(0, 0),
        }
        page.insert_link(link)
        self.pdf.mark_dirty()

    def add_file_attachment(self, page_index: int,
                            point: tuple[float, float],
                            file_path: str,
                            description: str = ""):
        """Embed a file as an attachment with a paperclip icon on the page."""
        if not os.path.exists(file_path):
            raise FileNotFoundError(file_path)
        page = self.pdf.doc[page_index]
        with open(file_path, "rb") as f:
            data = f.read()
        filename = os.path.basename(file_path)
        x, y = point
        rect = fitz.Rect(x, y, x + 20, y + 20)
        annot = page.add_file_annot(
            rect.tl,            # top-left point
            data,
            filename=filename,
            desc=description or filename,
        )
        if annot:
            annot.set_info(title=filename, content=description or filename)
            annot.update()
        self.pdf.mark_dirty()

    def add_media_pointer(self, page_index: int,
                          rect: tuple,
                          file_path: str,
                          label: str = "Click to play media"):
        """Embed an audio/video file as an attachment, and put a clickable
        labelled box on the page. The viewer will open the file with the
        OS default application — the most portable option."""
        if not os.path.exists(file_path):
            raise FileNotFoundError(file_path)
        page = self.pdf.doc[page_index]
        # Draw the label box
        r = fitz.Rect(*rect)
        page.draw_rect(r, color=(0.2, 0.4, 0.8), width=1.5, fill=(0.93, 0.96, 1))
        page.insert_textbox(r, "▶  " + label,
                            fontname="hebo", fontsize=11,
                            color=(0.2, 0.4, 0.8), align=1)
        # Embed the media as a file attachment
        with open(file_path, "rb") as f:
            data = f.read()
        filename = os.path.basename(file_path)
        # Attach via document level so the link can reference it
        try:
            self.pdf.doc.embfile_add(filename, data, filename=filename,
                                     desc=label)
        except Exception:
            # if a name collision occurs, append a number
            i = 1
            while True:
                new_name = f"{i}_{filename}"
                try:
                    self.pdf.doc.embfile_add(new_name, data,
                                             filename=filename, desc=label)
                    break
                except Exception:
                    i += 1
                    if i > 99:
                        raise
        self.pdf.mark_dirty()

    def list_links(self) -> list[dict]:
        """List every link in the document."""
        out = []
        if not self.pdf or not self.pdf.doc:
            return out
        for pno, page in enumerate(self.pdf.doc):
            for link in page.get_links() or []:
                out.append({
                    "page": pno,
                    "kind": link.get("kind"),
                    "uri": link.get("uri"),
                    "target_page": link.get("page"),
                    "rect": link.get("from"),
                })
        return out
