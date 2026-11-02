"""VeriAICTE API — AI-assisted application validation prototype (SIH 2026, PS 26261).

Development prototype: there is no authentication. Do not expose it publicly or load real documents
containing personal data.
"""
import logging
import threading
from collections import Counter
from contextlib import asynccontextmanager
from datetime import datetime

import fitz
from fastapi import Depends, FastAPI, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from . import catalog
from .config import AUTO_SEED, CORS_ORIGINS, MAX_UPLOAD_BYTES, MAX_UPLOAD_MB, UPLOAD_DIR
from .database import get_db
from .models import Application, AuditEvent, Document, Finding, ReviewAction, Rule, Setting, next_id, utcnow
from .services import audit, ocr, pipeline, report, rules as rules_mod, scoring
from .services.uploads import UploadRejected, store_file, validate_upload

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("veriaicte")
DEFAULT_OFFICER = "Demo Officer"


@asynccontextmanager
async def lifespan(_):
    from .seed import ensure_defaults, init_db, run
    if AUTO_SEED:
        log.info("Initialising database (seeding synthetic demo data if empty; first run takes ~1 min)…")
        run(reset=False)
    else:
        init_db()
        ensure_defaults()
    threading.Thread(target=ocr.warm_up, daemon=True).start()
    yield


app = FastAPI(
    title="VeriAICTE API",
    version="0.1.0",
    description="AI Verification Co-Pilot — hackathon prototype for SIH 2026 PS 26261. **Not an official AICTE "
                "system.** No authentication: local development use only. All seeded data is synthetic.",
    lifespan=lifespan,
)
app.add_middleware(CORSMiddleware, allow_origins=CORS_ORIGINS, allow_methods=["GET", "POST", "PATCH", "DELETE"],
                   allow_headers=["Content-Type"], expose_headers=["Content-Disposition"])


@app.middleware("http")
async def limit_body(request: Request, call_next):
    # Hard guard against very large bodies (connection is closed without reading them). Ordinary
    # oversize uploads are read up to the limit by the endpoint and get a clean 413 response.
    cl = request.headers.get("content-length")
    if cl and cl.isdigit() and int(cl) > 3 * MAX_UPLOAD_BYTES:
        return JSONResponse({"detail": f"Request body exceeds the {MAX_UPLOAD_MB:g} MB limit."}, status_code=413)
    return await call_next(request)


@app.exception_handler(Exception)
async def unhandled(_, exc: Exception):
    log.exception("Unhandled error")
    return JSONResponse({"detail": "Internal server error. See backend logs."}, status_code=500)


# ------------------------------------------------------------------ serializers

def iso(dt):
    return dt.isoformat() + "Z" if isinstance(dt, datetime) else dt


def app_summary(a: Application) -> dict:
    open_f = [f for f in a.findings if f.status == "Open"]
    return {
        "id": a.id, "institution_name": a.institution_name, "institution_id": a.institution_id,
        "application_type": a.application_type, "state": a.state, "academic_year": a.academic_year,
        "submitted_at": iso(a.submitted_at), "processing_status": a.processing_status,
        "review_status": a.review_status, "risk_score": a.risk_score, "risk_band": a.risk_band,
        "is_demo": a.is_demo, "document_count": len(a.documents), "finding_count": len(a.findings),
        "open_finding_count": len(open_f),
        "outcome_counts": dict(Counter(f.outcome for f in a.findings)),
    }


def doc_summary(d: Document) -> dict:
    return {
        "id": d.id, "application_id": d.application_id, "declared_category": d.declared_category,
        "declared_category_label": catalog.DOCUMENT_CATEGORIES.get(d.declared_category, d.declared_category),
        "original_filename": d.original_filename, "mime_type": d.mime_type, "size_bytes": d.size_bytes,
        "sha256": d.sha256, "page_count": d.page_count, "processing_status": d.processing_status,
        "processing_error": d.processing_error, "extraction_method": d.extraction_method,
        "ocr_engine": d.ocr_engine, "ocr_confidence": d.ocr_confidence, "detected_type": d.detected_type,
        "detected_type_label": catalog.DOCUMENT_CATEGORIES.get(d.detected_type, d.detected_type),
        "classification_confidence": d.classification_confidence, "document_status": d.document_status,
        "issuer_verification": d.issuer_verification, "is_demo": d.is_demo, "uploaded_at": iso(d.uploaded_at),
        "processed_at": iso(d.processed_at),
    }


