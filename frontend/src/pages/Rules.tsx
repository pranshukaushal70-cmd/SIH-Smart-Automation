import { useCallback, useEffect, useState } from "react";
import { Pencil, Play, Plus, Save } from "lucide-react";
import { api } from "../api";
import type { Meta, Rule } from "../types";
import { Button, Card, cx, ErrorBox, fmtDate, inputCls, Label, Modal, SeverityBadge, Spinner, useToast } from "../components/ui";

type Scoring = Awaited<ReturnType<typeof api.scoring>>;

export default function Rules() {
  const toast = useToast();
  const [rules, setRules] = useState<Rule[] | null>(null);
  const [fp, setFp] = useState("");
  const [meta, setMeta] = useState<Meta | null>(null);
  const [scoring, setScoring] = useState<Scoring | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [editing, setEditing] = useState<Rule | null>(null);
  const [adding, setAdding] = useState(false);
  const [running, setRunning] = useState(false);

  const load = useCallback(() => {
    Promise.all([api.rules(), api.meta(), api.scoring()])
      .then(([r, m, s]) => {
        setRules(r.rules);
        setFp(r.ruleset_fingerprint);
        setMeta(m);
        setScoring(s);
        setError(null);
      })
      .catch((e) => setError(e.message));
  }, []);
  useEffect(load, [load]);

  if (error) return <ErrorBox error={error} onRetry={load} />;
  if (!rules || !meta || !scoring) return <Spinner />;

  const toggle = async (r: Rule) => {
    try {
      const u = await api.updateRule(r.id, { enabled: !r.enabled });
      toast("success", `${r.id} ${u.enabled ? "enabled" : "disabled"} (now v${u.version}). Re-run checks to apply.`);
      load();
    } catch (e) {
      toast("error", (e as Error).message);
    }
  };
  const rerunAll = async () => {
    setRunning(true);
    try {
      const r = await api.evaluateAll();
      toast("success", `Re-evaluated ${r.evaluated} applications with rule set ${fp}`);
    } catch (e) {
      toast("error", (e as Error).message);
    } finally {
      setRunning(false);
    }
  };

  const groups: [string, string, Rule[]][] = [
    ["compliance", "Compliance rules", rules.filter((r) => r.group === "compliance")],
    ["screening", "Authenticity screening (signals, not proof)", rules.filter((r) => r.group === "screening")],
  ];

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-navy-900">Compliance rules</h1>
          <p className="text-sm text-slate-500">
            Every change increments the rule version and is written to the audit log. Reports list each applied rule as <span className="font-mono">ID vN</span>. Current rule-set fingerprint{" "}
            <span className="rounded bg-navy-100 px-1.5 font-mono text-navy-800">{fp}</span>
          </p>
        </div>
        <div className="flex gap-2">
          <Button icon={<Plus className="h-4 w-4" />} onClick={() => setAdding(true)}>
            Add field rule
          </Button>
          <Button variant="primary" icon={<Play className="h-4 w-4" />} loading={running} onClick={rerunAll}>
            Re-run all applications
          </Button>
        </div>
      </div>

      {groups.map(([key, title, list]) => (
        <Card key={key} title={title}>
          <ul className="divide-y divide-slate-100">
            {list.map((r) => (
              <li key={r.id} className={cx("flex flex-wrap items-start gap-4 px-5 py-3.5", !r.enabled && "bg-slate-50/70")}>
                <button role="switch" aria-checked={r.enabled} aria-label={`Toggle ${r.id}`} onClick={() => toggle(r)} className={cx("mt-0.5 h-5 w-9 shrink-0 rounded-full p-0.5 transition-colors", r.enabled ? "bg-teal-600" : "bg-slate-300")}>
                  <span className={cx("block h-4 w-4 rounded-full bg-white shadow transition-transform", r.enabled && "translate-x-4")} />
                </button>
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-mono text-xs font-semibold text-navy-800">{r.id}</span>
                    <span className="rounded bg-slate-100 px-1.5 text-[11px] font-medium text-slate-600">v{r.version}</span>
                    <SeverityBadge severity={r.severity} />
                    {!r.is_builtin && <span className="rounded bg-teal-50 px-1.5 text-[11px] font-medium text-teal-700">custom</span>}
                  </div>
                  <div className={cx("mt-0.5 text-sm font-medium", r.enabled ? "text-navy-900" : "text-slate-500")}>{r.name}</div>
                  <div className="text-xs text-slate-500">{r.description}</div>
                  <div className="mt-1.5 flex flex-wrap gap-1.5">
                    {Object.entries(r.params).map(([k, v]) => (
                      <span key={k} className="rounded border border-slate-200 bg-white px-1.5 py-0.5 font-mono text-[11px] text-slate-600">
                        {k}: {Array.isArray(v) ? v.join(", ") : String(v)}
                      </span>
                    ))}
                  </div>
                </div>
                <div className="flex items-center gap-2 text-xs text-slate-400">
                  <span className="hidden sm:inline">updated {fmtDate(r.updated_at)}</span>
                  <Button icon={<Pencil className="h-3.5 w-3.5" />} onClick={() => setEditing(r)} className="py-1.5 text-xs">
                    Edit
                  </Button>
                </div>
              </li>
            ))}
          </ul>
        </Card>
      ))}

      <ScoringCard scoring={scoring} onSaved={load} />
      {editing && <EditRule rule={editing} meta={meta} onClose={() => setEditing(null)} onSaved={load} />}
      {adding && <AddRule meta={meta} onClose={() => setAdding(false)} onSaved={load} />}
    </div>
  );
}

