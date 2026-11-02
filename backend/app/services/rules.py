"""Configurable compliance and screening rules.

Each rule has a stable ID and an integer version that increments on every change, so a report can
state exactly which rule configuration produced each finding.
"""
import re
from datetime import date
from difflib import SequenceMatcher

from ..catalog import DOCUMENT_CATEGORIES, FIELD_LABELS
from .fields import squash

DEFAULT_RULES = [
    {"id": "R-DOC-001", "name": "Required documents are present", "rule_type": "required_document",
     "group": "compliance", "severity": "high",
     "description": "Each listed document category must be submitted with the application.",
     "params": {"categories": ["affiliation_letter", "fire_safety_certificate", "occupancy_certificate",
                               "trust_registration_certificate"]}},
    {"id": "R-FLD-001", "name": "Fire safety certificate: mandatory fields", "rule_type": "required_fields",
     "group": "compliance", "severity": "medium",
     "description": "Fire safety certificates must state the institution, identifier, issuer, number and validity.",
     "params": {"category": "fire_safety_certificate",
                "fields": ["institution_name", "institution_id", "issuer_name", "reference_number",
                           "issue_date", "expiry_date"]}},
    {"id": "R-FLD-002", "name": "Occupancy certificate: mandatory fields", "rule_type": "required_fields",
     "group": "compliance", "severity": "medium",
     "description": "Occupancy / completion certificates must state the institution, identifier, issuer and number.",
     "params": {"category": "occupancy_certificate",
                "fields": ["institution_name", "institution_id", "issuer_name", "reference_number", "issue_date"]}},
    {"id": "R-FLD-003", "name": "Affiliation letter: mandatory fields", "rule_type": "required_fields",
     "group": "compliance", "severity": "medium",
     "description": "Affiliation letters must state the institution, identifier, university and affiliation number.",
     "params": {"category": "affiliation_letter",
                "fields": ["institution_name", "institution_id", "issuer_name", "approval_reference",
                           "issue_date", "expiry_date"]}},
    {"id": "R-FLD-004", "name": "Trust / society registration: mandatory fields", "rule_type": "required_fields",
     "group": "compliance", "severity": "medium",
     "description": "Registration certificates must state the registered body, identifier and registration number.",
     "params": {"category": "trust_registration_certificate",
                "fields": ["institution_name", "institution_id", "issuer_name", "reference_number", "issue_date"]}},
    {"id": "R-EXP-001", "name": "Document is within its validity period", "rule_type": "expiry",
     "group": "compliance", "severity": "high",
     "description": "A document whose expiry / valid-until date has passed is not acceptable evidence.",
     "params": {"warn_within_days": 60}},
    {"id": "R-ID-001", "name": "Institution identifier matches the application", "rule_type": "identifier_match",
     "group": "compliance", "severity": "high",
     "description": "The institution identifier printed on each document must equal the applicant's identifier.",
     "params": {}},
    {"id": "R-NAME-001", "name": "Institution name matches the application", "rule_type": "name_match",
     "group": "compliance", "severity": "medium",
     "description": "The institution name on each document should closely match the application.",
     "params": {"min_similarity": 0.85}},
    {"id": "R-TYPE-001", "name": "Document content matches its declared category", "rule_type": "doc_type_match",
     "group": "compliance", "severity": "medium",
     "description": "The classifier's detected document type must agree with the category the document was uploaded under.",
     "params": {"min_confidence": 0.35}},
    {"id": "R-AFF-001", "name": "Affiliation letter states that affiliation is granted", "rule_type": "keyword_present",
     "group": "compliance", "severity": "medium",
     "description": "The affiliation letter must contain an explicit grant / continuation of affiliation statement.",
     "params": {"category": "affiliation_letter",
                "keywords": ["affiliation is hereby granted", "grant of affiliation", "continuation of affiliation",
                             "affiliation is granted", "provisional affiliation"]}},
    {"id": "R-DATE-001", "name": "Issue date is plausible", "rule_type": "issue_date_sanity",
     "group": "compliance", "severity": "medium",
     "description": "Issue dates must not be in the future, must precede the expiry date, and should not be very old.",
     "params": {"max_age_days": 3650,
                "age_exempt_categories": ["trust_registration_certificate", "occupancy_certificate"]}},
    {"id": "R-OCR-001", "name": "OCR quality is sufficient", "rule_type": "ocr_quality",
     "group": "compliance", "severity": "low",
     "description": "Scanned documents read with low OCR confidence need manual reading by the officer.",
     "params": {"min_confidence": 0.80}},
    {"id": "S-META-001", "name": "PDF metadata screening", "rule_type": "screening_pdf_metadata",
     "group": "screening", "severity": "medium",
     "description": "Looks for editing-tool producers, late modification and incremental saves in PDF metadata.",
     "params": {"suspicious_producers": ["photoshop", "gimp", "ilovepdf", "smallpdf", "pdfescape", "sejda",
                                         "foxit phantompdf", "pdf-xchange editor", "canva"],
                "max_modification_gap_days": 30}},
    {"id": "S-DUP-001", "name": "Reused file detection (SHA-256)", "rule_type": "screening_duplicate",
     "group": "screening", "severity": "high",
     "description": "Byte-identical files submitted in another application. A hash shows identical content, "
                    "not whether the original is genuine.",
     "params": {}},
    {"id": "S-IMG-001", "name": "Image consistency screening (ELA)", "rule_type": "screening_image",
     "group": "screening", "severity": "medium",
     "description": "Error-level analysis on JPEG images and EXIF editing-software tags. Heuristic only.",
     "params": {"ela_block_ratio_threshold": 10.0,
                "suspicious_software": ["photoshop", "gimp", "snapseed", "picsart", "canva"]}},
]

