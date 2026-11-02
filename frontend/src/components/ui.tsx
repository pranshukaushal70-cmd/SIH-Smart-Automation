import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { AlertTriangle, CheckCircle2, CircleDashed, Clock, FileX2, Info, Loader2, ShieldAlert, X, XCircle } from "lucide-react";

export const cx = (...c: (string | false | null | undefined)[]) => c.filter(Boolean).join(" ");

export function Card({ children, className, title, action, subtitle }: { children: ReactNode; className?: string; title?: ReactNode; subtitle?: ReactNode; action?: ReactNode }) {
  return (
    <section className={cx("rounded-xl border border-slate-200 bg-white shadow-[0_1px_2px_rgba(16,24,40,0.04)]", className)}>
      {(title || action) && (
        <header className="flex items-start justify-between gap-3 border-b border-slate-100 px-5 py-3.5">
          <div>
            <h2 className="text-[15px] font-semibold text-navy-900">{title}</h2>
            {subtitle && <p className="mt-0.5 text-xs text-slate-500">{subtitle}</p>}
          </div>
          {action}
        </header>
      )}
      {children}
    </section>
  );
}

type BtnVariant = "primary" | "secondary" | "ghost" | "danger" | "teal";
export function Button({ variant = "secondary", loading, icon, children, className, ...rest }: React.ButtonHTMLAttributes<HTMLButtonElement> & { variant?: BtnVariant; loading?: boolean; icon?: ReactNode }) {
  const styles: Record<BtnVariant, string> = {
    primary: "bg-navy-900 text-white hover:bg-navy-800 border-navy-900",
    teal: "bg-teal-600 text-white hover:bg-teal-700 border-teal-600",
    secondary: "bg-white text-slate-700 hover:bg-slate-50 border-slate-300",
    ghost: "bg-transparent text-slate-600 hover:bg-slate-100 border-transparent",
    danger: "bg-white text-red-700 hover:bg-red-50 border-red-200",
  };
  return (
    <button
      {...rest}
      disabled={rest.disabled || loading}
      className={cx(
        "inline-flex items-center justify-center gap-1.5 rounded-lg border px-3.5 py-2 text-sm font-medium transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-teal-500 focus-visible:ring-offset-1 disabled:cursor-not-allowed disabled:opacity-55",
        styles[variant],
        className,
      )}
    >
      {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : icon}
      {children}
    </button>
  );
}

const STATUS: Record<string, { cls: string; icon: ReactNode }> = {
  Verified: { cls: "bg-emerald-50 text-emerald-800 ring-emerald-200", icon: <CheckCircle2 className="h-3.5 w-3.5" /> },
  "Review Required": { cls: "bg-amber-50 text-amber-800 ring-amber-200", icon: <AlertTriangle className="h-3.5 w-3.5" /> },
  Flagged: { cls: "bg-red-50 text-red-800 ring-red-200", icon: <ShieldAlert className="h-3.5 w-3.5" /> },
  Missing: { cls: "bg-fuchsia-50 text-fuchsia-800 ring-fuchsia-200", icon: <FileX2 className="h-3.5 w-3.5" /> },
  Expired: { cls: "bg-orange-50 text-orange-800 ring-orange-200", icon: <Clock className="h-3.5 w-3.5" /> },
  "Screening Signal": { cls: "bg-sky-50 text-sky-800 ring-sky-200", icon: <Info className="h-3.5 w-3.5" /> },
  "Pending Processing": { cls: "bg-slate-100 text-slate-700 ring-slate-200", icon: <CircleDashed className="h-3.5 w-3.5" /> },
  "Processing Failed": { cls: "bg-red-50 text-red-800 ring-red-300", icon: <XCircle className="h-3.5 w-3.5" /> },
};

export function StatusBadge({ status, className }: { status: string; className?: string }) {
  const s = STATUS[status] ?? { cls: "bg-slate-100 text-slate-700 ring-slate-200", icon: null };
  return (
    <span className={cx("inline-flex items-center gap-1 whitespace-nowrap rounded-full px-2 py-0.5 text-xs font-medium ring-1 ring-inset", s.cls, className)}>
      {s.icon}
      {status}
    </span>
  );
}

const SEV: Record<string, string> = {
  critical: "bg-red-900 text-white",
  high: "bg-red-600 text-white",
  medium: "bg-amber-500 text-white",
  low: "bg-slate-500 text-white",
  info: "bg-slate-200 text-slate-700",
};
export function SeverityBadge({ severity }: { severity: string }) {
  return <span className={cx("rounded px-1.5 py-0.5 text-[10.5px] font-bold uppercase tracking-wide", SEV[severity])}>{severity}</span>;
}

export function RiskBadge({ score, band, size = "sm" }: { score: number | null; band: string | null; size?: "sm" | "lg" }) {
  if (score === null || !band) return <span className="text-xs text-slate-400">Not evaluated</span>;
  const cls = band === "High" ? "bg-red-50 text-red-800 ring-red-200" : band === "Medium" ? "bg-amber-50 text-amber-800 ring-amber-200" : "bg-emerald-50 text-emerald-800 ring-emerald-200";
  return (
    <span className={cx("inline-flex items-center gap-1.5 rounded-full font-semibold ring-1 ring-inset tabular", cls, size === "lg" ? "px-3 py-1 text-sm" : "px-2 py-0.5 text-xs")}>
      {score}
      <span className="font-medium opacity-80">· {band}</span>
    </span>
  );
}

export function ReviewStatus({ status }: { status: string }) {
  const cls = status.startsWith("Provisional")
    ? "text-emerald-700 bg-emerald-50"
    : status === "Pending Review"
      ? "text-navy-800 bg-navy-100"
      : status.startsWith("Returned")
        ? "text-fuchsia-700 bg-fuchsia-50"
        : "text-amber-800 bg-amber-50";
  return <span className={cx("whitespace-nowrap rounded-md px-2 py-0.5 text-xs font-medium", cls)}>{status}</span>;
}

