# VeriAICTE — AI Verification Co-Pilot

**Smart India Hackathon 2026 · Problem Statement 26261**
*AI-Powered Application Validation, Document Authentication and Regulatory Compliance Verification*
Organisation: AICTE · Department: Regulation Bureau · Theme: Smart Automation

> **Hackathon prototype — not an official AICTE system.** It has no access to AICTE databases, DigiLocker,
> API Setu or any government verification API. All seeded institutions, issuers, identifiers and documents are
> **synthetic and fictional**. Findings are decision support only; an authorised officer makes every decision.

VeriAICTE helps a reviewing officer process institutional applications. It extracts text from uploaded PDFs and
scans (with OCR), extracts and classifies key fields, runs configurable and versioned compliance rules, raises
explainable authenticity-screening signals, computes a transparent risk indicator, records officer decisions in a
hash-chained audit log and produces a downloadable PDF review report.

---

## Quick start (Windows PowerShell)

Prerequisites: **Python 3.11+** (tested on 3.12.3) and **Node.js 18+** (tested on 24.x). No Docker, GPU, paid
API or Tesseract install is needed; OCR uses RapidOCR (ONNX, CPU), installed through pip.

### 1. Backend (terminal 1)

```powershell
cd "D:\Projects\SIH Smart Automation\backend"
python -m venv .venv                       # first time only
.\.venv\Scripts\python -m pip install -r requirements.txt   # first time only
.\.venv\Scripts\python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

On the first start the database is created and the synthetic demo data is seeded. Seeding runs the real pipeline,
OCR included, so it takes about a minute. Later starts are instant.

### 2. Frontend (terminal 2)

```powershell
cd "D:\Projects\SIH Smart Automation\frontend"
npm install                                # first time only
npm run dev
```

### 3. Open

| What | URL |
|---|---|
| Application | http://localhost:5173 |
| API docs (Swagger UI) | http://127.0.0.1:8000/docs |
| Health check | http://127.0.0.1:8000/api/health |

The Vite dev server proxies `/api` to the backend on port 8000.

### Reset the demo data

Stop the backend first, then run:

```powershell
cd backend
.\.venv\Scripts\python -m app.seed --reset   # deletes backend/data (DB, uploads, demo files) and reseeds
```

Expiry dates in the demo data are generated relative to the current date, so the scenarios stay valid on any demo day.

### Run the tests

```powershell
cd backend
.\.venv\Scripts\python -m pytest -q tests
```

The tests use an isolated temporary database; they never touch the demo data.

---

## What it does

| Area | Implementation |
|---|---|
| Secure upload | Allows PDF/JPG/JPEG/PNG only. Checks the extension, the declared MIME type and the magic-byte signature, then parses the file (PyMuPDF/Pillow) to reject malformed ones. Limits: 10 MB and 30 pages (configurable). Password-protected PDFs are rejected. Files get random UUID names in `backend/data/uploads`, and client paths are stripped. There is no static file serving: files are reachable only by document ID through the preview endpoint. |
| Text extraction | PyMuPDF reads the PDF text layer. Pages with fewer than 40 characters count as scanned: they are rendered at 200 dpi and OCR'd. Images always go to OCR. |
| OCR | **RapidOCR (ONNX Runtime, CPU)** is bundled. Tesseract is used if it is installed and `VERI_OCR_ENGINE=tesseract`. If no engine is available the document is marked *Failed* with a clear message, and no text is fabricated. |
| Field extraction | Deterministic, label-based patterns that tolerate OCR quirks (lost spaces, I/l confusion). Fields: institution name, institution ID, issue date, expiry date, issuer, certificate/reference no., affiliation/approval reference. Each field is **detected / uncertain / missing**, with page number and source line. Values are never invented. |
| Classification | Weighted keyword evidence per document category, with a confidence value. |
| Compliance rules | 12 configurable compliance rules: required documents, required fields per category, expiry, identifier match, name similarity, type match, affiliation statement, date plausibility and OCR quality. Officers can add *field pattern*, *required fields* or *keyword* rules. **Every edit increments the rule version** and is audited. Reports list `rule ID vN` and a rule-set fingerprint. |
| Authenticity screening | Screening signals, not proof. PDF metadata: editing-tool producer, late modification, incremental saves (multiple `%%EOF`), missing metadata. JPEG error-level analysis and EXIF software tags. **SHA-256 reuse detection** across applications (identical bytes ≠ genuine). |
| Findings | Each finding carries an ID, severity, outcome (Missing / Expired / Flagged / Review Required / Screening Signal), rule ID and version, description, expected vs actual values, the evidence source and quoted line, the page, and a recommended action. |
| Risk indicator | `risk = min(100, Σ severity_points × factor_weight)`. Weights and bands can be edited in the UI and are versioned. Labelled as an internal prototype indicator, **not a fraud probability and not an official score**. Findings never auto-reject anything. |
| Human review | Officers can mark findings reviewed or re-open them, with notes. Decisions: request clarification, request issuer verification (**simulated**, shown as "Pending (simulated - no issuer integration)"), return for missing information, record a provisional approval recommendation, recommend further scrutiny, add a note. Notes are required. |
| Audit log | Append-only from the application's point of view and **hash-chained** (`sha256(prev_hash + event)`). `GET /api/audit/verify` recomputes the chain and reports the first broken event. This is tamper-*evident*, not tamper-proof: the SQLite file can still be edited by anyone with file access. |
| Report | ReportLab PDF containing the summary, score breakdown with weights, documents, extracted fields with evidence, findings, applied rules with versions, officer decisions, and the audit trail with chain status. |

### Document statuses

**Verified** means the document passed the enabled prototype checks. It does *not* mean the issuer confirmed it, and
issuer verification always shows **Not Verified** or **Pending (simulated)**. The other statuses are **Review Required**,
**Flagged**, **Expired**, **Pending Processing** and **Processing Failed**. **Missing** is reported as an application-level finding.

---

## Demo data

| Application | Scenario | Risk |
|---|---|---|
| APP-2026-0001 Vindhya Institute of Technology | All four documents pass. The trust registration is a **scanned image-only PDF (OCR)** | 0 · Low |
| APP-2026-0002 Konark College of Engineering | **Fire NOC expired** and **trust registration missing** | 50 · Medium |
| APP-2026-0003 Sahyadri Polytechnic | Occupancy certificate has the **wrong institution ID** (SYN-INST-30941 vs 30914) and a different name. It was re-saved with iLovePDF metadata and an incremental update. The affiliation letter is a **photographed JPG (OCR)** | 47 · Medium |
| APP-2026-0004 Godavari Institute of Pharmacy | Fire NOC is **missing its validity date, issuer and certificate number** | 36 · Medium |
| APP-2026-0005 Kaveri School of Architecture | An occupancy certificate was uploaded in the fire-NOC slot (**type mismatch**), the trust certificate shows **another institution's ID**, and the occupancy certificate is **missing** | 74 · High |

`samples/` holds files for the **live upload** demo. Create an application for *Narmada Institute of Management
Studies (Fictional)*, ID **SYN-INST-61208**, then upload:

| File | Expected result |
|---|---|
| `01_affiliation_letter_valid.pdf` | Text extraction · Verified |
| `02_fire_noc_scanned.jpg` | OCR · Verified |
| `03_occupancy_certificate_scanned.pdf` | Scanned PDF → OCR · Verified |
| `04_trust_registration_wrong_id.pdf` | **Flagged**: identifier SYN-INST-61280 ≠ SYN-INST-61208 |
| `05_reused_copy_of_APP-2026-0001_fire_noc.pdf` | **Flagged**: identical SHA-256 to a file in APP-2026-0001, plus ID and name mismatch |
| `06_invalid_renamed_text_file.pdf` | **Rejected**: invalid file signature (HTTP 422) |

---

## Architecture

```
frontend/  React 18 + Vite 6 + TypeScript + Tailwind 4 + React Router + Recharts + lucide-react
  src/pages/        Dashboard, Applications, Workspace (review), Rules, Reports
  src/api.ts        typed API client with visible error handling
