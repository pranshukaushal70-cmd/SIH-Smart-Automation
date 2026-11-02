"""OCR engines. RapidOCR (ONNX, pip-installed) is bundled; Tesseract is used if installed and selected.

No OCR result is ever fabricated: if no engine is available, OCRUnavailable is raised and the
document is marked as failed with a clear message.
"""
import logging
import shutil
import threading
import unicodedata

import cv2
import numpy as np

from ..config import OCR_ENGINE, TESSERACT_CMD

log = logging.getLogger("veriaicte.ocr")


class OCRUnavailable(RuntimeError):
    pass


_lock = threading.Lock()
_rapid = None
_rapid_error: str | None = None


def _tesseract_path() -> str | None:
    return TESSERACT_CMD or shutil.which("tesseract") or None


def _load_rapid():
    global _rapid, _rapid_error
    if _rapid is not None or _rapid_error is not None:
        return _rapid
    with _lock:
        if _rapid is None and _rapid_error is None:
            try:
                from rapidocr_onnxruntime import RapidOCR
                _rapid = RapidOCR()
            except Exception as exc:  # pragma: no cover - environment dependent
                _rapid_error = f"RapidOCR could not be loaded: {exc.__class__.__name__}"
                log.warning(_rapid_error)
    return _rapid


def warm_up() -> None:
    """Load the OCR model ahead of the first request (called in a background thread at startup)."""
    if engine_name() == "rapidocr":
        _load_rapid()


def engine_name() -> str | None:
    if OCR_ENGINE == "none":
        return None
    if OCR_ENGINE == "tesseract":
        return "tesseract" if _tesseract_path() else None
    if OCR_ENGINE in ("auto", "rapidocr"):
        try:
            import rapidocr_onnxruntime  # noqa: F401
            return "rapidocr"
        except ImportError:
            pass
        if OCR_ENGINE == "auto" and _tesseract_path():
            return "tesseract"
    return None


def status() -> dict:
    name = engine_name()
    return {
        "available": name is not None,
        "engine": name,
        "configured": OCR_ENGINE,
        "tesseract_installed": _tesseract_path() is not None,
        "error": _rapid_error,
    }


def preprocess(img: np.ndarray) -> np.ndarray:
    """Light, explainable preprocessing: grayscale, upscale small images, contrast normalisation."""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img
    h, w = gray.shape[:2]
    if max(h, w) < 1400:
        scale = 1400 / max(h, w)
        gray = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
    gray = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(gray)
    return cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)


def _group_lines(items: list[tuple[float, float, float, str, float]]) -> list[tuple[str, float]]:
    """items: (y_center, x_left, height, text, conf) -> reading-order lines with mean confidence."""
    items.sort(key=lambda t: (t[0], t[1]))
    lines: list[list] = []
    for it in items:
        if lines and abs(it[0] - lines[-1][0][0]) < 0.6 * max(it[2], lines[-1][0][2]):
            lines[-1].append(it)
        else:
            lines.append([it])
    out = []
    for ln in lines:
        ln.sort(key=lambda t: t[1])
        out.append((" ".join(t[3] for t in ln), float(np.mean([t[4] for t in ln]))))
    return out


def ocr_image(img: np.ndarray) -> tuple[str, float, str]:
    """Returns (text, mean_confidence 0..1, engine)."""
    name = engine_name()
    if name is None:
        raise OCRUnavailable(
            "No OCR engine is available. Install the Python package 'rapidocr-onnxruntime' "
            "(pip install -r requirements.txt) or install Tesseract and set TESSERACT_CMD.")
    prepared = preprocess(img)
    if name == "rapidocr":
        engine = _load_rapid()
        if engine is None:
            raise OCRUnavailable(_rapid_error or "RapidOCR failed to load.")
        # angle classifier skipped: scans are upright and it costs ~1s per page on CPU
        result, _ = engine(prepared, use_cls=False)
        items = []
        for box, text, conf in result or []:
            ys = [p[1] for p in box]
            xs = [p[0] for p in box]
            items.append(((min(ys) + max(ys)) / 2, min(xs), max(ys) - min(ys), text, float(conf)))
        lines = _group_lines(items)
    else:
        import pytesseract
        if TESSERACT_CMD:
            pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD
        try:
            data = pytesseract.image_to_data(prepared, lang="eng", output_type=pytesseract.Output.DICT)
        except Exception as exc:
            raise OCRUnavailable(f"Tesseract failed ({exc.__class__.__name__}); check the install and 'eng' language data.")
        items = []
        for i, word in enumerate(data["text"]):
            conf = float(data["conf"][i])
            if word.strip() and conf >= 0:
                items.append((data["top"][i] + data["height"][i] / 2, data["left"][i], data["height"][i], word, conf / 100))
        lines = _group_lines(items)
    if not lines:
        return "", 0.0, name
    text = unicodedata.normalize("NFKC", "\n".join(t for t, _ in lines))
    conf = float(np.mean([c for _, c in lines]))
    return text, conf, name
