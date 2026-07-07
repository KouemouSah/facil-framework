import { codeField, requiredText } from "@/lib/form-schemas";
import type { FieldDef } from "@/components/ui/record-form";

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
 */
export const SITE_FIELDS: FieldDef[] = [
  { name: "code", label: "Code", required: true, immutable: true, zod: codeField,
    hint: "Immutable identifier." },
  { name: "name", label: "Name", required: true, zod: requiredText("Name") },
  { name: "site_type", label: "Type", type: "select", required: true, selectOptions: SITE_TYPES },
  { name: "is_primary", label: "Primary site", type: "checkbox" },
  { name: "phone", label: "Phone" },
  { name: "email", label: "Email" },
  { name: "timezone", label: "Timezone", placeholder: "UTC" },
  { name: "address_id", label: "Address", type: "address" },
  { name: "notes", label: "Notes", type: "textarea", colSpan: 2 },
  { name: "operating_hours", label: "Operating hours (JSON)", type: "json",
    hint: 'e.g. {"mon": ["09:00-17:00"], "sat": []}' },
  { name: "metadata", label: "Metadata (JSON)", type: "json", hint: "Free-form site metadata." },
];
