"use client";

import { useMemo, useState } from "react";
import { z } from "zod";
import { Check } from "lucide-react";
import { ApiError } from "@/lib/api";
import { isVisible } from "@/lib/schema/conditions";
import type { FieldRules, FieldSpec, FieldSpecType } from "@/lib/schema/types";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { JsonField } from "@/components/ui/json-field";
import { RefSelect } from "@/components/ui/ref-select";
import { OrgCombobox } from "@/components/ui/org-combobox";
import { TimezoneField } from "@/components/ui/timezone-field";
import { PartyCombobox } from "@/components/ui/party-combobox";
import { AddressField } from "@/components/ui/address-field";
import { FileUpload } from "@/components/ui/file-upload";

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
// ⚠️ COLLISION: `FieldDef.type` is `FieldType | FieldSpecType` (merged union),
// and exactly one name means two different things depending on which
// vocabulary it came from:
//   legacy FieldType.text  = single-line <Input>  — the documented default
//                             (an omitted `type` falls here, see below).
//   spec FieldSpecType.text = MULTI-LINE (what legacy called "textarea").
// The two are told apart by `widget`: a server-served FieldSpec ALWAYS
// carries one (backend fills `DEFAULT_WIDGET` for every spec — see
// app/core/schema/types.py), a hand-written legacy FieldDef NEVER sets one.
// `controlKindFor` below is the single place that resolves this; every
// spec-driven dispatch branch in `renderControl` must gate through it —
// never dispatch on a bare `f.type === "text"` (or any other type that
// exists in both vocabularies). Mirrors the backend's `LEGACY_TYPE_ALIASES`
// comment (app/core/schema/types.py), which explains why "text" is
// deliberately NOT aliased there for the identical reason.
export type FieldType =
  | "text" | "email" | "password" | "textarea" | "number" | "checkbox"
  | "ref" | "org" | "party" | "address" | "json" | "select" | "image" | "color" | "timezone";

export interface FieldDef {
  name: string;
  label: string;
  /** Legacy literal (default "text") OR a server-served FieldSpec type (spec §5,
   *  axis 1) — `renderControl` dispatches new (type, widget) pairs before
   *  falling through to the untouched legacy switch below. */
  type?: FieldType | FieldSpecType;
  required?: boolean;
  hint?: string;
  placeholder?: string;
  colSpan?: 1 | 2;
  /** Read-only in edit mode (e.g. an immutable `code`). */
  immutable?: boolean;
  /** Override the derived zod rule (text/number/select only). A DB-defined field
   *  can never carry this (not serialisable) — see `rules` below. */
  zod?: z.ZodTypeAny;
  refResource?: "countries" | "currencies" | "regions";
  refFilter?: Record<string, string>;
  selectOptions?: { value: string; label: string }[];
  /** Presentation variant within `type` (spec §5, axis 2). Falls back to the
   *  type's canonical widget when absent. */
  widget?: string;
  /** Declarative validation/visibility from a server-served spec, compiled to
   *  zod by `rulesToZod`. `zod` still wins when both are set (hand-written
   *  fields keep their bespoke rule). */
  rules?: FieldRules;
  /** Target resource for `type: "relation"` (generalises refResource). */
  relationResource?: string;
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
  /** Permission-driven: render every field disabled and hide the save actions
   *  (the user may read but not write). The backend still enforces. */
  readOnly?: boolean;
}

// Types whose value is a plain string/number the zod rule (`fieldRule`, hand-
// written OR `rulesToZod`-compiled from a server spec) actually validates.
// Everything else (checkbox/boolean, json, pickers, file) only gets the
// simpler required-check below — a picker's "emptiness" isn't a string rule.
// Without the FieldSpecType members here, a server-served field's compiled
// `rules` (max_length/pattern/min/max) would silently never run: `fieldRule()`
// is only reached from inside this gate.
const SCALAR = new Set<FieldType | FieldSpecType>([
  "text", "email", "password", "textarea", "number", "select",
  "string", "richtext", "decimal", "money", "date", "datetime", "time",
]);

