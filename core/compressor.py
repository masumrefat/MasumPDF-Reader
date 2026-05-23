"""PDF compressor.

Reduces PDF file size by:
  - downsampling embedded images to a chosen target DPI
  - re-encoding them as JPEG with chosen quality
  - cleaning up the document with garbage collection + deflate
"""

import io
import os
import fitz   # PyMuPDF
from PIL import Image


# Friendly DPI presets
DPI_PRESETS = [
    ("Smallest size (50 DPI)", 50, 50),
    ("Small (75 DPI)", 75, 60),
    ("Medium (100 DPI)", 100, 70),
    ("Good (150 DPI)", 150, 80),
    ("High (200 DPI)", 200, 85),
    ("Maximum (300 DPI)", 300, 90),
]


def _estimate_image_dpi(width_px, page_w_pt, height_px, page_h_pt):
    """Rough DPI estimate for an image based on how big it is on the page."""
    if page_w_pt <= 0 or page_h_pt <= 0:
        return 0
    dpi_w = width_px * 72.0 / page_w_pt
    dpi_h = height_px * 72.0 / page_h_pt
    return max(dpi_w, dpi_h)


def compress_pdf(input_path: str,
                 output_path: str,
                 target_dpi: int = 100,
                 jpeg_quality: int = 70,
                 progress_cb=None) -> dict:
    """Compress a PDF. Returns a dict with stats."""
    src = fitz.open(input_path)
    original_size = os.path.getsize(input_path)
    images_replaced = 0
    images_skipped = 0

    total_pages = src.page_count
    for pno in range(total_pages):
        if progress_cb:
            progress_cb(int((pno / max(1, total_pages)) * 100),
                        f"Page {pno + 1} of {total_pages}")
        page = src[pno]
        page_rect = page.rect
        # get_images returns (xref, smask, w, h, bpc, cs, alt, name, filter, ...)
        for img_info in page.get_images(full=True):
            xref = img_info[0]
            try:
                pix = fitz.Pixmap(src, xref)
            except Exception:
                images_skipped += 1
                continue

            # how big does this image appear on the page?
            placements = page.get_image_rects(xref) or [page_rect]
            largest = max(placements, key=lambda r: (r.width * r.height))
            current_dpi = _estimate_image_dpi(pix.width, largest.width,
                                              pix.height, largest.height)

            # skip if already small enough
            if current_dpi <= target_dpi:
                images_skipped += 1
                if pix:
                    pix = None
                continue

            # compute target pixel dims
            scale = target_dpi / current_dpi
            new_w = max(1, int(pix.width * scale))
            new_h = max(1, int(pix.height * scale))

            # convert via PIL for high-quality downsample + JPEG encode
            try:
                if pix.alpha:
                    # has alpha — drop it onto white so JPEG works
                    rgb = fitz.Pixmap(fitz.csRGB, pix)
                    img = Image.frombytes("RGB", (rgb.width, rgb.height), rgb.samples)
                    rgb = None
                else:
                    if pix.n - pix.alpha not in (1, 3):
                        # convert to RGB through fitz first
                        rgb = fitz.Pixmap(fitz.csRGB, pix)
                        img = Image.frombytes("RGB", (rgb.width, rgb.height), rgb.samples)
                        rgb = None
                    elif pix.n == 1:
                        img = Image.frombytes("L", (pix.width, pix.height), pix.samples)
                    else:
                        img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)

                img_small = img.resize((new_w, new_h), Image.LANCZOS)
                buf = io.BytesIO()
                save_kwargs = {"format": "JPEG", "quality": int(jpeg_quality),
                               "optimize": True}
                if img_small.mode != "RGB":
                    img_small = img_small.convert("RGB")
                img_small.save(buf, **save_kwargs)
                new_bytes = buf.getvalue()

                # replace in the document
                src.update_stream(xref, new_bytes, new=False)
                images_replaced += 1
            except Exception:
                images_skipped += 1
            finally:
                pix = None

    if progress_cb:
        progress_cb(100, "Writing output…")

    # save with garbage collection + deflation
    src.save(output_path,
             garbage=4,
             deflate=True,
             deflate_images=True,
             deflate_fonts=True,
             clean=True)
    src.close()

    new_size = os.path.getsize(output_path)
    return {
        "original_size": original_size,
        "new_size": new_size,
        "ratio": (new_size / original_size) if original_size else 1.0,
        "images_replaced": images_replaced,
        "images_skipped": images_skipped,
        "target_dpi": target_dpi,
        "jpeg_quality": jpeg_quality,
    }
