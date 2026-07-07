import { codeField, requiredText } from "@/lib/form-schemas";
import type { FieldDef } from "@/components/ui/record-form";

/**
 * Canonical Company fields (ERP-grade F.3), shared by create + edit (§11bis DRY).
 *
 * The legal identity (tax id / registration / postal address) lives on the linked
 * Party + Address — the org keeps its code/branding/scope plus FK links to that
 * master data. The old flat free-text geo/tax/currency inputs are intentionally
 * gone. Pilot-1 change (audit 4): the logo is a `FileUpload` (`type: "image"`,
 * stored as a same-origin asset URL in `logo_url`) — never a paste-a-URL text input.
 */
export const ORG_FIELDS: FieldDef[] = [
  { name: "code", label: "Code", required: true, immutable: true, zod: codeField,
    hint: "Immutable identifier." },
  { name: "legal_name", label: "Legal name", required: true, zod: requiredText("Legal name") },
  { name: "display_name", label: "Display name" },
  { name: "party_id", label: "Legal identity (directory)", type: "party",
    hint: "Party holding tax id / registration / contacts." },
  { name: "parent_id", label: "Consolidation parent", type: "org",
    hint: "Owning company for multi-company groups." },
  { name: "currency_id", label: "Currency", type: "ref", refResource: "currencies" },
  { name: "email", label: "Email" },
  { name: "phone", label: "Phone" },
  { name: "website", label: "Website" },
  { name: "logo_url", label: "Logo", type: "image", colSpan: 2 },
  { name: "default_locale", label: "Default locale", placeholder: "en" },
  { name: "timezone", label: "Timezone", placeholder: "UTC" },
  { name: "hq_address_id", label: "Head office address", type: "address" },
  { name: "document_identity", label: "Document identity (JSON)", type: "json",
    hint: "Identifiers shown on generated documents (registry, VAT…)." },
  { name: "settings", label: "Settings (JSON)", type: "json",
    hint: "Free-form organization settings." },
];
