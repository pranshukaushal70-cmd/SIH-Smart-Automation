import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Plus, Search } from "lucide-react";
import { api } from "../api";
import type { AppSummary } from "../types";
import NewApplication from "../components/NewApplication";
import { Button, Card, DemoTag, Empty, ErrorBox, fmtDate, inputCls, ReviewStatus, RiskBadge, Spinner } from "../components/ui";

const REVIEW_STATUSES = ["Pending Review", "Clarification Requested", "Issuer Verification Pending", "Returned for Missing Information", "Provisional Approval Recommended", "Further Scrutiny Recommended"];

export default function Applications() {
  const [rows, setRows] = useState<AppSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [q, setQ] = useState("");
  const [filters, setFilters] = useState({ review_status: "", risk_band: "", application_type: "" });
  const [types, setTypes] = useState<string[]>([]);
  const [newOpen, setNewOpen] = useState(false);
  const nav = useNavigate();

  useEffect(() => {
    api.meta().then((m) => setTypes(m.application_types)).catch(() => {});
  }, []);
  const load = useCallback(() => {
    setError(null);
    api.applications({ q: q || undefined, ...Object.fromEntries(Object.entries(filters).map(([k, v]) => [k, v || undefined])) })
      .then(setRows)
      .catch((e) => setError(e.message));
  }, [q, filters]);
  useEffect(() => {
    const h = setTimeout(load, 200);
    return () => clearTimeout(h);
  }, [load]);

  const setF = (k: keyof typeof filters) => (e: React.ChangeEvent<HTMLSelectElement>) => setFilters({ ...filters, [k]: e.target.value });

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-navy-900">Applications</h1>
          <p className="text-sm text-slate-500">Institutional applications and their verification status.</p>
        </div>
        <Button variant="primary" icon={<Plus className="h-4 w-4" />} onClick={() => setNewOpen(true)}>
          New application
        </Button>
      </div>

      <Card>
        <div className="flex flex-wrap gap-2 border-b border-slate-100 p-4">
          <div className="relative min-w-[240px] flex-1">
            <Search className="absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
            <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search by application ID, institution or identifier" className={inputCls + " pl-9"} />
          </div>
          <select aria-label="Review status" value={filters.review_status} onChange={setF("review_status")} className={inputCls.replace("w-full", "w-auto")}>
            <option value="">All review statuses</option>
            {REVIEW_STATUSES.map((s) => (
              <option key={s}>{s}</option>
            ))}
          </select>
          <select aria-label="Risk band" value={filters.risk_band} onChange={setF("risk_band")} className={inputCls.replace("w-full", "w-auto")}>
            <option value="">All risk bands</option>
            {["Low", "Medium", "High", "Not evaluated"].map((s) => (
              <option key={s}>{s}</option>
            ))}
          </select>
          <select aria-label="Application type" value={filters.application_type} onChange={setF("application_type")} className={inputCls.replace("w-full", "w-auto")}>
            <option value="">All types</option>
            {types.map((s) => (
              <option key={s}>{s}</option>
            ))}
          </select>
        </div>
        {error ? (
          <div className="p-4">
            <ErrorBox error={error} onRetry={load} />
          </div>
        ) : !rows ? (
          <Spinner />
        ) : rows.length === 0 ? (
          <Empty icon={<Search className="h-5 w-5" />} title="No applications match these filters" />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[900px] text-sm">
              <thead className="bg-slate-50 text-left text-xs text-slate-500">
                <tr>
                  {["Application ID", "Institution", "Type", "Submitted", "Processing", "Documents", "Risk score", "Review status"].map((h) => (
                    <th key={h} className="px-4 py-2.5 font-medium">
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {rows.map((a) => (
                  <tr key={a.id} onClick={() => nav(`/applications/${a.id}`)} className="cursor-pointer border-t border-slate-100 hover:bg-teal-50/40">
                    <td className="px-4 py-3 font-mono text-xs text-navy-800">{a.id}</td>
                    <td className="px-4 py-3">
                      <div className="font-medium text-navy-900">{a.institution_name}</div>
                      <div className="flex items-center gap-2 font-mono text-xs text-slate-500">
                        {a.institution_id} {a.is_demo && <DemoTag />}
                      </div>
                    </td>
                    <td className="px-4 py-3 text-slate-600">{a.application_type}</td>
                    <td className="px-4 py-3 text-slate-600 tabular">{fmtDate(a.submitted_at)}</td>
                    <td className="px-4 py-3 text-slate-600">{a.processing_status}</td>
                    <td className="px-4 py-3 text-slate-600 tabular">
                      {a.document_count} <span className="text-xs text-slate-400">· {a.open_finding_count} open findings</span>
                    </td>
                    <td className="px-4 py-3">
                      <RiskBadge score={a.risk_score} band={a.risk_band} />
                    </td>
                    <td className="px-4 py-3">
                      <ReviewStatus status={a.review_status} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
      <NewApplication open={newOpen} onClose={() => setNewOpen(false)} />
    </div>
  );
}