RULE_TYPES = {
    "required_document": "Required document categories present",
    "required_fields": "Required fields present in a document category",
    "expiry": "Expiry date not passed",
    "identifier_match": "Institution identifier equals application",
    "name_match": "Institution name similarity",
    "doc_type_match": "Detected type equals declared category",
    "keyword_present": "Document contains one of the keywords",
    "field_pattern": "Field value matches a regular expression",
    "issue_date_sanity": "Issue date plausibility",
    "ocr_quality": "OCR confidence threshold",
    "screening_pdf_metadata": "PDF metadata screening",
    "screening_duplicate": "Duplicate file (hash) screening",
    "screening_image": "Image ELA / EXIF screening",
}
CUSTOM_RULE_TYPES = {"required_fields", "keyword_present", "field_pattern"}


def validate_params(rule_type: str, params: dict) -> dict:
    """Raise ValueError for invalid params; return a cleaned dict."""
    p = dict(params or {})
    if rule_type in ("required_fields", "keyword_present", "field_pattern"):
        cat = p.get("category")
        if cat not in DOCUMENT_CATEGORIES and cat != "any":
            raise ValueError(f"Unknown document category '{cat}'.")
    if rule_type == "required_fields":
        fields = p.get("fields") or []
        bad = [f for f in fields if f not in FIELD_LABELS]
        if not fields or bad:
            raise ValueError(f"fields must be a non-empty list of: {', '.join(FIELD_LABELS)}")
    if rule_type == "required_document":
        bad = [c for c in p.get("categories", []) if c not in DOCUMENT_CATEGORIES]
        if bad:
            raise ValueError(f"Unknown categories: {bad}")
    if rule_type == "keyword_present" and not p.get("keywords"):
        raise ValueError("keywords must be a non-empty list.")
    if rule_type == "field_pattern":
        if p.get("field") not in FIELD_LABELS:
            raise ValueError("field must be one of: " + ", ".join(FIELD_LABELS))
        try:
            re.compile(p.get("pattern") or "")
        except re.error as exc:
            raise ValueError(f"Invalid regular expression: {exc}")
        if not p.get("pattern"):
            raise ValueError("pattern is required.")
    for key in ("min_similarity", "min_confidence"):
        if key in p and not (0 <= float(p[key]) <= 1):
            raise ValueError(f"{key} must be between 0 and 1.")
    for key in ("warn_within_days", "max_age_days", "max_modification_gap_days"):
        if key in p and int(p[key]) < 0:
            raise ValueError(f"{key} must be zero or positive.")
    return p


# ---------------------------------------------------------------- evaluation

def _norm_id(v: str | None) -> str:
    return re.sub(r"\s+", "", (v or "").upper())


