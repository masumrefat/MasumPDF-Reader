"""Background worker threads for long-running PDF operations.

Each worker is a QThread that emits progress/finished/error signals
so the UI stays responsive during OCR, merging, conversion, etc.
"""

from PySide6.QtCore import QThread, Signal


class BaseWorker(QThread):
    """Common base — exposes progress, message, finished_ok, failed signals."""

    progress = Signal(int)          # 0-100
    message = Signal(str)           # status text
    finished_ok = Signal(object)    # result payload
    failed = Signal(str)            # error message

    def __init__(self, parent=None):
        super().__init__(parent)
        self._cancel = False

    def cancel(self):
        self._cancel = True

    def is_cancelled(self) -> bool:
        return self._cancel


class OCRWorker(BaseWorker):
    """Run OCR over a PDF, producing a searchable copy."""

    def __init__(self, pdf_path: str, output_path: str, language: str = "eng"):
        super().__init__()
        self.pdf_path = pdf_path
        self.output_path = output_path
        self.language = language

    def run(self):
        try:
            from core.ocr_engine import OCREngine
            engine = OCREngine(language=self.language)

            def cb(done: int, total: int, page_text: str = ""):
                if self.is_cancelled():
                    raise RuntimeError("OCR cancelled by user")
                pct = int(done * 100 / max(total, 1))
                self.progress.emit(pct)
                self.message.emit(f"OCR page {done}/{total}")

            engine.ocr_pdf_to_searchable(self.pdf_path, self.output_path, progress_cb=cb)
            self.finished_ok.emit(self.output_path)
        except Exception as e:
            self.failed.emit(str(e))


class MergeWorker(BaseWorker):
    """Merge multiple PDFs into one."""

    def __init__(self, input_paths: list, output_path: str):
        super().__init__()
        self.input_paths = input_paths
        self.output_path = output_path

    def run(self):
        try:
            import pypdf
            writer = pypdf.PdfWriter()
            total = len(self.input_paths)
            for i, path in enumerate(self.input_paths, 1):
                if self.is_cancelled():
                    self.failed.emit("Merge cancelled")
                    return
                self.message.emit(f"Adding {i}/{total}: {path}")
                reader = pypdf.PdfReader(path)
                for page in reader.pages:
                    writer.add_page(page)
                self.progress.emit(int(i * 100 / total))
            with open(self.output_path, "wb") as f:
                writer.write(f)
            self.finished_ok.emit(self.output_path)
        except Exception as e:
            self.failed.emit(str(e))


class ImageExportWorker(BaseWorker):
    """Render PDF pages to image files (PNG / JPG)."""

    def __init__(self, pdf_path: str, out_folder: str, fmt: str = "png", dpi: int = 150,
                 pages: list | None = None):
        super().__init__()
        self.pdf_path = pdf_path
        self.out_folder = out_folder
        self.fmt = fmt.lower()
        self.dpi = dpi
        self.pages = pages

    def run(self):
        try:
            import fitz
            import os
            doc = fitz.open(self.pdf_path)
            page_indices = self.pages if self.pages else list(range(len(doc)))
            total = len(page_indices)
            os.makedirs(self.out_folder, exist_ok=True)
            zoom = self.dpi / 72.0
            mat = fitz.Matrix(zoom, zoom)
            for i, idx in enumerate(page_indices, 1):
                if self.is_cancelled():
                    doc.close()
                    self.failed.emit("Export cancelled")
                    return
                page = doc.load_page(idx)
                pix = page.get_pixmap(matrix=mat, alpha=False)
                ext = "jpg" if self.fmt in ("jpg", "jpeg") else "png"
                out = os.path.join(self.out_folder, f"page_{idx + 1:04d}.{ext}")
                pix.save(out)
                self.progress.emit(int(i * 100 / total))
                self.message.emit(f"Exported page {idx + 1}")
            doc.close()
            self.finished_ok.emit(self.out_folder)
        except Exception as e:
            self.failed.emit(str(e))


class PdfToWordWorker(BaseWorker):
    """Convert a PDF to a Word .docx file in the background."""

    def __init__(self, pdf_path: str, output_path: str):
        super().__init__()
        self.pdf_path = pdf_path
        self.output_path = output_path

    def run(self):
        try:
            from core.converter import Converter

            def cb(done: int, total: int):
                if self.is_cancelled():
                    raise RuntimeError("PDF to Word conversion cancelled")
                self.progress.emit(int(done * 100 / max(total, 1)))
                self.message.emit(f"Converting page {done}/{total}")

            ok = Converter.pdf_to_docx(self.pdf_path, self.output_path, progress_cb=cb)
            if not ok:
                self.failed.emit("python-docx is not installed. Please install requirements again.")
                return
            self.finished_ok.emit(self.output_path)
        except Exception as e:
            self.failed.emit(str(e))


class CompressWorker(BaseWorker):
    """Compress a PDF in the background."""

    def __init__(self, input_path: str, output_path: str,
                 target_dpi: int = 100, jpeg_quality: int = 70,
                 options: dict | None = None):
        super().__init__()
        self.input_path = input_path
        self.output_path = output_path
        self.target_dpi = target_dpi
        self.jpeg_quality = jpeg_quality
        self.options = options or {}
        self.stats = None

    def run(self):
        try:
            from core.compressor import compress_pdf

            def cb(pct, msg):
                if self.is_cancelled():
                    raise RuntimeError("Cancelled by user")
                self.progress.emit(int(pct))
                self.message.emit(msg)

            self.stats = compress_pdf(
                self.input_path, self.output_path,
                target_dpi=self.target_dpi,
                jpeg_quality=self.jpeg_quality,
                progress_cb=cb,
                options=self.options,
            )
            self.finished_ok.emit(self.output_path)
        except Exception as e:
            self.failed.emit(str(e))