def doc_detail(d: Document) -> dict:
    return {**doc_summary(d), "pages": d.pages or [], "fields": d.fields or {}, "screening": d.screening or {},
            "classification_scores": d.classification_scores or {}}


def finding_out(f: Finding) -> dict:
    return {c: (iso(getattr(f, c))) for c in (
        "id", "application_id", "document_id", "rule_id", "rule_version", "outcome", "severity", "title",
        "description", "expected", "actual", "evidence", "evidence_source", "page", "recommended_action",
        "factor", "status", "reviewer_note", "reviewed_by", "reviewed_at", "created_at")}


def rule_out(r: Rule) -> dict:
    return {"id": r.id, "name": r.name, "description": r.description, "rule_type": r.rule_type,
            "rule_type_label": rules_mod.RULE_TYPES.get(r.rule_type, r.rule_type), "group": r.group,
            "params": r.params, "severity": r.severity, "enabled": r.enabled, "version": r.version,
            "is_builtin": r.is_builtin, "updated_at": iso(r.updated_at)}


def audit_out(e: AuditEvent) -> dict:
    return {"id": e.id, "application_id": e.application_id, "event_type": e.event_type, "actor": e.actor,
            "details": e.details, "created_at": e.created_at, "prev_hash": e.prev_hash, "hash": e.hash}


def review_out(r: ReviewAction) -> dict:
    return {"id": r.id, "action": r.action, "action_label": catalog.REVIEW_ACTIONS.get(r.action, (None, r.action))[1],
            "notes": r.notes, "officer_name": r.officer_name, "created_at": iso(r.created_at)}


def get_app_or_404(db, app_id) -> Application:
    a = db.get(Application, app_id)
    if a is None:
        raise HTTPException(404, f"Application {app_id} not found.")
    return a


def get_doc_or_404(db, doc_id) -> Document:
    d = db.get(Document, doc_id)
    if d is None:
        raise HTTPException(404, f"Document {doc_id} not found.")
    return d


# ------------------------------------------------------------------ meta / dashboard

@app.get("/api/health", tags=["meta"])
def health(db: Session = Depends(get_db)):
    db.execute(select(1))
    return {"status": "ok", "database": "ok", "ocr": ocr.status(), "max_upload_mb": MAX_UPLOAD_MB,
            "authentication": "none (development prototype)", "version": app.version}


@app.get("/api/meta", tags=["meta"])
def meta():
    return {"document_categories": catalog.DOCUMENT_CATEGORIES, "application_types": catalog.APPLICATION_TYPES,
            "review_actions": {k: {"label": v[1], "resulting_status": v[0]} for k, v in catalog.REVIEW_ACTIONS.items()},
            "fields": catalog.FIELD_LABELS, "rule_types": rules_mod.RULE_TYPES,
            "custom_rule_types": sorted(rules_mod.CUSTOM_RULE_TYPES), "severities": catalog.SEVERITIES,
            "max_upload_mb": MAX_UPLOAD_MB, "accepted_types": [".pdf", ".jpg", ".jpeg", ".png"]}


