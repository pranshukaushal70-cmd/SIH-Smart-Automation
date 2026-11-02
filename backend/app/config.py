"""Runtime configuration. Values come from environment variables or an optional backend/.env file."""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent  # backend/


def _load_dotenv() -> None:
    env_file = BASE_DIR / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_dotenv()


def _path(name: str, default: Path) -> Path:
    value = os.environ.get(name)
    p = Path(value) if value else default
    if not p.is_absolute():
        p = BASE_DIR / p
    return p


DATA_DIR = _path("VERI_DATA_DIR", BASE_DIR / "data")
DB_PATH = _path("VERI_DB_PATH", DATA_DIR / "veriaicte.db")
UPLOAD_DIR = _path("VERI_UPLOAD_DIR", DATA_DIR / "uploads")       # officer uploads (real files)
DEMO_DIR = _path("VERI_DEMO_DIR", DATA_DIR / "demo_documents")    # synthetic seeded files (kept separate)

MAX_UPLOAD_MB = float(os.environ.get("VERI_MAX_UPLOAD_MB", "10"))
MAX_UPLOAD_BYTES = int(MAX_UPLOAD_MB * 1024 * 1024)
MAX_PDF_PAGES = int(os.environ.get("VERI_MAX_PDF_PAGES", "30"))
CORS_ORIGINS = [o.strip() for o in os.environ.get(
    "VERI_CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",") if o.strip()]

# auto | rapidocr | tesseract | none
OCR_ENGINE = os.environ.get("VERI_OCR_ENGINE", "auto").lower()
TESSERACT_CMD = os.environ.get("TESSERACT_CMD", "")
OCR_DPI = int(os.environ.get("VERI_OCR_DPI", "200"))
MIN_TEXT_CHARS_PER_PAGE = int(os.environ.get("VERI_MIN_TEXT_CHARS", "40"))

AUTO_SEED = os.environ.get("VERI_AUTO_SEED", "1") == "1"

for d in (DATA_DIR, UPLOAD_DIR, DEMO_DIR):
    d.mkdir(parents=True, exist_ok=True)
