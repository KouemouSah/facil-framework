import { useTranslations } from "next-intl";
import { requiredText } from "@/lib/form-schemas";
import type { FieldDef } from "@/components/ui/record-form";
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
  { name: "custom_fields", type: "json" },
  { name: "is_active", type: "checkbox" },
];

export function usePartyFields(): FieldDef[] {
  const t = useTranslations("directory.f");
  return PARTY_FIELD_SPECS.map((s) => ({
    ...s,
    label: t(s.name),
    ...(s.name === "name" ? { zod: requiredText(t("name")) } : {}),
  }));
}
