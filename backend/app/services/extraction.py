"""Text extraction: PyMuPDF for born-digital PDFs, OCR for scanned PDF pages and images."""
from dataclasses import dataclass, field
from pathlib import Path

import cv2
import fitz
import numpy as np

from ..config import MIN_TEXT_CHARS_PER_PAGE, OCR_DPI
from .ocr import ocr_image


@dataclass
class ExtractionResult:
    pages: list[dict] = field(default_factory=list)  # {page, text, method, confidence}
    method: str = "text"            # text | ocr | mixed
    ocr_engine: str | None = None
    ocr_confidence: float | None = None

    @property
    def full_text(self) -> str:
        return "\n".join(p["text"] for p in self.pages)


def _pixmap_to_bgr(pix: fitz.Pixmap) -> np.ndarray:
    arr = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
    if pix.n == 4:
        return cv2.cvtColor(arr, cv2.COLOR_RGBA2BGR)
    if pix.n == 1:
        return cv2.cvtColor(arr, cv2.COLOR_GRAY2BGR)
    return cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)


def load_image(path: Path) -> np.ndarray:
    # np.fromfile + imdecode handles non-ASCII Windows paths, unlike cv2.imread
    img = cv2.imdecode(np.fromfile(str(path), dtype=np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("Image could not be decoded.")
    return img


def extract_text(path: Path, mime_type: str) -> ExtractionResult:
    res = ExtractionResult()
    confs: list[float] = []
    if mime_type == "application/pdf":
        with fitz.open(path) as doc:
            for i, page in enumerate(doc, start=1):
                text = page.get_text("text").strip()
                if len(text) >= MIN_TEXT_CHARS_PER_PAGE:
                    res.pages.append({"page": i, "text": text, "method": "text", "confidence": None})
                    continue
                # Little or no selectable text: treat page as scanned and OCR the rendering.
                pix = page.get_pixmap(matrix=fitz.Matrix(OCR_DPI / 72, OCR_DPI / 72), alpha=False)
                ocr_text, conf, engine = ocr_image(_pixmap_to_bgr(pix))
                res.ocr_engine = engine
                confs.append(conf)
                res.pages.append({"page": i, "text": ocr_text, "method": "ocr", "confidence": round(conf, 3)})
    else:
        ocr_text, conf, engine = ocr_image(load_image(path))
        res.ocr_engine = engine
        confs.append(conf)
        res.pages.append({"page": 1, "text": ocr_text, "method": "ocr", "confidence": round(conf, 3)})

    methods = {p["method"] for p in res.pages}
    res.method = "mixed" if len(methods) > 1 else (methods.pop() if methods else "text")
    res.ocr_confidence = round(float(np.mean(confs)), 3) if confs else None
    return res