/**
 * Discriminates a server-served, spec-driven field from a hand-written legacy
 * one. This is the fix for the `text` collision documented on `FieldType`
 * above: a `FieldSpec` served by the backend always carries a `widget`
 * (`DEFAULT_WIDGET` is filled for every spec — see
 * `packages/backend/app/core/schema/types.py` and
 * `lib/schema/to-field-def.ts:14`); a hand-written legacy `FieldDef` never
 * sets one. Every new pre-switch branch in `renderControl` MUST gate on
 * `controlKindFor(f) === "spec"` (not on the bare `f.type`) so a legacy field
 * can never fall into a spec-only branch. Exported + pure so the collision is
 * pinned by a test (record-form.test.ts) without touching the DOM.
 */
export function controlKindFor(f: FieldDef): "legacy" | "spec" {
  return f.widget !== undefined ? "spec" : "legacy";
}

function initialValue(f: FieldDef, initial?: Record<string, unknown>): string {
  const v = initial?.[f.name];
  return v === undefined || v === null ? "" : String(v);
}

export function RecordForm({
  fields, mode, initial, etag, onSubmit, onSuccess, onCancel, onConflict,
  submitLabel = "Save", enableSaveNew = false, layout = "compact", readOnly = false,
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

  // Adapter: `isVisible` (lib/schema/conditions, mirrors the server) takes a
  // FieldSpec; a hand-written FieldDef only ever carries `rules` (server-served
  // fields do — hand-written ones have no `rules` and are therefore always
  // visible, matching today's behaviour exactly).
  function isVisibleDef(f: FieldDef, vals: Record<string, string>): boolean {
    if (!f.rules) return true;
    return isVisible({ rules: f.rules } as unknown as FieldSpec, vals);
  }

  function validate(): boolean {
    const next: Record<string, string> = {};
    for (const f of fields) {
      // A hidden field is neither validated nor submitted — mirrors
      // app/core/schema/conditions.py. The server re-checks regardless.
      if (!isVisibleDef(f, values)) continue;
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
      // A hidden field must never be posted — the server rejects an unexpected
      // field with a 422 (Task 4), which would otherwise break the UX.
      if (!isVisibleDef(f, values)) continue;
      if (f.type === "json") { out[f.name] = jsonValues[f.name] ?? {}; continue; }
      const raw = values[f.name] ?? "";
      if (f.type === "checkbox" || f.type === "boolean") { out[f.name] = raw === "true"; continue; }
      if (f.type === "number") { out[f.name] = raw === "" ? null : Number(raw); continue; }
      // Blank → null uniformly: text/select clear to null, and empty FK pickers
      // (org/party/address/ref) are ids that must be null (never "") to detach.
      out[f.name] = raw === "" ? null : raw;
    }
    return out;
  }

  async function submit(again: boolean) {
    // No write permission → never fire (guards the implicit Enter-key submit even
    // though the buttons are hidden). The backend still enforces regardless.
    if (readOnly) return;
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

  // Render helpers shared between the new spec-driven dispatch below and the
  // legacy `switch` (Fix 2 — a control's markup now lives in exactly one
  // place). Closures over `values`/`setField` since both call sites are
  // inside the component.
  function renderColorControl(f: FieldDef, fieldRO: boolean, id: string) {
    const hex = values[f.name] ?? "";
    const valid = /^#[0-9a-fA-F]{6}$/.test(hex);
    return (
      <div className="flex items-center gap-2">
        <input type="color" aria-label={f.label} disabled={fieldRO}
          className="h-9 w-12 shrink-0 cursor-pointer rounded-md border border-input bg-background p-1 disabled:opacity-50"
          value={valid ? hex : "#000000"}
          onChange={(e) => setField(f.name, e.target.value)} />
        <Input id={id} className="font-mono" value={hex} disabled={fieldRO} placeholder={f.placeholder}
          onChange={(e) => setField(f.name, e.target.value)} />
      </div>
    );
  }

  function renderCheckboxControl(f: FieldDef, fieldRO: boolean) {
    return (
      <label className="flex items-center gap-2 text-sm">
        <input type="checkbox" className="size-4 accent-[hsl(var(--primary))]"
          checked={values[f.name] === "true"} disabled={fieldRO}
          onChange={(e) => setField(f.name, e.target.checked ? "true" : "")} />
        {f.label}
      </label>
    );
  }

  function renderTextareaControl(f: FieldDef, fieldRO: boolean, id: string) {
    return (
      <textarea id={id} value={values[f.name] ?? ""} rows={3} disabled={fieldRO}
        placeholder={f.placeholder}
        onChange={(e) => setField(f.name, e.target.value)}
        className="flex w-full rounded-md border border-input bg-background px-3 py-2 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-50" />
    );
  }

  function renderControl(f: FieldDef) {
    // Disabled when the form is read-only (no write permission) or this is an
    // immutable field in edit mode.
    const fieldRO = Boolean(readOnly || (f.immutable && mode === "edit"));
    const id = `rf-${f.name}`;
    // New (type, widget) pairs first; the legacy `switch` below still handles
    // every hand-written field list untouched. Every branch here is gated on
    // `controlKindFor(f) === "spec"` (Fix 1) — NOT the bare `f.type` — so a
    // hand-written legacy FieldDef can never be misrouted into a spec-only
    // control. See the `text` collision note on `FieldType` above.
    const specDriven = controlKindFor(f) === "spec";
    if (specDriven && f.type === "string" && f.widget === "color")
      // Same control as the legacy `case "color"` below (kept there for the
      // hand-written literal `type: "color"` alias) — swatch + hex input.
      return renderColorControl(f, fieldRO, id);
    if (specDriven && f.type === "string" && f.widget === "timezone")
      return <TimezoneField value={values[f.name] ?? ""} disabled={fieldRO}
               onChange={(v) => setField(f.name, v)} />;
    if (specDriven && f.type === "relation")
      return <RefSelect resource={(f.relationResource ?? f.refResource ?? "countries") as never}
               value={values[f.name] ?? ""} filter={f.refFilter} disabled={fieldRO}
               onChange={(v) => setField(f.name, v)} />;
    // A server-served `type: "file"` (e.g. document_identity.logo_url/seal_url,
    // widget "image") stores the uploaded asset URL exactly like the legacy
    // `case "image"` below — same control, reached before the legacy switch so
    // it isn't misrouted into the default text input.
    if (specDriven && f.type === "file")
      return <FileUpload value={values[f.name] ?? ""} disabled={fieldRO}
               onUploaded={(url) => setField(f.name, url)}
               onRemove={() => setField(f.name, "")} />;
    // NEW "text" = multi-line (types.py LEGACY_TYPE_ALIASES note: the legacy
    // literal "text" meant single-line and is deliberately NOT aliased to the
    // new "text", to avoid silently downgrading it). No dedicated "code" widget
    // editor exists yet, so both `text` widgets ("plain"/"code") render the same
    // textarea as the legacy `case "textarea"` below for now. `specDriven` is
    // what keeps a legacy `{type: "text"}` (no widget, single-line default)
    // out of this branch — see `controlKindFor`.
    if (specDriven && f.type === "text")
      return renderTextareaControl(f, fieldRO, id);
    // `boolean` is a new type-axis value with no legacy switch case (the legacy
    // literal is the type "checkbox", not "boolean") — dispatch it here so a
    // server-served boolean config field (e.g. providers' `use_tls`) renders as
    // a checkbox instead of falling through to the default text input. This is
    // the MANDATORY providers regression fix (Task 7 brief amendment): the
    // 13 built-in providers declare several `type="boolean"` config fields.
    if (specDriven && f.type === "boolean")
      return renderCheckboxControl(f, fieldRO);
    // NOTE: `json` + widget `weekly_hours` (Site.operating_hours, spec §12) is
    // declared in WIDGETS_BY_TYPE but not yet used by any registered field —
    // its bespoke `WeeklyHoursField` control ships with M2, not here.
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
            filter={f.refFilter} disabled={fieldRO}
            onChange={(v) => setField(f.name, v)} />
        );
      case "org":
        return <OrgCombobox value={values[f.name] ?? ""} disabled={fieldRO}
          onChange={(v) => setField(f.name, v)} />;
      case "timezone":
        return <TimezoneField value={values[f.name] ?? ""} disabled={fieldRO}
          onChange={(v) => setField(f.name, v)} />;
      case "party":
        return <PartyCombobox value={values[f.name] ?? ""} disabled={fieldRO}
          onChange={(v) => setField(f.name, v)} />;
      case "address":
        return <AddressField label={f.label} value={values[f.name] ?? ""} disabled={fieldRO}
          onChange={(v) => setField(f.name, v)} />;
      case "image":
        // Stores the uploaded asset URL (same-origin) as a plain string value,
        // exactly like ref/address store an id — buildPayload/validate handle it.
        return <FileUpload value={values[f.name] ?? ""} disabled={fieldRO}
          onUploaded={(url) => setField(f.name, url)}
          onRemove={() => setField(f.name, "")} />;
      case "color":
        // Swatch picker + hex input, both bound to the same string value.
        return renderColorControl(f, fieldRO, id);
      case "checkbox":
        return renderCheckboxControl(f, fieldRO);
      case "select":
        return (
          <select id={id} value={values[f.name] ?? ""} disabled={fieldRO}
            onChange={(e) => setField(f.name, e.target.value)}
            className="flex h-9 w-full rounded-md border border-input bg-background px-3 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-50">
            {!f.required && <option value="">— none —</option>}
            {(f.selectOptions ?? []).map((o) => (
              <option key={o.value} value={o.value}>{o.label}</option>
            ))}
          </select>
        );
      case "textarea":
        return renderTextareaControl(f, fieldRO, id);
      default: {
        // text (default) + number/email/password map straight to the native input
        // type — email gives the right mobile keyboard, password masks entry.
        const htmlType =
          f.type === "number" ? "number"
            : f.type === "email" ? "email"
              : f.type === "password" ? "password"
                : "text";
        return (
          <Input id={id} type={htmlType} autoComplete={f.type === "password" ? "new-password" : undefined}
            value={values[f.name] ?? ""} disabled={fieldRO} placeholder={f.placeholder}
            onChange={(e) => setField(f.name, e.target.value)} />
        );
      }
    }
  }

  const gridCls = layout === "rich"
    ? "grid grid-cols-1 gap-3 sm:grid-cols-2"
    : "grid grid-cols-1 gap-3";

  return (
    <form className="space-y-4" onSubmit={(e) => { e.preventDefault(); submit(false); }}>
      <div className={gridCls}>
        {fields.map((f) => {
          // A hidden field (server-served `visible_if` not met) is neither
          // rendered, validated, nor submitted — mirrors the server.
          if (!isVisibleDef(f, values)) return null;
          const span = f.colSpan === 2 || f.type === "json" || f.type === "address"
            ? "sm:col-span-2" : "";
          // Address/checkbox/boolean render their own label; others get a Label.
          return (
            <div key={f.name} className={`space-y-1.5 ${span}`}>
              {f.type !== "address" && f.type !== "json" && f.type !== "checkbox" && f.type !== "boolean" && (
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
          {/* No write permission → no save actions (the fields are disabled too). */}
          {!readOnly && mode === "create" && enableSaveNew && (
            <Button type="button" variant="secondary" size="sm" disabled={submitting}
              onClick={() => submit(true)}>Save &amp; New</Button>
          )}
          {!readOnly && (
            <Button type="submit" size="sm" disabled={submitting}>
              {submitting ? "Saving…" : submitLabel}
            </Button>
          )}
        </div>
      </div>
    </form>
  );
}
