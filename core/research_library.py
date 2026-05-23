"""Research Library — a personal database of PDF papers.

Stores papers (with extracted metadata), user collections/folders, tags,
favorites, and recent opens. Persisted to a JSON file so the library survives
restarts. No AI, fully offline.

A "paper" is identified by its file path. Metadata (title, author, year,
keywords, DOI) is auto-extracted from the PDF when imported, and can be edited.
"""

import os
import re
import json
from datetime import datetime


def library_path() -> str:
    """Where the library database file lives (per user)."""
    base = os.path.join(os.path.expanduser("~"), ".masumpdf")
    os.makedirs(base, exist_ok=True)
    return os.path.join(base, "library.json")


_DOI = re.compile(r"\b10\.\d{4,9}/[-._;()/:A-Za-z0-9]+\b")
_YEAR = re.compile(r"\b(19|20)\d{2}\b")


def extract_metadata(pdf_path: str) -> dict:
    """Pull title, author, year, doi, and a short preview from a PDF.
    Best-effort and offline — uses the PDF's own metadata first, then text."""
    import fitz
    info = {"title": "", "author": "", "year": "", "doi": "",
            "keywords": "", "preview": ""}
    try:
        doc = fitz.open(pdf_path)
    except Exception:
        return info
    try:
        md = doc.metadata or {}
        info["title"] = (md.get("title") or "").strip()
        info["author"] = (md.get("author") or "").strip()
        info["keywords"] = (md.get("keywords") or "").strip()
        # first page text for preview + fallback parsing
        first = doc[0].get_text("text") if doc.page_count else ""
        info["preview"] = " ".join(first.split())[:600]
        # DOI anywhere on first 2 pages
        scan = first
        if doc.page_count > 1:
            scan += "\n" + doc[1].get_text("text")
        m = _DOI.search(scan)
        if m:
            info["doi"] = m.group(0).rstrip(".,;)")
        # year: prefer metadata creation date, else first year on page 1
        cdate = md.get("creationDate") or ""
        ym = re.search(r"(19|20)\d{2}", cdate)
        if ym:
            info["year"] = ym.group(0)
        elif _YEAR.search(first):
            info["year"] = _YEAR.search(first).group(0)
        # title fallback: first non-empty line of page 1 if metadata empty
        if not info["title"] and first:
            for line in first.splitlines():
                s = line.strip()
                if len(s) > 8:
                    info["title"] = s[:200]
                    break
    finally:
        doc.close()
    if not info["title"]:
        info["title"] = os.path.splitext(os.path.basename(pdf_path))[0]
    return info