function EditRule({ rule, meta, onClose, onSaved }: { rule: Rule; meta: Meta; onClose: () => void; onSaved: () => void }) {
  const toast = useToast();
  const [severity, setSeverity] = useState(rule.severity);
  const [vals, setVals] = useState<Record<string, string>>(() =>
    Object.fromEntries(Object.entries(rule.params).map(([k, v]) => [k, Array.isArray(v) ? v.join(", ") : String(v)])),
  );
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const save = async () => {
    const params: Record<string, unknown> = {};
    for (const [k, orig] of Object.entries(rule.params)) {
      const s = vals[k] ?? "";
      params[k] = Array.isArray(orig) ? s.split(",").map((x) => x.trim()).filter(Boolean) : typeof orig === "number" ? Number(s) : typeof orig === "boolean" ? s === "true" : s;
      if (typeof orig === "number" && Number.isNaN(params[k])) return setErr(`${k} must be a number`);
    }
    setBusy(true);
    try {
      const u = await api.updateRule(rule.id, { params, severity });
      toast("success", `${rule.id} saved as v${u.version}. Re-run checks to apply.`);
      onSaved();
      onClose();
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setBusy(false);
    }
  };
  return (
    <Modal open onClose={onClose} title={`Edit ${rule.id} · v${rule.version}`}>
      <div className="space-y-3">
        <p className="text-sm font-medium text-navy-900">{rule.name}</p>
        <p className="text-xs text-slate-500">{rule.rule_type_label}</p>
        <label className="block">
          <Label>Severity</Label>
          <select value={severity} onChange={(e) => setSeverity(e.target.value as Rule["severity"])} className={inputCls}>
            {meta.severities.map((s) => (
              <option key={s}>{s}</option>
            ))}
          </select>
        </label>
        {Object.entries(rule.params).map(([k, orig]) => (
          <label key={k} className="block">
            <Label hint={Array.isArray(orig) ? "comma-separated" : typeof orig === "number" ? "number" : undefined}>{k.replace(/_/g, " ")}</Label>
            {Array.isArray(orig) ? (
              <textarea rows={2} value={vals[k]} onChange={(e) => setVals({ ...vals, [k]: e.target.value })} className={inputCls + " font-mono text-xs"} />
            ) : (
              <input value={vals[k]} onChange={(e) => setVals({ ...vals, [k]: e.target.value })} className={inputCls + " font-mono"} />
            )}
          </label>
        ))}
        {Object.keys(rule.params).length === 0 && <p className="text-xs text-slate-500">This rule has no thresholds; only severity and enablement can change.</p>}
        {k_hint(rule)}
        {err && <ErrorBox error={err} />}
        <div className="flex justify-end gap-2">
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button variant="primary" icon={<Save className="h-4 w-4" />} loading={busy} onClick={save}>
            Save new version
          </Button>
        </div>
      </div>
    </Modal>
  );
}

const k_hint = (r: Rule) =>
  "categories" in r.params || "category" in r.params || "fields" in r.params ? (
    <p className="text-[11px] text-slate-500">
      Category keys: affiliation_letter, fire_safety_certificate, occupancy_certificate, trust_registration_certificate. Field keys: institution_name, institution_id, issue_date, expiry_date, issuer_name, reference_number, approval_reference.
    </p>
  ) : null;

