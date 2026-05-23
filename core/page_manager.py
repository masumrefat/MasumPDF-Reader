"""Higher-level page operations: split, merge, extract ranges, etc.

Most of this is implemented via PyMuPDF directly; pypdf is used where
its API is simpler (mainly merge).
"""

import fitz
import pypdf
import os


class PageManager:
    """Operations that act on whole pages or ranges of pages."""

    def __init__(self, pdf_document=None):
        self.pdf = pdf_document  # optional — many methods are static-like

    # ---- range parsing ----
    @staticmethod
    def parse_page_range(spec: str, max_pages: int) -> list[int]:
        """
        Parse '1-3,5,7-9' into a sorted unique list of 0-indexed page numbers.
        Pages out of bounds are silently dropped.
        """
        if not spec:
            return []
        spec = spec.strip()
        if spec.lower() == "all":
            return list(range(max_pages))
        pages = set()
        for chunk in spec.split(","):
            chunk = chunk.strip()
            if not chunk:
                continue
            if "-" in chunk:
                a, _, b = chunk.partition("-")
                try:
                    start = int(a)
                    end = int(b)
                except ValueError:
                    continue
                for p in range(min(start, end), max(start, end) + 1):
                    if 1 <= p <= max_pages:
                        pages.add(p - 1)
            else:
                try:
                    p = int(chunk)
                except ValueError:
                    continue
                if 1 <= p <= max_pages:
                    pages.add(p - 1)
        return sorted(pages)

    # ---- merge ----
    @staticmethod
    def merge_pdfs(input_paths: list[str], output_path: str):
        """Concatenate multiple PDFs."""
        writer = pypdf.PdfWriter()
        for path in input_paths:
            reader = pypdf.PdfReader(path)
            for page in reader.pages:
                writer.add_page(page)
        with open(output_path, "wb") as f:
            writer.write(f)

    # ---- split ----
    @staticmethod
    def split_by_ranges(input_path: str, output_folder: str, ranges: list[str]):
        """Save each range expression to its own file inside output_folder."""
        os.makedirs(output_folder, exist_ok=True)
        src = fitz.open(input_path)
        outputs = []
        for i, spec in enumerate(ranges, 1):
            pages = PageManager.parse_page_range(spec, src.page_count)
            if not pages:
                continue
            out_doc = fitz.open()
            for p in pages:
                out_doc.insert_pdf(src, from_page=p, to_page=p)
            stem = os.path.splitext(os.path.basename(input_path))[0]
            out_path = os.path.join(output_folder, f"{stem}_part{i}.pdf")
            out_doc.save(out_path, garbage=4, deflate=True)
            out_doc.close()
            outputs.append(out_path)
        src.close()
        return outputs

    @staticmethod
    def split_each_page(input_path: str, output_folder: str):
        """Save every page of the input PDF as its own one-page PDF."""
        os.makedirs(output_folder, exist_ok=True)
        src = fitz.open(input_path)
        outputs = []
        stem = os.path.splitext(os.path.basename(input_path))[0]
        for i in range(src.page_count):
            out_doc = fitz.open()
            out_doc.insert_pdf(src, from_page=i, to_page=i)
            out = os.path.join(output_folder, f"{stem}_page{i + 1:04d}.pdf")
            out_doc.save(out, garbage=4, deflate=True)
            out_doc.close()
            outputs.append(out)
        src.close()
        return outputs

    # ---- extract ----
    @staticmethod
    def extract_pages(input_path: str, page_indices: list[int], output_path: str):
        src = fitz.open(input_path)
        out_doc = fitz.open()
        for idx in page_indices:
            if 0 <= idx < src.page_count:
                out_doc.insert_pdf(src, from_page=idx, to_page=idx)
        out_doc.save(output_path, garbage=4, deflate=True)
        out_doc.close()
        src.close()
