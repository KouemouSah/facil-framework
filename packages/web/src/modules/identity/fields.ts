import { useTranslations } from "next-intl";
import { z } from "zod";
import { emailField, passwordField } from "@/lib/form-schemas";
import type { FieldDef } from "@/components/ui/record-form";

// Edit allows clearing the email (AccountUpdate.email is optional); validate the
// format only when a value is present.
const optionalEmail = emailField.or(z.literal(""));

/**
 * Account fields (pilot 2), mirroring the backend `AccountIn` / `AccountUpdate`
 * schemas (admin_accounts.py). Create takes a temporary password (min 12, SEC-009);
 * edit never touches the password. Both share email/display_name/organization via
 * the shared `RecordForm` (§11bis, audit 12 — retires the ad-hoc account form).
 *
 * Pure testable specs + `useAccount{Create,Edit}Fields` hooks that localize labels/
 * hints/password-placeholder (i18n mandate, P1.4) — mirror `useOrgFields`. Keys
 * live under `agents.f`.
 */
export const ACCOUNT_CREATE_SPECS: Omit<FieldDef, "label" | "hint">[] = [
  { name: "email", type: "email", required: true, zod: emailField, placeholder: "agent@org.com" },
  { name: "password", type: "password", required: true, zod: passwordField },
  { name: "display_name", placeholder: "Jane Agent" },
  { name: "organization_id", type: "org" },
];

export const ACCOUNT_EDIT_SPECS: Omit<FieldDef, "label" | "hint">[] = [
  { name: "email", type: "email", zod: optionalEmail },
  { name: "display_name", placeholder: "Jane Agent" },
  { name: "organization_id", type: "org" },
];

function useDecorate(specs: Omit<FieldDef, "label" | "hint">[]): FieldDef[] {
  const t = useTranslations("agents.f");
  return specs.map((s) => ({
    ...s,
    label: t(s.name),
    ...(s.name === "password" ? { hint: t("password_hint"), placeholder: t("password_ph") } : {}),
  }));
}

export function useAccountCreateFields(): FieldDef[] {
  return useDecorate(ACCOUNT_CREATE_SPECS);
}

export function useAccountEditFields(): FieldDef[] {
  return useDecorate(ACCOUNT_EDIT_SPECS);
}
