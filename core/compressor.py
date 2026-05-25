"""PDF compressor.

Reduces PDF file size by safely downsampling embedded images and cleaning the PDF.

Important safety rule:
    Do NOT write JPEG bytes into an existing image object with update_stream().
    That changes only the raw bytes, not the PDF image dictionary. Use
    page.replace_image(..., stream=...) so PyMuPDF updates the image object
    correctly and images do not disappear after compression.
"""

import io
import os

import fitz   # PyMuPDF
from PIL import Image


# Friendly DPI presets. Keep labels stable for the UI.
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


def _pixmap_to_pil_rgb(pix: fitz.Pixmap) -> Image.Image:
    """Convert a PyMuPDF pixmap to a PIL RGB image for JPEG/PNG output."""
    if pix.n - pix.alpha == 1:
        img = Image.frombytes("L", (pix.width, pix.height), pix.samples)
        return img.convert("RGB")

    if pix.n - pix.alpha == 3 and not pix.alpha:
        return Image.frombytes("RGB", (pix.width, pix.height), pix.samples)

    rgb = fitz.Pixmap(fitz.csRGB, pix)
    try:
        return Image.frombytes("RGB", (rgb.width, rgb.height), rgb.samples)
    finally:
        rgb = None


def _pixmap_kind(pix: fitz.Pixmap) -> str:
    """Classify image as color, grayscale, or monochrome-like."""
    if pix.n - pix.alpha <= 1:
        # True 1-bit images are not always exposed as 1-bit by PyMuPDF, so treat
        # single-channel images as grayscale / monochrome candidates.
        if pix.width * pix.height > 0 and len(set(pix.samples[: min(len(pix.samples), 4096)])) <= 2:
            return "mono"
        return "gray"
    return "color"


def _encode_image(img: Image.Image, compression: str, quality: int) -> bytes:
    """Encode image according to the selected optimizer settings."""
    buf = io.BytesIO()
    compression = (compression or "JPEG").upper()
    if compression == "PNG":
        img.save(buf, format="PNG", optimize=True)
    else:
        img.save(
            buf,
            format="JPEG",
            quality=max(20, min(int(quality), 95)),
            optimize=True,
            progressive=True,
        )
    return buf.getvalue()


def _default_options(target_dpi: int, jpeg_quality: int) -> dict:
    above = max(target_dpi + 50, int(target_dpi * 1.5))
    return {
        "image_enabled": True,
        "color_target_dpi": target_dpi,
        "color_above_dpi": above,
        "color_quality": jpeg_quality,
        "color_compression": "JPEG",
        "gray_target_dpi": target_dpi,
        "gray_above_dpi": above,
        "gray_quality": jpeg_quality,
        "gray_compression": "JPEG",
        "mono_target_dpi": max(150, target_dpi),
        "mono_above_dpi": max(300, above),
        "mono_quality": 100,
        "mono_compression": "PNG",
        "optimize_only_if_smaller": True,
        "deflate_fonts": True,
        "deflate_streams": True,
        "discard_metadata": False,
        "clean": False,
        "allow_transparency_changes": False,
    }


