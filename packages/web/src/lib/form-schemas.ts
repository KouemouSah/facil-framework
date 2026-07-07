import { z } from "zod";

/**
 * Shared zod field builders for create/edit forms. These MIRROR the backend
 * Pydantic constraints (app.modules.*.schemas, app.api.admin_accounts) so the
 * client rejects bad input inline before the round-trip — the backend remains
 * the source of truth (the UI reflects, the server decides).
 */

// Backend `_CODE` pattern: ^[A-Za-z0-9][A-Za-z0-9_.-]{0,49}$
export const codeField = z
  .string()
  .trim()
  .min(1, "Code is required")
  .max(50, "Max 50 characters")
  .regex(/^[A-Za-z0-9][A-Za-z0-9_.-]{0,49}$/,
    "Letters, digits, . _ - only (must start with a letter or digit)");

export function requiredText(label: string, max = 255) {
  return z.string().trim().min(1, `${label} is required`).max(max, `Max ${max} characters`);
}

// Optional free text → empty string normalised so it can be sent as null.
export function optionalText(max = 255) {
  return z.string().trim().max(max, `Max ${max} characters`).optional().or(z.literal(""));
}

// Backend account email validator (regex, no external dep): basic shape check.
export const emailField = z
  .string()
  .trim()
  .min(1, "Email is required")
  .regex(/^[^@\s]+@[^@\s]+\.[^@\s]+$/, "Enter a valid email address");

// Mirrors app.auth.password.check_strength (SEC-009): >=12 chars + upper + lower
// + digit. The server also rejects common bases (a blocklist) — left to the
// backend (422 → field) rather than duplicating a drifting list on the client.
export const passwordField = z
  .string()
  .min(12, "At least 12 characters")
  .regex(/[a-z]/, "Needs a lowercase letter")
  .regex(/[A-Z]/, "Needs an uppercase letter")
  .regex(/[0-9]/, "Needs a digit");

// Exactly N characters (ISO referential codes: country=2/3, currency=3).
export function exactLen(n: number, label = "Value") {
  return z.string().trim().length(n, `${label} must be exactly ${n} characters`);
}

// Numeric input bounded to mirror a backend field. Values arrive as strings from
// the form, so coerce; `int` forbids fractions, min/max mirror the pydantic bounds.
export function numericField(opts: { min?: number; max?: number; int?: boolean }) {
  let s = z.coerce.number({ invalid_type_error: "Must be a number" });
  if (opts.int) s = s.int("Must be a whole number");
  if (opts.min !== undefined) s = s.min(opts.min, `Min ${opts.min}`);
  if (opts.max !== undefined) s = s.max(opts.max, `Max ${opts.max}`);
  return s;
}

// #RRGGBB — mirrors the branding color fields (backend max_length 7).
export const hexColor = z
  .string()
  .trim()
  .regex(/^#[0-9a-fA-F]{6}$/, "Enter a 6-digit hex color like #2563eb");
