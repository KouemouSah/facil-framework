import { useLocale } from "next-intl";
import { z } from "zod";
import type { FieldDef } from "@/components/ui/record-form";
import { requiredText } from "@/lib/form-schemas";
import { tr, type FieldSpecType, type I18nString, type Locale } from "@/lib/schema/types";
import enMessages from "@/i18n/messages/en.json";
import frMessages from "@/i18n/messages/fr.json";
import esMessages from "@/i18n/messages/es.json";
import { TARGETS, type Definition, type DefinitionIn, type IndexState, type Target } from "./api";

export { TARGETS, type Target };

/**
 * next-intl (and the pure `ft()` walker below) resolve a translation key by
 * splitting it on "." to descend through nested messages — a key segment
 * that itself CONTAINS a literal "." breaks that resolution, because it gets
 * mis-parsed as extra nesting instead of one flat key. `Target` values
 * (`"organization.custom_fields"`, `"org_unit.custom_fields"`,
 * `"site.custom_fields"`) are exactly that: real API/URL values (must match
 * the backend's `EXTENSIBLE_TARGETS` strings byte-for-byte) that happen to
 * contain a dot. `t(\`target.${target}\`)` therefore never resolved and
 * rendered the raw fallback key text (e.g. literally
 * "fields.target.organization.custom_fields") instead of "Organization" —
 * caught live by the Task 16 e2e, not by any unit test (this file's own
 * vitest suite never renders through next-intl).
 *
 * The fix: index `fields.target.*` in the messages files by the dot-free
 * PREFIX of the target (`"organization"` / `"org_unit"` / `"site"`), which
 * is already unique across all three targets — no separate mapping table
 * needed, and the wire-level `Target` strings are untouched.
 */
export function targetLabelKey(target: Target): string {
  return target.split(".")[0];
}

/**
 * Mirror of `app/core/schema/types.py` (FIELD_TYPES / WIDGETS_BY_TYPE /
 * INDEXABLE_TYPES). Client-side only NARROWS the UI; the backend
 * (`FieldSpec._coherent`) is the sole authority and rejects an incoherent
 * (type, widget) pair or a non-indexable `indexed` type with a 422 regardless
 * of what this file offers — keep in sync by hand when the backend changes.
 */
export const FIELD_SPEC_TYPES: FieldSpecType[] = [
  "string", "text", "richtext",
  "number", "decimal", "money",
  "boolean",
  "date", "datetime", "time",
  "select", "multiselect",
  "relation",
  "file",
  "json",
];

// IMPORTANT-1 fix (final fix wave): `RecordForm` (`components/ui/record-form.
// tsx`) has no control for `money` (needs a `{amount, currency}` object) or
// `multiselect` (needs a list) — both fall through to the default single-line
// `<Input>`, which posts a plain STRING. The server's `_coerce`
// (pydantic_gen.py) then rejects every save of the host entity with a 422 the
// admin cannot fix from the UI (the only escape is archiving the field) — a
// guaranteed-broken capability the Studio must not advertise (repo parity
// rule: no UI toward a capability that cannot work). `FIELD_SPEC_TYPES`
// itself stays the full backend mirror (used by `INDEXABLE_TYPES`/
// `WIDGETS_BY_TYPE`, and by `widgetsFor` for a pre-existing money/multiselect
// definition still being edited) — only the Studio's CREATE picker narrows.
const STUDIO_UNSUPPORTED_TYPES: readonly FieldSpecType[] = ["money", "multiselect"];

// The types RecordForm can actually round-trip end-to-end today (every type
// EXCEPT the two above) — kept as an explicit, separately-testable constant
// (`fields.test.ts` pins `STUDIO_OFFERED_TYPES` as a SUBSET of this) rather
// than only ever expressed as "FIELD_SPEC_TYPES minus the unsupported ones",
// so a future type added to `FIELD_SPEC_TYPES` without RecordForm support
// fails that test instead of silently becoming offerable.
export const RECORD_FORM_ROUND_TRIPPABLE_TYPES: FieldSpecType[] =
  FIELD_SPEC_TYPES.filter((t) => !STUDIO_UNSUPPORTED_TYPES.includes(t));

// What the Studio's "New field" `type` picker offers for a NEW field. An
// EXISTING field already carrying an unsupported type (created before this
// fix, or via a direct API call) is still fully editable — see
// `buildFieldDefFields`'s `seedType` handling below, which re-admits it.
export const STUDIO_OFFERED_TYPES: FieldSpecType[] = RECORD_FORM_ROUND_TRIPPABLE_TYPES;