export function DemoTag() {
  return <span className="rounded bg-saffron-50 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-orange-700 ring-1 ring-inset ring-orange-200">Synthetic demo</span>;
}

export function Spinner({ label }: { label?: string }) {
  return (
    <div className="flex items-center justify-center gap-2 py-12 text-sm text-slate-500">
      <Loader2 className="h-5 w-5 animate-spin text-teal-600" />
      {label ?? "Loading…"}
    </div>
  );
}

export function ErrorBox({ error, onRetry }: { error: string; onRetry?: () => void }) {
  return (
    <div role="alert" className="flex items-start gap-3 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
      <XCircle className="mt-0.5 h-4 w-4 shrink-0" />
      <div className="flex-1">{error}</div>
      {onRetry && (
        <button onClick={onRetry} className="font-medium underline">
          Retry
        </button>
      )}
    </div>
  );
}

export function Empty({ icon, title, children }: { icon?: ReactNode; title: string; children?: ReactNode }) {
  return (
    <div className="flex flex-col items-center justify-center px-6 py-10 text-center">
      <div className="mb-3 rounded-full bg-slate-100 p-3 text-slate-400">{icon ?? <Info className="h-5 w-5" />}</div>
      <p className="text-sm font-medium text-slate-700">{title}</p>
      {children && <div className="mt-1 max-w-sm text-xs text-slate-500">{children}</div>}
    </div>
  );
}

export function Modal({ open, onClose, title, children, wide }: { open: boolean; onClose: () => void; title: string; children: ReactNode; wide?: boolean }) {
  useEffect(() => {
    const h = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  }, [onClose]);
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-navy-950/40 p-4" onMouseDown={onClose}>
      <div role="dialog" aria-modal="true" aria-label={title} onMouseDown={(e) => e.stopPropagation()} className={cx("max-h-[92vh] w-full overflow-auto rounded-xl bg-white shadow-xl", wide ? "max-w-4xl" : "max-w-lg")}>
        <div className="flex items-center justify-between border-b border-slate-100 px-5 py-3.5">
          <h3 className="font-semibold text-navy-900">{title}</h3>
          <button onClick={onClose} aria-label="Close" className="rounded p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-600">
            <X className="h-4 w-4" />
          </button>
        </div>
        <div className="p-5">{children}</div>
      </div>
    </div>
  );
}

export const inputCls = "w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-800 placeholder:text-slate-400 focus:border-teal-500 focus:outline-none focus:ring-2 focus:ring-teal-500/20";
export function Label({ children, hint }: { children: ReactNode; hint?: string }) {
  return (
    <span className="mb-1 block text-xs font-medium text-slate-600">
      {children}
      {hint && <span className="ml-1 font-normal text-slate-400">{hint}</span>}
    </span>
  );
}

// ------------------------------------------------------------------ toasts
type Toast = { id: number; kind: "success" | "error" | "info"; text: string };
const ToastCtx = createContext<(kind: Toast["kind"], text: string) => void>(() => {});
export const useToast = () => useContext(ToastCtx);
export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const push = useCallback((kind: Toast["kind"], text: string) => {
    const id = Date.now() + Math.random();
    setToasts((t) => [...t, { id, kind, text }]);
    setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), kind === "error" ? 7000 : 4000);
  }, []);
  return (
    <ToastCtx.Provider value={push}>
      {children}
      <div className="pointer-events-none fixed bottom-4 right-4 z-[60] flex w-80 flex-col gap-2" aria-live="polite">
        {toasts.map((t) => (
          <div key={t.id} className={cx("pointer-events-auto flex items-start gap-2 rounded-lg border px-3.5 py-2.5 text-sm shadow-lg", t.kind === "error" ? "border-red-200 bg-white text-red-800" : t.kind === "success" ? "border-emerald-200 bg-white text-emerald-800" : "border-slate-200 bg-white text-slate-700")}>
            {t.kind === "error" ? <XCircle className="mt-0.5 h-4 w-4 shrink-0" /> : t.kind === "success" ? <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0" /> : <Info className="mt-0.5 h-4 w-4 shrink-0" />}
            <span>{t.text}</span>
          </div>
        ))}
      </div>
    </ToastCtx.Provider>
  );
}

export const fmtDate = (s: string | null | undefined, withTime = false) => {
  if (!s) return "—";
  const d = new Date(s);
  if (isNaN(d.getTime())) return s;
  return d.toLocaleString("en-IN", withTime ? { day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" } : { day: "2-digit", month: "short", year: "numeric" });
};
export const fmtBytes = (n: number) => (n > 1048576 ? `${(n / 1048576).toFixed(1)} MB` : `${Math.max(1, Math.round(n / 1024))} KB`);
export const pct = (n: number | null | undefined) => (n === null || n === undefined ? "—" : `${Math.round(n * 100)}%`);
export const EVENT_LABELS: Record<string, string> = {
  application_created: "Application created",
  document_uploaded: "Document uploaded",
  document_processed: "Document processed",
  application_evaluated: "Compliance checks run",
  finding_reviewed: "Finding marked reviewed",
  finding_reopened: "Finding re-opened",
  review_action: "Officer review action",
  report_generated: "Report generated",
  rule_updated: "Rule updated",
  rule_created: "Rule created",
  scoring_updated: "Scoring weights updated",
  upload_rejected: "Upload rejected",
  document_deleted: "Document deleted",
  application_deleted: "Application deleted",
  demo_seeded: "Synthetic demo data seeded",
};
