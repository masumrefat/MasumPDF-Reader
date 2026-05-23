"""OCR using pytesseract.

Renders each PDF page to an image, runs Tesseract, and stitches the
recognised text back into a searchable PDF.

Tesseract must be installed on the host:
  Windows  : https://github.com/UB-Mannheim/tesseract/wiki
  macOS    : brew install tesseract
  Linux    : sudo apt install tesseract-ocr
"""

import os
import fitz


class OCREngine:
    def __init__(self, language: str = "eng", dpi: int = 200):
        self.language = language
        self.dpi = dpi

    def is_available(self) -> bool:
        try:
            import pytesseract
            pytesseract.get_tesseract_version()
            return True
        except Exception:
            return False

    def ocr_page_to_text(self, pdf_path: str, page_index: int) -> str:
        import pytesseract
        from PIL import Image
        import io
        doc = fitz.open(pdf_path)
        page = doc.load_page(page_index)
        zoom = self.dpi / 72.0
        pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
        img = Image.open(io.BytesIO(pix.tobytes("png")))
        text = pytesseract.image_to_string(img, lang=self.language)
        doc.close()
        return text

    def ocr_pdf_to_searchable(self, pdf_path: str, output_path: str, progress_cb=None):
        """Build a new PDF where each page has an invisible text layer."""
        import pytesseract
        from PIL import Image
        import io

        src = fitz.open(pdf_path)
        out = fitz.open()  # blank target
        total = src.page_count
        zoom = self.dpi / 72.0
        mat = fitz.Matrix(zoom, zoom)

        for i in range(total):
            page = src.load_page(i)
            pix = page.get_pixmap(matrix=mat, alpha=False)
            img = Image.open(io.BytesIO(pix.tobytes("png")))

            # build a target page with the same size as the source page
            new_page = out.new_page(width=page.rect.width, height=page.rect.height)
            # paste the original page image as the background
            img_bytes = pix.tobytes("png")
            new_page.insert_image(new_page.rect, stream=img_bytes)

            # run Tesseract to get per-word bounding boxes (TSV-like dict)
            try:
                data = pytesseract.image_to_data(
                    img, lang=self.language, output_type=pytesseract.Output.DICT
                )
            except Exception:
                data = None

            if data:
                for j in range(len(data.get("text", []))):
                    word = data["text"][j].strip()
                    if not word:
                        continue
                    x, y, w, h = (data["left"][j], data["top"][j],
                                  data["width"][j], data["height"][j])
                    # convert image-pixel coords to PDF coords
                    x0 = x / zoom
                    y0 = y / zoom
                    rect = fitz.Rect(x0, y0, x0 + w / zoom, y0 + h / zoom)
                    # invisible text overlay so it becomes searchable & copyable
                    new_page.insert_textbox(
                        rect, word, fontname="helv",
                        fontsize=max(rect.height * 0.8, 4),
                        render_mode=3,  # invisible
                    )

            if progress_cb:
                progress_cb(i + 1, total)

        out.save(output_path, garbage=4, deflate=True)
        out.close()
        src.close()

    @staticmethod
    def is_scanned(pdf_path: str, sample_pages: int = 3) -> bool:
        """Heuristic: if the first few pages have little or no text, treat as scanned."""
        doc = fitz.open(pdf_path)
        n = min(sample_pages, doc.page_count)
        total_text = 0
        for i in range(n):
            total_text += len(doc.load_page(i).get_text().strip())
        doc.close()
        return total_text < 40  # < ~40 chars across sample = probably scanned