export const WIDGETS_BY_TYPE: Record<FieldSpecType, string[]> = {
  string: ["plain", "email", "password", "url", "phone", "color", "timezone", "badge", "copyable", "masked"],
  text: ["plain", "code"],
  richtext: ["editor"],
  number: ["plain", "percent", "rating", "progress", "slider"],
  decimal: ["plain", "percent"],
  money: ["plain"],
  boolean: ["checkbox", "switch"],
  date: ["date", "month", "quarter", "year"],
  datetime: ["datetime"],
  time: ["time"],
  select: ["dropdown", "radio", "segmented"],
  multiselect: ["tags", "checkboxes"],
  relation: ["combobox", "radio", "cards"],
  file: ["document", "image", "avatar", "gallery"],
  // `weekly_hours` is the bespoke control this task ships (WeeklyHoursField),
  // wired into RecordForm for `type: "json", widget: "weekly_hours"`.
  json: ["raw", "weekly_hours"],
};

// Blob-ish types cannot be sorted/filtered -> `indexed` is refused on them
// (mirrors `INDEXABLE_TYPES` in types.py). Used to hide the `indexed` toggle
// on the field-definition form for a type where it could never apply.
export const INDEXABLE_TYPES: FieldSpecType[] =
  FIELD_SPEC_TYPES.filter((t) => !["richtext", "multiselect", "file", "json"].includes(t));

// The ONLY resources a `relation` field may target (mirrors
// `reserved.RELATION_RESOURCES` — a free-form string would be interpolated
// into a request path by the picker, so this is an allowlist, not a hint).
export const RELATION_RESOURCES = ["countries", "currencies", "regions"] as const;

const ALL_WIDGETS = Array.from(
  new Set(FIELD_SPEC_TYPES.flatMap((t) => WIDGETS_BY_TYPE[t])),
).sort();

/** Returns the widgets valid for `type` (empty array for an unknown type —
 *  never throws, since a stale/partial in-progress selection must not crash
 *  the Studio). Mirrors `WIDGETS_BY_TYPE` (types.py). */
export function widgetsFor(type: string): string[] {
  return WIDGETS_BY_TYPE[type as FieldSpecType] ?? [];
}

// English-fallback options (mirrors SITE_TYPES/PARTY_TYPES convention) — the
// raw constant a pure test can assert on; `buildFieldDefFields` overlays the
// localized label at the point of use. Studio-offered set only (see
// `STUDIO_OFFERED_TYPES` above) — `buildFieldDefFields` re-admits `seedType`
// for editing a pre-existing money/multiselect definition.
export const TYPE_OPTIONS: { value: FieldSpecType; label: string }[] =
  STUDIO_OFFERED_TYPES.map((t) => ({ value: t, label: t }));

// --- Pure locale lookup (no React hook — this module is imported by a plain
// vitest test with no component tree, and `buildFieldDefFields` must work
// there). Reads directly from the same JSON messages next-intl serves, so the
// `fields.*` namespace stays the single source of truth (no string
// duplicated between this file and i18n/messages/*.json). Mirrors the
// "fallback to English, then to the raw key" spirit of `lib/schema/types.tr`. ---
type Messages = typeof enMessages;
const MESSAGES: Record<Locale, Messages> = { en: enMessages, fr: frMessages, es: esMessages };

function ft(locale: Locale, path: string): string {
  const pick = (m: Messages): string | undefined =>
    path.split(".").reduce<unknown>(
      (acc, k) => (acc && typeof acc === "object" ? (acc as Record<string, unknown>)[k] : undefined),
      m,
    ) as string | undefined;
  return pick(MESSAGES[locale] ?? MESSAGES.en) ?? pick(MESSAGES.en) ?? path;
}

const KEY_RE = /^[a-z][a-z0-9_]{0,59}$/;

/**
 * The field-definition create/edit form's OWN fields — a real `FieldDef[]`
 * consumed by the SAME `RecordForm` every other admin page uses (the socle
 * eats its own dog food, per the brief). `key` is `immutable: true`
 * unconditionally (RecordForm only actually locks it in `mode: "edit"` —
 * same convention as `SITE_FIELD_SPECS.code`); renaming a key would orphan
 * every value already stored under the old one.
 *
 * `seedType` (optional) narrows the `widget` choices to `widgetsFor(seedType)`
 * — pass the ROW's current `type` when opening an edit surface. Without it
 * (create, or after changing `type` mid-edit) the full cross-type widget
 * union is offered; the server is the final authority (a mismatched pair is
 * rejected with a 422 mapped onto the `widget` field) and leaving `widget`
 * blank always resolves to the type's canonical default.
 *
 * `relation_resource`/`relation_filter` and `options` are shown only when
 * `type` is coherent with them (`relation`, `select`/`multiselect`) — done
 * with RecordForm's OWN `visible_if` engine (`f.rules`), which reads the
 * form's live values, not a prop RecordForm doesn't expose. `indexed` is
 * hidden for a non-indexable type the same way.
 */