backend/   FastAPI + SQLAlchemy 2 + SQLite
  app/main.py       REST API (Swagger at /docs)
  app/models.py     Application, Document, Finding, Rule, ReviewAction, AuditEvent, Setting
  app/services/
    uploads.py      validation & safe storage
    extraction.py   PyMuPDF text layer / page rendering
    ocr.py          RapidOCR (default) or Tesseract, line grouping
    fields.py       field extraction, date parsing, classifier
    screening.py    PDF metadata, EOF markers, EXIF, ELA facts
    rules.py        versioned rule definitions & evaluators
    scoring.py      transparent risk formula
    pipeline.py     process document → evaluate application
    audit.py        hash-chained audit log + verification
    report.py       ReportLab PDF report
  app/seed.py       DB init + synthetic demo generation (runs the real pipeline)
  app/sample_docs.py synthetic certificate generator (ReportLab)
  tests/            pytest: rules, extraction, uploads, API workflow, audit tampering, OCR
```

Pipeline: **upload → validate → store → extract (text/OCR) → fields + classification + screening facts →
rules → findings → document statuses → risk score → audit event.**

## API endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/health` | Status, OCR engine availability |
| GET | `/api/meta` | Categories, application types, review actions, field names |
| GET | `/api/dashboard` | Metrics, risk distribution, recent applications and activity |
| GET/POST | `/api/applications` | List (filters: `q`, `review_status`, `risk_band`, `application_type`) / create |
| GET/DELETE | `/api/applications/{id}` | Details with documents, findings, score, reviews / delete (non-demo only) |
| POST | `/api/applications/{id}/documents` | Multipart upload (`file`, `category`; `?process=true` to process immediately) |
| GET | `/api/documents/{id}` | Text, fields, screening facts and findings for a document |
| POST | `/api/documents/{id}/process` | Run extraction, OCR and checks |
| GET | `/api/documents/{id}/preview?page=n` | PNG page rendering |
| DELETE | `/api/documents/{id}` | Delete an uploaded (non-demo) document |
| POST | `/api/applications/{id}/evaluate` | Re-run rules |
| GET | `/api/applications/{id}/findings` | Findings |
| PATCH | `/api/findings/{id}` | Mark reviewed / re-open, with a note |
| POST | `/api/applications/{id}/review` | Record an officer action |
| GET/POST | `/api/rules` | List / add a custom rule |
| PATCH | `/api/rules/{id}` | Enable/disable, severity, thresholds (bumps the version) |
| GET/PATCH | `/api/settings/scoring` | Scoring weights (versioned) |
| POST | `/api/evaluate-all` | Re-evaluate every application |
| GET | `/api/applications/{id}/report` | PDF report download |
| GET | `/api/applications/{id}/audit-log` · `/api/audit-log` | Audit events |
| GET | `/api/audit/verify` | Verify the hash chain |

