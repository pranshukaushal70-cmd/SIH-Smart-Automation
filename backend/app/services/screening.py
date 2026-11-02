"""Basic authenticity *screening* facts. These are signals for a human reviewer, never proof of forgery.

This module only gathers raw, explainable facts; thresholds are applied by the screening rules so
that officers can tune them.
"""
import io
import re
from datetime import datetime

import fitz
import numpy as np
from PIL import Image, ImageChops


def _pdf_date(raw: str | None) -> str | None:
    if not raw:
        return None
    m = re.match(r"D?:?(\d{4})(\d{2})?(\d{2})?(\d{2})?(\d{2})?(\d{2})?", raw)
    if not m:
        return None
    parts = [int(g) if g else d for g, d in zip(m.groups(), (0, 1, 1, 0, 0, 0))]
    try:
        return datetime(*parts).isoformat()
    except ValueError:
        return None


def pdf_facts(data: bytes) -> dict:
    with fitz.open(stream=data, filetype="pdf") as doc:
        meta = doc.metadata or {}
        image_only_pages = sum(1 for p in doc if not p.get_text("text").strip() and p.get_images())
        facts = {
            "kind": "pdf",
            "producer": meta.get("producer") or None,
            "creator": meta.get("creator") or None,
            "author": meta.get("author") or None,
            "created": _pdf_date(meta.get("creationDate")),
            "modified": _pdf_date(meta.get("modDate")),
            "pdf_format": meta.get("format") or None,
            "eof_markers": data.count(b"%%EOF"),
            "image_only_pages": image_only_pages,
            "page_count": doc.page_count,
        }
    return facts


def image_facts(data: bytes, mime: str) -> dict:
    with Image.open(io.BytesIO(data)) as img:
        exif = img.getexif()
        facts = {
            "kind": "image",
            "format": img.format,
            "width": img.width,
            "height": img.height,
            "exif_software": (str(exif.get(0x0131)) if exif and exif.get(0x0131) else None),
            "exif_datetime": (str(exif.get(0x0132)) if exif and exif.get(0x0132) else None),
            "ela": None,
        }
        if mime == "image/jpeg":
            facts["ela"] = error_level_analysis(img)
    return facts


def error_level_analysis(img: Image.Image, quality: int = 90, block: int = 32) -> dict:
    """Recompress at a fixed quality and measure how unevenly the image responds.

    Regions pasted from a different source often recompress differently. A high ratio between the
    most-responsive block and the median block is a weak, heuristic signal only.
    """
    rgb = img.convert("RGB")
    buf = io.BytesIO()
    rgb.save(buf, "JPEG", quality=quality)
    buf.seek(0)
    diff = np.asarray(ImageChops.difference(rgb, Image.open(buf).convert("RGB")), dtype=np.float32).mean(axis=2)
    h, w = diff.shape
    hb, wb = h // block, w // block
    if hb == 0 or wb == 0:
        return {"mean": round(float(diff.mean()), 3), "block_ratio": None}
    blocks = diff[: hb * block, : wb * block].reshape(hb, block, wb, block).mean(axis=(1, 3))
    med = float(np.median(blocks))
    return {
        "mean": round(float(diff.mean()), 3),
        "max_block": round(float(blocks.max()), 3),
        "median_block": round(med, 3),
        "block_ratio": round(float(blocks.max()) / med, 2) if med > 0.05 else None,
        "quality": quality,
    }
