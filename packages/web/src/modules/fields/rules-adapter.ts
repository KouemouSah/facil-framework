import type { FieldRules } from "@/lib/schema/types";

export const UI_RULE_KEYS = [
  "min", "max", "min_length", "max_length", "pattern", "step", "precision",
  "min_items", "max_items", "must_be_true", "allowed_extensions",
] as const;

export const PATTERN_PRESETS: { value: string; pattern: string }[] = [
  { value: "email", pattern: "^[^@\\s]+@[^@\\s]+\\.[^@\\s]+$" },
  { value: "phone", pattern: "^[+]?[0-9 ()-]{6,}$" },
  { value: "url", pattern: "^https?://.+" },
  { value: "slug", pattern: "^[a-z0-9]+(?:-[a-z0-9]+)*$" },
  { value: "alphanumeric", pattern: "^[a-zA-Z0-9]+$" },
  { value: "custom", pattern: "" },
];

// Split the rules object into flat form values (rule_<key>) + leftover advanced.
export function flattenRules(rules: FieldRules): {
  form: Record<string, unknown>; advanced: Record<string, unknown>;
} {
  const r = { ...(rules ?? {}) } as Record<string, unknown>;
  const form: Record<string, unknown> = {};
  const put = (k: string, v: unknown) => { if (v !== undefined) form[k] = v; };
  // numeric min/max, dates, money all read from rules.min/max — the visible input
  // per type owns it; we pre-fill all three targets, hidden ones are ignored.
  put("rule_min", r.min); put("rule_max", r.max);
  put("rule_date_min", r.min); put("rule_date_max", r.max);
  put("rule_money_min", r.min); put("rule_money_max", r.max);
  put("rule_min_length", r.min_length); put("rule_max_length", r.max_length);
  put("rule_pattern", r.pattern); put("rule_step", r.step); put("rule_precision", r.precision);
  put("rule_min_items", r.min_items); put("rule_max_items", r.max_items);
  put("rule_must_be_true", r.must_be_true); put("rule_allowed_extensions", r.allowed_extensions);
  const advanced: Record<string, unknown> = {};
  for (const [k, v] of Object.entries(r)) {
    if (!(UI_RULE_KEYS as readonly string[]).includes(k) && k !== "visible_if" && k !== "required_if")
      advanced[k] = v;
  }
  // keep condition keys in advanced so they round-trip untouched
  if (r.visible_if !== undefined) advanced.visible_if = r.visible_if;
  if (r.required_if !== undefined) advanced.required_if = r.required_if;
  return { form, advanced };
}

// Recompose rules from flat form values + the advanced JSON; disjoint guard.
export function nestRules(
  form: Record<string, unknown>, advanced: Record<string, unknown>,
): { rules: FieldRules; error?: string } {
  const adv = advanced ?? {};
  for (const k of Object.keys(adv)) {
    if ((UI_RULE_KEYS as readonly string[]).includes(k))
      return { rules: {}, error: `${k} is managed via the UI — remove it from Advanced JSON` };
  }
  const out: Record<string, unknown> = { ...adv };
  const first = (...vs: unknown[]) => vs.find((v) => v !== undefined && v !== "" && v !== null);
  const set = (k: string, v: unknown) => { if (v !== undefined && v !== "" && v !== null) out[k] = v; };
  set("min", first(form.rule_min, form.rule_date_min, form.rule_money_min));
  set("max", first(form.rule_max, form.rule_date_max, form.rule_money_max));
  set("min_length", form.rule_min_length); set("max_length", form.rule_max_length);
  set("pattern", form.rule_pattern); set("step", form.rule_step); set("precision", form.rule_precision);
  set("min_items", form.rule_min_items); set("max_items", form.rule_max_items);
  set("allowed_extensions", form.rule_allowed_extensions);
  if (form.rule_must_be_true === true) out.must_be_true = true;
  return { rules: out as FieldRules };
}

// Client-side-only sanity guard (the backend `_coerce` is still the sole
// authority): catches an incoherent rule combination BEFORE a save round-trip
// — min>max, a non-positive step, or a regex that doesn't even compile —
// with a message a RecordForm caller can surface as a field error on
// `rules_advanced` (see `buildDefinitionPayload` in `fields.ts`).
export function ruleSanity(form: Record<string, unknown>): { error?: string } {
  const n = (v: unknown) => (v === "" || v === undefined || v === null ? undefined : Number(v));
  const pairs: [unknown, unknown, string][] = [
    [n(form.rule_min), n(form.rule_max), "min must be ≤ max"],
    [n(form.rule_min_length), n(form.rule_max_length), "min length must be ≤ max length"],
    [n(form.rule_min_items), n(form.rule_max_items), "min items must be ≤ max items"],
  ];
  for (const [lo, hi, msg] of pairs)
    if (lo !== undefined && hi !== undefined && (lo as number) > (hi as number)) return { error: msg };
  const step = n(form.rule_step);
  if (step !== undefined && step <= 0) return { error: "step must be > 0" };
  const p = form.rule_pattern;
  if (typeof p === "string" && p) { try { new RegExp(p); } catch { return { error: "pattern is not a valid regex" }; } }
  return {};
}
