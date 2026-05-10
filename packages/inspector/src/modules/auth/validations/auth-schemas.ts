/**
 * Auth Zod Validation Schemas - Facil Inspeccion
 *
 * Aligned with backend Pydantic models:
 * - packages/backend/app/modules/auth/api/auth_routes.py (LoginRequest)
 * - packages/backend/app/modules/auth/models/auth_models.py
 *
 * IMPORTANT: Constraints MUST match backend exactly to prevent
 * client-side validation passing but server-side rejecting.
 *
 * Inspector app only uses login + 2FA (no registration — agents are
 * created by admin). Schemas kept minimal to match actual usage.
 */

import { z } from 'zod';

// ---------------------------------------------------------------------------
// Auth Schemas
// ---------------------------------------------------------------------------

/** POST /auth/login — LoginRequest (email + password) */
export const loginSchema = z.object({
  email: z
    .string()
    .min(1, 'auth.emailRequired')
    .email('auth.invalidEmail'),
  password: z
    .string()
    .min(1, 'auth.passwordRequired'),
});

/** POST /auth/login/2fa-verify — 6-digit TOTP code */
export const twoFactorSchema = z.object({
  code: z
    .string()
    .min(1, 'auth.codeRequired')
    .regex(/^\d{6}$/, 'auth.invalidTwoFactorCode'),
});

// ---------------------------------------------------------------------------
// Inferred Types
// ---------------------------------------------------------------------------

export type LoginInput = z.infer<typeof loginSchema>;
export type TwoFactorInput = z.infer<typeof twoFactorSchema>;
