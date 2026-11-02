"""Core validation-rule, extraction, upload and workflow tests."""
from datetime import date, timedelta
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app import sample_docs as sd
from app.services import fields, rules, scoring
from app.services.ocr import engine_name
from app.services.uploads import UploadRejected, validate_upload

TODAY = date(2026, 10, 26)
APP = SimpleNamespace(id="APP-T", institution_id="SYN-INST-11111", institution_name="Test Institute (Fictional)")


def _rule(rule_id):
    spec = next(r for r in rules.DEFAULT_RULES if r["id"] == rule_id)
    return SimpleNamespace(**spec, version=1, enabled=True)


def _doc(category, text, doc_id="DOC-T1", **kw):
    pages = [{"page": 1, "text": text, "method": "text", "confidence": None}]
    det, conf, _ = fields.classify(text)
    base = dict(id=doc_id, declared_category=category, original_filename="t.pdf", processing_status="Processed",
                pages=pages, fields=fields.extract_fields(pages), detected_type=det, classification_confidence=conf,
                screening={}, ocr_confidence=None, sha256="x" * 64)
    base.update(kw)
    return SimpleNamespace(**base)


FIRE_OK = """FIRE SAFETY NO OBJECTION CERTIFICATE
Certificate No.: FES/NOC/2026/1
Name of the Institution: Test Institute (Fictional)
Institution ID: SYN-INST-11111
Date of Issue: 01/01/2026
Valid Until: 31 December 2027
Issued By: Chief Fire Officer
fire safety extinguishers evacuation no objection"""


def run(rule_id, docs):
    r = _rule(rule_id)
    return rules.HANDLERS[r.rule_type](r, rules.Ctx(APP, docs, {}, TODAY))


# ---------------------------------------------------------------- extraction

def test_field_extraction_and_dates():
    f = fields.extract_fields([{"page": 1, "text": FIRE_OK, "method": "text"}])
    assert f["institution_id"]["normalized"] == "SYN-INST-11111"
    assert f["issue_date"]["normalized"] == "2026-01-01"
    assert f["expiry_date"]["normalized"] == "2027-12-31"
    assert f["issuer_name"]["status"] == "detected"
    assert f["approval_reference"]["status"] == "missing"  # never invented


def test_ocr_style_text_without_spaces():
    text = "NameoftheInstitution:Test Institute\nInstitutionID:SYN-INST-11111\nDateoflssue:13January2012"
    f = fields.extract_fields([{"page": 1, "text": text, "method": "ocr", "confidence": 0.95}])
    assert f["institution_id"]["value"] == "SYN-INST-11111"
    assert f["issue_date"]["normalized"] == "2012-01-13"


def test_low_ocr_confidence_marks_uncertain():
    f = fields.extract_fields([{"page": 1, "text": "Institution ID: SYN-INST-11111", "method": "ocr", "confidence": 0.5}])
    assert f["institution_id"]["status"] == "uncertain"


def test_classifier():
    assert fields.classify(FIRE_OK)[0] == "fire_safety_certificate"
    assert fields.classify("hello world")[0] == "unknown"


# ---------------------------------------------------------------- rules

def test_valid_document_passes_core_rules():
    d = _doc("fire_safety_certificate", FIRE_OK)
    for rid in ("R-FLD-001", "R-EXP-001", "R-ID-001", "R-NAME-001", "R-TYPE-001", "R-DATE-001"):
        assert run(rid, [d]) == [], rid


def test_missing_required_document():
    out = run("R-DOC-001", [_doc("fire_safety_certificate", FIRE_OK)])
    assert {f["outcome"] for f in out} == {"Missing"}
    assert len(out) == 3


def test_expired_document():
    d = _doc("fire_safety_certificate", FIRE_OK.replace("31 December 2027", "01/06/2026"))
    out = run("R-EXP-001", [d])
    assert out and out[0]["outcome"] == "Expired" and out[0]["page"] == 1
    assert "2026-06-01" in out[0]["actual"]


def test_missing_mandatory_field():
    d = _doc("fire_safety_certificate", FIRE_OK.replace("Valid Until: 31 December 2027\n", ""))
    out = run("R-FLD-001", [d])
    assert [f["outcome"] for f in out] == ["Review Required"]
    assert "Expiry" in out[0]["title"]


def test_identifier_mismatch_is_flagged():
    d = _doc("fire_safety_certificate", FIRE_OK.replace("SYN-INST-11111", "SYN-INST-11112"))
    out = run("R-ID-001", [d])
    assert out[0]["outcome"] == "Flagged"
    assert out[0]["expected"] == "SYN-INST-11111" and out[0]["actual"] == "SYN-INST-11112"


def test_doc_type_mismatch():
    d = _doc("affiliation_letter", FIRE_OK)
    assert run("R-TYPE-001", [d])[0]["outcome"] == "Flagged"


def test_custom_field_pattern_rule():
    r = SimpleNamespace(id="R-CUS-001", version=1, enabled=True, severity="medium", rule_type="field_pattern",
                        name="Fire NOC number format",
                        params=rules.validate_params("field_pattern", {"category": "fire_safety_certificate",
                                                                       "field": "reference_number",
                                                                       "pattern": r"FES/NOC/\d{4}/\d{5}"}))
    out = rules.r_field_pattern(r, rules.Ctx(APP, [_doc("fire_safety_certificate", FIRE_OK)], {}, TODAY))
    assert out and out[0]["actual"] == "FES/NOC/2026/1"
    with pytest.raises(ValueError):
        rules.validate_params("field_pattern", {"category": "affiliation_letter", "field": "x", "pattern": "("})


