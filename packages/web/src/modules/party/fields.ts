import { requiredText } from "@/lib/form-schemas";
import type { FieldDef } from "@/components/ui/record-form";
import { PARTY_TYPES } from "./api";

/**
 * Party fields (directory), shared by create + edit (§11bis DRY). `party_type` is
 * immutable in edit (PartyUpdate can't change it). Mirrors the backend `PartyIn` /
 * `PartyUpdate` schemas. `email` is a plain string on the backend (no format
 * validation) but we render an email control for the keyboard/UX.
 */
export const PARTY_FIELDS: FieldDef[] = [
  { name: "party_type", label: "Type", type: "select", required: true, immutable: true,
    selectOptions: PARTY_TYPES.map((t) => ({ value: t, label: t })) },
  { name: "name", label: "Name", required: true, zod: requiredText("Name") },
  { name: "tax_id", label: "Tax ID" },
  { name: "registration_number", label: "Registration number" },
  { name: "email", label: "Email", type: "email" },
  { name: "phone", label: "Phone" },
  { name: "website", label: "Website" },
  { name: "custom_fields", label: "Custom fields (JSON)", type: "json" },
  { name: "is_active", label: "Active", type: "checkbox" },
];