function AddRule({ meta, onClose, onSaved }: { meta: Meta; onClose: () => void; onSaved: () => void }) {
  const toast = useToast();
  const [type, setType] = useState("field_pattern");
  const [name, setName] = useState("Fire NOC number follows FES/NOC/YYYY/NNNNN");
  const [category, setCategory] = useState("fire_safety_certificate");
  const [field, setField] = useState("reference_number");
  const [pattern, setPattern] = useState("FES/NOC/\\d{4}/\\d{5}");
  const [fields, setFields] = useState<string[]>(["institution_id"]);
  const [keywords, setKeywords] = useState("");
  const [severity, setSeverity] = useState("medium");
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const save = async () => {
    const params: Record<string, unknown> = { category };
    if (type === "field_pattern") Object.assign(params, { field, pattern });
    if (type === "required_fields") params.fields = fields;
    if (type === "keyword_present") params.keywords = keywords.split(",").map((s) => s.trim()).filter(Boolean);
    setBusy(true);
    try {
      const r = await api.createRule({ name, rule_type: type, severity, params, description: name });
      toast("success", `Rule ${r.id} created. Re-run checks to apply.`);
      onSaved();
      onClose();
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setBusy(false);
    }
  };
  return (
    <Modal open onClose={onClose} title="Add field-validation rule">
      <div className="space-y-3">
        <label className="block">
          <Label>Rule type</Label>
          <select value={type} onChange={(e) => setType(e.target.value)} className={inputCls}>
            {meta.custom_rule_types.map((t) => (
              <option key={t} value={t}>
                {meta.rule_types[t]}
              </option>
            ))}
          </select>
        </label>
        <label className="block">
          <Label>Name</Label>
          <input value={name} onChange={(e) => setName(e.target.value)} className={inputCls} />
        </label>
        <div className="grid grid-cols-2 gap-3">
          <label className="block">
            <Label>Document category</Label>
            <select value={category} onChange={(e) => setCategory(e.target.value)} className={inputCls}>
              <option value="any">Any category</option>
              {Object.entries(meta.document_categories).map(([k, v]) => (
                <option key={k} value={k}>
                  {v}
                </option>
              ))}
            </select>
          </label>
          <label className="block">
            <Label>Severity</Label>
            <select value={severity} onChange={(e) => setSeverity(e.target.value)} className={inputCls}>
              {meta.severities.map((s) => (
                <option key={s}>{s}</option>
              ))}
            </select>
          </label>
        </div>
        {type === "field_pattern" && (
          <div className="grid grid-cols-2 gap-3">
            <label className="block">
              <Label>Field</Label>
              <select value={field} onChange={(e) => setField(e.target.value)} className={inputCls}>
                {Object.entries(meta.fields).map(([k, v]) => (
                  <option key={k} value={k}>
                    {v}
                  </option>
                ))}
              </select>
            </label>
            <label className="block">
              <Label hint="full match">Regular expression</Label>
              <input value={pattern} onChange={(e) => setPattern(e.target.value)} className={inputCls + " font-mono"} />
            </label>
          </div>
        )}
        {type === "required_fields" && (
          <div>
            <Label>Required fields</Label>
            <div className="grid grid-cols-2 gap-1">
              {Object.entries(meta.fields).map(([k, v]) => (
                <label key={k} className="flex items-center gap-2 text-sm">
                  <input type="checkbox" checked={fields.includes(k)} onChange={(e) => setFields(e.target.checked ? [...fields, k] : fields.filter((f) => f !== k))} />
                  {v}
                </label>
              ))}
            </div>
          </div>
        )}
        {type === "keyword_present" && (
          <label className="block">
            <Label hint="comma-separated, any one must appear">Keywords / phrases</Label>
            <input value={keywords} onChange={(e) => setKeywords(e.target.value)} className={inputCls} placeholder="e.g. structural stability, fit for occupation" />
          </label>
        )}
        {err && <ErrorBox error={err} />}
        <div className="flex justify-end gap-2">
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button variant="primary" loading={busy} onClick={save}>
            Create rule
          </Button>
        </div>
      </div>
    </Modal>
  );
}

function ScoringCard({ scoring, onSaved }: { scoring: Scoring; onSaved: () => void }) {
  const toast = useToast();
  const [cfg, setCfg] = useState(scoring.config);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => setCfg(scoring.config), [scoring]);
  const set = (group: keyof typeof cfg, k: string, v: string) => setCfg({ ...cfg, [group]: { ...cfg[group], [k]: Number(v) } });
  const save = async () => {
    setBusy(true);
    setErr(null);
    try {
      await api.updateScoring(cfg);
      toast("success", "Scoring weights saved as a new version. Re-run checks to apply.");
      onSaved();
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setBusy(false);
    }
  };
  const num = (group: keyof typeof cfg, k: string, label: string, step = "1") => (
    <label key={k} className="block">
      <Label>{label}</Label>
      <input type="number" min={0} max={100} step={step} value={cfg[group][k]} onChange={(e) => set(group, k, e.target.value)} className={inputCls + " tabular"} />
    </label>
  );
  return (
    <Card title={`Risk scoring weights · v${scoring.version}`} subtitle={scoring.disclaimer} action={<Button variant="primary" icon={<Save className="h-4 w-4" />} loading={busy} onClick={save}>Save weights</Button>}>
      <div className="grid gap-6 p-5 lg:grid-cols-3">
        <div>
          <p className="mb-2 text-xs font-semibold text-slate-600">Points per finding severity</p>
          <div className="grid grid-cols-2 gap-2">{Object.keys(cfg.severity_points).map((k) => num("severity_points", k, k))}</div>
        </div>
        <div>
          <p className="mb-2 text-xs font-semibold text-slate-600">Factor weights (multipliers)</p>
          <div className="grid grid-cols-2 gap-2">{Object.keys(cfg.factor_weights).map((k) => num("factor_weights", k, scoring.factor_labels[k] ?? k, "0.1"))}</div>
        </div>
        <div>
          <p className="mb-2 text-xs font-semibold text-slate-600">Band thresholds</p>
          <div className="grid grid-cols-2 gap-2">
            {num("bands", "medium", "Medium from")}
            {num("bands", "high", "High from")}
          </div>
          <p className="mt-3 font-mono text-[11px] text-slate-500">risk = min(100, Σ severity_points × factor_weight)</p>
        </div>
      </div>
      {err && (
        <div className="px-5 pb-4">
          <ErrorBox error={err} />
        </div>
      )}
    </Card>
  );
}
