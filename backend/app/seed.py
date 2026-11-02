"""Database initialisation and synthetic demo seeding.

Usage:
    python -m app.seed            # create tables + seed if the database is empty
    python -m app.seed --reset    # delete the database, demo files and uploads, then reseed

Seeded documents are generated as files and then run through the *real* processing pipeline, so
their findings come from the same code that handles uploads.
"""
import argparse
import hashlib
import logging
import shutil
from datetime import datetime, timedelta

from sqlalchemy import select

from . import sample_docs as sd
from .config import BASE_DIR, DB_PATH, DEMO_DIR, UPLOAD_DIR
from .database import Base, SessionLocal, engine
from .models import Application, Document, Rule, next_id
from .services import audit, pipeline
from .services.fields import today as get_today
from .services.rules import DEFAULT_RULES
from .services.scoring import DEFAULT_SCORING

log = logging.getLogger("veriaicte.seed")
SAMPLES_DIR = BASE_DIR.parent / "samples"
ACTOR = "seed-script"


def init_db():
    Base.metadata.create_all(engine)


def ensure_rules(db):
    for r in DEFAULT_RULES:
        if db.get(Rule, r["id"]) is None:
            db.add(Rule(**r, version=1, is_builtin=True))
    pipeline.get_scoring(db)
    db.flush()


def _add_doc(db, app, category, filename, data: bytes, mime, page_count=1):
    stored = f"{hashlib.sha256(data).hexdigest()[:24]}_{app.id}_{category}"[:60]
    ext = ".pdf" if mime == "application/pdf" else ".jpg"
    (DEMO_DIR / (stored + ext)).write_bytes(data)
    doc = Document(id=next_id(db, "document", "DOC-", 5), application_id=app.id, declared_category=category,
                   original_filename=filename, stored_filename=stored + ext, storage="demo", mime_type=mime,
                   size_bytes=len(data), sha256=hashlib.sha256(data).hexdigest(), page_count=page_count,
                   is_demo=True)
    db.add(doc)
    db.flush()
    audit.record(db, "document_uploaded", ACTOR, app.id, {"document_id": doc.id, "category": category,
                                                           "filename": filename, "sha256": doc.sha256})
    return doc


