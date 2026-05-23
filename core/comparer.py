"""PDF comparison.

Reads text from two PDFs page by page and produces a textual diff.
Pages are paired by index (page 1 vs page 1, etc). Pages that only
exist in one document are reported as added/removed.

This is a text-level diff. Layout, fonts, and images are not compared.
"""

import difflib
import fitz


def _page_text(doc, idx):
    if idx < 0 or idx >= doc.page_count:
        return None
    try:
        return doc[idx].get_text("text") or ""
    except Exception:
        return ""


def compare_pdfs(old_path: str, new_path: str) -> list:
    """Return a list of per-page comparison dicts.

    Each dict has:
        page (1-indexed),
        status: 'same' | 'changed' | 'old_only' | 'new_only',
        added_lines: int, removed_lines: int,
        diff_html: HTML string for display.
    """
    old = fitz.open(old_path)
    new = fitz.open(new_path)
    max_pages = max(old.page_count, new.page_count)

    results = []
    for i in range(max_pages):
        old_text = _page_text(old, i)
        new_text = _page_text(new, i)

        if old_text is None and new_text is not None:
            results.append({
                "page": i + 1, "status": "new_only",
                "added_lines": len(new_text.splitlines()),
                "removed_lines": 0,
                "diff_html": _wrap_html("[Page added in new file]\n\n" + new_text, "add"),
            })
            continue
        if new_text is None and old_text is not None:
            results.append({
                "page": i + 1, "status": "old_only",
                "added_lines": 0,
                "removed_lines": len(old_text.splitlines()),
                "diff_html": _wrap_html("[Page removed]\n\n" + old_text, "remove"),
            })
            continue
        if old_text == new_text:
            results.append({
                "page": i + 1, "status": "same",
                "added_lines": 0, "removed_lines": 0,
                "diff_html": _wrap_html("(no text differences)", "same"),
            })
            continue

        # changed: build a line-by-line diff
        old_lines = old_text.splitlines()
        new_lines = new_text.splitlines()
        differ = difflib.unified_diff(old_lines, new_lines,
                                      fromfile=f"old page {i + 1}",
                                      tofile=f"new page {i + 1}",
                                      lineterm="")
        added = removed = 0
        html_lines = []
        for line in differ:
            esc = (line.replace("&", "&amp;")
                       .replace("<", "&lt;")
                       .replace(">", "&gt;"))
            if line.startswith("+++") or line.startswith("---"):
                html_lines.append(f'<div style="color:#888">{esc}</div>')
            elif line.startswith("@@"):
                html_lines.append(f'<div style="color:#0066cc;background:#eaf2ff">{esc}</div>')
            elif line.startswith("+"):
                added += 1
                html_lines.append(f'<div style="background:#e7f7e7;color:#0a5a0a">{esc}</div>')
            elif line.startswith("-"):
                removed += 1
                html_lines.append(f'<div style="background:#fdecec;color:#8a1a1a">{esc}</div>')
            else:
                html_lines.append(f'<div>{esc}</div>')
        results.append({
            "page": i + 1, "status": "changed",
            "added_lines": added, "removed_lines": removed,
            "diff_html": "<div style='font-family:monospace;font-size:12px'>"
                         + "".join(html_lines) + "</div>",
        })

    old.close()
    new.close()
    return results


