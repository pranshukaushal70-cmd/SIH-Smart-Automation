"""PDF review report (ReportLab)."""
import io
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from ..catalog import DOCUMENT_CATEGORIES, FIELD_LABELS
from .scoring import DISCLAIMER

NAVY = colors.HexColor("#0b2545")
TEAL = colors.HexColor("#0f8b8d")
SAFFRON = colors.HexColor("#f29d38")
GREY = colors.HexColor("#5b6472")
LIGHT = colors.HexColor("#eef2f6")
SEV = {"critical": "#7a0916", "high": "#b42318", "medium": "#b54708", "low": "#475467", "info": "#667085"}

ss = getSampleStyleSheet()
H1 = ParagraphStyle("h1", parent=ss["Heading1"], fontSize=17, textColor=NAVY, spaceAfter=2)
H2 = ParagraphStyle("h2", parent=ss["Heading2"], fontSize=12.5, textColor=NAVY, spaceBefore=10, spaceAfter=4)
BODY = ParagraphStyle("b", parent=ss["BodyText"], fontSize=8.8, leading=11.5, alignment=TA_LEFT)
SMALL = ParagraphStyle("s", parent=BODY, fontSize=7.6, leading=9.6, textColor=GREY)
CELL = ParagraphStyle("c", parent=BODY, fontSize=7.8, leading=9.8)


def _p(text, style=CELL):
    from xml.sax.saxutils import escape
    return Paragraph(escape(str(text if text is not None else "—")), style)


def _table(rows, widths, header=True):
    t = Table(rows, colWidths=widths, repeatRows=1 if header else 0)
    style = [("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#d0d5dd")),
             ("VALIGN", (0, 0), (-1, -1), "TOP"),
             ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4)]
    if header:
        style += [("BACKGROUND", (0, 0), (-1, 0), LIGHT), ("TEXTCOLOR", (0, 0), (-1, 0), NAVY)]
    t.setStyle(TableStyle(style))
    return t


def _header_footer(canvas, doc):
    w, h = A4
    canvas.saveState()
    canvas.setFillColor(NAVY)
    canvas.rect(0, h - 14 * mm, w, 14 * mm, fill=1, stroke=0)
    canvas.setFillColor(colors.white)
    canvas.setFont("Helvetica-Bold", 10)
    canvas.drawString(15 * mm, h - 9 * mm, "VeriAICTE · AI Verification Co-Pilot")
    canvas.setFont("Helvetica", 8)
    canvas.drawRightString(w - 15 * mm, h - 9 * mm, "SIH 2026 · PS 26261 · PROTOTYPE")
    canvas.setFillColor(SAFFRON)
    canvas.rect(0, h - 15 * mm, w / 3, 1 * mm, fill=1, stroke=0)
    canvas.setFillColor(colors.white)
    canvas.rect(w / 3, h - 15 * mm, w / 3, 1 * mm, fill=1, stroke=0)
    canvas.setFillColor(colors.HexColor("#138808"))
    canvas.rect(2 * w / 3, h - 15 * mm, w / 3, 1 * mm, fill=1, stroke=0)
    canvas.setFillColor(GREY)
    canvas.setFont("Helvetica", 7)
    canvas.drawString(15 * mm, 9 * mm, "Hackathon prototype - not an official AICTE system or document. "
                                       "Decision support only; the authorised officer decides.")
    canvas.drawRightString(w - 15 * mm, 9 * mm, f"Page {doc.page}")
    canvas.restoreState()