export function buildFieldDefFields(locale: Locale, seedType?: FieldSpecType): FieldDef[] {
  const t = (k: string) => ft(locale, `fields.f.${k}`);
  // `seedType` re-admitted even when it's outside `STUDIO_OFFERED_TYPES`: an
  // EXISTING field of an unsupported type (money/multiselect — created before
  // this fix, or via a direct API call) must stay editable. Without this, its
  // `type` <select> would render with no matching option and silently coerce
  // to whichever type happens to render first on save — corrupting the
  // definition, not just hiding a create-time choice.
  const offeredTypes = seedType && !STUDIO_OFFERED_TYPES.includes(seedType)
    ? [...STUDIO_OFFERED_TYPES, seedType] : STUDIO_OFFERED_TYPES;
  const typeOptions = offeredTypes.map((v) => ({ value: v, label: ft(locale, `fields.type.${v}`) }));
  const widgetChoices = seedType ? widgetsFor(seedType) : ALL_WIDGETS;

  return [
    { name: "key", label: t("key"), required: true, immutable: true, hint: t("key_hint"),
      zod: z.string().trim().min(1, `${t("key")} is required`).regex(KEY_RE, t("key_hint")) },
    { name: "type", label: t("type"), type: "select", required: true, selectOptions: typeOptions },
    { name: "widget", label: t("widget"), type: "select", hint: t("widget_hint"),
      selectOptions: [{ value: "", label: "—" }, ...widgetChoices.map((w) => ({ value: w, label: w }))] },
    { name: "label_en", label: t("label_en"), required: true, zod: requiredText(t("label_en")) },
    { name: "label_fr", label: t("label_fr"), required: true, zod: requiredText(t("label_fr")) },
    { name: "label_es", label: t("label_es"), required: true, zod: requiredText(t("label_es")) },
    { name: "hint_en", label: t("hint_en") },
    { name: "hint_fr", label: t("hint_fr") },
    { name: "hint_es", label: t("hint_es") },
    { name: "required", label: t("required"), type: "checkbox" },
    { name: "group", label: t("group"), hint: t("group_hint") },
    { name: "order", label: t("order"), type: "number" },
    { name: "col_span", label: t("col_span"), type: "select",
      selectOptions: [
        { value: "1", label: ft(locale, "fields.col_span_option.1") },
        { value: "2", label: ft(locale, "fields.col_span_option.2") },
      ] },
    { name: "indexed", label: t("indexed"), type: "checkbox", hint: t("indexed_hint"),
      rules: { visible_if: { field: "type", op: "in", value: INDEXABLE_TYPES } } },
    { name: "inherit_to_suborgs", label: t("inherit_to_suborgs"), type: "checkbox" },
    // `required: true` is safe (and load-bearing) even though `relation` is
    // one of 15 types: a hidden field (this one, whenever `type !== "relation"`)
    // is never validated regardless of `required` (RecordForm's `validate()`
    // skips it via `isVisibleDef`) — so this only actually enforces presence
    // once `visible_if` makes the field visible, matching the backend's own
    // `relation requires relation_resource` rule with a field-level error
    // instead of the server's whole-model 422 (which has no per-field `loc`).
    { name: "relation_resource", label: t("relation_resource"), type: "select", required: true,
      selectOptions: RELATION_RESOURCES.map((r) => ({ value: r, label: r })),
      rules: { visible_if: { field: "type", op: "eq", value: "relation" } } },
    { name: "relation_filter", label: t("relation_filter"), type: "json", hint: t("relation_filter_hint"),
      colSpan: 2,
      rules: { visible_if: { field: "type", op: "eq", value: "relation" } } },
    { name: "options", label: t("options"), type: "json", hint: t("options_hint"), colSpan: 2,
      rules: { visible_if: { field: "type", op: "in", value: ["select", "multiselect"] } } },
    { name: "rules", label: t("rules"), type: "json", hint: t("rules_hint"), colSpan: 2 },
    { name: "default", label: t("default"), type: "json", hint: t("default_hint"), colSpan: 2 },
  ];
}