@app.get("/api/dashboard", tags=["dashboard"])
def dashboard(db: Session = Depends(get_db)):
    apps = list(db.execute(select(Application).order_by(Application.submitted_at.desc())).scalars())
    docs = list(db.execute(select(Document)).scalars())
    findings = list(db.execute(select(Finding)).scalars())
    status_counts = Counter(d.document_status for d in docs)
    missing_or_expired = sum(1 for f in findings if f.outcome in ("Missing", "Expired"))
    events = db.execute(select(AuditEvent).order_by(AuditEvent.id.desc()).limit(12)).scalars()
    return {
        "totals": {
            "applications": len(apps),
            "pending_reviews": sum(1 for a in apps if a.review_status == "Pending Review"),
            "documents": len(docs),
            "verified_documents": status_counts.get("Verified", 0),
            "flagged_documents": status_counts.get("Flagged", 0),
            "review_required_documents": status_counts.get("Review Required", 0),
            "expired_documents": status_counts.get("Expired", 0),
            "missing_or_expired": missing_or_expired,
            "missing_documents": sum(1 for f in findings if f.outcome == "Missing"),
            "open_findings": sum(1 for f in findings if f.status == "Open"),
            "demo_applications": sum(1 for a in apps if a.is_demo),
        },
        "risk_distribution": [{"band": b, "count": sum(1 for a in apps if a.risk_band == b)}
                              for b in ("Low", "Medium", "High")]
                             + [{"band": "Not evaluated", "count": sum(1 for a in apps if a.risk_band is None)}],
        "document_status": dict(status_counts),
        "findings_by_outcome": dict(Counter(f.outcome for f in findings)),
        "recent_applications": [app_summary(a) for a in apps[:6]],
        "recent_activity": [audit_out(e) for e in events],
    }


# ------------------------------------------------------------------ applications

class ApplicationIn(BaseModel):
    institution_name: str = Field(min_length=3, max_length=200)
    institution_id: str = Field(min_length=3, max_length=40, pattern=r"^[A-Za-z0-9][A-Za-z0-9\-/]*$")
    application_type: str = Field(min_length=3, max_length=80)
    state: str = Field(default="", max_length=60)
    academic_year: str = Field(default="2026-27", max_length=20)
    officer_name: str = Field(default=DEFAULT_OFFICER, max_length=80)


@app.get("/api/applications", tags=["applications"])
def list_applications(q: str | None = None, review_status: str | None = None, risk_band: str | None = None,
                      application_type: str | None = None, processing_status: str | None = None,
                      db: Session = Depends(get_db)):
    stmt = select(Application).order_by(Application.submitted_at.desc())
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(or_(Application.id.ilike(like), Application.institution_name.ilike(like),
                              Application.institution_id.ilike(like)))
    if review_status:
        stmt = stmt.where(Application.review_status == review_status)
    if risk_band:
        stmt = stmt.where(Application.risk_band == risk_band) if risk_band != "Not evaluated" \
            else stmt.where(Application.risk_band.is_(None))
    if application_type:
        stmt = stmt.where(Application.application_type == application_type)
    if processing_status:
        stmt = stmt.where(Application.processing_status == processing_status)
    return [app_summary(a) for a in db.execute(stmt).scalars()]


@app.post("/api/applications", status_code=201, tags=["applications"])
def create_application(body: ApplicationIn, db: Session = Depends(get_db)):
    a = Application(id=next_id(db, "application", "APP-2026-", 4), institution_name=body.institution_name.strip(),
                    institution_id=body.institution_id.strip().upper(), application_type=body.application_type,
                    state=body.state.strip(), academic_year=body.academic_year.strip(), submitted_at=utcnow())
    db.add(a)
    db.flush()
    audit.record(db, "application_created", body.officer_name, a.id,
                 {"institution_id": a.institution_id, "application_type": a.application_type})
    pipeline.evaluate_application(db, a, body.officer_name)
    db.commit()
    return app_summary(a)


@app.get("/api/applications/{app_id}", tags=["applications"])
def get_application(app_id: str, db: Session = Depends(get_db)):
    a = get_app_or_404(db, app_id)
    return {**app_summary(a), "documents": [doc_summary(d) for d in a.documents],
            "findings": [finding_out(f) for f in a.findings], "reviews": [review_out(r) for r in a.reviews],
            "score_breakdown": a.score_breakdown, "applied_rules": a.applied_rules,
            "ruleset_fingerprint": a.ruleset_fingerprint, "last_evaluated_at": iso(a.last_evaluated_at)}


