"""Upload validation: extension, declared MIME type, magic bytes, structural parse, size and page limits."""
import hashlib
import io
import re
import uuid
from dataclasses import dataclass
from pathlib import Path

import fitz
from PIL import Image

from ..config import MAX_PDF_PAGES, MAX_UPLOAD_BYTES

ALLOWED = {
    ".pdf": ("application/pdf", (b"%PDF-",)),
    ".jpg": ("image/jpeg", (b"\xff\xd8\xff",)),
    ".jpeg": ("image/jpeg", (b"\xff\xd8\xff",)),
    ".png": ("image/png", (b"\x89PNG\r\n\x1a\n",)),
}
# Some browsers/OSes send a generic type; we still require matching magic bytes.
GENERIC_TYPES = {"", "application/octet-stream", "binary/octet-stream"}


class UploadRejected(ValueError):
    pass


@dataclass
class ValidatedFile:
    safe_name: str
    ext: str
    mime_type: str
    data: bytes
    sha256: str
    page_count: int


def sanitize_filename(name: str) -> str:
    name = (name or "").replace("\\", "/").split("/")[-1]  # drop any path components
    name = re.sub(r"[^A-Za-z0-9._ ()-]", "_", name).strip(" .")
    return (name or "document")[:150]


def validate_upload(filename: str, declared_type: str | None, data: bytes) -> ValidatedFile:
    safe = sanitize_filename(filename)
    ext = Path(safe).suffix.lower()
    if ext not in ALLOWED:
        raise UploadRejected(f"Unsupported file type '{ext or 'none'}'. Allowed: PDF, JPG, JPEG, PNG.")
    if not data:
        raise UploadRejected("The uploaded file is empty.")
    if len(data) > MAX_UPLOAD_BYTES:
        raise UploadRejected(f"File exceeds the {MAX_UPLOAD_BYTES // (1024 * 1024)} MB limit.")
    mime, signatures = ALLOWED[ext]
    declared = (declared_type or "").split(";")[0].strip().lower()
    if declared not in GENERIC_TYPES and declared != mime and not (mime == "image/jpeg" and declared == "image/jpg"):
        raise UploadRejected(f"Declared content type '{declared}' does not match the '{ext}' extension.")
    if not any(data.startswith(sig) for sig in signatures):
        raise UploadRejected("File content does not match its extension (invalid file signature).")

    page_count = 1
    try:
        if mime == "application/pdf":
            with fitz.open(stream=data, filetype="pdf") as doc:
                if doc.needs_pass:
                    raise UploadRejected("Password-protected PDFs are not supported.")
                page_count = doc.page_count
                if page_count == 0:
                    raise UploadRejected("The PDF has no pages.")
                if page_count > MAX_PDF_PAGES:
                    raise UploadRejected(f"The PDF has {page_count} pages; the limit is {MAX_PDF_PAGES}.")
        else:
            with Image.open(io.BytesIO(data)) as img:
                img.verify()
    except UploadRejected:
        raise
    except Exception:
        raise UploadRejected("The file is malformed or could not be parsed.")

    return ValidatedFile(safe, ext, mime, data, hashlib.sha256(data).hexdigest(), page_count)


def store_file(directory: Path, vf: ValidatedFile) -> str:
    stored = f"{uuid.uuid4().hex}{vf.ext}"
    target = (directory / stored).resolve()
    if target.parent != directory.resolve():  # defence in depth against traversal
        raise UploadRejected("Invalid storage path.")
    target.write_bytes(vf.data)
    return stored