def _norm_name(v: str | None) -> str:
    # spacing and punctuation are ignored (OCR often drops spaces); the demo "(Fictional)" tag too
    return re.sub(r"[^a-z0-9]", "", (v or "").lower().replace("fictional", ""))


def name_similarity(a: str, b: str) -> float:
    return round(SequenceMatcher(None, _norm_name(a), _norm_name(b)).ratio(), 3)


def _cat(c: str) -> str:
    return DOCUMENT_CATEGORIES.get(c, c)


def _src(doc, page=None) -> str:
    s = f"{doc.id} · {doc.original_filename}"
    return f"{s} · page {page}" if page else s


class Ctx:
    def __init__(self, app, docs, duplicates: dict, today: date):
        self.app = app
        self.docs = docs
        self.processed = [d for d in docs if d.processing_status == "Processed"]
        self.duplicates = duplicates  # doc_id -> [(other_doc_id, other_app_id)]
        self.today = today


def _f(rule, key, doc, outcome, title, description, action, factor, severity=None, expected=None, actual=None,
       evidence=None, page=None):
    return {
        "fingerprint": f"{rule.id}|{doc.id if doc else '-'}|{key}",
        "rule_id": rule.id, "rule_version": rule.version, "document_id": doc.id if doc else None,
        "outcome": outcome, "severity": severity or rule.severity, "title": title, "description": description,
        "expected": expected, "actual": actual, "evidence": evidence,
        "evidence_source": _src(doc, page) if doc else "Application document list",
        "page": page, "recommended_action": action, "factor": factor,
    }


def _field(doc, name) -> dict:
    return (doc.fields or {}).get(name) or {"status": "missing"}


def r_required_document(rule, ctx):
    present = {d.declared_category for d in ctx.docs if d.processing_status != "Failed"}
    out = []
    submitted = ", ".join(sorted({_cat(d.declared_category) for d in ctx.docs})) or "none"
    for cat in rule.params.get("categories", []):
        if cat not in present:
            out.append(_f(rule, cat, None, "Missing", f"Required document missing: {_cat(cat)}",
                          f"No usable '{_cat(cat)}' was found among the submitted documents.",
                          "Return the application or request the institution to upload this document.",
                          "missing_evidence", expected=_cat(cat), actual=f"Submitted: {submitted}"))
    return out


def r_required_fields(rule, ctx):
    out = []
    cat = rule.params.get("category")
    for d in ctx.processed:
        if cat != "any" and d.declared_category != cat:
            continue
        for name in rule.params.get("fields", []):
            fv = _field(d, name)
            label = FIELD_LABELS.get(name, name)
            if fv["status"] == "missing":
                out.append(_f(rule, name, d, "Review Required", f"Mandatory field not found: {label}",
                              f"'{label}' could not be located in the text of this {_cat(d.declared_category)}.",
                              "Inspect the document manually; request a complete copy if the field is genuinely absent.",
                              "review", expected=f"{label} present", actual="Not found"))
            elif fv["status"] == "uncertain":
                out.append(_f(rule, name + ":uncertain", d, "Review Required", f"Uncertain field value: {label}",
                              f"'{label}' was read as '{fv.get('value')}' but marked uncertain. {fv.get('note') or ''}".strip(),
                              "Confirm the value against the document image.", "uncertain", severity="low",
                              expected=f"{label} clearly readable", actual=fv.get("value"),
                              evidence=fv.get("evidence"), page=fv.get("page")))
    return out


def r_expiry(rule, ctx):
    out = []
    warn = int(rule.params.get("warn_within_days", 0))
    for d in ctx.processed:
        fv = _field(d, "expiry_date")
        if not fv.get("normalized"):
            continue
        exp = date.fromisoformat(fv["normalized"])
        days = (exp - ctx.today).days
        if days < 0:
            out.append(_f(rule, "expired", d, "Expired", f"{_cat(d.declared_category)} expired {-days} days ago",
                          f"The document states it is valid until {fv['value']} ({exp.isoformat()}), which is before "
                          f"the evaluation date {ctx.today.isoformat()}.",
                          "Request a renewed / currently valid certificate from the institution.", "expired",
                          expected=f"Valid on {ctx.today.isoformat()}", actual=f"Expired on {exp.isoformat()}",
                          evidence=fv.get("evidence"), page=fv.get("page")))
        elif days <= warn:
            out.append(_f(rule, "expiring", d, "Review Required", f"{_cat(d.declared_category)} expires in {days} days",
                          f"Valid until {exp.isoformat()}; within the {warn}-day warning window.",
                          "Note the upcoming expiry; consider requesting the renewal in advance.", "review",
                          severity="low", expected=f"Valid beyond {warn} days", actual=f"Expires {exp.isoformat()}",
                          evidence=fv.get("evidence"), page=fv.get("page")))
    return out


