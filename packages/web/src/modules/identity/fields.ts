import { z } from "zod";
import { emailField, passwordField } from "@/lib/form-schemas";
import type { FieldDef } from "@/components/ui/record-form";

// Edit allows clearing the email (AccountUpdate.email is optional); validate the
// format only when a value is present.
const optionalEmail = emailField.or(z.literal(""));

const displayNameField: FieldDef = { name: "display_name", label: "Display name", placeholder: "Jane Agent" };
const orgField: FieldDef = { name: "organization_id", label: "Organization", type: "org" };

/**
 * Account fields (pilot 2), mirroring the backend `AccountIn` / `AccountUpdate`
 * schemas (admin_accounts.py). Create takes a temporary password (min 12, SEC-009);
 * edit never touches the password. Both share email/display_name/organization via
 * the shared `RecordForm` (§11bis, audit 12 — retires the ad-hoc account form).
 */
export const ACCOUNT_CREATE_FIELDS: FieldDef[] = [
  { name: "email", label: "Email", type: "email", required: true, zod: emailField,
    placeholder: "agent@org.com" },
  { name: "password", label: "Temporary password", type: "password", required: true,
    zod: passwordField, placeholder: "≥ 12 chars · upper/lower/digit",
    hint: "The agent must change it at first sign-in." },
  displayNameField,
  orgField,
];

export const ACCOUNT_EDIT_FIELDS: FieldDef[] = [
  { name: "email", label: "Email", type: "email", zod: optionalEmail },
  displayNameField,
  orgField,
];
