import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api";
import { Button, ErrorBox, inputCls, Label, Modal, useToast } from "./ui";

const TYPES_FALLBACK = ["Extension of Approval (EoA)", "Approval for New Institution", "Increase in Intake"];

export default function NewApplication({ open, onClose }: { open: boolean; onClose: () => void }) {
  const nav = useNavigate();
  const toast = useToast();
  const [types, setTypes] = useState<string[]>(TYPES_FALLBACK);
  const [form, setForm] = useState({ institution_name: "", institution_id: "", application_type: TYPES_FALLBACK[0], state: "", academic_year: "2026-27" });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (open) api.meta().then((m) => setTypes(m.application_types)).catch(() => {});
  }, [open]);

  const set = (k: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => setForm({ ...form, [k]: e.target.value });
  const fillDemo = () =>
    setForm({ institution_name: "Narmada Institute of Management Studies (Fictional)", institution_id: "SYN-INST-61208", application_type: "Approval for New Institution", state: "State of Vindhyachal (Fictional)", academic_year: "2026-27" });

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const a = await api.createApplication(form);
      toast("success", `Application ${a.id} created`);
      onClose();
      nav(`/applications/${a.id}`);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Modal open={open} onClose={onClose} title="New institutional application">
      <form onSubmit={submit} className="space-y-4">
        <div className="rounded-lg bg-navy-50 px-3 py-2 text-xs text-navy-800">
          Use fictional details only. The sample upload files in <code className="font-mono">samples/</code> are made for{" "}
          <button type="button" onClick={fillDemo} className="font-semibold text-teal-700 underline">
            Narmada Institute (SYN-INST-61208)
          </button>
          .
        </div>
        <label className="block">
          <Label>Institution name</Label>
          <input required minLength={3} value={form.institution_name} onChange={set("institution_name")} className={inputCls} placeholder="e.g. Narmada Institute of Management Studies (Fictional)" />
        </label>
        <div className="grid grid-cols-2 gap-3">
          <label className="block">
            <Label hint="letters, digits, - /">Institution identifier</Label>
            <input required pattern="[A-Za-z0-9][A-Za-z0-9\-/]*" value={form.institution_id} onChange={set("institution_id")} className={inputCls + " font-mono"} placeholder="SYN-INST-61208" />
          </label>
          <label className="block">
            <Label>Academic year</Label>
            <input value={form.academic_year} onChange={set("academic_year")} className={inputCls} />
          </label>
        </div>
        <label className="block">
          <Label>Application type</Label>
          <select value={form.application_type} onChange={set("application_type")} className={inputCls}>
            {types.map((t) => (
              <option key={t}>{t}</option>
            ))}
          </select>
        </label>
        <label className="block">
          <Label>State / UT</Label>
          <input value={form.state} onChange={set("state")} className={inputCls} placeholder="optional" />
        </label>
        {error && <ErrorBox error={error} />}
        <div className="flex justify-end gap-2 pt-1">
          <Button type="button" variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" variant="primary" loading={busy}>
            Create & open workspace
          </Button>
        </div>
      </form>
    </Modal>
  );
}
