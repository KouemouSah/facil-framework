import { useTranslations } from "next-intl";
import { codeField, requiredText } from "@/lib/form-schemas";
import type { FieldDef } from "@/components/ui/record-form";

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
  { name: "timezone", placeholder: "UTC" },
  { name: "address_id", type: "address" },
  { name: "notes", type: "textarea", colSpan: 2 },
  { name: "operating_hours", type: "json" },
  { name: "metadata", type: "json" },
];

const HINTED = new Set(["code", "operating_hours", "metadata"]);

export function useSiteFields(): FieldDef[] {
  const t = useTranslations("sites.f");
  return SITE_FIELD_SPECS.map((s) => ({
    ...s,
    label: t(s.name),
    ...(HINTED.has(s.name) ? { hint: t(`${s.name}_hint`) } : {}),
    ...(s.name === "name" ? { zod: requiredText(t("name")) } : {}),
    ...(s.name === "site_type"
      ? { selectOptions: SITE_TYPES.map((o) => ({ value: o.value, label: t(`type.${o.value}`) })) }
      : {}),
  }));
}