@app.delete("/api/applications/{app_id}", tags=["applications"])
def delete_application(app_id: str, officer_name: str = DEFAULT_OFFICER, db: Session = Depends(get_db)):
    a = get_app_or_404(db, app_id)
    if a.is_demo:
        raise HTTPException(409, "Seeded demo applications cannot be deleted here; use 'python -m app.seed --reset'.")
    for d in a.documents:
        (UPLOAD_DIR / d.stored_filename).unlink(missing_ok=True)
    audit.record(db, "application_deleted", officer_name, a.id, {"documents_removed": len(a.documents)})
    db.delete(a)
    db.commit()
    return {"deleted": app_id}


@app.post("/api/applications/{app_id}/evaluate", tags=["applications"])
def evaluate(app_id: str, officer_name: str = DEFAULT_OFFICER, db: Session = Depends(get_db)):
    a = get_app_or_404(db, app_id)
    pipeline.evaluate_application(db, a, officer_name)
    db.commit()
    return get_application(app_id, db)


@app.get("/api/applications/{app_id}/findings", tags=["findings"])
def list_findings(app_id: str, db: Session = Depends(get_db)):
    return [finding_out(f) for f in get_app_or_404(db, app_id).findings]


# ------------------------------------------------------------------ documents

@app.post("/api/applications/{app_id}/documents", status_code=201, tags=["documents"])
async def upload_document(app_id: str, file: UploadFile = File(...), category: str = Form(...),
                          officer_name: str = Form(DEFAULT_OFFICER), process: bool = Query(False),
                          db: Session = Depends(get_db)):
    a = get_app_or_404(db, app_id)
    if category not in catalog.DOCUMENT_CATEGORIES:
        raise HTTPException(422, f"Unknown document category '{category}'.")
    data = await file.read(MAX_UPLOAD_BYTES + 1)
    try:
        vf = validate_upload(file.filename or "", file.content_type, data)
    except UploadRejected as exc:
        audit.record(db, "upload_rejected", officer_name, a.id, {"filename": (file.filename or "")[:150],
                                                                  "reason": str(exc)})
        db.commit()
        status = 413 if "limit" in str(exc) and "MB" in str(exc) else 415 if "Unsupported" in str(exc) else 422
        raise HTTPException(status, str(exc))
    stored = store_file(UPLOAD_DIR, vf)
    d = Document(id=next_id(db, "document", "DOC-", 5), application_id=a.id, declared_category=category,
                 original_filename=vf.safe_name, stored_filename=stored, storage="upload", mime_type=vf.mime_type,
                 size_bytes=len(vf.data), sha256=vf.sha256, page_count=vf.page_count)
    db.add(d)
    db.flush()
    audit.record(db, "document_uploaded", officer_name, a.id, {"document_id": d.id, "category": category,
                                                                "filename": vf.safe_name, "sha256": vf.sha256,
                                                                "size_bytes": len(vf.data)})
    if process:
        pipeline.process_document(db, d, officer_name)
    db.refresh(a)  # reload the documents relationship
    pipeline.evaluate_application(db, a, officer_name)
    db.commit()
    return doc_summary(d)


@app.get("/api/documents/{doc_id}", tags=["documents"])
def get_document(doc_id: str, db: Session = Depends(get_db)):
    d = get_doc_or_404(db, doc_id)
    return {**doc_detail(d), "findings": [finding_out(f) for f in d.application.findings if f.document_id == d.id]}


@app.post("/api/documents/{doc_id}/process", tags=["documents"])
def process_document(doc_id: str, officer_name: str = DEFAULT_OFFICER, db: Session = Depends(get_db)):
    d = get_doc_or_404(db, doc_id)
    pipeline.process_document(db, d, officer_name)
    pipeline.evaluate_application(db, d.application, officer_name)
    db.commit()
    return get_document(doc_id, db)


@app.get("/api/documents/{doc_id}/preview", tags=["documents"],
         responses={200: {"content": {"image/png": {}}}})
