"""Generates clearly-labelled SYNTHETIC certificates for demos. All institutions, issuers and
identifiers are fictional; none of these documents are issued by AICTE or any real authority."""
import io
import random
from datetime import date, timedelta
from pathlib import Path

import fitz
import numpy as np
from PIL import Image, ImageFilter
from reportlab.lib.colors import Color, HexColor
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

FOOTER = ("SYNTHETIC DEMO DOCUMENT - fictional institution, issuer and identifiers - generated for the "
          "VeriAICTE SIH 2026 prototype - not an official document of AICTE or any real authority")

STATE = "State of Vindhyachal (Fictional)"
ISSUERS = {
    "fire_safety_certificate": ("Directorate of Fire & Emergency Services", STATE,
                                "FIRE SAFETY NO OBJECTION CERTIFICATE"),
    "occupancy_certificate": ("Municipal Corporation of Navapur", "Navapur, " + STATE,
                              "BUILDING OCCUPANCY / COMPLETION CERTIFICATE"),
    "affiliation_letter": ("Fictional State Technical University", "Office of the Registrar, Navapur",
                           "GRANT OF AFFILIATION - ACADEMIC SESSION 2026-27"),
    "trust_registration_certificate": ("Office of the Registrar of Societies", STATE,
                                       "CERTIFICATE OF REGISTRATION"),
}
BODIES = {
    "fire_safety_certificate": [
        "This is to certify that the premises of the above institution were inspected by the fire safety "
        "officer of this Directorate. Fire extinguishers, the wet riser and hydrant system, fire alarms and "
        "marked evacuation routes were found to be in working order.",
        "No Objection is accordingly granted for the use of the premises for academic purposes, subject to "
        "annual maintenance of all fire safety installations.",
    ],
    "occupancy_certificate": [
        "This is to certify that the building constructed for the above institution has been inspected and "
        "the building completion is in accordance with the sanctioned plan. A structural stability report "
        "has been submitted by a licensed engineer.",
        "The building is declared fit for occupation for educational use.",
    ],
    "affiliation_letter": [
        "With reference to the application of the above institution, and on the recommendation of the "
        "inspection committee, affiliation is hereby granted to the institution for the programmes and "
        "approved intake listed in the schedule for the academic session stated above.",
        "The affiliation is subject to the institution maintaining faculty, infrastructure and academic "
        "standards as prescribed by the University.",
    ],
    "trust_registration_certificate": [
        "This is to certify that the society named above has been registered under the Societies "
        "Registration Act as applicable in the State, and the memorandum of association and rules of the "
        "society have been filed in this office.",
        "The society is the sponsoring body of the institution named above.",
    ],
}


def fmt(d: date, style: int = 0) -> str:
    return d.strftime("%d/%m/%Y") if style == 0 else d.strftime("%d %B %Y")


def certificate_pdf(category: str, fields: list[tuple[str, str]], signatory: str, extra_body: str | None = None) -> bytes:
    issuer, sub, title = ISSUERS[category]
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    w, h = A4
    # watermark first (light) so the certificate text stays on top
    c.saveState()
    c.setFillColor(Color(0.85, 0.85, 0.85))
    c.setFont("Helvetica-Bold", 46)
    c.translate(w / 2, h / 2 - 40)
    c.rotate(35)
    c.drawCentredString(0, 0, "SYNTHETIC DEMO")
    c.restoreState()

    c.setFillColor(HexColor("#0b2545"))
    c.rect(0, h - 38 * mm, w, 38 * mm, fill=1, stroke=0)
    c.setFillColor(HexColor("#ffffff"))
    c.setFont("Helvetica-Bold", 17)
    c.drawCentredString(w / 2, h - 17 * mm, issuer)
    c.setFont("Helvetica", 11)
    c.drawCentredString(w / 2, h - 25 * mm, sub)
    c.setFillColor(HexColor("#13a89e"))
    c.rect(0, h - 40 * mm, w, 2 * mm, fill=1, stroke=0)

    c.setFillColor(HexColor("#0b2545"))
    c.setFont("Helvetica-Bold", 15)
    c.drawCentredString(w / 2, h - 56 * mm, title)

    y = h - 74 * mm
    c.setFont("Helvetica", 11.5)
    for label, value in fields:
        c.setFont("Helvetica-Bold", 11.5)
        c.drawString(25 * mm, y, f"{label}:")
        lw = c.stringWidth(f"{label}:", "Helvetica-Bold", 11.5)
        c.setFont("Helvetica", 11.5)
        c.drawString(25 * mm + lw + 6, y, value)
        y -= 8.5 * mm

    y -= 4 * mm
    text = c.beginText(25 * mm, y)
    text.setFont("Helvetica", 11)
    text.setLeading(16)
    paragraphs = BODIES[category] + ([extra_body] if extra_body else [])
    for para in paragraphs:
        line = ""
        for word in para.split():
            if c.stringWidth(line + " " + word, "Helvetica", 11) > w - 50 * mm:
                text.textLine(line.strip())
                line = ""
            line += " " + word
        text.textLine(line.strip())
        text.textLine("")
    c.drawText(text)

    c.setFont("Helvetica-Bold", 11)
    c.drawRightString(w - 25 * mm, 62 * mm, signatory)
    c.setFont("Helvetica", 10)
    c.drawRightString(w - 25 * mm, 56 * mm, issuer)
    c.setStrokeColor(HexColor("#0b2545"))
    c.circle(45 * mm, 62 * mm, 14 * mm, stroke=1, fill=0)
    c.setFont("Helvetica", 7)
    c.drawCentredString(45 * mm, 62 * mm, "SEAL (SYNTHETIC)")

    c.setFillColor(HexColor("#b42318"))
    c.setFont("Helvetica", 7.2)
    c.drawCentredString(w / 2, 14 * mm, FOOTER)
    c.showPage()
    c.save()
    return buf.getvalue()


