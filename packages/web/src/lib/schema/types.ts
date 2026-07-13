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
  min?: number;
  max?: number;
  min_length?: number;
  max_length?: number;
  pattern?: string;
  precision?: number;
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
}

/** Pick a localised string, falling back to English then to the raw key. */
export function tr(s: I18nString, locale: Locale): string {
  return s[locale] || s.en || "";
}
