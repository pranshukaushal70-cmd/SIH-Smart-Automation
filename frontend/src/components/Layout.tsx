import { useEffect, useState } from "react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { ClipboardCheck, FileSearch, FileText, LayoutDashboard, ListChecks, ShieldCheck, UserRound } from "lucide-react";
import { api } from "../api";
import { cx } from "./ui";

const NAV = [
  { to: "/", label: "Dashboard", icon: LayoutDashboard, end: true },
  { to: "/applications", label: "Applications", icon: FileSearch },
  { to: "/review", label: "Review Workspace", icon: ClipboardCheck },
  { to: "/rules", label: "Compliance Rules", icon: ListChecks },
  { to: "/reports", label: "Reports & Audit", icon: FileText },
];

export default function Layout() {
  const [health, setHealth] = useState<{ ok: boolean; ocr?: string | null }>({ ok: true });
  const [name, setName] = useState(() => {
    try {
      return localStorage.getItem("veri.officer") || "Demo Officer";
    } catch {
      return "Demo Officer";
    }
  });
  useEffect(() => {
    api.health().then((h) => setHealth({ ok: true, ocr: h.ocr.available ? h.ocr.engine : null })).catch(() => setHealth({ ok: false }));
  }, []);
  const saveName = (v: string) => {
    setName(v);
    try {
      localStorage.setItem("veri.officer", v.trim() || "Demo Officer");
    } catch {
      /* storage unavailable */
    }
  };

  return (
    <div className="flex min-h-screen">
      <aside className="sticky top-0 hidden h-screen w-60 shrink-0 flex-col bg-navy-900 text-navy-100 lg:flex">
        <div className="flex items-center gap-2.5 px-5 pb-5 pt-6">
          <div className="grid h-9 w-9 place-items-center rounded-lg bg-teal-600">
            <ShieldCheck className="h-5 w-5 text-white" />
          </div>
          <div>
            <div className="text-[15px] font-bold tracking-tight text-white">VeriAICTE</div>
            <div className="text-[11px] text-navy-100/70">AI Verification Co-Pilot</div>
          </div>
        </div>
        <div className="mx-5 mb-4 flex h-1 overflow-hidden rounded">
          <span className="flex-1 bg-saffron-500" />
          <span className="flex-1 bg-white" />
          <span className="flex-1 bg-bharat-green" />
        </div>
        <nav className="flex-1 space-y-0.5 px-3">
          {NAV.map(({ to, label, icon: Icon, end }) => (
            <NavLink key={to} to={to} end={end} className={({ isActive }) => cx("flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm font-medium transition-colors", isActive ? "bg-white/10 text-white" : "text-navy-100/75 hover:bg-white/5 hover:text-white")}>
              <Icon className="h-4 w-4" />
              {label}
            </NavLink>
          ))}
        </nav>
        <div className="space-y-3 border-t border-white/10 p-4 text-xs">
          <label className="block">
            <span className="mb-1 flex items-center gap-1 text-navy-100/70">
              <UserRound className="h-3.5 w-3.5" /> Reviewing officer
            </span>
            <input value={name} onChange={(e) => saveName(e.target.value)} className="w-full rounded-md border border-white/15 bg-white/5 px-2 py-1.5 text-white focus:border-teal-500 focus:outline-none" />
          </label>
          <div className="flex items-center gap-1.5 text-navy-100/70">
            <span className={cx("h-2 w-2 rounded-full", health.ok ? "bg-emerald-400" : "bg-red-400")} />
            {health.ok ? `API online · OCR: ${health.ocr ?? "unavailable"}` : "API offline"}
          </div>
          <p className="leading-relaxed text-navy-100/55">SIH 2026 · PS 26261 · AICTE Regulation Bureau theme. Hackathon prototype — not an official AICTE system.</p>
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <div className="flex flex-wrap items-center gap-x-2 border-b border-amber-200 bg-amber-50 px-4 py-1.5 text-xs text-amber-900 sm:px-6">
          <span className="font-semibold">Development prototype.</span>
          <span className="min-w-0">No authentication · synthetic demo data · findings are decision support only; an authorised officer decides.</span>
        </div>
        <MobileNav />
        {!health.ok && <div className="bg-red-600 px-6 py-2 text-sm text-white">Backend API is not reachable. Start it with <code className="font-mono">uvicorn app.main:app --port 8000</code> in the backend folder.</div>}
        <main className="mx-auto w-full max-w-[1400px] flex-1 px-4 py-6 sm:px-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
}

function MobileNav() {
  const nav = useNavigate();
  return (
    <div className="flex items-center gap-3 bg-navy-900 px-4 py-2.5 lg:hidden">
      <ShieldCheck className="h-5 w-5 text-teal-500" />
      <span className="font-bold text-white">VeriAICTE</span>
      <select aria-label="Navigate" onChange={(e) => nav(e.target.value)} className="ml-auto rounded bg-white/10 px-2 py-1 text-sm text-white">
        {NAV.map((n) => (
          <option key={n.to} value={n.to} className="text-slate-900">
            {n.label}
          </option>
        ))}
      </select>
    </div>
  );
}
