"""Research Library — a personal database of PDF papers.

Stores papers (with extracted metadata), user collections/folders, tags,
favorites, and recent opens. Persisted to a JSON file so the library survives
restarts. Fully offline.

A "paper" is identified by its file path. Metadata (title, author, year,
keywords, DOI) is auto-extracted from the PDF when imported, and can be edited.
"""

import os
import re
import json
import uuid
from datetime import datetime
from urllib.parse import quote


def library_path() -> str:
    """Where the library database file lives (per user)."""
    base = os.path.join(os.path.expanduser("~"), ".masumpdf")
    os.makedirs(base, exist_ok=True)
    return os.path.join(base, "library.json")


_DOI = re.compile(r"\b10\.\d{4,9}/[-._;()/:A-Za-z0-9]+\b")
_YEAR = re.compile(r"\b(19|20)\d{2}\b")
_WEB_PREFIX = "weblink::"


def extract_metadata(pdf_path: str) -> dict:
    """Pull title, author, year, doi, and a short preview from a PDF.
    Best-effort and offline — uses the PDF's own metadata first, then text."""
    import fitz
    info = {"title": "", "author": "", "year": "", "doi": "",
            "keywords": "", "preview": "", "url": ""}
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
        # title fallback: many PDFs report unhelpful metadata like
        # "untitled". Use the first meaningful line from page 1 instead.
        bad_titles = {"", "untitled", "untitled document", "document"}
        if info["title"].strip().lower() in bad_titles and first:
            for line in first.splitlines():
                s = line.strip()
                if len(s) > 8 and not s.lower().startswith(("doi:", "abstract")):
                    info["title"] = s[:200]
                    break
    finally:
        doc.close()
    if not info["title"]:
        info["title"] = os.path.splitext(os.path.basename(pdf_path))[0]
    return info


def normalize_web_link(url: str) -> str:
    """Normalize a user-entered web link while keeping empty strings empty."""
    url = (url or "").strip()
    if not url:
        return ""
    if url.startswith("doi:"):
        return doi_to_url(url[4:].strip())
    if url.startswith("10."):
        return doi_to_url(url)
    if not re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", url):
        url = "https://" + url
    return url


def doi_to_url(doi: str) -> str:
    doi = (doi or "").strip().removeprefix("doi:").strip()
    if not doi:
        return ""
    if doi.startswith("http://") or doi.startswith("https://"):
        return doi
    return "https://doi.org/" + quote(doi, safe="/._;():-")


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
                "url": meta.get("url", ""),
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

    def add_web_resource(self, title: str, url: str, about: str = "",
                         tags: list | None = None, collection: str | None = None) -> str:
        """Add a manual web resource to the research library.

        This is not limited to papers: users can save datasets, project pages,
        publisher pages, GitHub repositories, lab websites, tutorials, videos,
        protocols, or any research-related web page with a short note about
        what the link is for. Returns the internal resource id.
        """
        title = (title or "").strip()
        url = normalize_web_link(url)
        about = (about or "").strip()
        if not title:
            title = url or "Untitled web resource"
        rid = _WEB_PREFIX + uuid.uuid4().hex[:12]
        self.papers[rid] = {
            "path": rid,
            "filename": "",
            "entry_type": "web",
            "title": title,
            "author": "",
            "year": "",
            "doi": "",
            "url": url,
            "about": about,
            "keywords": about,
            "preview": about,
            "tags": [t.strip() for t in (tags or []) if str(t).strip()],
            "favorite": False,
            "added": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "last_opened": "",
        }
        if collection:
            self.add_to_collection(collection, rid)
        self.save()
        return rid

    def update_web_resource(self, resource_id: str, title: str | None = None,
                            url: str | None = None, about: str | None = None,
                            tags: list | None = None):
        if resource_id not in self.papers:
            return
        item = self.papers[resource_id]
        if item.get("entry_type") != "web" and not str(resource_id).startswith(_WEB_PREFIX):
            return
        if title is not None:
            item["title"] = (title or "").strip() or item.get("title", "Untitled web resource")
        if url is not None:
            item["url"] = normalize_web_link(url)
        if about is not None:
            item["about"] = (about or "").strip()
            item["keywords"] = item["about"]
            item["preview"] = item["about"]
        if tags is not None:
            item["tags"] = [t.strip() for t in tags if str(t).strip()]
        self.save()

    def is_web_resource(self, item_or_path) -> bool:
        if isinstance(item_or_path, dict):
            return item_or_path.get("entry_type") == "web" or str(item_or_path.get("path", "")).startswith(_WEB_PREFIX)
        return str(item_or_path).startswith(_WEB_PREFIX)

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
        if not self.is_web_resource(pdf_path):
            pdf_path = os.path.abspath(pdf_path)
        if pdf_path in self.papers:
            self.papers[pdf_path]["last_opened"] = \
                datetime.now().strftime("%Y-%m-%d %H:%M")
            self.save()

    def set_web_link(self, pdf_path: str, url: str):
        """Save a paper's web page, DOI URL, publisher page, or project link."""
        if pdf_path in self.papers:
            self.papers[pdf_path]["url"] = normalize_web_link(url)
            self.save()

    def web_link_for(self, pdf_path: str) -> str:
        """Return the best web link for a paper: manual link first, then DOI."""
        p = self.papers.get(pdf_path, {})
        url = normalize_web_link(p.get("url", ""))
        if url:
            return url
        doi = (p.get("doi") or "").strip()
        if doi:
            return doi_to_url(doi)
        return ""

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
                    str(p.get("url", "")), str(p.get("about", "")),
                    str(p.get("entry_type", "")), str(p.get("year", "")),
                    " ".join(p.get("tags", [])),
                    str(p.get("filename", "")),
                ]).lower()
                if term not in blob:
                    continue
            results.append(p)
        return results

    def related(self, pdf_path: str) -> list:
        """Papers sharing a tag or an author with the given one."""
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