def _wrap_html(text: str, kind: str) -> str:
    text = (text.replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;"))
    if kind == "add":
        return (f"<div style='font-family:monospace;font-size:12px;"
                f"background:#e7f7e7;color:#0a5a0a;white-space:pre-wrap'>{text}</div>")
    if kind == "remove":
        return (f"<div style='font-family:monospace;font-size:12px;"
                f"background:#fdecec;color:#8a1a1a;white-space:pre-wrap'>{text}</div>")
    return (f"<div style='font-family:monospace;font-size:12px;"
            f"color:#666;white-space:pre-wrap'>{text}</div>")


# =============================================================================
# PDF comparison REPORT generation
# =============================================================================
import os
from datetime import datetime


def _normalize_word(w: str, ignore_case: bool, ignore_quotes: bool) -> str:
    """Normalize a word for comparison (matches the reference viewer's
    ignore-case / ignore-quotes options)."""
    if ignore_case:
        w = w.lower()
    if ignore_quotes:
        # unify curly and straight quotes
        for ch in ("\u2018", "\u2019", "\u201b", "\u2032", "`", "\u00b4"):
            w = w.replace(ch, "'")
        for ch in ("\u201c", "\u201d", "\u201e", "\u2033"):
            w = w.replace(ch, '"')
    return w


def global_word_diff(old_doc, new_doc,
                     ignore_case: bool = False, ignore_quotes: bool = False):
    """Diff the WHOLE document as one continuous word stream.

    This is the key to a sane comparison: when you remove or add content,
    everything after it reflows onto different pages. Comparing page-by-page
    then flags entire pages as 'changed' even though the words are identical
    and merely shifted. By diffing the whole document at once, only the words
    that were truly added or removed get flagged; everything else is matched.

    Returns two dicts keyed by page index:
        old_marks[page] = list of (word_tuple, color)
        new_marks[page] = list of (word_tuple, color)
    where color is:
        "red"   -> removed (only in OLD)
        "green" -> added   (only in NEW)
        "blue"  -> identical text that moved to a different page (reflow)
        None    -> unchanged and on the same page (no highlight)
    word_tuple is (page, x0, y0, x1, y1, text).
    """
    old_words = []
    for pno in range(old_doc.page_count):
        for w in old_doc[pno].get_text("words"):
            old_words.append((pno,) + tuple(w[:4]) + (w[4],))
    new_words = []
    for pno in range(new_doc.page_count):
        for w in new_doc[pno].get_text("words"):
            new_words.append((pno,) + tuple(w[:4]) + (w[4],))

    old_seq = [_normalize_word(w[5], ignore_case, ignore_quotes) for w in old_words]
    new_seq = [_normalize_word(w[5], ignore_case, ignore_quotes) for w in new_words]

    matcher = difflib.SequenceMatcher(None, old_seq, new_seq, autojunk=False)

    from collections import defaultdict
    old_marks = defaultdict(list)
    new_marks = defaultdict(list)

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            for k in range(i2 - i1):
                ow = old_words[i1 + k]
                nw = new_words[j1 + k]
                if ow[0] != nw[0]:   # moved to a different page -> blue
                    old_marks[ow[0]].append((ow, "blue"))
                    new_marks[nw[0]].append((nw, "blue"))
        elif tag == "delete":
            for k in range(i1, i2):
                ow = old_words[k]
                old_marks[ow[0]].append((ow, "red"))
        elif tag == "insert":
            for k in range(j1, j2):
                nw = new_words[k]
                new_marks[nw[0]].append((nw, "green"))
        elif tag == "replace":
            for k in range(i1, i2):
                ow = old_words[k]
                old_marks[ow[0]].append((ow, "red"))
            for k in range(j1, j2):
                nw = new_words[k]
                new_marks[nw[0]].append((nw, "green"))

    return dict(old_marks), dict(new_marks)


def _word_diff(old_words, new_words,
               ignore_case: bool = False, ignore_quotes: bool = False):
    """Precise word-level diff. Returns (removed_idx_in_old, added_idx_in_new).

    Key fix: autojunk=False so that common words (which difflib would
    otherwise treat as 'junk' on long pages) still act as anchors. Without
    this, a single edit on a dense page can cascade into the whole page
    being marked changed. We also normalize words the same way the diff
    statistics do, so a pure case/quote change isn't flagged when the user
    asked to ignore it.
    """
    old_seq = [_normalize_word(w[4], ignore_case, ignore_quotes) for w in old_words]
    new_seq = [_normalize_word(w[4], ignore_case, ignore_quotes) for w in new_words]
    matcher = difflib.SequenceMatcher(None, old_seq, new_seq, autojunk=False)
    removed, added = [], []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "delete":
            removed.extend(range(i1, i2))
        elif tag == "insert":
            added.extend(range(j1, j2))
        elif tag == "replace":
            removed.extend(range(i1, i2))
            added.extend(range(j1, j2))
    return removed, added




def page_changelog(old_words, new_words,
                   ignore_case: bool = False,
                   ignore_quotes: bool = False) -> list[dict]:
    """Produce a structured list of changes for one page.

    Each change is a dict:
        {"type": "replace"|"insert"|"delete",
         "old": "old text",  "new": "new text"}
    Contiguous word runs are grouped so changes read naturally
    (e.g. a replaced phrase shows the whole old phrase -> new phrase).
    """
    old_seq = [_normalize_word(w[4], ignore_case, ignore_quotes) for w in old_words]
    new_seq = [_normalize_word(w[4], ignore_case, ignore_quotes) for w in new_words]
    old_raw = [w[4] for w in old_words]
    new_raw = [w[4] for w in new_words]

    matcher = difflib.SequenceMatcher(None, old_seq, new_seq, autojunk=False)
    changes = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue
        old_text = " ".join(old_raw[i1:i2]).strip()
        new_text = " ".join(new_raw[j1:j2]).strip()
        if tag == "replace":
            changes.append({"type": "replace", "old": old_text, "new": new_text})
        elif tag == "delete":
            changes.append({"type": "delete", "old": old_text, "new": ""})
        elif tag == "insert":
            changes.append({"type": "insert", "old": "", "new": new_text})
    return changes


def build_full_changelog(old_path: str, new_path: str,
                         ignore_case: bool = False,
                         ignore_quotes: bool = False) -> dict:
    """Build a complete change report across all pages.

    Returns:
        {
          "pages": [ {"page": 1, "status": "...", "changes": [...] }, ... ],
          "totals": {"replaced": n, "inserted": n, "deleted": n,
                     "added_words": n, "removed_words": n,
                     "changed_pages": n},
        }
    """
    old_doc = fitz.open(old_path)
    new_doc = fitz.open(new_path)
    max_pages = max(old_doc.page_count, new_doc.page_count)

    pages = []
    totals = {"replaced": 0, "inserted": 0, "deleted": 0,
              "added_words": 0, "removed_words": 0, "changed_pages": 0}

    for i in range(max_pages):
        old_words = old_doc[i].get_text("words") if i < old_doc.page_count else []
        new_words = new_doc[i].get_text("words") if i < new_doc.page_count else []

        if i >= old_doc.page_count:
            status = "new_only"
        elif i >= new_doc.page_count:
            status = "old_only"
        else:
            status = None  # decided below

        changes = page_changelog(old_words, new_words,
                                 ignore_case, ignore_quotes)
        if status is None:
            status = "changed" if changes else "same"

        for c in changes:
            if c["type"] == "replace":
                totals["replaced"] += 1
                totals["removed_words"] += len(c["old"].split())
                totals["added_words"] += len(c["new"].split())
            elif c["type"] == "insert":
                totals["inserted"] += 1
                totals["added_words"] += len(c["new"].split())
            elif c["type"] == "delete":
                totals["deleted"] += 1
                totals["removed_words"] += len(c["old"].split())

        if status != "same":
            totals["changed_pages"] += 1

        pages.append({"page": i + 1, "status": status, "changes": changes})

    old_doc.close()
    new_doc.close()
    return {"pages": pages, "totals": totals}


def _human_size(n):
    if n < 1024: return f"{n} B"
    if n < 1024 ** 2: return f"{n/1024:.1f} KB"
    return f"{n / (1024**2):.2f} MB"


def visual_region_diff(old_page, new_page, render_dpi: int = 110,
                       grid: int = 36, threshold: float = 0.04):
    """Find visual (non-text) differences between two pages — e.g. a swapped
    figure, chart, photo, or logo.

    Renders both pages, splits into a grid of cells, and flags cells whose
    pixels differ beyond `threshold`. Cells that are mostly text are skipped
    because the word diff already handles text. Returns a list of fitz.Rect
    (in PDF points on the NEW page) marking changed visual regions.
    """
    try:
        import numpy as np
    except Exception:
        return []

    pm_old = old_page.get_pixmap(dpi=render_dpi)
    pm_new = new_page.get_pixmap(dpi=render_dpi)
    h = min(pm_old.height, pm_new.height)
    w = min(pm_old.width, pm_new.width)
    if h == 0 or w == 0:
        return []

    def to_array(pm):
        arr = np.frombuffer(pm.samples, dtype=np.uint8)
        arr = arr.reshape(pm.height, pm.width, pm.n)
        return arr[:h, :w, :3].astype(np.int16)

    a = to_array(pm_old)
    b = to_array(pm_new)
    diff = np.abs(a - b).sum(axis=2)

    scale = render_dpi / 72.0
    text_mask = np.zeros((h, w), dtype=bool)
    try:
        for wd in new_page.get_text("words"):
            x0, y0, x1, y1 = wd[:4]
            px0, py0 = int(x0 * scale), int(y0 * scale)
            px1, py1 = int(x1 * scale), int(y1 * scale)
            px0 = max(0, min(w - 1, px0)); px1 = max(0, min(w, px1))
            py0 = max(0, min(h - 1, py0)); py1 = max(0, min(h, py1))
            if px1 > px0 and py1 > py0:
                text_mask[py0:py1, px0:px1] = True
    except Exception:
        pass

    cell_h = max(1, h // grid)
    cell_w = max(1, w // grid)
    changed_cells = []
    for gy in range(0, h, cell_h):
        for gx in range(0, w, cell_w):
            cell_diff = diff[gy:gy + cell_h, gx:gx + cell_w]
            cell_text = text_mask[gy:gy + cell_h, gx:gx + cell_w]
            if cell_diff.size == 0:
                continue
            non_text = ~cell_text
            denom = max(1, int(non_text.sum()))
            changed = int(((cell_diff > 40) & non_text).sum())
            if changed / denom > threshold and denom > (cell_diff.size * 0.2):
                changed_cells.append((gx, gy, gx + cell_w, gy + cell_h))

    if not changed_cells:
        return []

    rects_px = _merge_cells(changed_cells, cell_w, cell_h)
    rects_pt = []
    for (x0, y0, x1, y1) in rects_px:
        rects_pt.append(fitz.Rect(x0 / scale, y0 / scale,
                                  x1 / scale, y1 / scale))
    return rects_pt


def _merge_cells(cells, cw, ch):
    """Greedily merge touching/overlapping cells into bounding rectangles."""
    rects = [list(c) for c in cells]
    merged = True
    while merged:
        merged = False
        out = []
        while rects:
            r = rects.pop()
            grew = True
            while grew:
                grew = False
                keep = []
                for o in rects:
                    if (r[0] - cw <= o[2] and o[0] - cw <= r[2] and
                            r[1] - ch <= o[3] and o[1] - ch <= r[3]):
                        r[0] = min(r[0], o[0]); r[1] = min(r[1], o[1])
                        r[2] = max(r[2], o[2]); r[3] = max(r[3], o[3])
                        grew = True; merged = True
                    else:
                        keep.append(o)
                rects = keep
            out.append(r)
        rects = out
    return [tuple(r) for r in rects]


def generate_compare_report(old_path: str,
                            new_path: str,
                            output_path: str,
                            render_dpi: int = 110,
                            author: str = "",
                            ignore_case: bool = False,
                            ignore_quotes: bool = False,
                            include_changelog: bool = True,
                            report_mode: str = "both",
                            all_pages: bool = True,
                            show_moved: bool = True,
                            compare_images: bool = True) -> dict:
    """Build a professional PDF comparison report.

    report_mode:
      - "both"        cover + detailed changes + side-by-side visual (default)
      - "changes"     cover + detailed text changes only (clean, easy to read)
      - "visual"      cover + side-by-side visual only

    Layout:
      - Cover page: file stats + summary + color legend.
      - Detailed change log pages: every replace / insert / delete listed
        as old text -> new text (when include_changelog is True).
      - One landscape page per changed page, with the OLD page on the
        left and the NEW page on the right, with word-level changes
        highlighted (red boxes for removed, green for added).
      - Identical pages are skipped (mentioned only in the cover summary).

    Returns: {"report_path", "pages", "changed", "added_words",
              "removed_words", "replaced", "inserted", "deleted"}
    """
    old_doc = fitz.open(old_path)
    new_doc = fitz.open(new_path)

    # Run page-level diff first to know what to render
    page_results = compare_pdfs(old_path, new_path)

    report = fitz.open()
    total_added_words = 0
    total_removed_words = 0

    # ------ Cover page ------
    A4_W, A4_H = 595.276, 841.890
    cover = report.new_page(width=A4_W, height=A4_H)

    # Branded header banner
    BRAND = (0.10, 0.10, 0.45)
    ACCENT = (0.149, 0.404, 1.0)   # #2667FF
    banner = fitz.Rect(0, 0, A4_W, 54)
    cover.draw_rect(banner, color=None, fill=BRAND)
    cover.insert_text((50, 34), "MasumPDF Reader",
                      fontname="hebo", fontsize=17, color=(1, 1, 1))
    cover.insert_text((A4_W - 50 - 130, 34), "Comparison Report",
                      fontname="helv", fontsize=11, color=(0.80, 0.85, 1.0))

    cover.insert_text((50, 96), "PDF Comparison Report",
                      fontname="hebo", fontsize=22, color=BRAND)
    cover.insert_text((50, 118),
                      f"Generated {datetime.now().strftime('%Y-%m-%d %H:%M')}"
                      + (f"   \u00b7   {author}" if author else ""),
                      fontname="helv", fontsize=9, color=(0.45, 0.45, 0.45))
    cover.draw_line(fitz.Point(50, 132), fitz.Point(A4_W - 50, 132),
                    color=(0.85, 0.85, 0.90), width=0.6)

    # File boxes
    box_y = 152
    box_h = 90
    box_w = (A4_W - 50 * 2 - 20) / 2
    # OLD
    old_box = fitz.Rect(50, box_y, 50 + box_w, box_y + box_h)
    cover.draw_rect(old_box, color=(0.78, 0.20, 0.20), width=1.2,
                    fill=(1.00, 0.95, 0.95))
    cover.insert_text((58, box_y + 18), "OLD", fontname="hebo",
                      fontsize=10, color=(0.6, 0.1, 0.1))
    cover.insert_textbox(
        fitz.Rect(58, box_y + 24, old_box.x1 - 8, old_box.y1 - 6),
        f"{os.path.basename(old_path)}\n"
        f"Pages: {old_doc.page_count}\n"
        f"Size:  {_human_size(os.path.getsize(old_path))}",
        fontname="helv", fontsize=10, color=(0.3, 0.1, 0.1))

    # NEW
    new_box = fitz.Rect(50 + box_w + 20, box_y, 50 + box_w * 2 + 20,
                        box_y + box_h)
    cover.draw_rect(new_box, color=(0.20, 0.55, 0.20), width=1.2,
                    fill=(0.95, 1.00, 0.95))
    cover.insert_text((new_box.x0 + 8, box_y + 18), "NEW", fontname="hebo",
                      fontsize=10, color=(0.1, 0.5, 0.1))
    cover.insert_textbox(
        fitz.Rect(new_box.x0 + 8, box_y + 24, new_box.x1 - 8, new_box.y1 - 6),
        f"{os.path.basename(new_path)}\n"
        f"Pages: {new_doc.page_count}\n"
        f"Size:  {_human_size(os.path.getsize(new_path))}",
        fontname="helv", fontsize=10, color=(0.1, 0.3, 0.1))

    # ------ Page-by-page word-level diff for stats ------
    page_diffs = []
    max_pages = max(old_doc.page_count, new_doc.page_count)
    for i in range(max_pages):
        old_words = old_doc[i].get_text("words") if i < old_doc.page_count else []
        new_words = new_doc[i].get_text("words") if i < new_doc.page_count else []
        rem, add = _word_diff(old_words, new_words,
                              ignore_case, ignore_quotes)
        total_removed_words += len(rem)
        total_added_words += len(add)
        page_diffs.append((old_words, new_words, rem, add))

    # ------ Global (cross-page) diff for accurate highlighting ------
    # This is what avoids the "whole page turns red" problem when content
    # reflows: only truly added/removed words are flagged; moved-but-equal
    # words are marked blue.
    global_old_marks, global_new_marks = global_word_diff(
        old_doc, new_doc, ignore_case, ignore_quotes)

    # If the user doesn't want reflow (moved) text shown, drop the blue marks
    if not show_moved:
        global_old_marks = {p: [(w, c) for (w, c) in m if c != "blue"]
                            for p, m in global_old_marks.items()}
        global_new_marks = {p: [(w, c) for (w, c) in m if c != "blue"]
                            for p, m in global_new_marks.items()}

    # ------ Summary block ------
    summary_y = 270
    cover.insert_text((50, summary_y), "Summary",
                      fontname="hebo", fontsize=14)
    summary_y += 22
    changed = sum(1 for r in page_results if r["status"] == "changed")
    same = sum(1 for r in page_results if r["status"] == "same")
    only_old = sum(1 for r in page_results if r["status"] == "old_only")
    only_new = sum(1 for r in page_results if r["status"] == "new_only")

    rows = [
        ("Total pages (old / new)", f"{old_doc.page_count} / {new_doc.page_count}"),
        ("Identical pages", str(same)),
        ("Changed pages", str(changed)),
        ("Only in OLD", str(only_old)),
        ("Only in NEW", str(only_new)),
        ("Words added (+)", f"+{total_added_words}"),
        ("Words removed (−)", f"-{total_removed_words}"),
    ]
    for lbl, val in rows:
        cover.insert_text((58, summary_y), lbl, fontname="helv", fontsize=10,
                          color=(0.3, 0.3, 0.3))
        cover.insert_text((280, summary_y), val, fontname="hebo", fontsize=10)
        summary_y += 16

    # Legend
    summary_y += 14
    cover.insert_text((50, summary_y), "Legend",
                      fontname="hebo", fontsize=12)
    summary_y += 18
    # red sample
    cover.draw_rect(fitz.Rect(58, summary_y, 80, summary_y + 12),
                    color=(0.78, 0.20, 0.20), width=0.6,
                    fill=(1.00, 0.78, 0.78))
    cover.insert_text((88, summary_y + 10),
                      "Removed in OLD (no longer in NEW)",
                      fontname="helv", fontsize=10)
    summary_y += 18
    cover.draw_rect(fitz.Rect(58, summary_y, 80, summary_y + 12),
                    color=(0.20, 0.55, 0.20), width=0.6,
                    fill=(0.78, 1.00, 0.78))
    cover.insert_text((88, summary_y + 10),
                      "Added in NEW (was not in OLD)",
                      fontname="helv", fontsize=10)
    if show_moved:
        summary_y += 18
        cover.draw_rect(fitz.Rect(58, summary_y, 80, summary_y + 12),
                        color=(0.20, 0.40, 0.85), width=0.6,
                        fill=(0.80, 0.88, 1.00))
        cover.insert_text((88, summary_y + 10),
                          "Same text, moved position (reflow) — not a real change",
                          fontname="helv", fontsize=10)
    if compare_images:
        summary_y += 18
        cover.draw_rect(fitz.Rect(58, summary_y, 80, summary_y + 12),
                        color=(0.90, 0.45, 0.0), width=1.2, dashes="[3 2] 0")
        cover.insert_text((88, summary_y + 10),
                          "Figure / image / chart changed (dashed orange box)",
                          fontname="helv", fontsize=10)

    # Footer
    cover.insert_text((50, A4_H - 40),
                      "MasumPDF Reader",
                      fontname="helv", fontsize=8, color=(0.55, 0.55, 0.55))

    # ------ Detailed change log pages ------
    changelog = build_full_changelog(old_path, new_path,
                                     ignore_case, ignore_quotes)

    # List the pages that actually changed, right on the cover, so the
    # reader instantly sees WHERE the changes are.
    changed_page_nums = [p["page"] for p in changelog["pages"]
                         if p["status"] != "same"]
    cl_y = summary_y + 44
    cover.insert_text((50, cl_y), "Pages with changes",
                      fontname="hebo", fontsize=12)
    cl_y += 18
    if changed_page_nums:
        nums = ", ".join(str(n) for n in changed_page_nums)
        cover.insert_textbox(
            fitz.Rect(58, cl_y, A4_W - 50, cl_y + 60),
            f"Pages {nums}\n\nOpen the bookmarks panel in your PDF reader "
            "and use 'Jump to Changes' to go straight to each one.",
            fontname="helv", fontsize=10, color=(0.25, 0.25, 0.30))
    else:
        cover.insert_text((58, cl_y),
                          "No textual changes detected.",
                          fontname="helv", fontsize=10,
                          color=(0.3, 0.3, 0.3))

    if include_changelog and report_mode in ("both", "changes"):
        _write_changelog_pages(report, changelog, A4_W, A4_H)

    # ------ Per-page comparison pages ------
    if report_mode not in ("both", "visual"):
        page_results_to_render = []
    else:
        page_results_to_render = page_results
    L_W, L_H = 841.890, 595.276  # A4 landscape
    margin = 32
    gap = 20

    # Track report page numbers for bookmarks: (level, title, report_page_no)
    visual_bookmarks = []

    for i, r in enumerate(page_results_to_render):
        # Show every page in the visual report when all_pages is on.
        # Pages with no real content change simply appear without any
        # red/green boxes — the word-level diff only flags genuinely
        # different words, so text that merely moved is NOT highlighted.
        if r["status"] == "same" and not all_pages:
            continue

        old_words, new_words, removed_idx, added_idx = page_diffs[i]
        # Count real changes on this page from the GLOBAL diff (accurate —
        # ignores reflow). Red = removed, green = added, blue = moved.
        om = global_old_marks.get(i, [])
        nm = global_new_marks.get(i, [])
        n_red = sum(1 for _, c in om if c == "red")
        n_green = sum(1 for _, c in nm if c == "green")
        n_blue = sum(1 for _, c in om if c == "blue") + \
                 sum(1 for _, c in nm if c == "blue")

        # Visual (figure/image) difference detection
        visual_rects = []
        if (compare_images and i < old_doc.page_count
                and i < new_doc.page_count):
            try:
                visual_rects = visual_region_diff(
                    old_doc[i], new_doc[i], render_dpi=render_dpi)
            except Exception:
                visual_rects = []

        # Decide a friendly per-page status from the global diff
        if i >= old_doc.page_count:
            gstatus = "new_only"
        elif i >= new_doc.page_count:
            gstatus = "old_only"
        elif n_red or n_green:
            gstatus = "changed"
        elif visual_rects:
            gstatus = "figure"
        elif n_blue:
            gstatus = "moved"
        else:
            gstatus = "same"

        cmp_page = report.new_page(width=L_W, height=L_H)
        _bm_label = {
            "changed": f"Page {r['page']} — Changed",
            "old_only": f"Page {r['page']} — Only in OLD",
            "new_only": f"Page {r['page']} — Only in NEW",
            "figure": f"Page {r['page']} — Figure/image changed",
            "moved": f"Page {r['page']} — Text shifted",
            "same": f"Page {r['page']} — No change",
        }[gstatus]
        visual_bookmarks.append((gstatus, _bm_label, report.page_count))

        # Header strip
        cmp_page.draw_rect(fitz.Rect(0, 0, L_W, 36),
                           color=None, fill=(0.96, 0.97, 0.99))
        status_label = {
            "changed": ("Changed", (0.85, 0.55, 0.10)),
            "old_only": ("Only in OLD", (0.78, 0.20, 0.20)),
            "new_only": ("Only in NEW", (0.20, 0.55, 0.20)),
            "figure": ("Figure / image changed", (0.85, 0.45, 0.05)),
            "moved": ("Text shifted (no real change)", (0.20, 0.40, 0.85)),
            "same": ("No change", (0.45, 0.45, 0.45)),
        }[gstatus]
        cmp_page.insert_text((margin, 22),
                             f"Page {r['page']}  \u00b7  {status_label[0]}",
                             fontname="hebo", fontsize=12,
                             color=status_label[1])
        if n_green or n_red:
            cmp_page.insert_text((margin + 320, 22),
                                 f"+{n_green} words   -{n_red} words",
                                 fontname="helv", fontsize=10,
                                 color=(0.4, 0.4, 0.4))

        # Compute side rectangles
        top = 50
        side_w = (L_W - 2 * margin - gap) / 2
        side_h = L_H - top - 30

        old_rect = fitz.Rect(margin, top, margin + side_w, top + side_h)
        new_rect = fitz.Rect(margin + side_w + gap, top,
                             L_W - margin, top + side_h)

        # Side titles
        cmp_page.insert_text((old_rect.x0, top - 4),
                             "OLD", fontname="hebo", fontsize=9,
                             color=(0.6, 0.1, 0.1))
        cmp_page.insert_text((new_rect.x0, top - 4),
                             "NEW", fontname="hebo", fontsize=9,
                             color=(0.1, 0.5, 0.1))

        # Render OLD page with global-diff highlights (red removed, blue moved)
        if i < old_doc.page_count:
            _render_side_marks(cmp_page, old_doc[i], old_rect,
                               global_old_marks.get(i, []),
                               render_dpi=render_dpi)
        else:
            cmp_page.draw_rect(old_rect, color=(0.8, 0.8, 0.8), width=0.8)
            cmp_page.insert_textbox(
                old_rect, "(no corresponding page in OLD)",
                fontname="helv", fontsize=11, color=(0.5, 0.5, 0.5), align=1)

        # Render NEW page with global-diff highlights (green added, blue moved)
        if i < new_doc.page_count:
            _render_side_marks(cmp_page, new_doc[i], new_rect,
                               global_new_marks.get(i, []),
                               render_dpi=render_dpi,
                               visual_rects=visual_rects)
        else:
            cmp_page.draw_rect(new_rect, color=(0.8, 0.8, 0.8), width=0.8)
            cmp_page.insert_textbox(
                new_rect, "(no corresponding page in NEW)",
                fontname="helv", fontsize=11, color=(0.5, 0.5, 0.5), align=1)

        # Footer
        cmp_page.insert_text((margin, L_H - 14),
                             f"MasumPDF Reader  ·  Comparison report",
                             fontname="helv", fontsize=8,
                             color=(0.55, 0.55, 0.55))

    total_pages = report.page_count

    # ------ Bookmarks (PDF outline) so the reader can jump to changes ------
    # Top entries: Cover, Detailed Changes (if present). Then one entry per
    # visual page, with changed pages grouped under a "Changes" heading so
    # the user can find exactly where the real edits are.
    toc = [[1, "Cover", 1]]
    if include_changelog and report_mode in ("both", "changes"):
        # the first changelog page is page 2 (right after the cover)
        toc.append([1, "Detailed Changes", 2])
    if visual_bookmarks:
        toc.append([1, "Pages", visual_bookmarks[0][2]])
        real_change = {"changed", "old_only", "new_only", "figure"}
        for status, label, pno in visual_bookmarks:
            if status in real_change:
                toc.append([2, "\u2691 " + label, pno])
            else:
                toc.append([2, label, pno])
        # Add a dedicated "Jump to changes" section listing only real changes
        changed_only = [(s, l, p) for (s, l, p) in visual_bookmarks
                        if s in real_change]
        if changed_only:
            first_changed = changed_only[0][2]
            toc.append([1, "Jump to Changes", first_changed])
            for status, label, pno in changed_only:
                toc.append([2, label, pno])
    try:
        report.set_toc(toc)
    except Exception:
        pass

    # ------ Clickable in-page links on the cover ------
    # Put a real "Go to first change" clickable link on the cover so the
    # user can click inside the PDF (not just the bookmarks panel).
    real_change = {"changed", "old_only", "new_only", "figure"}
    changed_pages = [(s, l, p) for (s, l, p) in visual_bookmarks
                     if s in real_change]
    cover_pg = report[0]
    link_y = A4_H - 120
    if changed_pages:
        first_changed_pno = changed_pages[0][2]  # 1-based
        label_rect = fitz.Rect(50, link_y, 320, link_y + 18)
        cover_pg.insert_textbox(
            label_rect, "\u27a4  Go to first change",
            fontname="hebo", fontsize=11, color=(0.149, 0.404, 1.0))
        cover_pg.insert_link({
            "kind": fitz.LINK_GOTO,
            "from": label_rect,
            "page": first_changed_pno - 1,   # 0-based target
            "to": fitz.Point(0, 0),
        })
        # also link each "Detailed Changes" page header back is handled by TOC
        ly = link_y + 24
        cover_pg.insert_text(
            (50, ly), "Tip: each entry in the bookmarks panel is clickable too.",
            fontname="helv", fontsize=9, color=(0.5, 0.5, 0.5))

    report.save(output_path, garbage=4, deflate=True)
    report.close()
    old_doc.close()
    new_doc.close()

    t = changelog["totals"]
    return {
        "report_path": output_path,
        "pages": total_pages,
        "changed": sum(1 for r in page_results if r["status"] != "same"),
        "added_words": total_added_words,
        "removed_words": total_removed_words,
        "replaced": t["replaced"],
        "inserted": t["inserted"],
        "deleted": t["deleted"],
    }


def _write_changelog_pages(report, changelog, page_w, page_h):
    """Write 'Detailed Changes' pages listing every replace/insert/delete."""
    margin = 50
    line_h = 13
    body_top = 96
    bottom_limit = page_h - 50

    RED = (0.72, 0.16, 0.16)
    GREEN = (0.13, 0.50, 0.16)
    GREY = (0.4, 0.4, 0.4)
    DARK = (0.15, 0.15, 0.2)

    def new_log_page(title_suffix=""):
        pg = report.new_page(width=page_w, height=page_h)
        pg.insert_text((margin, 60), "Detailed Changes" + title_suffix,
                       fontname="hebo", fontsize=18, color=(0.10, 0.10, 0.45))
        pg.draw_line(fitz.Point(margin, 74),
                     fitz.Point(page_w - margin, 74),
                     color=(0.85, 0.85, 0.90), width=0.6)
        return pg

    pg = None
    y = bottom_limit + 1  # force a new page on first write
    page_no = 0

    def ensure_space(needed):
        nonlocal pg, y, page_no
        if pg is None or y + needed > bottom_limit:
            page_no += 1
            pg = new_log_page(f"  (cont. {page_no})" if page_no > 1 else "")
            y = body_top
            return True
        return False

    def wrap(text, max_chars):
        text = text.replace("\n", " ").strip()
        if not text:
            return [""]
        words = text.split()
        lines, cur = [], ""
        for w in words:
            if len(cur) + len(w) + 1 <= max_chars:
                cur = (cur + " " + w).strip()
            else:
                if cur:
                    lines.append(cur)
                cur = w
        if cur:
            lines.append(cur)
        return lines[:8]  # cap very long runs

    any_changes = any(p["changes"] or p["status"] in ("old_only", "new_only")
                      for p in changelog["pages"])
    if not any_changes:
        pg = new_log_page()
        pg.insert_text((margin, body_top),
                       "No textual differences found between the two documents.",
                       fontname="helv", fontsize=11, color=GREY)
        return

    for p in changelog["pages"]:
        if p["status"] == "same":
            continue
        # Page heading
        ensure_space(line_h * 2)
        ensure_space(0)
        pg.insert_text((margin, y),
                       f"Page {p['page']}",
                       fontname="hebo", fontsize=12, color=DARK)
        y += line_h + 3

        if p["status"] == "new_only":
            pg.insert_text((margin + 10, y),
                           "This page is new (only in the NEW document).",
                           fontname="helv", fontsize=10, color=GREEN)
            y += line_h + 6
            continue
        if p["status"] == "old_only":
            pg.insert_text((margin + 10, y),
                           "This page was removed (only in the OLD document).",
                           fontname="helv", fontsize=10, color=RED)
            y += line_h + 6
            continue

        num = 0
        for c in p["changes"]:
            num += 1
            if c["type"] == "replace":
                old_lines = wrap(c["old"], 70)
                new_lines = wrap(c["new"], 70)
                ensure_space(line_h * (len(old_lines) + len(new_lines) + 1))
                pg.insert_text((margin + 10, y),
                               f"{num}. Replaced:",
                               fontname="hebo", fontsize=9, color=GREY)
                y += line_h
                for i, ln in enumerate(old_lines):
                    prefix = "   \u2212 " if i == 0 else "      "
                    pg.insert_text((margin + 16, y), prefix + ln,
                                   fontname="helv", fontsize=9, color=RED)
                    y += line_h
                for i, ln in enumerate(new_lines):
                    prefix = "   + " if i == 0 else "      "
                    pg.insert_text((margin + 16, y), prefix + ln,
                                   fontname="helv", fontsize=9, color=GREEN)
                    y += line_h
                y += 3
            elif c["type"] == "insert":
                new_lines = wrap(c["new"], 70)
                ensure_space(line_h * (len(new_lines) + 1))
                pg.insert_text((margin + 10, y),
                               f"{num}. Inserted:",
                               fontname="hebo", fontsize=9, color=GREY)
                y += line_h
                for i, ln in enumerate(new_lines):
                    prefix = "   + " if i == 0 else "      "
                    pg.insert_text((margin + 16, y), prefix + ln,
                                   fontname="helv", fontsize=9, color=GREEN)
                    y += line_h
                y += 3
            elif c["type"] == "delete":
                old_lines = wrap(c["old"], 70)
                ensure_space(line_h * (len(old_lines) + 1))
                pg.insert_text((margin + 10, y),
                               f"{num}. Deleted:",
                               fontname="hebo", fontsize=9, color=GREY)
                y += line_h
                for i, ln in enumerate(old_lines):
                    prefix = "   \u2212 " if i == 0 else "      "
                    pg.insert_text((margin + 16, y), prefix + ln,
                                   fontname="helv", fontsize=9, color=RED)
                    y += line_h
                y += 3
        y += 6


def _render_side_marks(report_page, source_page, target_rect, marks,
                       render_dpi, visual_rects=None):
    """Render a source page into target_rect, drawing colored boxes over the
    words in `marks`. marks is a list of ((page,x0,y0,x1,y1,text), color).
    visual_rects: optional list of fitz.Rect (figure/image changes) drawn
    as dashed orange boxes."""
    pix = source_page.get_pixmap(dpi=render_dpi)
    src_w_pt = source_page.rect.width
    src_h_pt = source_page.rect.height
    avail_w = target_rect.width
    avail_h = target_rect.height
    scale = min(avail_w / src_w_pt, avail_h / src_h_pt)
    fitted_w = src_w_pt * scale
    fitted_h = src_h_pt * scale
    off_x = target_rect.x0 + (avail_w - fitted_w) / 2
    off_y = target_rect.y0 + (avail_h - fitted_h) / 2
    fitted_rect = fitz.Rect(off_x, off_y, off_x + fitted_w, off_y + fitted_h)
    report_page.insert_image(fitted_rect, pixmap=pix)
    report_page.draw_rect(fitted_rect, color=(0.7, 0.7, 0.7), width=0.6)

    palette = {
        "red":   ((0.78, 0.20, 0.20), (1.00, 0.80, 0.80)),
        "green": ((0.20, 0.55, 0.20), (0.80, 1.00, 0.80)),
        "blue":  ((0.20, 0.40, 0.85), (0.82, 0.89, 1.00)),
    }
    for word, color in marks:
        stroke, fill = palette.get(color, ((0.5, 0.5, 0.5), (0.9, 0.9, 0.9)))
        _, x0, y0, x1, y1, _txt = word
        mapped = fitz.Rect(off_x + x0 * scale, off_y + y0 * scale,
                           off_x + x1 * scale, off_y + y1 * scale)
        mapped = mapped + (-0.5, -0.5, 0.5, 0.5)
        opacity = 0.30 if color == "blue" else 0.42
        report_page.draw_rect(mapped, color=stroke, fill=fill,
                              width=0.5, fill_opacity=opacity)

    # Figure / image change boxes (orange, dashed, no fill so the image shows)
    for vr in (visual_rects or []):
        mapped = fitz.Rect(off_x + vr.x0 * scale, off_y + vr.y0 * scale,
                           off_x + vr.x1 * scale, off_y + vr.y1 * scale)
        report_page.draw_rect(mapped, color=(0.90, 0.45, 0.0), width=1.4,
                              dashes="[3 2] 0")


def _render_side(report_page, source_page, target_rect,
                 words, highlight_indices,
                 color, fill, render_dpi):
    """Render a source page into target_rect with word highlights overlaid."""
    pix = source_page.get_pixmap(dpi=render_dpi)
    src_w_px, src_h_px = pix.width, pix.height
    src_w_pt = source_page.rect.width
    src_h_pt = source_page.rect.height

    # Fit while preserving aspect ratio
    avail_w = target_rect.width
    avail_h = target_rect.height
    scale = min(avail_w / src_w_pt, avail_h / src_h_pt)
    fitted_w = src_w_pt * scale
    fitted_h = src_h_pt * scale

    # Center the fitted image inside the target slot
    off_x = target_rect.x0 + (avail_w - fitted_w) / 2
    off_y = target_rect.y0 + (avail_h - fitted_h) / 2
    fitted_rect = fitz.Rect(off_x, off_y, off_x + fitted_w, off_y + fitted_h)

    report_page.insert_image(fitted_rect, pixmap=pix)
    # subtle border
    report_page.draw_rect(fitted_rect, color=color, width=0.8)

    # Overlay highlight rectangles in report-page coords
    for wi in highlight_indices:
        if wi >= len(words):
            continue
        w = words[wi]
        word_rect = fitz.Rect(w[0], w[1], w[2], w[3])
        mapped = fitz.Rect(
            off_x + word_rect.x0 * scale,
            off_y + word_rect.y0 * scale,
            off_x + word_rect.x1 * scale,
            off_y + word_rect.y1 * scale,
        )
        # Pad slightly so the box is visible at small page sizes
        mapped = mapped + (-0.5, -0.5, 0.5, 0.5)
        report_page.draw_rect(mapped, color=color, fill=fill,
                              width=0.6, fill_opacity=0.40)