class ResearchLibrary:
    def __init__(self, path: str | None = None):
        self.path = path or library_path()
        # papers keyed by file path
        self.papers = {}     # path -> dict(metadata + tags + favorite + added + last_opened)
        self.collections = {}  # name -> [paths]
        self.load()

    # ---------- persistence ----------
    def load(self):
        if not os.path.exists(self.path):
            return
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.papers = data.get("papers", {})
            self.collections = data.get("collections", {})
        except Exception:
            self.papers, self.collections = {}, {}

    def save(self):
        try:
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump({"papers": self.papers,
                           "collections": self.collections}, f, indent=2)
        except Exception:
            pass

    # ---------- papers ----------
    def add_paper(self, pdf_path: str, collection: str | None = None) -> bool:
        """Import a PDF. Returns True if newly added, False if already there."""
        pdf_path = os.path.abspath(pdf_path)
        new = pdf_path not in self.papers
        if new:
            meta = extract_metadata(pdf_path)
            self.papers[pdf_path] = {
                "path": pdf_path,
                "filename": os.path.basename(pdf_path),
                "title": meta["title"],
                "author": meta["author"],
                "year": meta["year"],
                "doi": meta["doi"],
                "keywords": meta["keywords"],
                "preview": meta["preview"],
                "tags": [],
                "favorite": False,
                "added": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "last_opened": "",
            }
        if collection:
            self.add_to_collection(collection, pdf_path)
        self.save()
        return new

    def remove_paper(self, pdf_path: str):
        self.papers.pop(pdf_path, None)
        for name in list(self.collections):
            self.collections[name] = [p for p in self.collections[name]
                                      if p != pdf_path]
        self.save()

    def set_favorite(self, pdf_path: str, fav: bool):
        if pdf_path in self.papers:
            self.papers[pdf_path]["favorite"] = bool(fav)
            self.save()

    def mark_opened(self, pdf_path: str):
        pdf_path = os.path.abspath(pdf_path)
        if pdf_path in self.papers:
            self.papers[pdf_path]["last_opened"] = \
                datetime.now().strftime("%Y-%m-%d %H:%M")
            self.save()

    def set_tags(self, pdf_path: str, tags: list):
        if pdf_path in self.papers:
            self.papers[pdf_path]["tags"] = [t.strip() for t in tags if t.strip()]
            self.save()

    def update_field(self, pdf_path: str, field: str, value):
        if pdf_path in self.papers and field in self.papers[pdf_path]:
            self.papers[pdf_path][field] = value
            self.save()

    # ---------- collections ----------
    def create_collection(self, name: str):
        name = name.strip()
        if name and name not in self.collections:
            self.collections[name] = []
            self.save()

    def delete_collection(self, name: str):
        self.collections.pop(name, None)
        self.save()

    def add_to_collection(self, name: str, pdf_path: str):
        name = name.strip()
        if not name:
            return
        self.collections.setdefault(name, [])
        if pdf_path not in self.collections[name]:
            self.collections[name].append(pdf_path)
            self.save()

    def remove_from_collection(self, name: str, pdf_path: str):
        if name in self.collections:
            self.collections[name] = [p for p in self.collections[name]
                                      if p != pdf_path]
            self.save()

    # ---------- queries ----------
    def all_papers(self) -> list:
        return list(self.papers.values())

    def all_tags(self) -> list:
        tags = set()
        for p in self.papers.values():
            tags.update(p.get("tags", []))
        return sorted(tags)

    def favorites(self) -> list:
        return [p for p in self.papers.values() if p.get("favorite")]

    def recent(self, limit: int = 10) -> list:
        opened = [p for p in self.papers.values() if p.get("last_opened")]
        opened.sort(key=lambda p: p.get("last_opened", ""), reverse=True)
        return opened[:limit]

    def search(self, term: str = "", tag: str = "",
               collection: str = "", year: str = "") -> list:
        term = (term or "").strip().lower()
        results = []
        if collection and collection in self.collections:
            paths = set(self.collections[collection])
            pool = [p for p in self.papers.values() if p["path"] in paths]
        else:
            pool = list(self.papers.values())
        for p in pool:
            if tag and tag not in p.get("tags", []):
                continue
            if year and str(p.get("year", "")) != str(year):
                continue
            if term:
                blob = " ".join([
                    str(p.get("title", "")), str(p.get("author", "")),
                    str(p.get("keywords", "")), str(p.get("doi", "")),
                    str(p.get("year", "")), " ".join(p.get("tags", [])),
                    str(p.get("filename", "")),
                ]).lower()
                if term not in blob:
                    continue
            results.append(p)
        return results

    def related(self, pdf_path: str) -> list:
        """Papers sharing a tag or an author with the given one. (No AI —
        relatedness is by shared tags/authors, which is honest and useful.)"""
        base = self.papers.get(pdf_path)
        if not base:
            return []
        base_tags = set(base.get("tags", []))
        base_auth = set(re.split(r"[;,]", base.get("author", "").lower()))
        base_auth = {a.strip() for a in base_auth if a.strip()}
        out = []
        for p in self.papers.values():
            if p["path"] == pdf_path:
                continue
            tags = set(p.get("tags", []))
            auth = {a.strip() for a in re.split(r"[;,]", p.get("author", "").lower()) if a.strip()}
            if (base_tags & tags) or (base_auth & auth):
                out.append(p)
        return out
