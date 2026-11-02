import type { AppDetail, AppSummary, AuditEvent, Dashboard, DocDetail, DocSummary, Finding, Meta, Rule } from "./types";

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`/api${path}`, init);
  } catch {
    throw new ApiError(0, "Cannot reach the backend. Is the API running on http://127.0.0.1:8000?");
  }
  if (!res.ok) {
    let msg = `${res.status} ${res.statusText}`;
    try {
      const body = await res.json();
      if (typeof body.detail === "string") msg = body.detail;
      else if (Array.isArray(body.detail))
        msg = body.detail.map((d: { loc?: string[]; msg: string }) => `${(d.loc || []).slice(-1)[0] ?? ""}: ${d.msg}`).join("; ");
    } catch {
      /* non-JSON error */
    }
    if (res.status === 502 || res.status === 504) msg = "Backend unavailable (proxy error). Start the API server.";
    throw new ApiError(res.status, msg);
  }
  return res.json() as Promise<T>;
}

const json = (method: string, body: unknown): RequestInit => ({
  method,
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body),
});

export const officer = () => {
  try {
    return localStorage.getItem("veri.officer") || "Demo Officer";
  } catch {
    return "Demo Officer";
  }
};
const qs = (o: Record<string, string | undefined>) => {
  const p = new URLSearchParams();
  Object.entries(o).forEach(([k, v]) => v && p.set(k, v));
  const s = p.toString();
  return s ? `?${s}` : "";
};

export const api = {
  health: () => request<{ status: string; ocr: { available: boolean; engine: string | null }; max_upload_mb: number }>("/health"),
  meta: () => request<Meta>("/meta"),
  dashboard: () => request<Dashboard>("/dashboard"),
  applications: (f: Record<string, string | undefined> = {}) => request<AppSummary[]>(`/applications${qs(f)}`),
  application: (id: string) => request<AppDetail>(`/applications/${id}`),
  createApplication: (body: Record<string, string>) =>
    request<AppSummary>("/applications", json("POST", { ...body, officer_name: officer() })),
  deleteApplication: (id: string) =>
    request<{ deleted: string }>(`/applications/${id}${qs({ officer_name: officer() })}`, { method: "DELETE" }),
  evaluate: (id: string) => request<AppDetail>(`/applications/${id}/evaluate${qs({ officer_name: officer() })}`, { method: "POST" }),
  upload: (appId: string, file: File, category: string) => {
    const fd = new FormData();
    fd.append("file", file);
    fd.append("category", category);
    fd.append("officer_name", officer());
    return request<DocSummary>(`/applications/${appId}/documents`, { method: "POST", body: fd });
  },
  processDocument: (id: string) =>
    request<DocDetail>(`/documents/${id}/process${qs({ officer_name: officer() })}`, { method: "POST" }),
  document: (id: string) => request<DocDetail>(`/documents/${id}`),
  deleteDocument: (id: string) =>
    request<{ deleted: string }>(`/documents/${id}${qs({ officer_name: officer() })}`, { method: "DELETE" }),
  previewUrl: (id: string, page = 1) => `/api/documents/${id}/preview?page=${page}`,
  updateFinding: (id: string, status: "Open" | "Reviewed", note: string) =>
    request<Finding>(`/findings/${id}`, json("PATCH", { status, note, officer_name: officer() })),
  review: (appId: string, action: string, notes: string) =>
    request(`/applications/${appId}/review`, json("POST", { action, notes, officer_name: officer() })),
  auditLog: (appId: string) => request<AuditEvent[]>(`/applications/${appId}/audit-log`),
  globalAudit: (limit = 200) => request<AuditEvent[]>(`/audit-log?limit=${limit}`),
  verifyAudit: () => request<{ valid: boolean; events_checked: number; message: string; head_hash?: string }>("/audit/verify"),
  rules: () => request<{ rules: Rule[]; ruleset_fingerprint: string }>("/rules"),
  updateRule: (id: string, patch: Record<string, unknown>) =>
    request<Rule>(`/rules/${id}`, json("PATCH", { ...patch, officer_name: officer() })),
  createRule: (body: Record<string, unknown>) => request<Rule>("/rules", json("POST", { ...body, officer_name: officer() })),
  scoring: () =>
    request<{ config: { severity_points: Record<string, number>; factor_weights: Record<string, number>; bands: Record<string, number> }; version: number; disclaimer: string; factor_labels: Record<string, string> }>(
      "/settings/scoring",
    ),
  updateScoring: (patch: Record<string, unknown>) => request("/settings/scoring", json("PATCH", { ...patch, officer_name: officer() })),
  evaluateAll: () => request<{ evaluated: number }>(`/evaluate-all${qs({ officer_name: officer() })}`, { method: "POST" }),
  downloadReport: async (appId: string) => {
    let res: Response;
    try {
      res = await fetch(`/api/applications/${appId}/report${qs({ officer_name: officer() })}`);
    } catch {
      throw new ApiError(0, "Cannot reach the backend.");
    }
    if (!res.ok) throw new ApiError(res.status, `Report generation failed (${res.status}).`);
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `VeriAICTE_Report_${appId}.pdf`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 2000);
  },
};