def set_pdf_metadata(pdf: bytes, created: date, producer: str = "VeriAICTE synthetic generator (ReportLab)",
                     modified: date | None = None) -> bytes:
    with fitz.open(stream=pdf, filetype="pdf") as doc:
        stamp = lambda d: f"D:{d.strftime('%Y%m%d')}103000+05'30'"
        doc.set_metadata({"producer": producer, "creator": producer, "title": "Synthetic demo certificate",
                          "creationDate": stamp(created), "modDate": stamp(modified or created)})
        return doc.tobytes(garbage=3, deflate=True)


def edited_incrementally(pdf: bytes, producer: str, created: date, modified: date, path: Path) -> None:
    """Writes the PDF, then re-saves it incrementally with editing-tool metadata (real screening signals)."""
    path.write_bytes(set_pdf_metadata(pdf, created))
    with fitz.open(path) as doc:
        stamp = lambda d: f"D:{d.strftime('%Y%m%d')}164500+05'30'"
        doc.set_metadata({**doc.metadata, "producer": producer, "creator": producer,
                          "creationDate": stamp(created), "modDate": stamp(modified)})
        doc.save(path, incremental=True, encryption=fitz.PDF_ENCRYPT_KEEP)


def scanned_image(pdf: bytes, seed: int = 7, dpi: int = 150) -> Image.Image:
    """Simulates a desk scan: rasterise, slight rotation, blur, noise."""
    rng = random.Random(seed)
    with fitz.open(stream=pdf, filetype="pdf") as doc:
        pix = doc[0].get_pixmap(matrix=fitz.Matrix(dpi / 72, dpi / 72), alpha=False)
        img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    img = img.rotate(rng.uniform(-0.8, 0.8), expand=False, fillcolor=(250, 250, 248), resample=Image.BICUBIC)
    img = img.filter(ImageFilter.GaussianBlur(0.5))
    arr = np.asarray(img).astype(np.int16)
    noise = np.random.default_rng(seed).normal(0, 6, arr.shape)
    arr = np.clip(arr + noise + np.array([4, 2, -6]), 0, 255).astype(np.uint8)  # faint paper tint
    return Image.fromarray(arr)


def image_bytes(img: Image.Image, fmt_: str = "JPEG", quality: int = 82) -> bytes:
    buf = io.BytesIO()
    img.save(buf, fmt_, quality=quality) if fmt_ == "JPEG" else img.save(buf, fmt_)
    return buf.getvalue()


def image_only_pdf(img: Image.Image) -> bytes:
    jpg = image_bytes(img, "JPEG", 78)
    doc = fitz.open()
    page = doc.new_page(width=A4[0], height=A4[1])
    page.insert_image(page.rect, stream=jpg)
    doc.set_metadata({"producer": "Synthetic flatbed scan (demo)", "creator": "Synthetic flatbed scan (demo)"})
    data = doc.tobytes(garbage=3, deflate=True)
    doc.close()
    return data


# ------------------------------------------------------------- document templates

