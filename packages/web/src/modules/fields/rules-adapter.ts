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
// Returns an i18n-safe `errorKey` (+ `errorParams` for interpolation) instead
// of an English message — the caller (`buildDefinitionPayload` in `fields.ts`)
// is the one with a translator in scope, so localization happens there; this
// module has no React/next-intl dependency and stays a pure, framework-free
// adapter (see `ruleSanity` below for the same convention).
export function nestRules(
  form: Record<string, unknown>, advanced: Record<string, unknown>,
): { rules: FieldRules; errorKey?: string; errorParams?: Record<string, string> } {
  const adv = advanced ?? {};
  for (const k of Object.keys(adv)) {
    if ((UI_RULE_KEYS as readonly string[]).includes(k))
      return { rules: {}, errorKey: "advanced_has_ui_key", errorParams: { key: k } };
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
// — min>max (numeric, money, or a static date pair), a non-positive step, or
// a regex that doesn't even compile — returning an i18n-safe `errorKey` (see
// `nestRules`'s docstring above for why: this module never touches
// next-intl). `buildDefinitionPayload` in `fields.ts` maps the key onto a
// field error on `rules_advanced`.
export function ruleSanity(form: Record<string, unknown>): { errorKey?: string } {
  const n = (v: unknown) => (v === "" || v === undefined || v === null ? undefined : Number(v));
  const pairs: [unknown, unknown, string][] = [
    [n(form.rule_min), n(form.rule_max), "min_gt_max"],
    [n(form.rule_min_length), n(form.rule_max_length), "minlen_gt_maxlen"],
    [n(form.rule_min_items), n(form.rule_max_items), "minitems_gt_maxitems"],
    [n(form.rule_money_min), n(form.rule_money_max), "money_min_gt_max"],
  ];
  for (const [lo, hi, errorKey] of pairs)
    if (lo !== undefined && hi !== undefined && (lo as number) > (hi as number)) return { errorKey };

  // date/datetime/time: a bound must be empty, the TYPE'S legal token
  // ("today" only for `date`, "now" only for `datetime`, no token at all for
  // `time`), or a value the browser can parse as that type — reject anything
  // else here, at authoring, so a poisoned def (e.g. "now" on a `date`) never
  // reaches save. The backend `_coerce` is still the sole authority; this is
  // the client half of the Final-review defense-in-depth fix (the shared
  // hint used to promise tokens for all three types, which is what
  // misdirected admins into this in the first place).
  const dtType = form.type;
  if (dtType === "date" || dtType === "datetime" || dtType === "time") {
    const legalToken = dtType === "date" ? "today" : dtType === "datetime" ? "now" : undefined;
    const isValidBound = (v: unknown): boolean => {
      if (v === undefined || v === null || v === "") return true;
      if (typeof v !== "string") return false;
      if (v === legalToken) return true;
      if (v === "today" || v === "now") return false; // illegal token for this type
      if (dtType === "time") return /^\d{2}:\d{2}(:\d{2})?$/.test(v);
      return !Number.isNaN(Date.parse(v));
    };
    if (!isValidBound(form.rule_date_min) || !isValidBound(form.rule_date_max))
      return { errorKey: "bad_date_bound" };
  }

  // Only a STATIC ISO-string pair is comparable here — "today"/"now" resolve
  // at submit/save time (server-side), so their actual ordering relative to
  // a static bound (or to each other) isn't known client-side; skip the
  // check rather than risk a false positive.
  const isToken = (v: unknown) => v === "today" || v === "now";
  const dMin = form.rule_date_min;
  const dMax = form.rule_date_max;
  if (
    typeof dMin === "string" && dMin && typeof dMax === "string" && dMax
    && !isToken(dMin) && !isToken(dMax) && dMin > dMax
  ) return { errorKey: "date_min_gt_max" };

  const step = n(form.rule_step);
  if (step !== undefined && step <= 0) return { errorKey: "step_not_positive" };
  const p = form.rule_pattern;
  if (typeof p === "string" && p) { try { new RegExp(p); } catch { return { errorKey: "bad_regex" }; } }
  return {};
}
