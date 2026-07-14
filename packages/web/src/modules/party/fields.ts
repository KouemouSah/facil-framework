import { useLocale, useTranslations } from "next-intl";
import { useQuery } from "@tanstack/react-query";
import { requiredText } from "@/lib/form-schemas";
import type { FieldDef } from "@/components/ui/record-form";
import { getSchema } from "@/lib/schema/api";
import { fieldSpecToFieldDef } from "@/lib/schema/to-field-def";
import type { Locale } from "@/lib/schema/types";
import { useFirstOrg } from "@/lib/use-organizations";
import { PARTY_TYPES } from "./api";

/**
 * Party fields (directory), shared by create + edit (§11bis DRY). `party_type` is
 * immutable in edit (PartyUpdate can't change it). Mirrors the backend `PartyIn` /
 * `PartyUpdate` schemas. `email` is a plain string on the backend (no format
 * validation) but we render an email control for the keyboard/UX.
 *
 * The structural specs (names/types/flags) are a pure, testable constant; the
 * hook decorates them with LOCALIZED labels + required-error (i18n mandate) —
 * mirrors org-unit's `useUnitFields`. The `f.<name>` i18n keys live under
 * `directory.f`, so every spec name maps to a label key.
 */
export const PARTY_FIELD_SPECS: Omit<FieldDef, "label">[] = [
  { name: "party_type", type: "select", required: true, immutable: true,
    selectOptions: PARTY_TYPES.map((ty) => ({ value: ty, label: ty })) },
  { name: "name", required: true },
  { name: "tax_id" },
  { name: "registration_number" },
  { name: "email", type: "email" },
  { name: "phone" },
  { name: "website" },
  { name: "is_active", type: "checkbox" },
];

/** The declared base column names — see `SITE_BASE_KEYS`'s twin docstring
 *  (`modules/location/fields.ts`) for why the split at submit time matters. */
export const PARTY_BASE_KEYS = PARTY_FIELD_SPECS.map((s) => s.name);

/**
 * The org whose `party.custom_fields` definitions apply (Task 15). `Party` is
 * GLOBAL directory data with no `organization_id` of its own (see the
 * backend's `_party_specs` docstring, `app/modules/party/api/__init__.py`) —
 * a `FieldDefinition` is always org-owned, so SOME organisation must be
 * named. The least-surprising default, and the one already used to gate
 * every other "no natural org on this entity" picker in this codebase
 * (`LocationsPage`'s site-org default), is the caller's first visible
 * organisation. `useFirstOrg` is already query-deduplicated (same
 * `["org","first"]` key), so calling it again at the party page's submit
 * site (for `definitions_org_id`) costs no extra request.
 */
export function usePartyCustomFieldsOrgId(): string {
  return useFirstOrg().id;
}

export function usePartyFields(): FieldDef[] {
  const t = useTranslations("directory.f");
  const locale = useLocale() as Locale;
  const organizationId = usePartyCustomFieldsOrgId();
  const schema = useQuery({
    queryKey: ["schema", "party.custom_fields", organizationId],
    queryFn: () => getSchema("party.custom_fields", organizationId),
    enabled: Boolean(organizationId),
  });
  const custom = (schema.data?.fields ?? []).map((s) => fieldSpecToFieldDef(s, locale));

  const base = PARTY_FIELD_SPECS.map((s) => ({
    ...s,
    label: t(s.name),
    ...(s.name === "name" ? { zod: requiredText(t("name")) } : {}),
  }));
  return [...base, ...custom];
}
