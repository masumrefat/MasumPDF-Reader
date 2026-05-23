"""Core (non-UI) PDF logic."""

from .pdf_document import PDFDocument
from .annotation_manager import AnnotationManager
from .page_manager import PageManager
from .converter import Converter
from .security import SecurityManager
from .metadata import MetadataManager

__all__ = [
    "PDFDocument", "AnnotationManager", "PageManager",
    "Converter", "SecurityManager", "MetadataManager",
]
