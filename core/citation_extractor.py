"""Citation and reference extractor.

Pulls in-text citations (like [1], [2-4], (Smith, 2020)) and the reference
list / bibliography out of a PDF. Fully offline; this uses plain text pattern
matching, so it works without any web service.

This module also contains a best-effort citation-link builder. Many academic
PDFs do not contain clickable citation links. The builder detects numbered
in-text citations such as [1], [2, 3], [4-6] and creates internal PDF links to
the matching numbered reference entry in the References section.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable

import fitz


# In-text numeric citations like [1], [2,3], [4-6]
_NUM_CITE = re.compile(r"\[(\d{1,3}(?:\s*[-,–]\s*\d{1,3}|\s*,\s*\d{1,3})*)\]")
# Author-year citations like (Smith, 2020) or (Smith et al., 2019)
_AUTHOR_YEAR = re.compile(r"\(([A-Z][A-Za-z]+(?:\s+et al\.?)?(?:\s*,\s*\d{4}[a-z]?))\)")
# Reference-list line starts like "[1] ..." or "1. ..."
_REF_LINE_BRACKET = re.compile(r"^\s*\[(\d{1,3})\]\s+(.*)")
_REF_LINE_DOT = re.compile(r"^\s*(\d{1,3})\.\s+(.*)")

_HEADINGS = ("references", "bibliography", "works cited", "literature cited")


@dataclass
class ReferenceTarget:
    number: int
    page_index: int
    rect: fitz.Rect
    text: str


def _full_text(doc) -> str:
    parts = []
    for page in doc:
        parts.append(page.get_text("text"))
    return "\n".join(parts)


def _line_text(line: dict) -> str:
    return "".join(span.get("text", "") for span in line.get("spans", []))


def _iter_text_lines(doc) -> Iterable[tuple[int, fitz.Rect, str]]:
    """Yield (page_index, line_rect, line_text) for visible text lines."""
    for page_index in range(doc.page_count):
        page = doc[page_index]
        try:
            data = page.get_text("dict")
        except Exception:
            continue
        for block in data.get("blocks", []):
            if block.get("type") != 0:
                continue
            for line in block.get("lines", []):
                text = _line_text(line).strip()
                if not text:
                    continue
                try:
                    rect = fitz.Rect(line.get("bbox"))
                except Exception:
                    continue
                yield page_index, rect, text


def _find_reference_heading(doc) -> tuple[int, float] | None:
    """Return (page_index, y_after_heading) for the last References heading."""
    found: tuple[int, float] | None = None
    for page_index, rect, text in _iter_text_lines(doc):
        low = " ".join(text.strip().lower().split())
        if low in _HEADINGS or (len(low) <= 28 and any(low.startswith(h) for h in _HEADINGS)):
            found = (page_index, float(rect.y1))
    return found


def _parse_numbers(expr: str) -> list[int]:
    """Turn '1, 3-5' into [1, 3, 4, 5]."""
    nums: list[int] = []
    for part in re.split(r"\s*,\s*", expr.strip()):
        if not part:
            continue
        if "-" in part or "–" in part:
            bits = re.split(r"[-–]", part, maxsplit=1)
            try:
                a, b = int(bits[0]), int(bits[1])
            except Exception:
                continue
            if a <= b:
                nums.extend(range(a, b + 1))
            else:
                nums.extend(range(a, b - 1, -1))
        else:
            try:
                nums.append(int(part))
            except Exception:
                pass
    # preserve order, remove duplicates
    out: list[int] = []
    seen: set[int] = set()
    for n in nums:
        if n not in seen:
            seen.add(n)
            out.append(n)
    return out


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


def find_numbered_reference_targets(doc) -> dict[int, ReferenceTarget]:
    """Return mapping reference number -> target location in the reference list.

    This is intentionally conservative. It only links references that clearly
    start with '[n]' or 'n.' after a References/Bibliography heading.
    """
    heading = _find_reference_heading(doc)
    if not heading:
        return {}
    start_page, start_y = heading
    targets: dict[int, ReferenceTarget] = {}
    for page_index, rect, text in _iter_text_lines(doc):
        if page_index < start_page:
            continue
        if page_index == start_page and rect.y0 < start_y:
            continue
        mb = _REF_LINE_BRACKET.match(text)
        md = _REF_LINE_DOT.match(text)
        match = mb or md
        if not match:
            continue
        try:
            number = int(match.group(1))
        except Exception:
            continue
        if number not in targets:
            # Give the destination a little margin so the clicked reference is
            # visible near the top of the viewport.
            dest_rect = fitz.Rect(rect)
            dest_rect.y0 = max(0, dest_rect.y0 - 8)
            targets[number] = ReferenceTarget(number, page_index, dest_rect, text)
    return targets


def _rect_overlaps_existing_link(page, rect: fitz.Rect) -> bool:
    try:
        links = page.get_links() or []
    except Exception:
        return False
    probe = fitz.Rect(rect)
    for lk in links:
        other = lk.get("from")
        if other is None:
            continue
        try:
            if fitz.Rect(other).intersects(probe):
                return True
        except Exception:
            pass
    return False


def _citation_target_number(expr: str, targets: dict[int, ReferenceTarget]) -> int | None:
    for n in _parse_numbers(expr):
        if n in targets:
            return n
    return None


def build_missing_citation_links(doc, max_links: int = 2000) -> dict:
    """Create missing internal links from in-text numeric citations to references.

    Returns a summary dict:
        {'created': int, 'references': int, 'skipped_existing': int,
         'reason': str}

    Limitations: this cannot reliably link author-year citations yet. It is
    designed for common numbered academic citation styles like [1], [2,3], and
    [4-6].
    """
    targets = find_numbered_reference_targets(doc)
    if not targets:
        return {"created": 0, "references": 0, "skipped_existing": 0,
                "reason": "No numbered reference list detected."}

    # Do not scan the actual reference pages as normal body text; otherwise the
    # reference numbers themselves can become links back to the same place.
    first_ref_page = min(t.page_index for t in targets.values())
    created = 0
    skipped_existing = 0

    for page_index in range(min(first_ref_page + 1, doc.page_count)):
        page = doc[page_index]
        try:
            text = page.get_text("text")
        except Exception:
            continue
        tokens: list[tuple[str, int]] = []
        seen: set[str] = set()
        for m in _NUM_CITE.finditer(text):
            token = m.group(0)
            if token in seen:
                continue
            target_no = _citation_target_number(m.group(1), targets)
            if target_no is None:
                continue
            seen.add(token)
            tokens.append((token, target_no))

        for token, target_no in tokens:
            try:
                rects = page.search_for(token)
            except Exception:
                rects = []
            for rect in rects:
                # On a page that also contains the reference heading, avoid
                # linking text below the reference entry area.
                target = targets[target_no]
                if page_index == first_ref_page and rect.y0 >= target.rect.y0 - 2:
                    continue
                if _rect_overlaps_existing_link(page, rect):
                    skipped_existing += 1
                    continue
                try:
                    page.insert_link({
                        "kind": fitz.LINK_GOTO,
                        "from": fitz.Rect(rect),
                        "page": target.page_index,
                        "to": fitz.Point(target.rect.x0, target.rect.y0),
                    })
                    created += 1
                    if created >= max_links:
                        return {"created": created, "references": len(targets),
                                "skipped_existing": skipped_existing,
                                "reason": "Reached safety link limit."}
                except Exception:
                    continue

    reason = "OK" if created else "No missing numbered citation links found."
    return {"created": created, "references": len(targets),
            "skipped_existing": skipped_existing, "reason": reason}


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