def preview(doc_id: str, page: int = Query(1, ge=1), db: Session = Depends(get_db)):
    """Renders a page as PNG. Files are only reachable by document ID through this endpoint."""
    d = get_doc_or_404(db, doc_id)
    path = pipeline.file_path(d)
    if not path.exists():
        raise HTTPException(404, "Stored file is no longer available.")
    try:
        if d.mime_type == "application/pdf":
            with fitz.open(path) as pdf:
                if page > pdf.page_count:
                    raise HTTPException(404, "Page out of range.")
                png = pdf[page - 1].get_pixmap(matrix=fitz.Matrix(1.4, 1.4), alpha=False).tobytes("png")
        else:
            pix = fitz.Pixmap(str(path))
            if pix.alpha or pix.n > 3:
                pix = fitz.Pixmap(fitz.csRGB, pix)
            if pix.width > 1400:
                pix = fitz.Pixmap(pix, 1400, int(pix.height * 1400 / pix.width))
            png = pix.tobytes("png")
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(422, "Preview could not be rendered for this file.")
    return Response(png, media_type="image/png", headers={"Cache-Control": "private, max-age=300"})


@app.delete("/api/documents/{doc_id}", tags=["documents"])
def delete_document(doc_id: str, officer_name: str = DEFAULT_OFFICER, db: Session = Depends(get_db)):
    d = get_doc_or_404(db, doc_id)
    if d.is_demo:
        raise HTTPException(409, "Seeded demo documents cannot be deleted; reset demo data instead.")
    a = d.application
    (UPLOAD_DIR / d.stored_filename).unlink(missing_ok=True)
    audit.record(db, "document_deleted", officer_name, a.id, {"document_id": d.id, "filename": d.original_filename})
    a.documents.remove(d)
    db.delete(d)
    db.flush()
    pipeline.evaluate_application(db, a, officer_name)
    db.commit()
    return {"deleted": doc_id}


# ------------------------------------------------------------------ findings & review

class FindingPatch(BaseModel):
    status: str = Field(pattern="^(Open|Reviewed)$")
    note: str = Field(default="", max_length=2000)
    officer_name: str = Field(default=DEFAULT_OFFICER, min_length=2, max_length=80)


@app.patch("/api/findings/{finding_id}", tags=["findings"])
def update_finding(finding_id: str, body: FindingPatch, db: Session = Depends(get_db)):
    f = db.get(Finding, finding_id)
    if f is None:
        raise HTTPException(404, f"Finding {finding_id} not found.")
    f.status = body.status
    f.reviewer_note = body.note or f.reviewer_note
    f.reviewed_by = body.officer_name
    f.reviewed_at = utcnow()
    audit.record(db, "finding_reviewed" if body.status == "Reviewed" else "finding_reopened", body.officer_name,
                 f.application_id, {"finding_id": f.id, "rule_id": f.rule_id, "note": body.note})
    db.commit()
    return finding_out(f)


class ReviewIn(BaseModel):
    action: str
    notes: str = Field(default="", max_length=4000)
    officer_name: str = Field(min_length=2, max_length=80)
    document_ids: list[str] = Field(default_factory=list, description="for request_issuer_verification")


@app.post("/api/applications/{app_id}/review", status_code=201, tags=["review"])
def record_review(app_id: str, body: ReviewIn, db: Session = Depends(get_db)):
    a = get_app_or_404(db, app_id)
    if body.action not in catalog.REVIEW_ACTIONS:
        raise HTTPException(422, f"Unknown action. Allowed: {', '.join(catalog.REVIEW_ACTIONS)}")
    if body.action != "add_note" and len(body.notes.strip()) < 5:
        raise HTTPException(422, "Please record notes (at least 5 characters) explaining the decision.")
    if body.action == "provisional_recommendation" and a.processing_status != "Processed":
        raise HTTPException(409, "All documents must be processed before recording a recommendation.")
    new_status, _ = catalog.REVIEW_ACTIONS[body.action]
    details = {"action": body.action, "notes": body.notes, "previous_status": a.review_status}
    if body.action == "request_issuer_verification":
        targets = [d for d in a.documents if not body.document_ids or d.id in body.document_ids]
        for d in targets:
            d.issuer_verification = "Pending (simulated - no issuer integration)"
        details["documents"] = [d.id for d in targets]
    if body.action == "provisional_recommendation":
        details["open_findings_at_decision"] = sum(1 for f in a.findings if f.status == "Open")
        details["risk_score_at_decision"] = a.risk_score
    if new_status:
        a.review_status = new_status
    r = ReviewAction(application_id=a.id, action=body.action, notes=body.notes.strip(), officer_name=body.officer_name)
    db.add(r)
    a.reviews.append(r)
    audit.record(db, "review_action", body.officer_name, a.id, {**details, "new_status": a.review_status})
    db.commit()
    return {"review": review_out(r), "application": app_summary(a)}