def build_report(app, audit_events, chain: dict) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=15 * mm, rightMargin=15 * mm, topMargin=22 * mm,
                            bottomMargin=16 * mm, title=f"VeriAICTE review report {app.id}",
                            author="VeriAICTE prototype")
    s = []
    sb = app.score_breakdown or {}
    s.append(Paragraph(f"Application Review Report — {app.id}", H1))
    s.append(Paragraph(f"Generated {datetime.now().strftime('%d %b %Y, %H:%M')} (local time)"
                       + (" · <b>SYNTHETIC DEMO RECORD (fictional institution)</b>" if app.is_demo else ""), SMALL))
    s.append(Spacer(1, 6))

    info = [
        ["Institution", app.institution_name, "Application type", app.application_type],
        ["Institution ID", app.institution_id, "Submitted", app.submitted_at.strftime("%d %b %Y")],
        ["Processing status", app.processing_status, "Review status", app.review_status],
        ["Risk indicator", f"{app.risk_score if app.risk_score is not None else '—'} / 100 ({app.risk_band or 'n/a'})",
         "Rule-set fingerprint", app.ruleset_fingerprint or "—"],
    ]
    s.append(_table([[_p(c) for c in r] for r in info], [32 * mm, 60 * mm, 32 * mm, 56 * mm], header=False))

    s.append(Paragraph("Risk indicator breakdown", H2))
    s.append(Paragraph(f"Formula: {sb.get('formula', '—')}. {DISCLAIMER}", SMALL))
    rows = [[_p("Factor"), _p("Findings"), _p("Points")]]
    for f in (sb.get("factors") or {}).values():
        rows.append([_p(f["label"]), _p(f["count"]), _p(f["points"])])
    rows.append([_p("Total (capped at 100)"), _p(""), _p(sb.get("score", "—"))])
    s.append(_table(rows, [110 * mm, 30 * mm, 40 * mm]))
    sp = sb.get("severity_points") or {}
    s.append(Paragraph("Severity points: " + ", ".join(f"{k} = {v}" for k, v in sp.items())
                       + " · Factor weights: " + ", ".join(f"{k} × {v}" for k, v in (sb.get("factor_weights") or {}).items()),
                       SMALL))

    s.append(Paragraph("Documents", H2))
    rows = [[_p(h) for h in ("ID", "Declared category", "File", "Extraction", "Detected type", "Status", "Issuer verification")]]
    for d in app.documents:
        method = d.extraction_method or "—"
        if d.ocr_engine:
            method += f" ({d.ocr_engine}, {d.ocr_confidence:.0%})" if d.ocr_confidence is not None else f" ({d.ocr_engine})"
        rows.append([_p(d.id), _p(DOCUMENT_CATEGORIES.get(d.declared_category, d.declared_category)),
                     _p(d.original_filename), _p(method),
                     _p(DOCUMENT_CATEGORIES.get(d.detected_type, d.detected_type or "—")),
                     _p(d.document_status), _p(d.issuer_verification)])
    s.append(_table(rows, [20 * mm, 31 * mm, 31 * mm, 28 * mm, 30 * mm, 20 * mm, 20 * mm]))
    s.append(Paragraph("“Verified” means the document passed the configured prototype checks. It does not mean the "
                       "issuing authority has confirmed the document.", SMALL))

    for d in app.documents:
        if not d.fields:
            continue
        rows = [[_p("Field"), _p("Value"), _p("Status"), _p("Page / evidence")]]
        for k, v in d.fields.items():
            rows.append([_p(FIELD_LABELS.get(k, k)), _p(v.get("value")), _p(v["status"]),
                         _p(f"p.{v['page']}: {v.get('evidence')}" if v.get("page") else (v.get("note") or "—"))])
        s.append(KeepTogether([Paragraph(f"Extracted fields — {d.id} ({d.original_filename})", H2),
                               _table(rows, [36 * mm, 50 * mm, 18 * mm, 76 * mm])]))

    s.append(Paragraph("Findings", H2))
    if not app.findings:
        s.append(Paragraph("No findings: all enabled checks passed for the processed documents.", BODY))
    for f in sorted(app.findings, key=lambda x: ["critical", "high", "medium", "low", "info"].index(x.severity)):
        color = SEV.get(f.severity, "#475467")
        rows = [
            [Paragraph(f"<font color='{color}'><b>{f.severity.upper()}</b></font> · {f.outcome} · "
                       f"<b>{f.id}</b> · rule {f.rule_id} v{f.rule_version} · {f.status}", CELL)],
            [_p(f"{f.title}. {f.description}")],
            [_p(f"Expected: {f.expected or '—'}   |   Actual: {f.actual or '—'}")],
            [_p(f"Evidence: {f.evidence_source or '—'}" + (f" — “{f.evidence}”" if f.evidence else ""))],
            [_p(f"Recommended action: {f.recommended_action}"
                + (f"   |   Officer note: {f.reviewer_note} ({f.reviewed_by})" if f.reviewer_note else ""))],
        ]
        t = Table(rows, colWidths=[180 * mm])
        t.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor(color)),
                               ("BACKGROUND", (0, 0), (-1, 0), LIGHT),
                               ("LEFTPADDING", (0, 0), (-1, -1), 5), ("TOPPADDING", (0, 0), (-1, -1), 2),
                               ("BOTTOMPADDING", (0, 0), (-1, -1), 2)]))
        s.append(KeepTogether([t, Spacer(1, 4)]))

    s.append(Paragraph("Applied rules", H2))
    rows = [[_p("Rule ID"), _p("Version"), _p("Name"), _p("Group")]]
    for r in app.applied_rules or []:
        rows.append([_p(r["id"]), _p(r["version"]), _p(r["name"]), _p(r["group"])])
    s.append(_table(rows, [26 * mm, 18 * mm, 110 * mm, 26 * mm]))

    s.append(Paragraph("Officer review actions", H2))
    if not app.reviews:
        s.append(Paragraph("No review action recorded yet.", BODY))
    else:
        rows = [[_p("Timestamp (UTC)"), _p("Officer"), _p("Action"), _p("Notes")]]
        for r in app.reviews:
            rows.append([_p(r.created_at.strftime("%Y-%m-%d %H:%M")), _p(r.officer_name), _p(r.action), _p(r.notes)])
        s.append(_table(rows, [30 * mm, 30 * mm, 50 * mm, 70 * mm]))
    s.append(Paragraph("Recorded actions are review recommendations within this prototype; they are not official "
                       "regulatory approvals.", SMALL))

    s.append(Paragraph("Audit trail", H2))
    s.append(Paragraph(f"Hash-chain verification: <b>{'INTACT' if chain['valid'] else 'BROKEN'}</b> — "
                       f"{chain['message']} (tamper-evident, not tamper-proof)", BODY))
    rows = [[_p("#"), _p("Timestamp (UTC)"), _p("Event"), _p("Actor"), _p("Hash")]]
    for e in audit_events:
        rows.append([_p(e.id), _p(e.created_at.replace("T", " ")[:19]), _p(e.event_type), _p(e.actor),
                     _p(e.hash[:16] + "…")])
    s.append(_table(rows, [12 * mm, 36 * mm, 56 * mm, 36 * mm, 40 * mm]))

    doc.build(s, onFirstPage=_header_footer, onLaterPages=_header_footer)
    return buf.getvalue()