def r_identifier_match(rule, ctx):
    out = []
    expected = _norm_id(ctx.app.institution_id)
    for d in ctx.processed:
        fv = _field(d, "institution_id")
        if not fv.get("normalized"):
            continue
        if _norm_id(fv["normalized"]) != expected:
            out.append(_f(rule, "mismatch", d, "Flagged", "Institution identifier does not match the application",
                          f"The document carries identifier '{fv['value']}' but the application is for "
                          f"'{ctx.app.institution_id}'.",
                          "Seek clarification from the institution and verify with the issuing authority.", "flags",
                          expected=ctx.app.institution_id, actual=fv["value"], evidence=fv.get("evidence"),
                          page=fv.get("page")))
    return out


def r_name_match(rule, ctx):
    out = []
    thr = float(rule.params.get("min_similarity", 0.85))
    for d in ctx.processed:
        fv = _field(d, "institution_name")
        if not fv.get("value"):
            continue
        sim = name_similarity(fv["value"], ctx.app.institution_name)
        if sim < thr:
            out.append(_f(rule, "name", d, "Review Required", "Institution name differs from the application",
                          f"Name similarity is {sim:.0%}, below the {thr:.0%} threshold.",
                          "Check whether the document belongs to this institution (e.g. renamed trust or typo).",
                          "review", expected=ctx.app.institution_name, actual=fv["value"],
                          evidence=fv.get("evidence"), page=fv.get("page")))
    return out


def r_doc_type_match(rule, ctx):
    out = []
    thr = float(rule.params.get("min_confidence", 0.35))
    for d in ctx.processed:
        if d.declared_category == "other":
            continue
        det, conf = d.detected_type or "unknown", d.classification_confidence or 0
        if det == "unknown" or conf < thr:
            out.append(_f(rule, "lowconf", d, "Review Required", "Document type could not be confirmed",
                          f"The classifier detected '{_cat(det)}' with confidence {conf:.0%} (threshold {thr:.0%}).",
                          "Open the document and confirm it is the declared type.", "uncertain", severity="low",
                          expected=_cat(d.declared_category), actual=f"{_cat(det)} ({conf:.0%})"))
        elif det != d.declared_category:
            out.append(_f(rule, "mismatch", d, "Flagged", "Document content does not match its declared category",
                          f"Uploaded as '{_cat(d.declared_category)}' but the content reads as '{_cat(det)}' "
                          f"(confidence {conf:.0%}).",
                          "Ask the institution to upload the correct document under this category.", "flags",
                          expected=_cat(d.declared_category), actual=f"{_cat(det)} ({conf:.0%})"))
    return out


def r_keyword_present(rule, ctx):
    out = []
    cat = rule.params.get("category")
    kws = [k.lower() for k in rule.params.get("keywords", [])]
    for d in ctx.processed:
        if cat != "any" and d.declared_category != cat:
            continue
        text = squash(" ".join(p["text"] for p in (d.pages or [])))
        if not any(squash(k) in text for k in kws):
            out.append(_f(rule, "kw", d, "Review Required", f"Expected statement not found ({rule.name})",
                          "None of the expected phrases were found in the document text.",
                          "Read the document to confirm the required approval / affiliation statement.", "review",
                          expected="One of: " + "; ".join(rule.params.get("keywords", [])), actual="Not found"))
    return out


def r_field_pattern(rule, ctx):
    out = []
    cat, field, pattern = rule.params.get("category"), rule.params.get("field"), rule.params.get("pattern")
    rx = re.compile(pattern)
    for d in ctx.processed:
        if cat != "any" and d.declared_category != cat:
            continue
        fv = _field(d, field)
        if fv.get("value") and not rx.fullmatch(str(fv["value"])):
            out.append(_f(rule, field, d, "Review Required", f"{FIELD_LABELS.get(field, field)} format is unexpected",
                          f"Value '{fv['value']}' does not match the configured pattern.",
                          "Verify the value against the issuing authority's format.", "review",
                          expected=f"Matches /{pattern}/", actual=fv["value"], evidence=fv.get("evidence"),
                          page=fv.get("page")))
    return out