# ------------------------------------------------------------------ rules & scoring

class RulePatch(BaseModel):
    enabled: bool | None = None
    severity: str | None = Field(default=None, pattern="^(critical|high|medium|low|info)$")
    params: dict | None = None
    name: str | None = Field(default=None, max_length=160)
    officer_name: str = Field(default=DEFAULT_OFFICER, max_length=80)


class RuleIn(BaseModel):
    name: str = Field(min_length=4, max_length=160)
    description: str = Field(default="", max_length=1000)
    rule_type: str
    severity: str = Field(default="medium", pattern="^(critical|high|medium|low|info)$")
    params: dict
    officer_name: str = Field(default=DEFAULT_OFFICER, max_length=80)


@app.get("/api/rules", tags=["rules"])
def list_rules(db: Session = Depends(get_db)):
    rules = list(db.execute(select(Rule).order_by(Rule.group, Rule.id)).scalars())
    cfg, ver = pipeline.get_scoring(db)
    return {"rules": [rule_out(r) for r in rules], "ruleset_fingerprint": pipeline.ruleset_fingerprint(rules, ver)}


@app.patch("/api/rules/{rule_id}", tags=["rules"])
def update_rule(rule_id: str, body: RulePatch, db: Session = Depends(get_db)):
    r = db.get(Rule, rule_id)
    if r is None:
        raise HTTPException(404, f"Rule {rule_id} not found.")
    before = rule_out(r)
    changed = False
    if body.params is not None:
        try:
            params = rules_mod.validate_params(r.rule_type, {**r.params, **body.params})
        except (ValueError, TypeError) as exc:
            raise HTTPException(422, str(exc))
        if params != r.params:
            r.params, changed = params, True
    for attr in ("enabled", "severity", "name"):
        v = getattr(body, attr)
        if v is not None and v != getattr(r, attr):
            setattr(r, attr, v)
            changed = True
    if changed:
        r.version += 1
        r.updated_at = utcnow()
        audit.record(db, "rule_updated", body.officer_name, None, {
            "rule_id": r.id, "new_version": r.version,
            "before": {k: before[k] for k in ("enabled", "severity", "params", "version")},
            "after": {"enabled": r.enabled, "severity": r.severity, "params": r.params}})
    db.commit()
    return rule_out(r)


@app.post("/api/rules", status_code=201, tags=["rules"])
def create_rule(body: RuleIn, db: Session = Depends(get_db)):
    if body.rule_type not in rules_mod.CUSTOM_RULE_TYPES:
        raise HTTPException(422, f"Custom rules may use: {', '.join(sorted(rules_mod.CUSTOM_RULE_TYPES))}")
    try:
        params = rules_mod.validate_params(body.rule_type, body.params)
    except (ValueError, TypeError) as exc:
        raise HTTPException(422, str(exc))
    n = db.execute(select(func.count()).select_from(Rule).where(Rule.is_builtin.is_(False))).scalar_one()
    r = Rule(id=f"R-CUS-{n + 1:03d}", name=body.name, description=body.description or body.name,
             rule_type=body.rule_type, group="compliance", params=params, severity=body.severity, enabled=True,
             version=1, is_builtin=False)
    while db.get(Rule, r.id):
        n += 1
        r.id = f"R-CUS-{n + 1:03d}"
    db.add(r)
    audit.record(db, "rule_created", body.officer_name, None, {"rule_id": r.id, "rule_type": r.rule_type,
                                                               "params": params, "severity": r.severity})
    db.commit()
    return rule_out(r)


