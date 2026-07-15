import { useLocale, useTranslations } from "next-intl";
import { useQuery } from "@tanstack/react-query";
import { codeField, requiredText } from "@/lib/form-schemas";
import type { FieldDef } from "@/components/ui/record-form";
import { getSchema } from "@/lib/schema/api";
import { fieldSpecToFieldDef } from "@/lib/schema/to-field-def";
import type { Locale } from "@/lib/schema/types";

// Canonical site-type values; option labels are localized in `useSiteFields`
// (`sites.f.type.<value>`). The English `label` here is a non-rendered fallback.
export const SITE_TYPES = [
  { value: "branch", label: "Branch" },
  { value: "headquarters", label: "Headquarters" },
  { value: "warehouse", label: "Warehouse" },
  { value: "office", label: "Office" },
  { value: "point_of_sale", label: "Point of sale" },
];

/**
 * Canonical Site fields (ERP-grade F.3c), shared by create + edit (§11bis DRY).
 * Geo lives on a reusable Address (`address_id` via AddressField); the old flat
 * address/city/country inputs are gone. `org_unit_id` / `parent_site_id` stay
 * API-only until their pickers land.
 *
 * Pure testable spec + a `useSiteFields` hook that localizes labels/hints/type
 * options + required-error (i18n mandate, P1.4) — mirrors `useOrgFields`. Keys
 * live under `sites.f`.
 */
export const SITE_FIELD_SPECS: Omit<FieldDef, "label" | "hint">[] = [
  { name: "code", required: true, immutable: true, zod: codeField },
  { name: "name", required: true },
  { name: "site_type", type: "select", required: true },
  { name: "is_primary", type: "checkbox" },
  { name: "phone" },
  { name: "email" },
  { name: "timezone", type: "timezone" },
  { name: "address_id", type: "address" },
  { name: "notes", type: "textarea", colSpan: 2 },
  // `widget: "weekly_hours"` (Task 15 — the Studio): the bespoke
  // `WeeklyHoursField` control instead of a raw JSON textarea for exactly the
  // shape this field motivated (spec §12: `{"mon": ["09:00-17:00"], ...}`).
  // Setting `widget` here does not change the wire shape or backend
  // validation (this column is plain JSONB, not a `FieldSpec`-checked
  // target) — RecordForm dispatches on it purely to pick the control.
  { name: "operating_hours", type: "json", widget: "weekly_hours" },
  { name: "metadata", type: "json" },
];

const HINTED = new Set(["code", "operating_hours", "metadata"]);

function useSiteCustomFieldsSchema(organizationId?: string) {
  return useQuery({
    queryKey: ["schema", "site.custom_fields", organizationId],
    queryFn: () => getSchema("site.custom_fields", organizationId),
    enabled: Boolean(organizationId),
  });
}

/**
 * IMPORTANT-4 fix (final fix wave): see `organization/fields.ts:
 * useOrgFieldsSchemaError`'s docstring — identical fix, identical reasoning.
 * Same react-query cache entry as `useSiteFields` below (same `queryKey`), no
 * extra network request.
 */
export function useSiteFieldsSchemaError(organizationId?: string): boolean {
  return useSiteCustomFieldsSchema(organizationId).isError;
}

/**
 * `organizationId` (Task 15) merges in this org's `site.custom_fields`
 * definitions, resolved server-side (`GET /api/v1/schema/site.custom_fields`)
 * — the Studio's screen B. Omitted (or before an org is chosen) => base
 * fields only, exactly today's behaviour; every existing call site keeps
 * working unchanged.
 */
export function useSiteFields(organizationId?: string): FieldDef[] {
  const t = useTranslations("sites.f");
  const locale = useLocale() as Locale;
  const schema = useSiteCustomFieldsSchema(organizationId);
  const custom = (schema.data?.fields ?? []).map((s) => fieldSpecToFieldDef(s, locale));

  const base = SITE_FIELD_SPECS.map((s) => ({
    ...s,
    label: t(s.name),
    ...(HINTED.has(s.name) ? { hint: t(`${s.name}_hint`) } : {}),
    ...(s.name === "name" ? { zod: requiredText(t("name")) } : {}),
    ...(s.name === "site_type"
      ? { selectOptions: SITE_TYPES.map((o) => ({ value: o.value, label: t(`type.${o.value}`) })) }
      : {}),
  }));
  return [...base, ...custom];
}

/** The declared base column names — everything else in a `useSiteFields()`
 *  payload is a custom-field key and must be nested under `custom_fields`
 *  before it reaches the API (see `modules/fields/fields.ts:splitCustomPayload`). */
export const SITE_BASE_KEYS = SITE_FIELD_SPECS.map((s) => s.name);