def seed(db):
    T = get_today()
    t = lambda days: T + timedelta(days=days)
    apps_spec = [
        dict(name="Vindhya Institute of Technology (Fictional)", iid="SYN-INST-10421",
             atype="Extension of Approval (EoA)", days_ago=6),
        dict(name="Konark College of Engineering (Fictional)", iid="SYN-INST-20587",
             atype="Increase in Intake", days_ago=4),
        dict(name="Sahyadri Polytechnic (Fictional)", iid="SYN-INST-30914",
             atype="Change of Site / Location", days_ago=3),
        dict(name="Godavari Institute of Pharmacy (Fictional)", iid="SYN-INST-40276",
             atype="Extension of Approval (EoA)", days_ago=2),
        dict(name="Kaveri School of Architecture (Fictional)", iid="SYN-INST-50133",
             atype="Approval for New Institution", days_ago=1),
    ]
    apps = []
    for spec in apps_spec:
        app = Application(id=next_id(db, "application", "APP-2026-", 4), institution_name=spec["name"],
                          institution_id=spec["iid"], application_type=spec["atype"],
                          state="State of Vindhyachal (Fictional)", academic_year="2026-27",
                          submitted_at=datetime.now() - timedelta(days=spec["days_ago"]), is_demo=True)
        db.add(app)
        db.flush()
        audit.record(db, "application_created", ACTOR, app.id, {"institution_id": app.institution_id,
                                                                 "synthetic_demo": True})
        apps.append(app)
    a1, a2, a3, a4, a5 = apps
    PDF, JPG = "application/pdf", "image/jpeg"

    # 1 — all configured checks pass (trust registration is a scanned image-only PDF -> OCR)
    _add_doc(db, a1, "affiliation_letter", "affiliation_letter_2026-27.pdf", sd.make_pdf(
        "affiliation_letter", sd.affiliation_letter(a1.institution_name, a1.institution_id, "FSTU/AFF/2026/118",
                                                    "FSTU-AFF-10421-26", t(-120), t(245)), t(-120)), PDF)
    fire1 = sd.make_pdf("fire_safety_certificate", sd.fire_cert(
        a1.institution_name, a1.institution_id, "FES/NOC/2026/04412", t(-200), t(530)), t(-200))
    _add_doc(db, a1, "fire_safety_certificate", "fire_noc.pdf", fire1, PDF)
    _add_doc(db, a1, "occupancy_certificate", "occupancy_certificate.pdf", sd.make_pdf(
        "occupancy_certificate", sd.occupancy_cert(a1.institution_name, a1.institution_id, "MCN/OC/2022/0931",
                                                   t(-1400)), t(-1400)), PDF)
    trust1 = sd.make_pdf("trust_registration_certificate", sd.trust_cert(
        a1.institution_name, "Vindhya Education Society (Fictional)", a1.institution_id, "ROS/VND/2011/00873",
        t(-5400)), t(-5400))
    _add_doc(db, a1, "trust_registration_certificate", "society_registration_scan.pdf",
             sd.image_only_pdf(sd.scanned_image(trust1, seed=3)), PDF)

    # 2 — expired fire certificate; trust registration missing
    _add_doc(db, a2, "affiliation_letter", "affiliation_letter.pdf", sd.make_pdf(
        "affiliation_letter", sd.affiliation_letter(a2.institution_name, a2.institution_id, "FSTU/AFF/2026/144",
                                                    "FSTU-AFF-20587-26", t(-95), t(270), style=1), t(-95)), PDF)
    _add_doc(db, a2, "fire_safety_certificate", "fire_safety_certificate.pdf", sd.make_pdf(
        "fire_safety_certificate", sd.fire_cert(a2.institution_name, a2.institution_id, "FES/NOC/2024/01987",
                                                t(-858), t(-128)), t(-858)), PDF)
    _add_doc(db, a2, "occupancy_certificate", "building_completion.pdf", sd.make_pdf(
        "occupancy_certificate", sd.occupancy_cert(a2.institution_name, a2.institution_id, "MCN/OC/2019/0412",
                                                   t(-2500)), t(-2500)), PDF)

    # 3 — occupancy certificate carries a different identifier and was re-saved in an editing tool;
    #     affiliation letter is a photographed JPG (OCR)
    aff3 = sd.make_pdf("affiliation_letter", sd.affiliation_letter(
        a3.institution_name, a3.institution_id, "FSTU/AFF/2026/162", "FSTU-AFF-30914-26", t(-70), t(295)), t(-70))
    _add_doc(db, a3, "affiliation_letter", "affiliation_letter_photo.jpg",
             sd.image_bytes(sd.scanned_image(aff3, seed=9), "JPEG", 84), JPG)
    _add_doc(db, a3, "fire_safety_certificate", "fire_noc.pdf", sd.make_pdf(
        "fire_safety_certificate", sd.fire_cert(a3.institution_name, a3.institution_id, "FES/NOC/2026/05120",
                                                t(-150), t(580), style=1), t(-150)), PDF)
    tmp = DEMO_DIR / "_tmp_edit.pdf"
    sd.edited_incrementally(sd.certificate_pdf("occupancy_certificate", sd.occupancy_cert(
        "Sahyadri Polytechnic Institute (Fictional)", "SYN-INST-30941", "MCN/OC/2021/0777", t(-1700)),
        "Executive Engineer"), "iLovePDF", t(-1700), t(-20), tmp)
    _add_doc(db, a3, "occupancy_certificate", "occupancy_certificate_final.pdf", tmp.read_bytes(), PDF)
    tmp.unlink()
    _add_doc(db, a3, "trust_registration_certificate", "trust_registration.pdf", sd.make_pdf(
        "trust_registration_certificate", sd.trust_cert(a3.institution_name, "Sahyadri Vidya Trust (Fictional)",
                                                        a3.institution_id, "ROS/VND/2005/00219", t(-7600)),
        t(-7600)), PDF)

    # 4 — fire certificate missing validity, issuer and certificate number
    _add_doc(db, a4, "affiliation_letter", "affiliation.pdf", sd.make_pdf(
        "affiliation_letter", sd.affiliation_letter(a4.institution_name, a4.institution_id, "FSTU/AFF/2026/171",
                                                    "FSTU-AFF-40276-26", t(-40), t(325)), t(-40)), PDF)
    _add_doc(db, a4, "fire_safety_certificate", "fire_noc_incomplete.pdf", sd.make_pdf(
        "fire_safety_certificate", sd.fire_cert(a4.institution_name, a4.institution_id, "", t(-30), t(700),
                                                omit=("Valid Until", "Issued By", "Certificate No."))
        , t(-30)), PDF)
    _add_doc(db, a4, "occupancy_certificate", "occupancy.pdf", sd.make_pdf(
        "occupancy_certificate", sd.occupancy_cert(a4.institution_name, a4.institution_id, "MCN/OC/2020/0555",
                                                   t(-2100)), t(-2100)), PDF)
    _add_doc(db, a4, "trust_registration_certificate", "trust.pdf", sd.make_pdf(
        "trust_registration_certificate", sd.trust_cert(a4.institution_name, "Godavari Seva Mandal (Fictional)",
                                                        a4.institution_id, "ROS/VND/2014/00650", t(-4300)),
        t(-4300)), PDF)

    # 5 — occupancy certificate uploaded in the fire-safety slot; trust certificate for another institution;
    #     occupancy certificate therefore missing
    _add_doc(db, a5, "affiliation_letter", "affiliation.pdf", sd.make_pdf(
        "affiliation_letter", sd.affiliation_letter(a5.institution_name, a5.institution_id, "FSTU/AFF/2026/190",
                                                    "FSTU-AFF-50133-26", t(-25), t(340)), t(-25)), PDF)
    _add_doc(db, a5, "fire_safety_certificate", "fire_certificate.pdf", sd.make_pdf(
        "occupancy_certificate", sd.occupancy_cert(a5.institution_name, a5.institution_id, "MCN/OC/2025/1450",
                                                   t(-200)), t(-200)), PDF)
    _add_doc(db, a5, "trust_registration_certificate", "trust_registration.pdf", sd.make_pdf(
        "trust_registration_certificate", sd.trust_cert(a5.institution_name, "Kaveri Kala Trust (Fictional)",
                                                        "SYN-INST-51033", "ROS/VND/2024/01104", t(-300)), t(-300)),
             PDF)
    db.flush()

    for app in apps:
        for doc in app.documents:
            pipeline.process_document(db, doc, ACTOR)
        pipeline.evaluate_application(db, app, ACTOR)

    # live-upload sample files (one is a byte-identical copy of application 1's fire NOC)
    fire1_doc = next(d for d in a1.documents if d.declared_category == "fire_safety_certificate")
    sd.write_upload_samples(SAMPLES_DIR, T, reused_from=pipeline.file_path(fire1_doc))
    audit.record(db, "demo_seeded", ACTOR, None, {"applications": [a.id for a in apps],
                                                  "note": "Synthetic, fictional demo data"})


def ensure_defaults():
    with SessionLocal() as db:
        ensure_rules(db)
        db.commit()


def run(reset: bool = False):
    if reset:
        engine.dispose()
        for p in (DB_PATH, DB_PATH.with_name(DB_PATH.name + "-wal"), DB_PATH.with_name(DB_PATH.name + "-shm")):
            if p.exists():
                p.unlink()
        for d in (DEMO_DIR, UPLOAD_DIR):
            shutil.rmtree(d, ignore_errors=True)
            d.mkdir(parents=True, exist_ok=True)
    init_db()
    with SessionLocal() as db:
        ensure_rules(db)
        if db.execute(select(Application).limit(1)).scalar_one_or_none() is None:
            seed(db)
        db.commit()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    ap = argparse.ArgumentParser()
    ap.add_argument("--reset", action="store_true", help="delete local data (DB, demo files, uploads) and reseed")
    run(ap.parse_args().reset)
    print("Database ready:", DB_PATH)
