"use client";

import { useMemo, useState } from "react";
import { z } from "zod";
import { Check } from "lucide-react";
import { ApiError } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { JsonField } from "@/components/ui/json-field";
import { RefSelect } from "@/components/ui/ref-select";
import { OrgCombobox } from "@/components/ui/org-combobox";
import { PartyCombobox } from "@/components/ui/party-combobox";
import { AddressField } from "@/components/ui/address-field";

/**
 * Generic, schema-driven create/edit form (ENGINEERING_STANDARDS §11bis). One
 * reusable component instead of an ad-hoc form per page: declare the fields, it
 * renders the right control per type, validates client-side with zod, maps the
 * server's 422 onto the offending field and a 409 onto a reload, sends `If-Match`
 * for optimistic concurrency, and offers Save / Save & New / Cancel with a dirty
 * guard. The backend stays the source of truth — this only *reflects* it.
 *
 * Controlled-state + per-field zod (not react-hook-form's dynamic resolver):
 * the field set is dynamic, so a hand-rolled validate pass is simpler and less
 * error-prone here while meeting every §11bis behaviour.
 */
export type FieldType =
  | "text" | "textarea" | "number"
  | "ref" | "org" | "party" | "address" | "json" | "select";

export interface FieldDef {
  name: string;
  label: string;
  type?: FieldType; // default "text"
  required?: boolean;
  hint?: string;
  placeholder?: string;
  colSpan?: 1 | 2;
  /** Read-only in edit mode (e.g. an immutable `code`). */
  immutable?: boolean;
  /** Override the derived zod rule (text/number/select only). */
  zod?: z.ZodTypeAny;
  refResource?: "countries" | "currencies" | "regions";
  refFilter?: Record<string, string>;
  selectOptions?: { value: string; label: string }[];
}

export interface RecordFormProps {
  fields: FieldDef[];
  mode: "create" | "edit";
  initial?: Record<string, unknown>;
  etag?: string;
  /** Persist the cleaned payload. Throw ApiError to surface 422/409/other. */
  onSubmit: (payload: Record<string, unknown>, etag?: string) => Promise<unknown>;
  onSuccess?: (opts: { again: boolean }) => void;
  onCancel?: () => void;
  /** 409 → caller reloads the latest row. */
  onConflict?: () => void;
  submitLabel?: string;
  /** Offer "Save & New" (create mode only). */
  enableSaveNew?: boolean;
  layout?: "compact" | "rich";
}

const SCALAR = new Set<FieldType>(["text", "textarea", "number", "select"]);

function initialValue(f: FieldDef, initial?: Record<string, unknown>): string {
  const v = initial?.[f.name];
  return v === undefined || v === null ? "" : String(v);
}

