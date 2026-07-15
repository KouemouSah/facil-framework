/** Exact mirror of app/core/schema/spec.py:FieldSpec. The backend is the single
 *  source of truth; this file must never drift from it. */

export type FieldSpecType =
  | "string" | "text" | "richtext"
  | "number" | "decimal" | "money"
  | "boolean"
  | "date" | "datetime" | "time"
  | "select" | "multiselect"
  | "relation"
  | "file"
  | "json";

export type Locale = "en" | "fr" | "es";
export type I18nString = Partial<Record<Locale, string>>;

export interface Condition {
  field: string;
  op: "eq" | "ne" | "in";
  value: unknown;
}

export interface FieldRules {
  min?: number | string;   // numeric OR date ISO/token ("today"/"now")
  max?: number | string;
  min_length?: number;
  max_length?: number;
  pattern?: string;
  precision?: number;      // decimal: max decimal places (now enforced)
  step?: number;           // number/decimal: multiple-of
  min_items?: number;      // multiselect
  max_items?: number;      // multiselect
  must_be_true?: boolean;  // boolean
  allowed_extensions?: string[]; // file
  visible_if?: Condition;
  required_if?: Condition;
}

export interface FieldSpec {
  key: string;
  type: FieldSpecType;
  widget: string;
  label: I18nString;
  hint: I18nString;
  required: boolean;
  default: unknown;
  rules: FieldRules;
  options: { value: string; label: I18nString }[];
  relation_resource: string;
  relation_filter: Record<string, string>;
  group: string;
  order: number;
  col_span: number;
  indexed: boolean;
  // MINORS fix (final fix wave): `as_spec()` (models/field_definition.py)
  // has always carried this on the wire — omitting it here contradicted this
  // file's own "exact mirror" claim above and left every caller unable to
  // type `spec.index_state` (e.g. `sortable_keys`-equivalent client logic)
  // without an `as unknown as` cast.
  index_state: "none" | "pending" | "ready" | "failed";
}

/** Pick a localised string, falling back to English then to the raw key. */
export function tr(s: I18nString, locale: Locale): string {
  return s[locale] || s.en || "";
}
