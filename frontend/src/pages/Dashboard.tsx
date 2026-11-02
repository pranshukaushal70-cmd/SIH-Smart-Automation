import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Activity, AlertTriangle, CheckCircle2, ClipboardCheck, FileClock, FileStack, Plus, ShieldAlert } from "lucide-react";
import { api } from "../api";
import type { Dashboard as D } from "../types";
import NewApplication from "../components/NewApplication";
import { Button, Card, DemoTag, Empty, ErrorBox, EVENT_LABELS, fmtDate, ReviewStatus, RiskBadge, Spinner } from "../components/ui";

// Reserved status colours (good / warning / critical); bands are also named on the axis.
const BAND_COLOR: Record<string, string> = { Low: "#12805c", Medium: "#d68b00", High: "#c4320a", "Not evaluated": "#98a2b3" };
const OUTCOME_HUE = "#0f8b8d";

export default function Dashboard() {
  const [data, setData] = useState<D | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [newOpen, setNewOpen] = useState(false);
  const nav = useNavigate();

  const load = useCallback(() => {
    setError(null);
    api.dashboard().then(setData).catch((e) => setError(e.message));
  }, []);
  useEffect(load, [load]);

  if (error) return <ErrorBox error={error} onRetry={load} />;
  if (!data) return <Spinner label="Loading dashboard…" />;
  const t = data.totals;
  const openWorkspace = () => {
    const next = [...data.recent_applications].filter((a) => a.review_status === "Pending Review").sort((a, b) => (b.risk_score ?? -1) - (a.risk_score ?? -1))[0] ?? data.recent_applications[0];
    nav(next ? `/applications/${next.id}` : "/applications");
  };
  const outcomes = ["Missing", "Expired", "Flagged", "Review Required", "Screening Signal"].map((o) => ({ outcome: o, count: data.findings_by_outcome[o] ?? 0 }));

  const kpis = [
    { label: "Total applications", value: t.applications, icon: FileStack, tone: "text-navy-800 bg-navy-100", sub: `${t.demo_applications} synthetic demo records` },
    { label: "Pending reviews", value: t.pending_reviews, icon: ClipboardCheck, tone: "text-teal-700 bg-teal-50", sub: "awaiting officer decision" },
    { label: "Verified documents", value: t.verified_documents, icon: CheckCircle2, tone: "text-emerald-700 bg-emerald-50", sub: `of ${t.documents} · passed prototype checks` },
    { label: "Flagged documents", value: t.flagged_documents, icon: ShieldAlert, tone: "text-red-700 bg-red-50", sub: `${t.review_required_documents} more need review` },
    { label: "Missing / expired", value: t.missing_or_expired, icon: FileClock, tone: "text-orange-700 bg-orange-50", sub: `${t.missing_documents} missing · ${t.expired_documents} expired` },
    { label: "Open findings", value: t.open_findings, icon: AlertTriangle, tone: "text-amber-700 bg-amber-50", sub: "across all applications" },
  ];

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wider text-teal-700">Regulation Bureau · Officer dashboard</p>
          <h1 className="mt-1 text-2xl font-bold tracking-tight text-navy-900">Application verification overview</h1>
          <p className="mt-1 text-sm text-slate-500">Live figures from the local database. Demo records are synthetic and labelled.</p>
        </div>
        <div className="flex gap-2">
          <Button variant="secondary" icon={<ClipboardCheck className="h-4 w-4" />} onClick={openWorkspace}>
            Open review workspace
          </Button>
          <Button variant="primary" icon={<Plus className="h-4 w-4" />} onClick={() => setNewOpen(true)}>
            New application
          </Button>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
        {kpis.map((k) => (
          <div key={k.label} className="rounded-xl border border-slate-200 bg-white p-4">
            <div className="flex items-center justify-between">
              <span className="text-xs font-medium text-slate-500">{k.label}</span>
              <span className={`rounded-md p-1.5 ${k.tone}`}>
                <k.icon className="h-4 w-4" />
              </span>
            </div>
            <div className="mt-2 text-3xl font-bold tracking-tight text-navy-900 tabular">{k.value}</div>
            <div className="mt-0.5 truncate text-[11px] text-slate-500">{k.sub}</div>
          </div>
        ))}
      </div>

      <div className="grid gap-4 lg:grid-cols-5">
        <Card className="lg:col-span-2" title="Risk distribution" subtitle="Applications by internal prototype risk band">
          <div className="h-56 px-2 pb-3 pt-4">
            <ResponsiveContainer>
              <BarChart data={data.risk_distribution} margin={{ top: 4, right: 12, left: -18, bottom: 0 }}>
                <CartesianGrid vertical={false} stroke="#eaecf0" />
                <XAxis dataKey="band" tickLine={false} axisLine={{ stroke: "#d0d5dd" }} tick={{ fontSize: 12, fill: "#475467" }} />
                <YAxis allowDecimals={false} tickLine={false} axisLine={false} tick={{ fontSize: 11, fill: "#667085" }} />
                <Tooltip cursor={{ fill: "#f2f4f7" }} formatter={(v: number) => [`${v} application${v === 1 ? "" : "s"}`, "Count"]} contentStyle={{ borderRadius: 8, border: "1px solid #eaecf0", fontSize: 12 }} />
                <Bar dataKey="count" radius={[4, 4, 0, 0]} maxBarSize={44} isAnimationActive={false}>
                  {data.risk_distribution.map((d) => (
                    <Cell key={d.band} fill={BAND_COLOR[d.band]} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Card>
        <Card className="lg:col-span-3" title="Findings by outcome" subtitle="All findings generated by the configured rules">
          <div className="h-56 px-2 pb-3 pt-4">
            <ResponsiveContainer>
              <BarChart data={outcomes} layout="vertical" margin={{ top: 0, right: 24, left: 30, bottom: 0 }}>
                <CartesianGrid horizontal={false} stroke="#eaecf0" />
                <XAxis type="number" allowDecimals={false} tickLine={false} axisLine={false} tick={{ fontSize: 11, fill: "#667085" }} />
                <YAxis type="category" dataKey="outcome" width={110} tickLine={false} axisLine={false} tick={{ fontSize: 12, fill: "#475467" }} />
                <Tooltip cursor={{ fill: "#f2f4f7" }} formatter={(v: number) => [v, "Findings"]} contentStyle={{ borderRadius: 8, border: "1px solid #eaecf0", fontSize: 12 }} />
                <Bar dataKey="count" fill={OUTCOME_HUE} radius={[0, 4, 4, 0]} maxBarSize={18} isAnimationActive={false} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Card>
      </div>

      <div className="grid gap-4 lg:grid-cols-5">
        <Card className="lg:col-span-3" title="Recent applications" action={<Link to="/applications" className="text-sm font-medium text-teal-700 hover:underline">View all</Link>}>
          {data.recent_applications.length === 0 ? (
            <Empty title="No applications yet">Create one to begin.</Empty>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="text-left text-xs text-slate-500">
                  <tr className="border-b border-slate-100">
                    <th className="px-5 py-2 font-medium">Application</th>
                    <th className="px-3 py-2 font-medium">Risk</th>
                    <th className="px-3 py-2 font-medium">Review status</th>
                  </tr>
                </thead>
                <tbody>
                  {data.recent_applications.map((a) => (
                    <tr key={a.id} onClick={() => nav(`/applications/${a.id}`)} className="cursor-pointer border-b border-slate-50 last:border-0 hover:bg-slate-50">
                      <td className="px-5 py-2.5">
                        <div className="flex items-center gap-2">
                          <span className="font-mono text-xs text-slate-500">{a.id}</span>
                          {a.is_demo && <DemoTag />}
                        </div>
                        <div className="font-medium text-navy-900">{a.institution_name}</div>
                      </td>
                      <td className="px-3 py-2.5">
                        <RiskBadge score={a.risk_score} band={a.risk_band} />
                      </td>
                      <td className="px-3 py-2.5">
                        <ReviewStatus status={a.review_status} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>
        <Card className="lg:col-span-2" title="Recent activity" subtitle="From the hash-chained audit log" action={<Link to="/reports" className="text-sm font-medium text-teal-700 hover:underline">Audit log</Link>}>
          <ul className="max-h-[360px] divide-y divide-slate-50 overflow-auto scroll-thin">
            {data.recent_activity.map((e) => (
              <li key={e.id} className="flex gap-3 px-5 py-2.5">
                <Activity className="mt-0.5 h-4 w-4 shrink-0 text-teal-600" />
                <div className="min-w-0 text-sm">
                  <div className="text-slate-800">
                    {EVENT_LABELS[e.event_type] ?? e.event_type}
                    {e.application_id && (
                      <Link to={`/applications/${e.application_id}`} className="ml-1 font-mono text-xs text-teal-700 hover:underline">
                        {e.application_id}
                      </Link>
                    )}
                  </div>
                  <div className="text-xs text-slate-500">
                    {e.actor} · {fmtDate(e.created_at, true)}
                  </div>
                </div>
              </li>
            ))}
          </ul>
        </Card>
      </div>
      <NewApplication open={newOpen} onClose={() => setNewOpen(false)} />
    </div>
  );
}