def test_score_reflects_findings():
    cfg = scoring.DEFAULT_SCORING
    assert scoring.compute([], cfg)["score"] == 0
    f = [{"severity": "high", "factor": "expired", "rule_id": "R", "title": "t"},
         {"severity": "medium", "factor": "screening", "rule_id": "S", "title": "t"}]
    res = scoring.compute(f, cfg)
    assert res["score"] == 25 + 6 and res["band"] == "Medium"
    assert scoring.compute(f * 5, cfg)["score"] == 100


# ---------------------------------------------------------------- uploads

def test_upload_validation_rejects_bad_files():
    with pytest.raises(UploadRejected):
        validate_upload("x.exe", "application/octet-stream", b"MZ....")
    with pytest.raises(UploadRejected):
        validate_upload("fake.pdf", "application/pdf", b"just text")
    with pytest.raises(UploadRejected):
        validate_upload("broken.pdf", "application/pdf", b"%PDF-1.4 garbage")
    with pytest.raises(UploadRejected):
        validate_upload("img.png", "image/jpeg", b"\x89PNG\r\n\x1a\n")


def test_filename_traversal_is_neutralised():
    pdf = sd.make_pdf("fire_safety_certificate", sd.fire_cert("A", "SYN-INST-11111", "R1", TODAY, TODAY), TODAY)
    vf = validate_upload("..\\..\\windows\\evil.pdf", "application/pdf", pdf)
    assert vf.safe_name == "evil.pdf"


# ---------------------------------------------------------------- API workflow

@pytest.fixture(scope="module")
def client():
    from app.main import app
    with TestClient(app) as c:
        yield c


def test_end_to_end_workflow(client):
    r = client.post("/api/applications", json={"institution_name": "Test Institute (Fictional)",
                                               "institution_id": "SYN-INST-11111",
                                               "application_type": "Increase in Intake"})
    assert r.status_code == 201
    app_id = r.json()["id"]

    today = fields.today()
    expired = sd.make_pdf("fire_safety_certificate", sd.fire_cert(
        "Test Institute (Fictional)", "SYN-INST-11111", "FES/NOC/1", today - timedelta(days=400),
        today - timedelta(days=10)), today)
    r = client.post(f"/api/applications/{app_id}/documents", data={"category": "fire_safety_certificate"},
                    files={"file": ("fire.pdf", expired, "application/pdf")})
    assert r.status_code == 201, r.text
    doc_id = r.json()["id"]
    r = client.post(f"/api/documents/{doc_id}/process")
    body = r.json()
    assert body["processing_status"] == "Processed" and body["extraction_method"] == "text"
    assert "Fire" in body["pages"][0]["text"]
    assert body["document_status"] == "Expired"

    detail = client.get(f"/api/applications/{app_id}").json()
    outcomes = {f["outcome"] for f in detail["findings"]}
    assert {"Expired", "Missing"} <= outcomes
    assert detail["risk_score"] > 0

    r = client.post(f"/api/applications/{app_id}/documents", data={"category": "other"},
                    files={"file": ("bad.pdf", b"not a pdf", "application/pdf")})
    assert r.status_code == 422

    r = client.post(f"/api/applications/{app_id}/review", json={
        "action": "request_clarification", "notes": "Please submit renewed fire NOC.", "officer_name": "Officer T"})
    assert r.status_code == 201 and r.json()["application"]["review_status"] == "Clarification Requested"

    events = client.get(f"/api/applications/{app_id}/audit-log").json()
    assert any(e["event_type"] == "review_action" for e in events)
    assert any(e["event_type"] == "upload_rejected" for e in events)
    assert client.get("/api/audit/verify").json()["valid"] is True

    r = client.get(f"/api/applications/{app_id}/report")
    assert r.status_code == 200 and r.content.startswith(b"%PDF")


def test_rule_edit_bumps_version(client):
    r = client.patch("/api/rules/R-EXP-001", json={"params": {"warn_within_days": 90}})
    assert r.status_code == 200 and r.json()["version"] == 2
    assert client.patch("/api/rules/R-NAME-001", json={"params": {"min_similarity": 5}}).status_code == 422


def test_audit_tampering_detected(client):
    from app.database import SessionLocal
    from app.models import AuditEvent
    with SessionLocal() as db:
        ev = db.query(AuditEvent).order_by(AuditEvent.id).first()
        ev.actor = "someone else"
        db.commit()
    res = client.get("/api/audit/verify").json()
    assert res["valid"] is False and res["first_invalid_event_id"] == ev.id


@pytest.mark.skipif(engine_name() is None, reason="no OCR engine installed")
def test_ocr_on_scanned_image(client):
    today = fields.today()
    pdf = sd.make_pdf("fire_safety_certificate", sd.fire_cert(
        "Scan Institute (Fictional)", "SYN-INST-22222", "FES/NOC/9", today, today + timedelta(days=300)), today)
    jpg = sd.image_bytes(sd.scanned_image(pdf), "JPEG", 85)
    app_id = client.post("/api/applications", json={"institution_name": "Scan Institute (Fictional)",
                                                    "institution_id": "SYN-INST-22222",
                                                    "application_type": "Increase in Intake"}).json()["id"]
    doc_id = client.post(f"/api/applications/{app_id}/documents", data={"category": "fire_safety_certificate"},
                         files={"file": ("scan.jpg", jpg, "image/jpeg")}).json()["id"]
    body = client.post(f"/api/documents/{doc_id}/process").json()
    assert body["extraction_method"] == "ocr" and body["ocr_engine"]
    assert body["fields"]["institution_id"]["value"] == "SYN-INST-22222"
    assert body["document_status"] == "Verified"
