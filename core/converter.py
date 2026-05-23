"""Format conversion helpers."""

import os
import fitz
from PIL import Image


class Converter:
    """PDF <-> images / text / docx (optional)."""

    # ---- PDF pages to images ----
    @staticmethod
    def pdf_to_images(pdf_path: str, out_folder: str, fmt: str = "png",
                      dpi: int = 150, pages: list[int] | None = None,
                      progress_cb=None) -> list[str]:
        os.makedirs(out_folder, exist_ok=True)
        doc = fitz.open(pdf_path)
        zoom = dpi / 72.0
        mat = fitz.Matrix(zoom, zoom)
        page_indices = pages if pages else list(range(doc.page_count))
        total = len(page_indices)
        outputs = []
        ext = "jpg" if fmt.lower() in ("jpg", "jpeg") else "png"
        for i, idx in enumerate(page_indices, 1):
            page = doc.load_page(idx)
            pix = page.get_pixmap(matrix=mat, alpha=False)
            out = os.path.join(out_folder, f"page_{idx + 1:04d}.{ext}")
            pix.save(out)
            outputs.append(out)
            if progress_cb:
                progress_cb(i, total)
        doc.close()
        return outputs

    # ---- images to PDF ----
    @staticmethod
    def images_to_pdf(image_paths: list[str], output_path: str):
        if not image_paths:
            raise ValueError("No images provided")
        images = []
        for p in image_paths:
            img = Image.open(p).convert("RGB")
            images.append(img)
        first, rest = images[0], images[1:]
        first.save(output_path, "PDF", resolution=100.0,
                   save_all=True, append_images=rest)
        for img in images:
            img.close()

    # ---- extract text ----
    @staticmethod
    def pdf_to_text(pdf_path: str, output_path: str | None = None,
                    pages: list[int] | None = None) -> str:
        doc = fitz.open(pdf_path)
        page_indices = pages if pages else list(range(doc.page_count))
        chunks = []
        for idx in page_indices:
            chunks.append(doc.load_page(idx).get_text())
        doc.close()
        full = "\n\n".join(chunks)
        if output_path:
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(full)
        return full

    # ---- to DOCX (optional, requires python-docx) ----
    @staticmethod
    def pdf_to_docx(pdf_path: str, output_path: str) -> bool:
        """Best-effort DOCX export. Returns True on success, False if dependency missing."""
        try:
            from docx import Document
        except ImportError:
            return False
        text = Converter.pdf_to_text(pdf_path)
        doc = Document()
        for paragraph in text.split("\n"):
            doc.add_paragraph(paragraph)
        doc.save(output_path)
        return True
