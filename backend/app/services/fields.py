"""Deterministic field extraction and document classification.

Every field is reported as detected, uncertain or missing. Values are only ever copied from the
document text; nothing is inferred or invented.
"""
import re
from datetime import date, datetime

from ..catalog import CLASSIFIER_KEYWORDS

OCR_UNCERTAIN_BELOW = 0.80

# Labels tolerate missing spaces and I/l/1 confusion, both common in OCR output.
I = r"[il1|]"
LABELS = {
    "institution_name": r"(?:name\s*of\s*(?:the\s*)?institut(?:ion|e)\b|institut(?:ion|e)\s*name\b|college\s*name\b)",
    "institution_id": rf"(?:institut(?:ion|e)\s*(?:{I}d\b|identifier|code)|permanent\s*{I}d\b)",
    "issue_date": rf"(?:date\s*of\s*{I}ssue|{I}ssue\s*date|{I}ssued\s*on|\bdated\b)",
    "expiry_date": r"(?:valid\s*(?:until|up\s*to|till)|expiry\s*date|date\s*of\s*expiry|expires\s*on)",
    "issuer_name": rf"(?:{I}ssued\s*by|{I}ssuing\s*authority)",
    "reference_number": r"(?:certificate\s*(?:no\b|number)|reference\s*(?:no\b|number)|ref\.?\s*no\b"
                        r"|registration\s*(?:no\b|number)|letter\s*no\b|noc\s*no\b)",
    "approval_reference": r"(?:affiliation\s*(?:no\b|number|reference)|approval\s*(?:no\b|number|reference))",
}
DATE_FIELDS = {"issue_date", "expiry_date"}
ID_FALLBACK = re.compile(r"\bSYN-INST-\d{5}\b", re.I)

MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], start=1)}
DATE_RE = re.compile(
    r"(\d{1,2}[./-]\d{1,2}[./-]\d{4}"
    r"|\d{4}-\d{2}-\d{2}"
    r"|\d{1,2}(?:st|nd|rd|th)?[\s-]*[A-Za-z]{3,9}\.?,?[\s-]*\d{4}"
    r"|[A-Za-z]{3,9}\.?\s*\d{1,2}(?:st|nd|rd|th)?,?\s*\d{4})")


def parse_date(raw: str) -> date | None:
    """Parse common Indian/ISO date formats. Numeric dates are read as DD/MM/YYYY."""
    s = raw.strip()
    m = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", s)
    if m:
        y, mo, d = map(int, m.groups())
    else:
        m = re.fullmatch(r"(\d{1,2})[./-](\d{1,2})[./-](\d{4})", s)
        if m:
            d, mo, y = map(int, m.groups())
        else:
            m = re.fullmatch(r"(\d{1,2})(?:st|nd|rd|th)?[\s-]*([A-Za-z]{3,9})\.?,?[\s-]*(\d{4})", s)
            if m:
                d, mon, y = m.group(1), m.group(2), m.group(3)
            else:
                m = re.fullmatch(r"([A-Za-z]{3,9})\.?\s*(\d{1,2})(?:st|nd|rd|th)?,?\s*(\d{4})", s)
                if not m:
                    return None
                mon, d, y = m.group(1), m.group(2), m.group(3)
            mo = MONTHS.get(mon[:3].lower())
            if mo is None:
                return None
            d, y = int(d), int(y)
    try:
        return date(y, mo, d)
    except ValueError:
        return None