/** Hook wrapper (Produces: `useFieldDefFields()`, per the brief) — resolves
 *  the caller's current locale and delegates to the pure builder above. */
export function useFieldDefFields(seedType?: FieldSpecType): FieldDef[] {
  const locale = useLocale() as Locale;
  return buildFieldDefFields(locale, seedType);
}

// --- Definition <-> RecordForm payload adapters -----------------------------
//
// `RecordForm`'s `type: "json"` control (`JsonField`) only accepts a JSON
// OBJECT — it explicitly rejects arrays and scalars (`lib/json-edit.ts:
// "Arrays and primitives are rejected because the target backend fields are
// dict"`). Two attributes of a field definition are NOT objects on the wire:
// `options` (`list[dict]`) and `default` (`Any` — routinely a string/number/
// bool/null). Wrapping them in a one-key envelope `{items: [...]}` /
// `{value: ...}` keeps them inside a real, valid `RecordForm` field (the same
// "shape adapter at the module boundary" pattern already used by
// `providers/fields.ts` `splitPayload`/`flattenProvider`) rather than
// reaching for something RecordForm does not offer. See the task report for
// why this is flagged as a contract gap worth closing in `JsonField` itself
// (accepting arrays directly) rather than always requiring this wrapper.

function wrapOptionsForJson(options: Definition["options"]): { items: Definition["options"] } {
  return { items: options ?? [] };
}
function unwrapOptionsFromJson(v: unknown): { value: string; label: I18nString }[] {
  const items = (v as { items?: unknown } | undefined)?.items;
  return Array.isArray(items) ? (items as { value: string; label: I18nString }[]) : [];
}
function wrapDefaultForJson(value: unknown): { value: unknown } {
  return { value: value ?? null };
}
function unwrapDefaultFromJson(v: unknown): unknown {
  return (v as { value?: unknown } | undefined)?.value ?? null;
}

/** `Definition` (API response row) -> flat `RecordForm` `initial`. */
export function flattenDefinition(row: Definition): Record<string, unknown> {
  return {
    key: row.key,
    type: row.type,
    widget: row.widget,
    label_en: row.label?.en ?? "",
    label_fr: row.label?.fr ?? "",
    label_es: row.label?.es ?? "",
    hint_en: row.hint?.en ?? "",
    hint_fr: row.hint?.fr ?? "",
    hint_es: row.hint?.es ?? "",
    required: row.required,
    group: row.group ?? "",
    order: row.order ?? 0,
    col_span: String(row.col_span ?? 1),
    indexed: row.indexed,
    inherit_to_suborgs: row.inherit_to_suborgs ?? false,
    relation_resource: row.relation_resource ?? "",
    relation_filter: row.relation_filter ?? {},
    options: wrapOptionsForJson(row.options),
    rules: row.rules ?? {},
    default: wrapDefaultForJson(row.default),
  };
}

/** Flat `RecordForm` payload -> the `DefinitionIn` request body. */
export function buildDefinitionPayload(
  payload: Record<string, unknown>, target: Target,
): DefinitionIn {
  const str = (v: unknown) => (v == null ? "" : String(v));
  return {
    key: str(payload.key),
    type: str(payload.type) as FieldSpecType,
    widget: str(payload.widget),
    label: { en: str(payload.label_en), fr: str(payload.label_fr), es: str(payload.label_es) },
    hint: { en: str(payload.hint_en), fr: str(payload.hint_fr), es: str(payload.hint_es) },
    required: payload.required === true,
    default: unwrapDefaultFromJson(payload.default),
    rules: (payload.rules as Record<string, unknown>) ?? {},
    options: unwrapOptionsFromJson(payload.options),
    relation_resource: str(payload.relation_resource),
    relation_filter: (payload.relation_filter as Record<string, string>) ?? {},
    group: str(payload.group),
    order: payload.order == null || payload.order === "" ? 0 : Number(payload.order),
    col_span: payload.col_span ? Number(payload.col_span) : 1,
    indexed: payload.indexed === true,
    target,
    inherit_to_suborgs: payload.inherit_to_suborgs === true,
  };
}

/** The not-sortable-unless-ready rule (spec/brief): a field whose index is
 *  not `ready` is NOT offered for sorting anywhere, no matter how `indexed`
 *  reads — never silently slow. Pure so both the Studio's badge and any
 *  future business-form sort-key whitelist can share one definition. */