def r_issue_date_sanity(rule, ctx):
    out = []
    max_age = int(rule.params.get("max_age_days", 3650))
    exempt = set(rule.params.get("age_exempt_categories", []))
    for d in ctx.processed:
        fi, fe = _field(d, "issue_date"), _field(d, "expiry_date")
        if not fi.get("normalized"):
            continue
        issued = date.fromisoformat(fi["normalized"])
        if issued > ctx.today:
            out.append(_f(rule, "future", d, "Flagged", "Issue date is in the future",
                          f"Issued {issued.isoformat()}, after the evaluation date.",
                          "Verify the date with the issuing authority.", "flags",
                          expected=f"On or before {ctx.today.isoformat()}", actual=issued.isoformat(),
                          evidence=fi.get("evidence"), page=fi.get("page")))
        elif (ctx.today - issued).days > max_age and d.declared_category not in exempt:
            out.append(_f(rule, "old", d, "Review Required", "Document is unusually old",
                          f"Issued {(ctx.today - issued).days} days ago (limit {max_age}).",
                          "Check whether a more recent document is required.", "review", severity="low",
                          expected=f"Issued within {max_age} days", actual=issued.isoformat(),
                          evidence=fi.get("evidence"), page=fi.get("page")))
        if fe.get("normalized") and date.fromisoformat(fe["normalized"]) < issued:
            out.append(_f(rule, "order", d, "Flagged", "Expiry date precedes issue date",
                          "The validity end date is earlier than the issue date.",
                          "Treat dates as unreliable and verify with the issuer.", "flags",
                          expected="Expiry after issue", actual=f"Issued {issued}, expires {fe['normalized']}",
                          evidence=fe.get("evidence"), page=fe.get("page")))
    return out


def r_ocr_quality(rule, ctx):
    out = []
    thr = float(rule.params.get("min_confidence", 0.8))
    for d in ctx.processed:
        if d.ocr_confidence is not None and d.ocr_confidence < thr:
            out.append(_f(rule, "ocr", d, "Review Required", "Low OCR confidence",
                          f"Mean OCR confidence {d.ocr_confidence:.0%} is below {thr:.0%}; extracted values may be wrong.",
                          "Read the document image directly before relying on extracted fields.", "uncertain",
                          expected=f">= {thr:.0%}", actual=f"{d.ocr_confidence:.0%}"))
    return out


def r_screening_pdf_metadata(rule, ctx):
    out = []
    tools = [t.lower() for t in rule.params.get("suspicious_producers", [])]
    gap = int(rule.params.get("max_modification_gap_days", 30))
    for d in ctx.processed:
        s = d.screening or {}
        if s.get("kind") != "pdf":
            continue
        prod = " / ".join(dict.fromkeys(filter(None, [s.get("producer"), s.get("creator")])))
        hit = next((t for t in tools if t in prod.lower()), None)
        if hit:
            out.append(_f(rule, "producer", d, "Screening Signal", "PDF produced or modified with an editing tool",
                          f"Metadata producer/creator is '{prod}'. Editing tools are common for legitimate reasons; "
                          "this is a screening signal, not proof of alteration.",
                          "Compare against the issuer's original or request issuer verification.", "screening",
                          expected="Producer typical of the issuing system", actual=prod))
        if s.get("created") and s.get("modified"):
            from datetime import datetime
            delta = (datetime.fromisoformat(s["modified"]) - datetime.fromisoformat(s["created"])).days
            if delta > gap:
                out.append(_f(rule, "modgap", d, "Screening Signal", "PDF modified long after creation",
                              f"Modified {delta} days after creation (threshold {gap} days).",
                              "Ask the institution why the file was modified after issue.", "screening",
                              severity="low", expected=f"<= {gap} days", actual=f"{delta} days",
                              evidence=f"Created {s['created']} · Modified {s['modified']}"))
        if (s.get("eof_markers") or 0) > 1:
            out.append(_f(rule, "incremental", d, "Screening Signal", "PDF contains incremental updates",
                          f"{s['eof_markers']} end-of-file markers indicate the file was re-saved with changes appended.",
                          "Inspect earlier revisions or request the original from the issuer.", "screening",
                          severity="low", expected="1 revision", actual=f"{s['eof_markers']} revisions"))
        if not any(s.get(k) for k in ("producer", "creator", "created")):
            out.append(_f(rule, "nometa", d, "Screening Signal", "PDF has no producer or date metadata",
                          "Metadata is absent. Some systems strip it; absence alone means little.",
                          "No action needed unless combined with other signals.", "screening", severity="info"))
    return out


