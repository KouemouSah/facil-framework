import { useLocale, useTranslations } from "next-intl";
import { useQuery } from "@tanstack/react-query";
import { codeField, requiredText } from "@/lib/form-schemas";
import { locales } from "@/i18n/config";
import type { FieldDef } from "@/components/ui/record-form";
import { getSchema } from "@/lib/schema/api";
import { fieldSpecToFieldDef } from "@/lib/schema/to-field-def";
import type { Locale } from "@/lib/schema/types";

/**
 * Canonical Company fields (ERP-grade F.3), shared by create + edit (§11bis DRY).
 *
 * The legal identity (tax id / registration / postal address) lives on the linked
 * Party + Address — the org keeps its code/branding/scope plus FK links to that
 * master data. The old flat free-text geo/tax/currency inputs are intentionally
 * gone. The logo is a `FileUpload` (`type: "image"`, stored as a same-origin asset
 * URL in `logo_url`) — never a paste-a-URL text input.
 *
 * The structural specs (names/types/flags) are a pure, testable constant; the
 * `useOrgFields` hook decorates them with LOCALIZED labels + hints + required-error
 * (i18n mandate, P1.4) — mirrors `usePartyFields`. The `f.<name>` (+ `<name>_hint`)
 * i18n keys live under `organizations.f`.
 */
export const ORG_FIELD_SPECS: Omit<FieldDef, "label" | "hint">[] = [
  { name: "code", required: true, immutable: true, zod: codeField },
  { name: "legal_name", required: true },
  { name: "display_name" },
  { name: "party_id", type: "party" },
  { name: "parent_id", type: "org" },
  { name: "currency_id", type: "ref", refResource: "currencies" },
  { name: "email" },
  { name: "phone" },
  { name: "website" },
  { name: "logo_url", type: "image", colSpan: 2 },
  { name: "default_locale", type: "select" },
  { name: "timezone", type: "timezone" },
  { name: "hq_address_id", type: "address" },
];

// Fields that carry an explanatory hint (localized as `<name>_hint`).
const HINTED = new Set(["code", "party_id", "parent_id"]);

/**
 * `organizationId` (Task 15) merges in `organization.custom_fields`
 * definitions scoped to THIS org, i.e. its OWN id — never available on
 * create (the row does not exist yet), so custom fields only ever appear
 * when editing. Every existing call site (create) keeps working unchanged.
 */
export function useOrgFields(organizationId?: string): FieldDef[] {
  const t = useTranslations("organizations.f");
  const locale = useLocale() as Locale;
  const schema = useQuery({
    queryKey: ["schema", "organization.custom_fields", organizationId],
    queryFn: () => getSchema("organization.custom_fields", organizationId),
    enabled: Boolean(organizationId),
  });
  const custom = (schema.data?.fields ?? []).map((s) => fieldSpecToFieldDef(s, locale));

  const base = ORG_FIELD_SPECS.map((s) => ({
    ...s,
    label: t(s.name),
    ...(HINTED.has(s.name) ? { hint: t(`${s.name}_hint`) } : {}),
    ...(s.name === "legal_name" ? { zod: requiredText(t("legal_name")) } : {}),
    ...(s.name === "default_locale"
      ? { selectOptions: locales.map((l) => ({ value: l, label: l })) }
      : {}),
  }));
  return [...base, ...custom];
}

/** The declared base column names — see `SITE_BASE_KEYS`'s twin docstring
 *  (`modules/location/fields.ts`) for why the split at submit time matters. */
export const ORG_BASE_KEYS = ORG_FIELD_SPECS.map((s) => s.name);
