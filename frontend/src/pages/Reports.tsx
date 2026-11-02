import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { Download, Link2, ShieldCheck, ShieldX } from "lucide-react";
import { api } from "../api";
import type { AppSummary, AuditEvent } from "../types";
import { Button, Card, DemoTag, ErrorBox, EVENT_LABELS, fmtDate, inputCls, ReviewStatus, RiskBadge, Spinner, useToast } from "../components/ui";

export default function Reports() {
  const toast = useToast();
  const [apps, setApps] = useState<AppSummary[] | null>(null);
  const [events, setEvents] = useState<AuditEvent[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [verify, setVerify] = useState<{ valid: boolean; message: string; head_hash?: string } | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [type, setType] = useState("");
  const [appFilter, setAppFilter] = useState("");

  const load = useCallback(() => {
    Promise.all([api.applications(), api.globalAudit(300)])
      .then(([a, e]) => {
        setApps(a);
        setEvents(e);
        setError(null);
      })
      .catch((e) => setError(e.message));
  }, []);
  useEffect(load, [load]);

  const filtered = useMemo(() => events.filter((e) => (!type || e.event_type === type) && (!appFilter || e.application_id === appFilter)), [events, type, appFilter]);
  const types = useMemo(() => [...new Set(events.map((e) => e.event_type))].sort(), [events]);

  if (error) return <ErrorBox error={error} onRetry={load} />;
  if (!apps) return <Spinner />;

  const download = async (id: string) => {
    setBusy(id);
    try {
      await api.downloadReport(id);
      toast("success", `Report for ${id} downloaded`);
      load();
    } catch (e) {
      toast("error", (e as Error).message);
    } finally {
      setBusy(null);
    }
  };
  const runVerify = async () => {
    setBusy("verify");
    try {
      setVerify(await api.verifyAudit());
    } catch (e) {
      toast("error", (e as Error).message);
    } finally {
      setBusy(null);
    }
  };

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-navy-900">Reports & audit log</h1>
        <p className="text-sm text-slate-500">PDF reports include findings with evidence, the score breakdown, applied rule IDs/versions, officer decisions and the audit trail.</p>
      </div>

      <Card title="Application review reports">
        <div className="overflow-x-auto">
          <table className="w-full min-w-[760px] text-sm">
            <thead className="bg-slate-50 text-left text-xs text-slate-500">
              <tr>
                {["Application", "Institution", "Risk", "Findings", "Review status", ""].map((h) => (
                  <th key={h} className="px-4 py-2.5 font-medium">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {apps.map((a) => (
                <tr key={a.id} className="border-t border-slate-100">
                  <td className="px-4 py-2.5">
                    <Link to={`/applications/${a.id}`} className="font-mono text-xs text-teal-700 hover:underline">
                      {a.id}
                    </Link>
                  </td>
                  <td className="px-4 py-2.5">
                    <span className="font-medium text-navy-900">{a.institution_name}</span> {a.is_demo && <DemoTag />}
                  </td>
                  <td className="px-4 py-2.5">
                    <RiskBadge score={a.risk_score} band={a.risk_band} />
                  </td>
                  <td className="px-4 py-2.5 tabular text-slate-600">
                    {a.finding_count} <span className="text-xs text-slate-400">({a.open_finding_count} open)</span>
                  </td>
                  <td className="px-4 py-2.5">
                    <ReviewStatus status={a.review_status} />
                  </td>
                  <td className="px-4 py-2.5 text-right">
                    <Button icon={<Download className="h-4 w-4" />} loading={busy === a.id} onClick={() => download(a.id)} className="py-1.5 text-xs">
                      PDF report
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      <Card
        title="Audit log"
        subtitle="Each event stores SHA-256(previous hash + event). Editing a stored event breaks the chain — tamper-evident, not tamper-proof."
        action={
          <Button variant="teal" icon={<Link2 className="h-4 w-4" />} loading={busy === "verify"} onClick={runVerify}>
            Verify hash chain
          </Button>
        }
      >
        {verify && (
          <div className={`mx-5 mt-4 flex items-start gap-2 rounded-lg px-4 py-3 text-sm ${verify.valid ? "bg-emerald-50 text-emerald-900" : "bg-red-50 text-red-900"}`}>
            {verify.valid ? <ShieldCheck className="mt-0.5 h-4 w-4" /> : <ShieldX className="mt-0.5 h-4 w-4" />}
            <div>
              <div className="font-medium">{verify.message}</div>
              {verify.head_hash && <div className="break-all font-mono text-xs opacity-80">head {verify.head_hash}</div>}
            </div>
          </div>
        )}
        <div className="flex flex-wrap gap-2 p-4">
          <select aria-label="Event type" value={type} onChange={(e) => setType(e.target.value)} className={inputCls.replace("w-full", "w-auto")}>
            <option value="">All event types</option>
            {types.map((t) => (
              <option key={t} value={t}>
                {EVENT_LABELS[t] ?? t}
              </option>
            ))}
          </select>
          <select aria-label="Application" value={appFilter} onChange={(e) => setAppFilter(e.target.value)} className={inputCls.replace("w-full", "w-auto")}>
            <option value="">All applications</option>
            {apps.map((a) => (
              <option key={a.id} value={a.id}>
                {a.id}
              </option>
            ))}
          </select>
          <span className="self-center text-xs text-slate-500">Showing latest {filtered.length} of {events.length} loaded events</span>
        </div>
        <div className="max-h-[560px] overflow-auto scroll-thin">
          <table className="w-full min-w-[860px] text-sm">
            <thead className="sticky top-0 bg-slate-50 text-left text-xs text-slate-500">
              <tr>
                {["#", "Timestamp", "Event", "Application", "Actor", "Details", "Hash"].map((h) => (
                  <th key={h} className="px-4 py-2 font-medium">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {filtered.map((e) => (
                <tr key={e.id} className="border-t border-slate-100 align-top">
                  <td className="px-4 py-2 font-mono text-xs text-slate-400">{e.id}</td>
                  <td className="whitespace-nowrap px-4 py-2 text-xs text-slate-600">{fmtDate(e.created_at, true)}</td>
                  <td className="px-4 py-2 font-medium text-slate-800">{EVENT_LABELS[e.event_type] ?? e.event_type}</td>
                  <td className="px-4 py-2 font-mono text-xs">{e.application_id ?? "—"}</td>
                  <td className="px-4 py-2 text-xs text-slate-600">{e.actor}</td>
                  <td className="max-w-[340px] px-4 py-2">
                    <code className="line-clamp-2 break-all text-[11px] text-slate-500" title={JSON.stringify(e.details)}>
                      {JSON.stringify(e.details)}
                    </code>
                  </td>
                  <td className="px-4 py-2 font-mono text-[11px] text-slate-500" title={`prev ${e.prev_hash}\nhash ${e.hash}`}>
                    {e.hash.slice(0, 12)}…
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}
