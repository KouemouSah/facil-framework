import { useTranslations } from "next-intl";
import { codeField, requiredText } from "@/lib/form-schemas";
import type { FieldDef } from "@/components/ui/record-form";

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
  { name: "default_locale", placeholder: "en" },
  { name: "timezone", placeholder: "UTC" },
  { name: "hq_address_id", type: "address" },
  { name: "document_identity", type: "json" },
  { name: "settings", type: "json" },
];

// Fields that carry an explanatory hint (localized as `<name>_hint`).
const HINTED = new Set(["code", "party_id", "parent_id", "document_identity", "settings"]);

export function useOrgFields(): FieldDef[] {
  const t = useTranslations("organizations.f");
  return ORG_FIELD_SPECS.map((s) => ({
    ...s,
    label: t(s.name),
    ...(HINTED.has(s.name) ? { hint: t(`${s.name}_hint`) } : {}),
    ...(s.name === "legal_name" ? { zod: requiredText(t("legal_name")) } : {}),
  }));
}