@app.get("/api/settings/scoring", tags=["rules"])
def get_scoring(db: Session = Depends(get_db)):
    cfg, ver = pipeline.get_scoring(db)
    db.commit()
    return {"config": cfg, "version": ver, "disclaimer": scoring.DISCLAIMER, "factor_labels": scoring.FACTOR_LABELS}


class ScoringPatch(BaseModel):
    severity_points: dict[str, float] | None = None
    factor_weights: dict[str, float] | None = None
    bands: dict[str, float] | None = None
    officer_name: str = Field(default=DEFAULT_OFFICER, max_length=80)


@app.patch("/api/settings/scoring", tags=["rules"])
def update_scoring(body: ScoringPatch, db: Session = Depends(get_db)):
    pipeline.get_scoring(db)
    s = db.get(Setting, "scoring")
    cfg = {k: dict(v) for k, v in s.value.items()}
    for key in ("severity_points", "factor_weights", "bands"):
        patch = getattr(body, key)
        if patch:
            unknown = set(patch) - set(cfg[key])
            if unknown:
                raise HTTPException(422, f"Unknown {key} keys: {sorted(unknown)}")
            if any(v < 0 or v > 100 for v in patch.values()):
                raise HTTPException(422, "Values must be between 0 and 100.")
            cfg[key].update(patch)
    if cfg["bands"]["medium"] >= cfg["bands"]["high"]:
        raise HTTPException(422, "The medium band threshold must be below the high band threshold.")
    s.value, s.version = cfg, s.version + 1
    audit.record(db, "scoring_updated", body.officer_name, None, {"version": s.version, "config": cfg})
    db.commit()
    return {"config": cfg, "version": s.version}


@app.post("/api/evaluate-all", tags=["rules"])
def evaluate_all(officer_name: str = DEFAULT_OFFICER, db: Session = Depends(get_db)):
    """Re-run the current rules against every application (e.g. after editing rules)."""
    apps = list(db.execute(select(Application)).scalars())
    for a in apps:
        pipeline.evaluate_application(db, a, officer_name)
    db.commit()
    return {"evaluated": len(apps)}


# ------------------------------------------------------------------ reports & audit

@app.get("/api/applications/{app_id}/report", tags=["reports"], responses={200: {"content": {"application/pdf": {}}}})
def download_report(app_id: str, officer_name: str = DEFAULT_OFFICER, db: Session = Depends(get_db)):
    a = get_app_or_404(db, app_id)
    audit.record(db, "report_generated", officer_name, a.id, {"ruleset_fingerprint": a.ruleset_fingerprint,
                                                               "risk_score": a.risk_score})
    db.commit()
    events = list(db.execute(select(AuditEvent).where(AuditEvent.application_id == a.id)
                             .order_by(AuditEvent.id)).scalars())
    pdf = report.build_report(a, events, audit.verify_chain(db))
    return Response(pdf, media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="VeriAICTE_Report_{a.id}.pdf"'})


@app.get("/api/applications/{app_id}/audit-log", tags=["audit"])
def app_audit(app_id: str, db: Session = Depends(get_db)):
    get_app_or_404(db, app_id)
    return [audit_out(e) for e in db.execute(select(AuditEvent).where(AuditEvent.application_id == app_id)
                                             .order_by(AuditEvent.id.desc())).scalars()]


@app.get("/api/audit-log", tags=["audit"])
def global_audit(limit: int = Query(100, ge=1, le=1000), event_type: str | None = None,
                 db: Session = Depends(get_db)):
    stmt = select(AuditEvent).order_by(AuditEvent.id.desc()).limit(limit)
    if event_type:
        stmt = stmt.where(AuditEvent.event_type == event_type)
    return [audit_out(e) for e in db.execute(stmt).scalars()]


@app.get("/api/audit/verify", tags=["audit"])
def verify_audit(db: Session = Depends(get_db)):
    return audit.verify_chain(db)
