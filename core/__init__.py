"""Core PDF logic package.

This package keeps imports lightweight so non-GUI modules such as
``core.research_library`` can be tested without importing PySide6 first.
Import concrete classes from their modules, for example:
    from core.pdf_document import PDFDocument
"""

__all__ = [
    "PDFDocument", "AnnotationManager", "PageManager",
    "Converter", "SecurityManager", "MetadataManager",
]


def __getattr__(name):
    if name == "PDFDocument":
        from .pdf_document import PDFDocument
        return PDFDocument
    if name == "AnnotationManager":
        from .annotation_manager import AnnotationManager
        return AnnotationManager
    if name == "PageManager":
        from .page_manager import PageManager
        return PageManager
    if name == "Converter":
        from .converter import Converter
        return Converter
    if name == "SecurityManager":
        from .security import SecurityManager
        return SecurityManager
    if name == "MetadataManager":
        from .metadata import MetadataManager
        return MetadataManager
    raise AttributeError(name)
