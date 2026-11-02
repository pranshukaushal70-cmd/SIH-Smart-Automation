import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, Navigate, useNavigate, useParams } from "react-router-dom";
import {
  ArrowLeft, Check, ChevronRight, Download, Eye, FileImage, FileText, Fingerprint, Gavel, History, Loader2, RefreshCw,
  RotateCcw, ScanText, Trash2, UploadCloud,
} from "lucide-react";
import { api } from "../api";
import type { AppDetail, AuditEvent, DocDetail, Finding, Meta } from "../types";
import {
  Button, Card, cx, DemoTag, Empty, ErrorBox, EVENT_LABELS, fmtBytes, fmtDate, inputCls, Label, pct, ReviewStatus, RiskBadge,
  SeverityBadge, Spinner, StatusBadge, useToast,
} from "../components/ui";

const SEV_ORDER = ["critical", "high", "medium", "low", "info"];

export function ReviewLanding() {
  const [target, setTarget] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => {
    api.applications()
      .then((apps) => {
        const pending = apps.filter((a) => a.review_status === "Pending Review").sort((a, b) => (b.risk_score ?? -1) - (a.risk_score ?? -1));
        setTarget((pending[0] ?? apps[0])?.id ?? "none");
      })
      .catch((e) => setErr(e.message));
  }, []);
  if (err) return <ErrorBox error={err} />;
  if (!target) return <Spinner />;
  return target === "none" ? <Navigate to="/applications" replace /> : <Navigate to={`/applications/${target}`} replace />;
}

export default function Workspace() {
  const { id = "" } = useParams();
  const toast = useToast();
  const nav = useNavigate();
  const [app, setApp] = useState<AppDetail | null>(null);
  const [meta, setMeta] = useState<Meta | null>(null);
  const [audit, setAudit] = useState<AuditEvent[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [focusPage, setFocusPage] = useState<{ doc: string; page: number; nonce: number } | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const [a, log] = await Promise.all([api.application(id), api.auditLog(id)]);
      setApp(a);
      setAudit(log);
      setError(null);
      setSelected((s) => (s && a.documents.some((d) => d.id === s) ? s : a.documents[0]?.id ?? null));
    } catch (e) {
      setError((e as Error).message);
    }
  }, [id]);
  useEffect(() => {
    setApp(null);
    load();
    api.meta().then(setMeta).catch(() => {});
  }, [load]);

  if (error && !app) return <ErrorBox error={error} onRetry={load} />;
  if (!app || !meta) return <Spinner label="Loading application…" />;

  const rerun = async () => {
    setBusy("rerun");
    try {
      await api.evaluate(app.id);
      await load();
      toast("success", "Compliance checks re-run with the current rule set");
    } catch (e) {
      toast("error", (e as Error).message);
    } finally {
      setBusy(null);
    }
  };
  const report = async () => {
    setBusy("report");
    try {
      await api.downloadReport(app.id);
      toast("success", "PDF report downloaded");
      load();
    } catch (e) {
      toast("error", (e as Error).message);
    } finally {
      setBusy(null);
    }
  };
  const del = async () => {
    if (!confirm(`Delete ${app.id} and its uploaded files? This cannot be undone.`)) return;
    try {
      await api.deleteApplication(app.id);
      toast("success", `${app.id} deleted`);
      nav("/applications");
    } catch (e) {
      toast("error", (e as Error).message);
    }
  };
  const jumpTo = (docId: string, page: number | null) => {
    setSelected(docId);
    setFocusPage({ doc: docId, page: page ?? 1, nonce: Date.now() });
    document.getElementById("doc-detail")?.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  return (
    <div className="space-y-5">
      <div>
        <Link to="/applications" className="inline-flex items-center gap-1 text-sm text-slate-500 hover:text-navy-800">
          <ArrowLeft className="h-4 w-4" /> Applications
        </Link>
        <div className="mt-2 flex flex-wrap items-start justify-between gap-4">
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <span className="font-mono text-sm text-slate-500">{app.id}</span>
              {app.is_demo && <DemoTag />}
              <ReviewStatus status={app.review_status} />
            </div>
            <h1 className="mt-1 text-2xl font-bold tracking-tight text-navy-900">{app.institution_name}</h1>
            <div className="mt-1 flex flex-wrap gap-x-5 gap-y-1 text-sm text-slate-600">
              <span>
                ID <span className="font-mono font-medium text-navy-800">{app.institution_id}</span>
              </span>
              <span>{app.application_type}</span>
              <span>AY {app.academic_year || "—"}</span>
              <span>Submitted {fmtDate(app.submitted_at)}</span>
              <span>{app.processing_status}</span>
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            {!app.is_demo && (
              <Button variant="danger" icon={<Trash2 className="h-4 w-4" />} onClick={del}>
                Delete
              </Button>
            )}
            <Button icon={<RefreshCw className="h-4 w-4" />} loading={busy === "rerun"} onClick={rerun}>
              Re-run checks
            </Button>
            <Button variant="primary" icon={<Download className="h-4 w-4" />} loading={busy === "report"} onClick={report}>
              Download PDF report
            </Button>
          </div>
        </div>
      </div>

      <div className="grid gap-5 xl:grid-cols-3">
        <div className="space-y-5 xl:col-span-2">
          <UploadPanel app={app} meta={meta} onChange={load} onSelect={setSelected} />
          <DocumentList app={app} selected={selected} onSelect={setSelected} onChange={load} />
          <div id="doc-detail" className="scroll-mt-4">
            {selected && <DocumentDetail key={selected} docId={selected} focus={focusPage?.doc === selected ? focusPage : null} meta={meta} appUpdatedAt={app.last_evaluated_at} />}
          </div>
          <Findings app={app} onChange={load} onJump={jumpTo} />
        </div>
        <div className="space-y-5">
          <ScoreCard app={app} />
          <DecisionPanel app={app} meta={meta} onChange={load} />
          <AuditTimeline events={audit} />
        </div>
      </div>
    </div>
  );
}

