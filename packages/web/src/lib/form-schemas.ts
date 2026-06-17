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

// Mirrors app.auth.password.check_strength: >=8 chars + upper + lower + digit.
export const passwordField = z
  .string()
  .min(8, "At least 8 characters")
  .regex(/[a-z]/, "Needs a lowercase letter")
  .regex(/[A-Z]/, "Needs an uppercase letter")
  .regex(/[0-9]/, "Needs a digit");