def fire_cert(name, inst_id, ref, issued, valid_until, omit=(), style=0):
    f = [("Certificate No.", ref), ("Name of the Institution", name), ("Institution ID", inst_id),
         ("Premises", "Campus Road, Navapur, " + STATE), ("Date of Issue", fmt(issued, style)),
         ("Valid Until", fmt(valid_until, style)), ("Issued By", "Chief Fire Officer, Navapur Division")]
    return [x for x in f if x[0] not in omit]


def occupancy_cert(name, inst_id, ref, issued, style=1):
    return [("Certificate No.", ref), ("Name of the Institution", name), ("Institution ID", inst_id),
            ("Built-up Area", "18,450 sq. m (academic and administrative blocks)"),
            ("Date of Issue", fmt(issued, style)), ("Issued By", "Executive Engineer (Building Permissions)")]


def affiliation_letter(name, inst_id, ref, aff_no, issued, valid_until, style=0):
    return [("Letter No.", ref), ("Affiliation No.", aff_no), ("Name of the Institution", name),
            ("Institution ID", inst_id), ("Approved Intake", "360 (B.Tech, six programmes)"),
            ("Date of Issue", fmt(issued, style)), ("Valid Until", fmt(valid_until, style)),
            ("Issued By", "Registrar, Fictional State Technical University")]


def trust_cert(name, society, inst_id, ref, issued, style=1):
    return [("Registration No.", ref), ("Name of the Society", society), ("Name of the Institution", name),
            ("Institution ID", inst_id), ("Date of Issue", fmt(issued, style)),
            ("Issued By", "Registrar of Societies, " + STATE)]


SIGNATORY = {
    "fire_safety_certificate": "Chief Fire Officer",
    "occupancy_certificate": "Executive Engineer",
    "affiliation_letter": "Registrar",
    "trust_registration_certificate": "Registrar of Societies",
}


def make_pdf(category, fields, created: date, extra_body=None) -> bytes:
    return set_pdf_metadata(certificate_pdf(category, fields, SIGNATORY[category], extra_body), created)


def write_upload_samples(out_dir: Path, today: date, reused_from: Path | None = None) -> list[Path]:
    """Sample files for the live upload demo (new application: SYN-INST-61208)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    name, iid = "Narmada Institute of Management Studies (Fictional)", "SYN-INST-61208"
    t = lambda days: today + timedelta(days=days)
    written = []

    p = out_dir / "01_affiliation_letter_valid.pdf"
    p.write_bytes(make_pdf("affiliation_letter", affiliation_letter(
        name, iid, "FSTU/AFF/2026/231", "FSTU-AFF-61208-26", t(-60), t(300)), t(-60)))
    written.append(p)

    fire = make_pdf("fire_safety_certificate", fire_cert(name, iid, "FES/NOC/2026/07731", t(-90), t(640), style=1), t(-90))
    p = out_dir / "02_fire_noc_scanned.jpg"
    p.write_bytes(image_bytes(scanned_image(fire, seed=11), "JPEG", 85))
    written.append(p)

    occ = make_pdf("occupancy_certificate", occupancy_cert(name, iid, "MCN/OC/2023/1187", t(-1100)), t(-1100))
    p = out_dir / "03_occupancy_certificate_scanned.pdf"
    p.write_bytes(image_only_pdf(scanned_image(occ, seed=5)))
    written.append(p)

    p = out_dir / "04_trust_registration_wrong_id.pdf"
    p.write_bytes(make_pdf("trust_registration_certificate", trust_cert(
        name, "Narmada Shiksha Samiti (Fictional)", "SYN-INST-61280", "ROS/VND/2009/00412", t(-6200)), t(-6200)))
    written.append(p)

    if reused_from and reused_from.exists():
        p = out_dir / "05_reused_copy_of_APP-2026-0001_fire_noc.pdf"
        p.write_bytes(reused_from.read_bytes())
        written.append(p)

    p = out_dir / "06_invalid_renamed_text_file.pdf"
    p.write_text("This is a plain text file renamed to .pdf. The upload validator must reject it.\n", encoding="utf-8")
    written.append(p)

    (out_dir / "README.txt").write_text(
        "SYNTHETIC SAMPLE FILES FOR THE VERIAICTE DEMO - all institutions, issuers and identifiers are fictional.\n"
        "Create an application for 'Narmada Institute of Management Studies (Fictional)', institution ID "
        "SYN-INST-61208, then upload files 01-03 (valid), 04 (identifier mismatch), 05 (re-used file), "
        "06 (must be rejected).\n", encoding="utf-8")
    return written