// ------------------------------------------------------------------ upload

type Step = "idle" | "uploading" | "processing" | "done" | "error";

function UploadPanel({ app, meta, onChange, onSelect }: { app: AppDetail; meta: Meta; onChange: () => Promise<void>; onSelect: (id: string) => void }) {
  const toast = useToast();
  const input = useRef<HTMLInputElement>(null);
  const missing = useMemo(() => {
    const have = new Set(app.documents.map((d) => d.declared_category));
    return Object.keys(meta.document_categories).filter((c) => c !== "other" && !have.has(c));
  }, [app.documents, meta]);
  const [category, setCategory] = useState<string>(missing[0] ?? "affiliation_letter");
  const [drag, setDrag] = useState(false);
  const [step, setStep] = useState<Step>("idle");
  const [file, setFile] = useState<File | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    if (step === "idle" && missing.length && !missing.includes(category)) setCategory(missing[0]);
  }, [missing]); // eslint-disable-line react-hooks/exhaustive-deps

  const run = async (f: File) => {
    setFile(f);
    setErr(null);
    if (f.size > meta.max_upload_mb * 1048576) {
      setStep("error");
      setErr(`File is ${fmtBytes(f.size)}; the limit is ${meta.max_upload_mb} MB.`);
      return;
    }
    setStep("uploading");
    try {
      const doc = await api.upload(app.id, f, category);
      setStep("processing");
      const processed = await api.processDocument(doc.id);
      setStep("done");
      await onChange();
      onSelect(doc.id);
      if (processed.processing_status === "Failed") toast("error", `Processing failed: ${processed.processing_error}`);
      else toast("success", `${doc.id} processed via ${processed.extraction_method === "ocr" ? `OCR (${processed.ocr_engine})` : processed.extraction_method === "mixed" ? "text + OCR" : "PDF text layer"} · ${processed.document_status}`);
    } catch (e) {
      setStep("error");
      setErr((e as Error).message);
      onChange();
    }
  };
  const onFiles = (files: FileList | null) => {
    if (files?.[0]) run(files[0]);
    if (input.current) input.current.value = "";
  };
  const working = step === "uploading" || step === "processing";

  return (
    <Card title="Upload supporting document" subtitle={`PDF (text or scanned), JPG, JPEG or PNG · max ${meta.max_upload_mb} MB · validated by extension, MIME type and file signature`}>
      <div className="grid gap-4 p-5 md:grid-cols-[220px_1fr]">
        <div className="space-y-3">
          <label className="block">
            <Label>Document category</Label>
            <select value={category} onChange={(e) => setCategory(e.target.value)} disabled={working} className={inputCls}>
              {Object.entries(meta.document_categories).map(([k, v]) => (
                <option key={k} value={k}>
                  {v}
                  {missing.includes(k) ? " (missing)" : ""}
                </option>
              ))}
            </select>
          </label>
          {missing.length > 0 && <p className="text-xs text-fuchsia-700">Still required: {missing.map((m) => meta.document_categories[m]).join(", ")}.</p>}
        </div>
        <div
          onDragOver={(e) => {
            e.preventDefault();
            setDrag(true);
          }}
          onDragLeave={() => setDrag(false)}
          onDrop={(e) => {
            e.preventDefault();
            setDrag(false);
            if (!working) onFiles(e.dataTransfer.files);
          }}
          onClick={() => !working && input.current?.click()}
          role="button"
          tabIndex={0}
          onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && input.current?.click()}
          className={cx("flex min-h-[132px] cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed px-4 py-5 text-center transition-colors", drag ? "border-teal-500 bg-teal-50" : "border-slate-300 bg-slate-50/60 hover:border-teal-400 hover:bg-teal-50/40", working && "cursor-wait")}
        >
          <input ref={input} type="file" accept=".pdf,.jpg,.jpeg,.png,application/pdf,image/jpeg,image/png" className="hidden" onChange={(e) => onFiles(e.target.files)} />
          {step === "idle" || step === "done" || step === "error" ? (
            <>
              <UploadCloud className="mb-2 h-7 w-7 text-teal-600" />
              <p className="text-sm font-medium text-navy-900">Drag & drop a file here, or click to browse</p>
              <p className="mt-0.5 text-xs text-slate-500">It will be uploaded as “{meta.document_categories[category]}” and processed immediately.</p>
            </>
          ) : (
            <div className="w-full max-w-sm text-left">
              <p className="mb-3 truncate text-sm font-medium text-navy-900">{file?.name}</p>
              <Progress label="Secure upload & validation" state={step === "uploading" ? "active" : "done"} />
              <Progress label="Text extraction / OCR, field extraction, classification" state={step === "processing" ? "active" : step === "uploading" ? "todo" : "done"} />
              <Progress label="Compliance rules, screening & risk score" state={step === "processing" ? "active" : "todo"} />
            </div>
          )}
          {step === "error" && err && (
            <div className="mt-3 w-full max-w-md" onClick={(e) => e.stopPropagation()}>
              <ErrorBox error={`${file?.name ?? "Upload"}: ${err}`} />
            </div>
          )}
        </div>
      </div>
    </Card>
  );
}