def compress_pdf(input_path: str,
                 output_path: str,
                 target_dpi: int = 100,
                 jpeg_quality: int = 70,
                 progress_cb=None,
                 options: dict | None = None) -> dict:
    """Compress a PDF. Returns a dict with stats.

    options is optional so old code can still call compress_pdf(input, output,
    target_dpi, jpeg_quality). The advanced optimizer dialog passes a full
    options dictionary.
    """
    opts = _default_options(target_dpi, jpeg_quality)
    if options:
        opts.update(options)

    src = fitz.open(input_path)
    original_size = os.path.getsize(input_path)
    images_replaced = 0
    images_skipped = 0
    images_not_smaller = 0
    processed_xrefs = set()

    if opts.get("discard_metadata"):
        try:
            src.set_metadata({})
        except Exception:
            pass
        try:
            if hasattr(src, "del_xml_metadata"):
                src.del_xml_metadata()
        except Exception:
            pass

    total_pages = src.page_count
    for pno in range(total_pages):
        if progress_cb:
            progress_cb(int((pno / max(1, total_pages)) * 100),
                        f"Page {pno + 1} of {total_pages}")

        if not opts.get("image_enabled", True):
            continue

        page = src[pno]
        page_rect = page.rect

        for img_info in page.get_images(full=True):
            xref = img_info[0]
            smask = img_info[1] if len(img_info) > 1 else 0

            if xref in processed_xrefs:
                continue

            pix = None
            try:
                pix = fitz.Pixmap(src, xref)

                # By default, keep transparent / soft-mask images untouched.
                # JPEG cannot keep alpha, and changing the stream can make these
                # images vanish or show black boxes in some viewers.
                if (smask or pix.alpha) and not opts.get("allow_transparency_changes", False):
                    images_skipped += 1
                    processed_xrefs.add(xref)
                    continue

                placements = page.get_image_rects(xref) or [page_rect]
                largest = max(placements, key=lambda r: (r.width * r.height))
                current_dpi = _estimate_image_dpi(
                    pix.width, largest.width, pix.height, largest.height
                )
                if current_dpi <= 0:
                    images_skipped += 1
                    processed_xrefs.add(xref)
                    continue

                kind = _pixmap_kind(pix)
                prefix = {"color": "color", "gray": "gray", "mono": "mono"}[kind]
                target = int(opts.get(f"{prefix}_target_dpi", target_dpi))
                above = int(opts.get(f"{prefix}_above_dpi", max(target + 50, int(target * 1.5))))
                quality = int(opts.get(f"{prefix}_quality", jpeg_quality))
                compression = opts.get(f"{prefix}_compression", "JPEG")

                # Acrobat-style behavior: only downsample images above threshold.
                if current_dpi <= above:
                    images_skipped += 1
                    processed_xrefs.add(xref)
                    continue

                scale = min(1.0, target / current_dpi)
                new_w = max(1, int(pix.width * scale))
                new_h = max(1, int(pix.height * scale))
                if new_w >= pix.width and new_h >= pix.height:
                    images_skipped += 1
                    processed_xrefs.add(xref)
                    continue

                img = _pixmap_to_pil_rgb(pix)
                img_small = img.resize((new_w, new_h), Image.LANCZOS)
                new_bytes = _encode_image(img_small, compression, quality)

                # Do not replace when the new stream is bigger unless the user
                # intentionally turned this safety off.
                if opts.get("optimize_only_if_smaller", True):
                    old_len = 0
                    try:
                        old_len = len(src.xref_stream_raw(xref) or b"")
                    except Exception:
                        try:
                            old_len = len(src.extract_image(xref).get("image", b""))
                        except Exception:
                            old_len = 0
                    if old_len and len(new_bytes) >= old_len:
                        images_not_smaller += 1
                        processed_xrefs.add(xref)
                        continue

                page.replace_image(xref, stream=new_bytes)
                images_replaced += 1
                processed_xrefs.add(xref)

            except Exception:
                images_skipped += 1
                processed_xrefs.add(xref)
            finally:
                pix = None

    if progress_cb:
        progress_cb(100, "Writing output…")

    save_kwargs = {
        "garbage": 4,
        "deflate": bool(opts.get("deflate_streams", True)),
        "deflate_images": bool(opts.get("deflate_streams", True)),
        "deflate_fonts": bool(opts.get("deflate_fonts", True)),
        # clean=True can rewrite content streams. It is available in the
        # advanced dialog but off in Basic mode for safer visual output.
        "clean": bool(opts.get("clean", False)),
    }
    src.save(output_path, **save_kwargs)
    src.close()

    new_size = os.path.getsize(output_path)
    return {
        "original_size": original_size,
        "new_size": new_size,
        "ratio": (new_size / original_size) if original_size else 1.0,
        "images_replaced": images_replaced,
        "images_skipped": images_skipped,
        "images_not_smaller": images_not_smaller,
        "target_dpi": int(opts.get("target_dpi", target_dpi)),
        "jpeg_quality": int(opts.get("jpeg_quality", jpeg_quality)),
        "advanced_options": opts,
    }