def _clean_value(field: str, value: str) -> tuple[str | None, str | None]:
    """Returns (display_value, normalized_value) or (None, None) if nothing usable."""
    value = value.strip().strip(":-–|").strip()
    if not value:
        return None, None
    if field in DATE_FIELDS:
        m = DATE_RE.search(value)
        if not m:
            return value[:60], None  # label present but no parseable date
        parsed = parse_date(m.group(1))
        return m.group(1), parsed.isoformat() if parsed else None
    if field == "institution_id":
        m = re.search(r"[A-Za-z0-9][A-Za-z0-9\-/]{4,}", value)
        if not m:
            return None, None
        v = m.group(0).upper()
        return v, v
    if field in ("reference_number", "approval_reference"):
        m = re.search(r"[A-Za-z0-9][A-Za-z0-9\-/.]{2,}", value)
        if not m:
            return None, None
        return m.group(0).rstrip("."), m.group(0).rstrip(".").upper()
    v = re.split(r"\s{3,}", value)[0].strip(" .,;")[:160]
    return (v, v) if len(v) >= 3 else (None, None)


def extract_fields(pages: list[dict]) -> dict:
    out: dict[str, dict] = {}
    for field, label in LABELS.items():
        pattern = re.compile(label + r"\.?\s*[:\-–]?\s*(.*)$", re.I)
        hits = []
        for p in pages:
            lines = [ln.strip() for ln in p["text"].splitlines()]
            for idx, line in enumerate(lines):
                m = pattern.search(line)
                if not m:
                    continue
                rest = m.group(1)
                # value on the following line (common in OCR output and two-column layouts)
                if not rest.strip(" :-–|") and idx + 1 < len(lines):
                    rest = lines[idx + 1]
                display, norm = _clean_value(field, rest)
                if display is None:
                    continue
                hits.append({"value": display, "normalized": norm, "page": p["page"], "evidence": line[:200],
                             "method": p["method"], "page_confidence": p.get("confidence")})
        if not hits and field == "institution_id":
            for p in pages:
                m = ID_FALLBACK.search(p["text"])
                if m:
                    line = next((ln for ln in p["text"].splitlines() if m.group(0) in ln), m.group(0))
                    hits.append({"value": m.group(0).upper(), "normalized": m.group(0).upper(), "page": p["page"],
                                 "evidence": line.strip()[:200], "method": p["method"],
                                 "page_confidence": p.get("confidence"), "fallback": True})
                    break
        out[field] = _resolve(field, hits)
    return out


def _resolve(field: str, hits: list[dict]) -> dict:
    if not hits:
        return {"value": None, "normalized": None, "status": "missing", "page": None, "evidence": None,
                "note": "No labelled value found in the document text."}
    first = hits[0]
    notes = []
    status = "detected"
    distinct = {h["normalized"] or h["value"] for h in hits}
    if len(distinct) > 1:
        status = "uncertain"
        notes.append("Conflicting values found: " + "; ".join(sorted(distinct))[:200])
    if first.get("fallback"):
        status = "uncertain"
        notes.append("Matched by identifier pattern, not by a field label.")
    if field in DATE_FIELDS and first["normalized"] is None:
        status = "uncertain"
        notes.append("Label found but the date could not be parsed.")
    conf = first.get("page_confidence")
    if first["method"] == "ocr" and conf is not None and conf < OCR_UNCERTAIN_BELOW:
        status = "uncertain"
        notes.append(f"Read by OCR with low page confidence ({conf:.0%}).")
    return {"value": first["value"], "normalized": first["normalized"], "status": status, "page": first["page"],
            "evidence": first["evidence"], "method": first["method"], "note": " ".join(notes) or None}


def classify(text: str) -> tuple[str, float, dict]:
    low = squash(text)
    scores = {}
    for cat, kws in CLASSIFIER_KEYWORDS.items():
        scores[cat] = round(sum(w * min(low.count(squash(k)), 3) for k, w in kws.items()), 2)
    ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    top_cat, top = ranked[0]
    total = sum(scores.values())
    if top < 3 or total == 0:
        return "unknown", 0.0, scores
    confidence = round((top / total) * min(1.0, top / 8), 3)
    return top_cat, confidence, scores


def squash(text: str) -> str:
    """Lower-case and drop all whitespace, so phrase matching survives OCR spacing loss."""
    return re.sub(r"\s+", "", text.lower())


def today() -> date:
    return datetime.now().date()