function Progress({ label, state }: { label: string; state: "todo" | "active" | "done" }) {
  return (
    <div className="flex items-center gap-2 py-1 text-xs">
      {state === "done" ? <Check className="h-4 w-4 text-emerald-600" /> : state === "active" ? <Loader2 className="h-4 w-4 animate-spin text-teal-600" /> : <span className="mx-1 h-2 w-2 rounded-full bg-slate-300" />}
      <span className={state === "todo" ? "text-slate-400" : "text-slate-700"}>{label}</span>
    </div>
  );
}

// ------------------------------------------------------------------ documents

function DocumentList({ app, selected, onSelect, onChange }: { app: AppDetail; selected: string | null; onSelect: (id: string) => void; onChange: () => void }) {
  const toast = useToast();
  const [busy, setBusy] = useState<string | null>(null);
  const reprocess = async (id: string) => {
    setBusy(id);
    try {
      await api.processDocument(id);
      toast("success", `${id} re-processed`);
      onChange();
    } catch (e) {
      toast("error", (e as Error).message);
    } finally {
      setBusy(null);
    }
  };
  const remove = async (id: string) => {
    if (!confirm(`Delete uploaded document ${id}?`)) return;
    try {
      await api.deleteDocument(id);
      toast("success", `${id} deleted`);
      onChange();
    } catch (e) {
      toast("error", (e as Error).message);
    }
  };
  return (
    <Card title={`Documents (${app.documents.length})`} subtitle="Issuer verification stays “Not Verified” — no authorised issuer integration exists in this prototype.">
      {app.documents.length === 0 ? (
        <Empty icon={<FileText className="h-5 w-5" />} title="No documents uploaded yet">
          Upload the required certificates above. Sample files are in the <code>samples/</code> folder.
        </Empty>
      ) : (
        <ul className="divide-y divide-slate-100">
          {app.documents.map((d) => (
            <li key={d.id} onClick={() => onSelect(d.id)} className={cx("flex cursor-pointer flex-wrap items-center gap-3 px-5 py-3 transition-colors", selected === d.id ? "bg-teal-50/60" : "hover:bg-slate-50")}>
              <div className={cx("grid h-9 w-9 shrink-0 place-items-center rounded-lg", d.mime_type === "application/pdf" ? "bg-navy-100 text-navy-800" : "bg-saffron-50 text-orange-700")}>
                {d.mime_type === "application/pdf" ? <FileText className="h-4 w-4" /> : <FileImage className="h-4 w-4" />}
              </div>
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <span className="truncate text-sm font-medium text-navy-900">{d.declared_category_label}</span>
                  <span className="font-mono text-[11px] text-slate-400">{d.id}</span>
                </div>
                <div className="truncate text-xs text-slate-500">
                  {d.original_filename} · {fmtBytes(d.size_bytes)} ·{" "}
                  {d.processing_status === "Processed"
                    ? d.extraction_method === "ocr"
                      ? `OCR · ${d.ocr_engine} · ${pct(d.ocr_confidence)} confidence`
                      : d.extraction_method === "mixed"
                        ? "text layer + OCR"
                        : "PDF text layer"
                    : d.processing_status}
                </div>
                {d.processing_error && <div className="mt-0.5 text-xs text-red-700">{d.processing_error}</div>}
              </div>
              <div className="flex items-center gap-2">
                <span className="hidden text-[11px] text-slate-400 md:inline">Issuer: {d.issuer_verification.startsWith("Pending") ? "Pending (simulated)" : d.issuer_verification}</span>
                <StatusBadge status={d.document_status} />
                {(d.processing_status !== "Processed" || !d.is_demo) && (
                  <button title="Re-process" onClick={(e) => (e.stopPropagation(), reprocess(d.id))} className="rounded p-1 text-slate-400 hover:bg-slate-100 hover:text-teal-700">
                    {busy === d.id ? <Loader2 className="h-4 w-4 animate-spin" /> : <RotateCcw className="h-4 w-4" />}
                  </button>
                )}
                {!d.is_demo && (
                  <button title="Delete upload" onClick={(e) => (e.stopPropagation(), remove(d.id))} className="rounded p-1 text-slate-400 hover:bg-red-50 hover:text-red-600">
                    <Trash2 className="h-4 w-4" />
                  </button>
                )}
                <ChevronRight className="h-4 w-4 text-slate-300" />
              </div>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}

const TABS = ["Fields", "Preview", "Extracted text", "Screening"] as const;

function DocumentDetail({ docId, focus, meta, appUpdatedAt }: { docId: string; focus: { page: number; nonce: number } | null; meta: Meta; appUpdatedAt: string | null }) {
  const [doc, setDoc] = useState<DocDetail | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [tab, setTab] = useState<(typeof TABS)[number]>("Fields");
  const [page, setPage] = useState(1);
  useEffect(() => {
    api.document(docId).then(setDoc).catch((e) => setErr(e.message));
  }, [docId, appUpdatedAt]);
  useEffect(() => {
    if (focus) {
      setTab("Preview");
      setPage(focus.page);
    }
  }, [focus?.nonce]); // eslint-disable-line react-hooks/exhaustive-deps

  if (err) return <ErrorBox error={err} />;
  if (!doc) return <Card><Spinner /></Card>;

  return (
    <Card
      title={
        <span className="flex items-center gap-2">
          <Eye className="h-4 w-4 text-teal-600" /> {doc.id} · {doc.original_filename}
        </span>
      }
      subtitle={`Declared: ${doc.declared_category_label} · Detected: ${doc.detected_type_label ?? "—"} (${pct(doc.classification_confidence)}) · SHA-256 ${doc.sha256.slice(0, 16)}…`}
      action={<StatusBadge status={doc.document_status} />}
    >
      <div className="flex gap-1 border-b border-slate-100 px-4">
        {TABS.map((t) => (
          <button key={t} onClick={() => setTab(t)} className={cx("-mb-px border-b-2 px-3 py-2.5 text-sm font-medium", tab === t ? "border-teal-600 text-teal-700" : "border-transparent text-slate-500 hover:text-slate-700")}>
            {t}
          </button>
        ))}
      </div>
      <div className="p-5">
        {doc.processing_status === "Failed" && <ErrorBox error={doc.processing_error ?? "Processing failed"} />}
        {tab === "Fields" && doc.processing_status === "Processed" && (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="text-left text-xs text-slate-500">
                <tr>
                  <th className="pb-2 pr-3 font-medium">Field</th>
                  <th className="pb-2 pr-3 font-medium">Extracted value</th>
                  <th className="pb-2 pr-3 font-medium">Status</th>
                  <th className="pb-2 font-medium">Evidence (source line)</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(doc.fields).map(([k, f]) => (
                  <tr key={k} className="border-t border-slate-100 align-top">
                    <td className="py-2 pr-3 text-slate-600">{meta.fields[k] ?? k}</td>
                    <td className="py-2 pr-3 font-medium text-navy-900">
                      {f.value ?? <span className="text-slate-400">—</span>}
                      {f.normalized && f.normalized !== f.value && <div className="font-mono text-[11px] font-normal text-slate-500">→ {f.normalized}</div>}
                    </td>
                    <td className="py-2 pr-3">
                      <span className={cx("rounded px-1.5 py-0.5 text-[11px] font-semibold", f.status === "detected" ? "bg-emerald-50 text-emerald-700" : f.status === "uncertain" ? "bg-amber-50 text-amber-700" : "bg-slate-100 text-slate-500")}>{f.status}</span>
                    </td>
                    <td className="py-2 text-xs text-slate-500">
                      {f.evidence ? (
                        <>
                          <span className="mr-1 rounded bg-slate-100 px-1 font-mono text-[10px]">p.{f.page}</span>“{f.evidence}”
                        </>
                      ) : (
                        f.note
                      )}
                      {f.evidence && f.note && <div className="text-amber-700">{f.note}</div>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="mt-3 text-xs text-slate-500">Values are copied from the document text only; fields that cannot be located are reported as missing, never guessed.</p>
          </div>
        )}
        {tab === "Preview" && (
          <div>
            {doc.page_count > 1 && (
              <div className="mb-3 flex items-center gap-2 text-sm">
                <Button disabled={page <= 1} onClick={() => setPage(page - 1)}>
                  Prev
                </Button>
                <span className="tabular">
                  Page {page} / {doc.page_count}
                </span>
                <Button disabled={page >= doc.page_count} onClick={() => setPage(page + 1)}>
                  Next
                </Button>
              </div>
            )}
            <div className="max-h-[720px] overflow-auto rounded-lg border border-slate-200 bg-slate-100 p-3 scroll-thin">
              <img src={api.previewUrl(doc.id, page)} alt={`Preview of ${doc.original_filename}, page ${page}`} className="mx-auto max-w-full bg-white shadow" />
            </div>
          </div>
        )}
        {tab === "Extracted text" && (
          <div className="space-y-3">
            {doc.pages.map((p) => (
              <div key={p.page}>
                <div className="mb-1 flex items-center gap-2 text-xs text-slate-500">
                  <ScanText className="h-3.5 w-3.5" /> Page {p.page} · {p.method === "ocr" ? `OCR (${doc.ocr_engine}) · ${pct(p.confidence)} mean confidence` : "PDF text layer"} · {p.text.length} characters
                </div>
                <pre className="max-h-80 overflow-auto whitespace-pre-wrap rounded-lg bg-slate-900 p-3 font-mono text-xs leading-relaxed text-slate-100 scroll-thin">{p.text || "(no text)"}</pre>
              </div>
            ))}
            {doc.pages.length === 0 && <Empty title="No text extracted" />}
          </div>
        )}
        {tab === "Screening" && (
          <div className="space-y-3 text-sm">
            <p className="rounded-lg bg-sky-50 px-3 py-2 text-xs text-sky-900">Screening facts are signals for the reviewer, not proof of forgery or authenticity. A SHA-256 hash shows identical file content only.</p>
            <dl className="grid grid-cols-1 gap-x-6 gap-y-2 sm:grid-cols-2">
              <Fact k="SHA-256" v={<span className="break-all font-mono text-xs">{doc.sha256}</span>} />
              {Object.entries(doc.screening).map(([k, v]) => (
                <Fact key={k} k={k.replace(/_/g, " ")} v={typeof v === "object" && v !== null ? <span className="font-mono text-xs">{JSON.stringify(v)}</span> : String(v ?? "—")} />
              ))}
              <Fact k="classifier scores" v={<span className="font-mono text-xs">{JSON.stringify(doc.classification_scores)}</span>} />
            </dl>
          </div>
        )}
      </div>
    </Card>
  );
}

function Fact({ k, v }: { k: string; v: React.ReactNode }) {
  return (
    <div className="border-b border-slate-100 pb-1.5">
      <dt className="text-xs capitalize text-slate-500">{k}</dt>
      <dd className="text-slate-800">{v}</dd>
    </div>
  );
}

// ------------------------------------------------------------------ findings

function Findings({ app, onChange, onJump }: { app: AppDetail; onChange: () => void; onJump: (doc: string, page: number | null) => void }) {
  const [outcome, setOutcome] = useState("");
  const [status, setStatus] = useState("");
  const list = app.findings
    .filter((f) => (!outcome || f.outcome === outcome) && (!status || f.status === status))
    .sort((a, b) => SEV_ORDER.indexOf(a.severity) - SEV_ORDER.indexOf(b.severity));
  const counts = app.outcome_counts;
  return (
    <Card
      title={`Findings (${app.findings.length})`}
      subtitle={`Rule set ${app.ruleset_fingerprint ?? "—"} · evaluated ${fmtDate(app.last_evaluated_at, true)}`}
      action={
        <div className="flex gap-2">
          <select aria-label="Filter by outcome" value={outcome} onChange={(e) => setOutcome(e.target.value)} className={inputCls.replace("w-full", "w-auto") + " py-1.5 text-xs"}>
            <option value="">All outcomes</option>
            {Object.entries(counts).map(([o, n]) => (
              <option key={o} value={o}>
                {o} ({n})
              </option>
            ))}
          </select>
          <select aria-label="Filter by status" value={status} onChange={(e) => setStatus(e.target.value)} className={inputCls.replace("w-full", "w-auto") + " py-1.5 text-xs"}>
            <option value="">Open & reviewed</option>
            <option>Open</option>
            <option>Reviewed</option>
          </select>
        </div>
      }
    >
      {app.findings.length === 0 ? (
        <Empty icon={<Check className="h-5 w-5" />} title={app.documents.length ? "No findings — all enabled checks passed" : "No findings yet"}>
          {app.documents.length ? "This means the prototype checks passed; it is not an issuer verification." : "Findings appear after documents are processed."}
        </Empty>
      ) : (
        <ul className="space-y-3 p-4">
          {list.map((f) => (
            <FindingCard key={f.id} f={f} app={app} onChange={onChange} onJump={onJump} />
          ))}
        </ul>
      )}
    </Card>
  );
}

function FindingCard({ f, app, onChange, onJump }: { f: Finding; app: AppDetail; onChange: () => void; onJump: (doc: string, page: number | null) => void }) {
  const toast = useToast();
  const [note, setNote] = useState("");
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const pts = app.score_breakdown?.items.find((i) => i.finding_id === f.id)?.points;
  const save = async (s: "Open" | "Reviewed") => {
    setBusy(true);
    try {
      await api.updateFinding(f.id, s, note);
      toast("success", `${f.id} marked ${s.toLowerCase()}`);
      setOpen(false);
      setNote("");
      onChange();
    } catch (e) {
      toast("error", (e as Error).message);
    } finally {
      setBusy(false);
    }
  };
  return (
    <li className={cx("rounded-lg border bg-white", f.status === "Reviewed" ? "border-slate-200 opacity-75" : "border-slate-200 border-l-4", f.status === "Open" && (f.severity === "high" || f.severity === "critical" ? "border-l-red-500" : f.severity === "medium" ? "border-l-amber-500" : "border-l-slate-400"))}>
      <div className="flex flex-wrap items-center gap-2 border-b border-slate-100 px-4 py-2">
        <SeverityBadge severity={f.severity} />
        <StatusBadge status={f.outcome} />
        <span className="font-mono text-[11px] text-slate-500">
          {f.id} · {f.rule_id} v{f.rule_version}
        </span>
        {pts !== undefined && <span className="text-[11px] text-slate-500 tabular">+{pts} risk pts</span>}
        <span className={cx("ml-auto rounded px-1.5 py-0.5 text-[11px] font-medium", f.status === "Reviewed" ? "bg-emerald-50 text-emerald-700" : "bg-slate-100 text-slate-600")}>{f.status}</span>
      </div>
      <div className="space-y-2 px-4 py-3 text-sm">
        <p className="font-semibold text-navy-900">{f.title}</p>
        <p className="text-slate-600">{f.description}</p>
        {(f.expected || f.actual) && (
          <div className="grid gap-2 sm:grid-cols-2">
            <div className="rounded-md bg-slate-50 px-3 py-1.5">
              <div className="text-[10.5px] font-semibold uppercase tracking-wide text-slate-500">Expected</div>
              <div className="text-slate-800">{f.expected ?? "—"}</div>
            </div>
            <div className="rounded-md bg-red-50/60 px-3 py-1.5">
              <div className="text-[10.5px] font-semibold uppercase tracking-wide text-slate-500">Actual</div>
              <div className="font-medium text-slate-900">{f.actual ?? "—"}</div>
            </div>
          </div>
        )}
        <div className="flex flex-wrap items-start gap-x-2 text-xs text-slate-500">
          <Fingerprint className="mt-0.5 h-3.5 w-3.5" />
          <span>Evidence: {f.evidence_source}</span>
          {f.evidence && <span className="italic text-slate-700">“{f.evidence}”</span>}
          {f.document_id && (
            <button onClick={() => onJump(f.document_id!, f.page)} className="font-medium text-teal-700 hover:underline">
              View in document{f.page ? ` (p.${f.page})` : ""}
            </button>
          )}
        </div>
        <p className="text-xs">
          <span className="font-semibold text-navy-800">Suggested action:</span> <span className="text-slate-700">{f.recommended_action}</span>
        </p>
        {f.reviewer_note && (
          <p className="rounded bg-emerald-50 px-2 py-1 text-xs text-emerald-900">
            Officer note ({f.reviewed_by}, {fmtDate(f.reviewed_at, true)}): {f.reviewer_note}
          </p>
        )}
        <div className="flex flex-wrap items-center gap-2 pt-1">
          {f.status === "Open" ? (
            open ? (
              <>
                <input value={note} onChange={(e) => setNote(e.target.value)} placeholder="Optional note (e.g. checked original, acceptable)" className={inputCls + " flex-1 py-1.5 text-xs"} />
                <Button variant="teal" loading={busy} onClick={() => save("Reviewed")} className="py-1.5 text-xs">
                  Confirm reviewed
                </Button>
                <Button variant="ghost" onClick={() => setOpen(false)} className="py-1.5 text-xs">
                  Cancel
                </Button>
              </>
            ) : (
              <Button icon={<Check className="h-3.5 w-3.5" />} onClick={() => setOpen(true)} className="py-1.5 text-xs">
                Mark as reviewed
              </Button>
            )
          ) : (
            <Button variant="ghost" loading={busy} onClick={() => save("Open")} className="py-1.5 text-xs">
              Re-open
            </Button>
          )}
        </div>
      </div>
    </li>
  );
}

// ------------------------------------------------------------------ score

function ScoreCard({ app }: { app: AppDetail }) {
  const sb = app.score_breakdown;
  if (!sb || app.risk_score === null)
    return (
      <Card title="Risk indicator">
        <Empty title="Not evaluated yet">Upload and process documents to compute the score.</Empty>
      </Card>
    );
  const factors = Object.entries(sb.factors);
  const ring = app.risk_band === "High" ? "#c4320a" : app.risk_band === "Medium" ? "#d68b00" : "#12805c";
  return (
    <Card title="Risk indicator" subtitle="Internal prototype indicator · not a fraud probability · not an official AICTE score">
      <div className="flex items-center gap-5 px-5 pt-4">
        <div className="relative h-24 w-24 shrink-0">
          <svg viewBox="0 0 36 36" className="h-24 w-24 -rotate-90">
            <circle cx="18" cy="18" r="15.5" fill="none" stroke="#eef2f6" strokeWidth="3.2" />
            <circle cx="18" cy="18" r="15.5" fill="none" stroke={ring} strokeWidth="3.2" strokeLinecap="round" strokeDasharray={`${(app.risk_score / 100) * 97.4} 97.4`} />
          </svg>
          <div className="absolute inset-0 flex flex-col items-center justify-center">
            <span className="text-2xl font-bold text-navy-900 tabular">{app.risk_score}</span>
            <span className="text-[10px] text-slate-500">/ 100</span>
          </div>
        </div>
        <div className="space-y-1 text-sm">
          <RiskBadge score={app.risk_score} band={app.risk_band} size="lg" />
          <p className="text-xs text-slate-500">
            Bands: Low &lt; {sb.bands.medium} ≤ Medium &lt; {sb.bands.high} ≤ High
          </p>
          <p className="font-mono text-[11px] text-slate-500">{sb.formula}</p>
        </div>
      </div>
      <div className="space-y-2 p-5">
        {factors.map(([k, f]) => (
          <div key={k}>
            <div className="flex justify-between text-xs">
              <span className={f.count ? "text-slate-700" : "text-slate-400"}>
                {f.label} <span className="text-slate-400">({f.count})</span>
              </span>
              <span className="font-medium tabular text-slate-700">{f.points} pts</span>
            </div>
            <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-slate-100">
              <div className="h-full rounded-full bg-navy-700" style={{ width: `${Math.min(100, f.points)}%` }} />
            </div>
          </div>
        ))}
        <div className="flex justify-between border-t border-slate-100 pt-2 text-xs">
          <span className="text-slate-500">Raw total (capped at 100)</span>
          <span className="font-semibold tabular">{sb.raw_total}</span>
        </div>
        <details className="text-xs text-slate-500">
          <summary className="cursor-pointer font-medium text-teal-700">Weights used (scoring v{sb.scoring_version})</summary>
          <div className="mt-1 space-y-0.5 font-mono text-[11px]">
            <div>severity: {Object.entries(sb.severity_points).map(([k, v]) => `${k}=${v}`).join(" ")}</div>
            <div>factor: {Object.entries(sb.factor_weights).map(([k, v]) => `${k}×${v}`).join(" ")}</div>
          </div>
        </details>
      </div>
    </Card>
  );
}

// ------------------------------------------------------------------ decision

function DecisionPanel({ app, meta, onChange }: { app: AppDetail; meta: Meta; onChange: () => void }) {
  const toast = useToast();
  const [action, setAction] = useState("request_clarification");
  const [notes, setNotes] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const open = app.findings.filter((f) => f.status === "Open").length;
  const submit = async () => {
    setBusy(true);
    setErr(null);
    try {
      await api.review(app.id, action, notes);
      toast("success", "Review action recorded in the audit log");
      setNotes("");
      onChange();
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setBusy(false);
    }
  };
  return (
    <Card title={<span className="flex items-center gap-2"><Gavel className="h-4 w-4 text-teal-600" />Officer review decision</span>} subtitle="Recommendations only — not an official regulatory approval.">
      <div className="space-y-3 p-5">
        <div className="flex items-center justify-between rounded-lg bg-slate-50 px-3 py-2 text-xs">
          <span className="text-slate-600">Current status</span>
          <ReviewStatus status={app.review_status} />
        </div>
        {open > 0 && action === "provisional_recommendation" && <p className="rounded bg-amber-50 px-2 py-1.5 text-xs text-amber-900">{open} finding(s) are still open. Your decision will be recorded with this count.</p>}
        <label className="block">
          <Label>Action</Label>
          <select value={action} onChange={(e) => setAction(e.target.value)} className={inputCls}>
            {Object.entries(meta.review_actions).map(([k, v]) => (
              <option key={k} value={k}>
                {v.label}
              </option>
            ))}
          </select>
        </label>
        {action === "request_issuer_verification" && <p className="text-xs text-slate-500">Marks all documents “Pending (simulated)”. No request is sent anywhere: no authorised issuer integration exists.</p>}
        <label className="block">
          <Label hint="required">Notes / reasons</Label>
          <textarea value={notes} onChange={(e) => setNotes(e.target.value)} rows={3} className={inputCls} placeholder="e.g. Fire NOC expired on 20 Jun 2026; renewed certificate requested." />
        </label>
        {err && <ErrorBox error={err} />}
        <Button variant="primary" className="w-full" loading={busy} onClick={submit}>
          Record decision
        </Button>
        {app.reviews.length > 0 && (
          <div className="border-t border-slate-100 pt-3">
            <p className="mb-2 text-xs font-semibold text-slate-600">Decision history</p>
            <ul className="space-y-2">
              {[...app.reviews].reverse().map((r) => (
                <li key={r.id} className="rounded-md border border-slate-100 px-3 py-2 text-xs">
                  <div className="font-medium text-navy-900">{r.action_label}</div>
                  <div className="text-slate-500">
                    {r.officer_name} · {fmtDate(r.created_at, true)}
                  </div>
                  {r.notes && <div className="mt-1 text-slate-700">{r.notes}</div>}
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </Card>
  );
}

function AuditTimeline({ events }: { events: AuditEvent[] }) {
  return (
    <Card title={<span className="flex items-center gap-2"><History className="h-4 w-4 text-teal-600" />Audit history</span>} subtitle="Append-only, hash-chained events for this application">
      <ol className="max-h-[420px] space-y-0 overflow-auto px-5 py-3 scroll-thin">
        {events.map((e) => (
          <li key={e.id} className="relative border-l border-slate-200 pb-3 pl-4 last:pb-0">
            <span className={cx("absolute -left-[5px] top-1 h-2.5 w-2.5 rounded-full ring-2 ring-white", e.event_type === "review_action" ? "bg-saffron-500" : e.event_type === "upload_rejected" ? "bg-red-500" : "bg-teal-500")} />
            <div className="text-xs font-medium text-slate-800">{EVENT_LABELS[e.event_type] ?? e.event_type}</div>
            <div className="text-[11px] text-slate-500">
              {e.actor} · {fmtDate(e.created_at, true)} · <span className="font-mono">#{e.hash.slice(0, 8)}</span>
            </div>
            <EventDetail e={e} />
          </li>
        ))}
      </ol>
    </Card>
  );
}

function EventDetail({ e }: { e: AuditEvent }) {
  const d = e.details as Record<string, unknown>;
  const bits: string[] = [];
  if (d.document_id) bits.push(String(d.document_id));
  if (d.action) bits.push(String(d.action).replace(/_/g, " "));
  if (d.new_status) bits.push(`→ ${d.new_status}`);
  if (e.event_type === "application_evaluated") bits.push(`score ${d.risk_score ?? "—"} · ${d.findings} findings`);
  if (d.reason) bits.push(String(d.reason));
  if (d.status && e.event_type === "document_processed") bits.push(`${d.status} via ${d.method ?? "—"}`);
  if (!bits.length) return null;
  return <div className="text-[11px] text-slate-600">{bits.join(" · ")}</div>;
}
