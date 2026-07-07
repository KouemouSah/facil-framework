import type { Setting } from "./api";

/** Distinct scopes present, sorted — feeds the scope filter. */
export function scopesOf(settings: Setting[]): string[] {
  return Array.from(new Set(settings.map((s) => s.scope))).sort();
}

/** Client-side search (key / scope / i18n name / description) + optional scope filter. */
export function filterSettings(settings: Setting[], q: string, scope: string): Setting[] {
  const needle = q.trim().toLowerCase();
  return settings.filter((s) => {
    if (scope && s.scope !== scope) return false;
    if (!needle) return true;
    const hay = [s.key, s.scope, s.description ?? "", s.name.en ?? "", s.name.fr ?? "", s.name.es ?? ""]
      .join(" ").toLowerCase();
    return hay.includes(needle);
  });
}

/** Group settings by scope (scopes sorted, keys sorted within each) — the hybrid
 *  layout: grouped sections + search/filter on top. */
export function groupByScope(settings: Setting[]): [string, Setting[]][] {
  const map = new Map<string, Setting[]>();
  for (const s of settings) {
    const arr = map.get(s.scope) ?? [];
    arr.push(s);
    map.set(s.scope, arr);
  }
  return [...map.entries()]
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([scope, arr]) => [scope, [...arr].sort((x, y) => x.key.localeCompare(y.key))] as [string, Setting[]]);
}

/** Form field states → the typed `value` for `SettingIn` (validated). The value
 *  control in the form adapts to `value_type`; this picks the right one. */
export function toSettingValue(
  valueType: string, fields: { text: string; bool: boolean; json: unknown },
): { ok: true; value: unknown } | { ok: false; error: "number" | "json" } {
  if (valueType === "boolean") return { ok: true, value: fields.bool };
  if (valueType === "json") return { ok: true, value: fields.json };
  if (valueType === "number") {
    const n = Number(fields.text);
    if (fields.text.trim() === "" || Number.isNaN(n)) return { ok: false, error: "number" };
    return { ok: true, value: n };
  }
  return { ok: true, value: fields.text }; // string
}

/** A setting's stored value → the three form field states (seed on edit). */
export function fromSettingValue(s: { value: unknown; value_type: string }): {
  text: string; bool: boolean; json: unknown;
} {
  return {
    text: (s.value_type === "string" || s.value_type === "number") && s.value != null
      ? String(s.value) : "",
    bool: s.value_type === "boolean" ? Boolean(s.value) : false,
    json: s.value_type === "json" ? (s.value ?? {}) : {},
  };
}

/** Compact, single-line preview of a value for the list row (never full JSON). */
export function formatValuePreview(value: unknown, valueType: string, max = 80): string {
  if (value === null || value === undefined) return "—";
  const s = (valueType === "json" || typeof value === "object")
    ? JSON.stringify(value) : String(value);
  return s.length > max ? `${s.slice(0, max)}…` : s;
}
