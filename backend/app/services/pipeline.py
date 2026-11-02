"""Orchestrates document processing and application evaluation."""
import hashlib
import json
import logging
from pathlib import Path

from sqlalchemy import select

from ..config import DEMO_DIR, UPLOAD_DIR
from ..models import Application, Document, Finding, Rule, Setting, next_id, utcnow
from . import audit, extraction, fields, rules as rules_mod, screening, scoring
from .ocr import OCRUnavailable

log = logging.getLogger("veriaicte.pipeline")


def file_path(doc: Document) -> Path:
    return (DEMO_DIR if doc.storage == "demo" else UPLOAD_DIR) / doc.stored_filename


def get_scoring(db) -> tuple[dict, int]:
    s = db.get(Setting, "scoring")
    if s is None:
        s = Setting(key="scoring", value=scoring.DEFAULT_SCORING, version=1)
        db.add(s)
        db.flush()
    return s.value, s.version


def process_document(db, doc: Document, actor: str = "system") -> Document:
    path = file_path(doc)
    try:
        data = path.read_bytes()
        result = extraction.extract_text(path, doc.mime_type)
        doc.pages = result.pages
        doc.extraction_method = result.method
        doc.ocr_engine = result.ocr_engine
        doc.ocr_confidence = result.ocr_confidence
        if not result.full_text.strip():
            raise ValueError("No text could be extracted from the document (blank page or unreadable scan).")
        doc.fields = fields.extract_fields(result.pages)
        doc.detected_type, doc.classification_confidence, doc.classification_scores = fields.classify(result.full_text)
        doc.screening = (screening.pdf_facts(data) if doc.mime_type == "application/pdf"
                         else screening.image_facts(data, doc.mime_type))
        doc.processing_status = "Processed"
        doc.processing_error = None
    except OCRUnavailable as exc:
        doc.processing_status, doc.processing_error = "Failed", str(exc)
    except Exception as exc:
        log.exception("Processing failed for %s", doc.id)
        doc.processing_status = "Failed"
        doc.processing_error = str(exc) if isinstance(exc, ValueError) else f"Processing error: {exc.__class__.__name__}"
    doc.processed_at = utcnow()
    db.flush()
    audit.record(db, "document_processed", actor, doc.application_id, {
        "document_id": doc.id, "status": doc.processing_status, "method": doc.extraction_method,
        "ocr_engine": doc.ocr_engine, "detected_type": doc.detected_type, "error": doc.processing_error,
        "fields_detected": sum(1 for f in (doc.fields or {}).values() if f["status"] == "detected"),
    })
    return doc


def ruleset_fingerprint(rules: list[Rule], scoring_version: int) -> str:
    sig = json.dumps([[r.id, r.version, r.enabled] for r in sorted(rules, key=lambda r: r.id)] + [scoring_version])
    return hashlib.sha256(sig.encode()).hexdigest()[:12]


def _duplicates(db, docs: list[Document]) -> dict:
    out = {}
    for d in docs:
        others = db.execute(select(Document.id, Document.application_id)
                            .where(Document.sha256 == d.sha256, Document.id != d.id)).all()
        if others:
            out[d.id] = [(o.id, o.application_id) for o in others]
    return out


def evaluate_application(db, app: Application, actor: str = "system") -> Application:
    all_rules = list(db.execute(select(Rule)).scalars())
    cfg, scoring_version = get_scoring(db)
    docs = list(app.documents)
    today = fields.today()
    new = rules_mod.evaluate(app, docs, all_rules, _duplicates(db, docs), today)

    # carry over officer review state for findings that persist across re-evaluation
    previous = {f.fingerprint: f for f in app.findings}
    keep_ids = set()
    for fd in new:
        old = previous.get(fd["fingerprint"])
        if old:
            for k, v in fd.items():
                setattr(old, k, v)
            fd["id"] = old.id
            keep_ids.add(old.id)
        else:
            f = Finding(id=next_id(db, "finding", "FND-", 5), application_id=app.id, **fd)
            db.add(f)
            app.findings.append(f)
            fd["id"] = f.id
    for f in list(app.findings):
        if f.id not in keep_ids and f.fingerprint in previous:
            app.findings.remove(f)
            db.delete(f)

    for d in docs:
        d.document_status = rules_mod.document_status(d, new)

    if not docs:
        app.processing_status, app.risk_score, app.risk_band = "Awaiting Documents", None, None
    elif any(d.processing_status == "Uploaded" for d in docs):
        app.processing_status = "Processing"
    else:
        app.processing_status = "Processed"

    result = scoring.compute(new, cfg)
    if docs:
        app.risk_score, app.risk_band = result["score"], result["band"]
    result["scoring_version"] = scoring_version
    app.score_breakdown = result
    enabled = [r for r in all_rules if r.enabled]
    app.applied_rules = [{"id": r.id, "version": r.version, "name": r.name, "group": r.group} for r in
                         sorted(enabled, key=lambda r: r.id)]
    app.ruleset_fingerprint = ruleset_fingerprint(all_rules, scoring_version)
    app.last_evaluated_at = utcnow()
    db.flush()
    audit.record(db, "application_evaluated", actor, app.id, {
        "risk_score": app.risk_score, "risk_band": app.risk_band, "findings": len(new),
        "ruleset_fingerprint": app.ruleset_fingerprint, "rules_applied": len(enabled),
    })
    return app