export function isSortable(row: { indexed: boolean; index_state: IndexState }): boolean {
  return row.indexed && row.index_state === "ready";
}

/** The entity GET response nests custom-field VALUES under `custom_fields`
 *  (same shape `splitCustomPayload` un-does on the way out) — but a merged
 *  custom `FieldDef`'s `name` is the bare key, and RecordForm's own
 *  `initial[f.name]` lookup is flat. Without this, an edit surface would seed
 *  every custom control BLANK even though the record has a value. Hoists
 *  `custom_fields` onto the top level for the `initial` prop only — mirrors
 *  `providers/fields.ts:flattenProvider`'s identical `config` hoist. Base
 *  fields are untouched (already flat on `row`). */
export function flattenCustomInitial(row: Record<string, unknown>): Record<string, unknown> {
  const custom = row.custom_fields;
  return custom && typeof custom === "object" && !Array.isArray(custom)
    ? { ...row, ...(custom as Record<string, unknown>) }
    : row;
}

/** Splits a flat `RecordForm` payload into the entity's own (declared) base
 *  columns and everything else — the custom-field values. The three
 *  extensible entities (organization, org_unit, site — NOT party, see
 *  `TARGETS`'s docstring) store custom values NESTED under a `custom_fields`
 *  dict (`app/modules/{organization,location}/schemas.py`), never as
 *  flat top-level columns; pydantic silently DROPS an undeclared top-level
 *  field (no `extra="forbid"`), so submitting the merged, flat RecordForm
 *  payload as-is would silently lose every custom value. This is the
 *  adapter that prevents that silent failure. */
export function splitCustomPayload(
  payload: Record<string, unknown>, baseKeys: Iterable<string>,
): { base: Record<string, unknown>; customFields: Record<string, unknown> } {
  const baseSet = new Set(baseKeys);
  const base: Record<string, unknown> = {};
  const customFields: Record<string, unknown> = {};
  for (const [k, v] of Object.entries(payload)) {
    if (baseSet.has(k)) base[k] = v;
    else customFields[k] = v;
  }
  return { base, customFields };
}

/** Client-side sort over the (small, ≤50-per-target-capped) definitions list
 *  — `GET /admin/field-definitions/` has no `sort` param (unlike the keyset
 *  entity lists), so the Studio sorts locally rather than inventing a
 *  backend contract the API doesn't offer. */
export function sortDefinitions(rows: Definition[], sort: string): Definition[] {
  const desc = sort.startsWith("-");
  const key = desc ? sort.slice(1) : sort;
  const dir = desc ? -1 : 1;
  const val = (r: Definition): string | number => {
    switch (key) {
      case "type": return r.type;
      case "widget": return r.widget;
      case "group": return r.group ?? "";
      case "required": return r.required ? 1 : 0;
      case "indexed": return r.indexed ? 1 : 0;
      default: return r.key;
    }
  };
  return [...rows].sort((a, b) => {
    const va = val(a);
    const vb = val(b);
    if (va < vb) return -1 * dir;
    if (va > vb) return 1 * dir;
    return 0;
  });
}

/** Client-side search filter (same "small, capped list" rationale as
 *  `sortDefinitions`) — matches the key or the localized label. */
export function filterDefinitions(rows: Definition[], q: string, locale: Locale): Definition[] {
  const needle = q.trim().toLowerCase();
  if (!needle) return rows;
  return rows.filter((r) =>
    r.key.toLowerCase().includes(needle) || tr(r.label, locale).toLowerCase().includes(needle));
}

/**
 * Fix wave 1 (Task 15, Important #3): whether the live, submittable
 * `CreateSurface` may render. `?new=1&sel=<anything>` makes the page's
 * `surfaceOpen` true via the `sel` disjunct regardless of `canManage` — the
 * dispatch then branched on `isNew` alone, so a caller with no `fields.manage`
 * could still get `CreateSurface` on screen (the backend still rejects the
 * write, but the repo rule is that the UI hides the action too, exactly like
 * `location/page.tsx`'s `isNew ? (canCreate && <SiteCreateSurface .../>) : ...`
 * and `party/page.tsx`'s equivalent). Extracted as a pure predicate (rather
 * than inlining `isNew && canManage` at the call site) so the exact
 * regression scenario — `isNew` true AND `canManage` false — is pinned by a
 * test independent of any component render. */
export function canRenderCreateSurface(isNew: boolean, canManage: boolean): boolean {
  return isNew && canManage;
}
