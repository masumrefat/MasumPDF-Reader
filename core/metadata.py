"""Read and edit PDF metadata."""

import fitz


class MetadataManager:

    READABLE_KEYS = ("title", "author", "subject", "keywords", "creator",
                     "producer", "creationDate", "modDate")

    @staticmethod
    def read(path: str) -> dict:
        doc = fitz.open(path)
        md = dict(doc.metadata or {})
        doc.close()
        return md

    @staticmethod
    def write(path: str, output_path: str, fields: dict):
        """Update metadata and save to output_path."""
        doc = fitz.open(path)
        current = dict(doc.metadata or {})
        current.update(fields)
        doc.set_metadata(current)
        doc.save(output_path, garbage=4, deflate=True)
        doc.close()