## Configuration

Copy `backend/.env.example` to `backend/.env` if you need to change anything. No secrets are required. Settings:
upload size and page limits, CORS origins (default: the Vite dev origin only), OCR engine (`auto | rapidocr |
tesseract | none`), `TESSERACT_CMD`, OCR DPI, and auto-seeding.

## Security and privacy notes

- **No authentication.** The officer name is typed into the sidebar, for attribution only. Run this locally; do not expose it publicly.
- CORS is restricted to `http://localhost:5173` and `http://127.0.0.1:5173`.
- Uploaded files are never served statically, and internal paths are never returned. Unhandled errors return a generic message.
- Synthetic demo files (`backend/data/demo_documents`) are kept apart from officer uploads (`backend/data/uploads`). Demo records cannot be deleted through the API, and uploaded documents and applications can.
- Do not upload real personal data to this prototype.

## Limitations

- OCR on CPU takes about 10–20 s per scanned page on a 4-core laptop. The UI shows progress while it runs, and processing is synchronous (no job queue).
- Field extraction relies on labelled fields (e.g. "Valid Until:"). Free-form or unusual layouts may yield *missing/uncertain* fields, which are surfaced for review rather than guessed. No LLM is used.
- The classifier and screening heuristics are simple and explainable. ELA and metadata signals have false positives and negatives, and they are not forensic proof.
- There is no real issuer, DigiLocker or API Setu integration. Issuer verification is simulated as *Pending*.
- SQLite with a single process, which suits a local demo but not production. The audit log is tamper-evident only.
- Mobile layout is responsive but not fully tested. The demo targets a desktop browser.

## Troubleshooting

| Symptom | Fix |
|---|---|
| UI says "API offline" | Start the backend on port 8000, and check that nothing else uses the port. |
| First backend start seems stuck | It is seeding and OCR-ing the demo documents (about a minute). Wait for `Application startup complete`. |
| `OCR engine unavailable` on scanned files | Run `pip install -r requirements.txt` inside the venv. Or install Tesseract and set `VERI_OCR_ENGINE=tesseract` and `TESSERACT_CMD`. |
| Port 5173 busy | Stop the other Vite instance. `strictPort` keeps the CORS/proxy setup predictable. |
| Want a clean demo | Stop the backend, run `python -m app.seed --reset`, then start it again. |
| `npm` warns about install scripts | Harmless for this project. The build was verified with these warnings present. |