def r_screening_duplicate(rule, ctx):
    out = []
    for d in ctx.processed:
        for other_doc, other_app in ctx.duplicates.get(d.id, []):
            same = other_app == ctx.app.id
            out.append(_f(rule, other_doc, d, "Screening Signal" if same else "Flagged",
                          "Identical file submitted twice in this application" if same
                          else f"Identical file also submitted in application {other_app}",
                          f"SHA-256 {d.sha256[:16]}… equals document {other_doc}. Identical bytes indicate a "
                          "re-used file; they do not show whether the original is genuine.",
                          "Remove the duplicate." if same else
                          "Confirm the document truly belongs to this institution; consider issuer verification.",
                          "screening", severity="low" if same else None,
                          expected="Unique file", actual=f"Same as {other_doc} ({other_app})"))
    return out


def r_screening_image(rule, ctx):
    out = []
    thr = float(rule.params.get("ela_block_ratio_threshold", 10.0))
    tools = [t.lower() for t in rule.params.get("suspicious_software", [])]
    for d in ctx.processed:
        s = d.screening or {}
        if s.get("kind") != "image":
            continue
        ela = s.get("ela") or {}
        if ela.get("block_ratio") and ela["block_ratio"] > thr:
            out.append(_f(rule, "ela", d, "Screening Signal", "Uneven JPEG recompression response (ELA)",
                          f"One region responds {ela['block_ratio']}x more than the median region (threshold {thr}). "
                          "This can indicate local editing but also occurs with stamps, signatures or photos.",
                          "Visually inspect the highlighted document; request the original if in doubt.", "screening",
                          expected=f"Block ratio <= {thr}", actual=str(ela["block_ratio"])))
        sw = (s.get("exif_software") or "").lower()
        hit = next((t for t in tools if t in sw), None)
        if hit:
            out.append(_f(rule, "exif", d, "Screening Signal", "Image saved by editing software",
                          f"EXIF software tag: '{s.get('exif_software')}'.",
                          "Request a direct scan or the issuer's original.", "screening",
                          expected="Scanner / camera software", actual=s.get("exif_software")))
    return out


HANDLERS = {
    "required_document": r_required_document, "required_fields": r_required_fields, "expiry": r_expiry,
    "identifier_match": r_identifier_match, "name_match": r_name_match, "doc_type_match": r_doc_type_match,
    "keyword_present": r_keyword_present, "field_pattern": r_field_pattern,
    "issue_date_sanity": r_issue_date_sanity, "ocr_quality": r_ocr_quality,
    "screening_pdf_metadata": r_screening_pdf_metadata, "screening_duplicate": r_screening_duplicate,
    "screening_image": r_screening_image,
}


def evaluate(app, docs, rules, duplicates: dict, today: date) -> list[dict]:
    ctx = Ctx(app, docs, duplicates, today)
    findings = []
    for rule in rules:
        if rule.enabled and rule.rule_type in HANDLERS:
            findings.extend(HANDLERS[rule.rule_type](rule, ctx))
    return findings


OUTCOME_PRIORITY = ["Expired", "Flagged", "Review Required"]


def document_status(doc, findings: list[dict]) -> str:
    if doc.processing_status == "Failed":
        return "Processing Failed"
    if doc.processing_status != "Processed":
        return "Pending Processing"
    mine = [f for f in findings if f["document_id"] == doc.id]
    outcomes = {f["outcome"] for f in mine}
    for o in OUTCOME_PRIORITY:
        if o in outcomes:
            return o
    if any(f["outcome"] == "Screening Signal" and f["severity"] in ("critical", "high", "medium") for f in mine):
        return "Review Required"
    return "Verified"
