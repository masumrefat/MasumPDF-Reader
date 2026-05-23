"""Citation and reference extractor.

Pulls in-text citations (like [1], [2-4], (Smith, 2020)) and the reference
list / bibliography out of a PDF. No internet or AI is used — this is plain
text pattern matching, so it works fully offline.

Intended for students and researchers reading academic papers.
"""

import re
import fitz


# In-text numeric citations like [1], [2,3], [4-6]
_NUM_CITE = re.compile(r"\[(\d{1,3}(?:\s*[-,–]\s*\d{1,3})*)\]")
# Author-year citations like (Smith, 2020) or (Smith et al., 2019)
_AUTHOR_YEAR = re.compile(r"\(([A-Z][A-Za-z]+(?:\s+et al\.?)?(?:\s*,\s*\d{4}[a-z]?))\)")
# Reference-list line starts like "[1] ..." or "1. ..."
_REF_LINE_BRACKET = re.compile(r"^\s*\[(\d{1,3})\]\s+(.*)")
_REF_LINE_DOT = re.compile(r"^\s*(\d{1,3})\.\s+(.*)")

_HEADINGS = ("references", "bibliography", "works cited", "literature cited")


def _full_text(doc) -> str:
    parts = []
    for page in doc:
        parts.append(page.get_text("text"))
    return "\n".join(parts)


def extract_intext_citations(doc) -> dict:
    """Return {'numeric': [...], 'author_year': [...]} of unique in-text
    citations found, in order of first appearance."""
    text = _full_text(doc)
    numeric, seen_n = [], set()
    for m in _NUM_CITE.finditer(text):
        token = "[" + m.group(1).replace(" ", "") + "]"
        if token not in seen_n:
            seen_n.add(token)
            numeric.append(token)
    author, seen_a = [], set()
    for m in _AUTHOR_YEAR.finditer(text):
        token = "(" + m.group(1).strip() + ")"
        if token not in seen_a:
            seen_a.add(token)
            author.append(token)
    return {"numeric": numeric, "author_year": author}


def extract_reference_list(doc) -> list:
    """Find the References / Bibliography section and return its entries
    as a list of strings. Returns [] if no reference section is found."""
    # Find the page + line where the reference heading appears (search from end)
    lines = []
    for page in doc:
        for ln in page.get_text("text").splitlines():
            lines.append(ln)

    start = -1
    for i in range(len(lines) - 1, -1, -1):
        low = lines[i].strip().lower()
        # heading is short and matches one of the keywords
        if low in _HEADINGS or any(low == h for h in _HEADINGS):
            start = i + 1
            break
        if len(low) <= 20 and any(low.startswith(h) for h in _HEADINGS):
            start = i + 1
            break
    if start < 0:
        return []

    # Collect entries after the heading. Numbered entries ([1] or 1.) start
    # a new reference; otherwise lines wrap onto the previous entry.
    entries = []
    current = ""
    for ln in lines[start:]:
        raw = ln.rstrip()
        if not raw.strip():
            continue
        mb = _REF_LINE_BRACKET.match(raw)
        md = _REF_LINE_DOT.match(raw)
        if mb:
            if current:
                entries.append(current.strip())
            current = f"[{mb.group(1)}] {mb.group(2)}"
        elif md:
            if current:
                entries.append(current.strip())
            current = f"{md.group(1)}. {md.group(2)}"
        else:
            # continuation of the previous entry
            if current:
                current += " " + raw.strip()
    if current:
        entries.append(current.strip())
    return entries


def extract_all(pdf_path: str) -> dict:
    """Convenience: open the file and return everything found.

    Returns {
      'numeric': [...], 'author_year': [...],
      'references': [...], 'reference_count': n
    }
    """
    doc = fitz.open(pdf_path)
    try:
        intext = extract_intext_citations(doc)
        refs = extract_reference_list(doc)
    finally:
        doc.close()
    return {
        "numeric": intext["numeric"],
        "author_year": intext["author_year"],
        "references": refs,
        "reference_count": len(refs),
    }