export function RecordForm({
  fields, mode, initial, etag, onSubmit, onSuccess, onCancel, onConflict,
  submitLabel = "Save", enableSaveNew = false, layout = "compact",
}: RecordFormProps) {
  const jsonFields = useMemo(() => fields.filter((f) => f.type === "json"), [fields]);

  const [values, setValues] = useState<Record<string, string>>(() => {
    const v: Record<string, string> = {};
    for (const f of fields) if (f.type !== "json") v[f.name] = initialValue(f, initial);
    return v;
  });
  const [jsonValues, setJsonValues] = useState<Record<string, unknown>>(() => {
    const v: Record<string, unknown> = {};
    for (const f of jsonFields) v[f.name] = initial?.[f.name] ?? {};
    return v;
  });
  const [jsonOk, setJsonOk] = useState<Record<string, boolean>>(() => {
    const v: Record<string, boolean> = {};
    for (const f of jsonFields) v[f.name] = true;
    return v;
  });

  const [errors, setErrors] = useState<Record<string, string>>({});
  const [formError, setFormError] = useState("");
  const [saved, setSaved] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [dirty, setDirty] = useState(false);
  // Bumped on "Save & New" to remount the (internally-uncontrolled) JsonField
  // editors so their textareas reset along with jsonValues.
  const [resetKey, setResetKey] = useState(0);

  function setField(name: string, v: string) {
    setValues((s) => ({ ...s, [name]: v }));
    setErrors((e) => (e[name] ? { ...e, [name]: "" } : e));
    setDirty(true); setSaved(false);
  }

  function fieldRule(f: FieldDef): z.ZodTypeAny {
    if (f.zod) return f.zod;
    if (f.required) return z.string().trim().min(1, `${f.label} is required`);
    return z.string().optional();
  }

  function validate(): boolean {
    const next: Record<string, string> = {};
    for (const f of fields) {
      if (f.type === "json") {
        if (!jsonOk[f.name]) next[f.name] = "Invalid JSON";
        continue;
      }
      if (!SCALAR.has(f.type ?? "text")) {
        if (f.required && !values[f.name]) next[f.name] = `${f.label} is required`;
        continue;
      }
      const res = fieldRule(f).safeParse(values[f.name]);
      if (!res.success) next[f.name] = res.error.issues[0]?.message ?? "Invalid value";
    }
    setErrors(next);
    return Object.keys(next).length === 0;
  }

  function buildPayload(): Record<string, unknown> {
    const out: Record<string, unknown> = {};
    for (const f of fields) {
      if (f.immutable && mode === "edit") continue;
      if (f.type === "json") { out[f.name] = jsonValues[f.name] ?? {}; continue; }
      const raw = values[f.name] ?? "";
      if (f.type === "number") { out[f.name] = raw === "" ? null : Number(raw); continue; }
      // Blank → null uniformly: text/select clear to null, and empty FK pickers
      // (org/party/address/ref) are ids that must be null (never "") to detach.
      out[f.name] = raw === "" ? null : raw;
    }
    return out;
  }

  async function submit(again: boolean) {
    setFormError("");
    if (!validate()) return;
    setSubmitting(true);
    try {
      await onSubmit(buildPayload(), etag);
      setDirty(false); setSaved(true);
      if (again) {
        // Reset every control for a fresh entry: scalars/pickers, JSON values +
        // validity, and field errors; bump resetKey to remount JsonField (its
        // textarea is seeded once from `value`, so state reset alone won't clear it).
        const clearedScalars: Record<string, string> = {};
        for (const f of fields) if (f.type !== "json") clearedScalars[f.name] = "";
        const clearedJson: Record<string, unknown> = {};
        const clearedJsonOk: Record<string, boolean> = {};
        for (const f of jsonFields) { clearedJson[f.name] = {}; clearedJsonOk[f.name] = true; }
        setValues(clearedScalars);
        setJsonValues(clearedJson);
        setJsonOk(clearedJsonOk);
        setErrors({});
        setResetKey((k) => k + 1);
      }
      onSuccess?.({ again });
    } catch (e) {
      if (e instanceof ApiError && e.status === 422) {
        const fe = e.fieldErrors();
        if (Object.keys(fe).length) setErrors(fe);
        else setFormError(e.message || "Validation failed");
      } else if (e instanceof ApiError && e.status === 409) {
        if (onConflict) { setFormError("Changed elsewhere — reloading."); onConflict(); }
        else setFormError("Changed elsewhere — please reload.");
      } else {
        setFormError(e instanceof ApiError ? e.message : "Save failed");
      }
    } finally {
      setSubmitting(false);
    }
  }

  function cancel() {
    if (dirty && !window.confirm("Discard unsaved changes?")) return;
    onCancel?.();
  }

  function renderControl(f: FieldDef) {
    const readOnly = f.immutable && mode === "edit";
    const id = `rf-${f.name}`;
    switch (f.type) {
      case "json":
        return (
          <JsonField key={`${f.name}-${resetKey}`} id={id} label={f.label}
            value={jsonValues[f.name]} hint={f.hint}
            onChange={(v, ok) => {
              setJsonValues((s) => ({ ...s, [f.name]: v }));
              setJsonOk((s) => ({ ...s, [f.name]: ok }));
              setDirty(true); setSaved(false);
              if (ok) setErrors((e) => (e[f.name] ? { ...e, [f.name]: "" } : e));
            }} />
        );
      case "ref":
        return (
          <RefSelect resource={f.refResource ?? "countries"} value={values[f.name] ?? ""}
            filter={f.refFilter} disabled={readOnly}
            onChange={(v) => setField(f.name, v)} />
        );
      case "org":
        return <OrgCombobox value={values[f.name] ?? ""} onChange={(v) => setField(f.name, v)} />;
      case "party":
        return <PartyCombobox value={values[f.name] ?? ""} onChange={(v) => setField(f.name, v)} />;
      case "address":
        return <AddressField label={f.label} value={values[f.name] ?? ""}
          onChange={(v) => setField(f.name, v)} />;
      case "select":
        return (
          <select id={id} value={values[f.name] ?? ""} disabled={readOnly}
            onChange={(e) => setField(f.name, e.target.value)}
            className="flex h-9 w-full rounded-md border border-input bg-background px-3 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-50">
            {!f.required && <option value="">— none —</option>}
            {(f.selectOptions ?? []).map((o) => (
              <option key={o.value} value={o.value}>{o.label}</option>
            ))}
          </select>
        );
      case "textarea":
        return (
          <textarea id={id} value={values[f.name] ?? ""} rows={3} disabled={readOnly}
            placeholder={f.placeholder}
            onChange={(e) => setField(f.name, e.target.value)}
            className="flex w-full rounded-md border border-input bg-background px-3 py-2 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-50" />
        );
      default:
        return (
          <Input id={id} type={f.type === "number" ? "number" : "text"}
            value={values[f.name] ?? ""} disabled={readOnly} placeholder={f.placeholder}
            onChange={(e) => setField(f.name, e.target.value)} />
        );
    }
  }

  const gridCls = layout === "rich"
    ? "grid grid-cols-1 gap-3 sm:grid-cols-2"
    : "grid grid-cols-1 gap-3";

  return (
    <form className="space-y-4" onSubmit={(e) => { e.preventDefault(); submit(false); }}>
      <div className={gridCls}>
        {fields.map((f) => {
          const span = f.colSpan === 2 || f.type === "json" || f.type === "address"
            ? "sm:col-span-2" : "";
          // Address renders its own label/border; others get a Label.
          return (
            <div key={f.name} className={`space-y-1.5 ${span}`}>
              {f.type !== "address" && f.type !== "json" && (
                <Label htmlFor={`rf-${f.name}`}>
                  {f.label}{f.required && <span className="text-destructive"> *</span>}
                </Label>
              )}
              {renderControl(f)}
              {f.hint && f.type !== "json" && (
                <p className="text-xs text-muted-foreground">{f.hint}</p>
              )}
              {errors[f.name] && <p className="text-xs text-destructive">{errors[f.name]}</p>}
            </div>
          );
        })}
      </div>

      <div className="flex items-center gap-2">
        {saved && (
          <span className="flex items-center gap-1 text-sm text-emerald-600">
            <Check className="size-4" /> Saved
          </span>
        )}
        {formError && <span className="text-sm text-destructive">{formError}</span>}
        <div className="ml-auto flex items-center gap-2">
          {onCancel && (
            <Button type="button" variant="ghost" size="sm" onClick={cancel}>Cancel</Button>
          )}
          {mode === "create" && enableSaveNew && (
            <Button type="button" variant="secondary" size="sm" disabled={submitting}
              onClick={() => submit(true)}>Save &amp; New</Button>
          )}
          <Button type="submit" size="sm" disabled={submitting}>
            {submitting ? "Saving…" : submitLabel}
          </Button>
        </div>
      </div>
    </form>
  );
}
