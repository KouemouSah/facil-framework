/**
 * Auth Zod Validation Schemas
 *
 * Aligned with backend Pydantic models:
 * - packages/backend/app/modules/auth/api/auth_routes.py (RegisterRequest, LoginRequest, etc.)
 * - packages/backend/app/modules/auth/models/auth_models.py
 *
 * IMPORTANT: Constraints MUST match backend exactly to prevent
 * client-side validation passing but server-side rejecting.
 */

import { z } from 'zod';

// ---------------------------------------------------------------------------
// Shared Validators
// ---------------------------------------------------------------------------

/**
 * Password strength rules matching backend validate_password_strength.
 * - Min 8 chars, max 100
 * - At least 1 uppercase letter
 * - At least 1 lowercase letter
 * - At least 1 digit
 * - At least 1 special character
 */
export const passwordStrengthSchema = z
  .string()
  .min(8, 'auth.passwordRequirements.minLength')
  .max(100, 'auth.passwordTooLong')
  .regex(/[A-Z]/, 'auth.passwordRequirements.uppercase')
  .regex(/[a-z]/, 'auth.passwordRequirements.lowercase')
  .regex(/[0-9]/, 'auth.passwordRequirements.digit')
  .regex(/[^A-Za-z0-9]/, 'auth.passwordRequirements.special');

/**
 * GE phone number validation.
 * Backend pattern: ^(222|555|551|333)\d{6}$
 * Operators: GETESA (222), Orange (555/551), Muni (333)
 */
export const phoneGESchema = z
  .string()
  .regex(
    /^(222|555|551|333)\d{6}$/,
    'auth.invalidPhoneGE'
  );

/** 6-digit verification code */
const verificationCodeSchema = z
  .string()
  .regex(/^\d{6}$/, 'auth.invalidVerificationCode');

/** Email with i18n error key */
const emailSchema = z
  .string()
  .min(1, 'auth.emailRequired')
  .email('auth.invalidEmail');

// ---------------------------------------------------------------------------
// Auth Schemas
// ---------------------------------------------------------------------------

/** POST /auth/login — LoginRequest */
export const loginSchema = z.object({
  email: emailSchema,
  password: z.string().min(1, 'auth.passwordRequired'),
  remember_me: z.boolean().optional(),
});

/** POST /auth/register — RegisterRequest */
export const registerSchema = z
  .object({
    email: emailSchema,
    verification_code: verificationCodeSchema,
    password: passwordStrengthSchema,
    confirm_password: z.string().min(1, 'auth.confirmPasswordRequired'),
    first_name: z
      .string()
      .min(2, 'auth.firstNameMin')
      .max(50, 'auth.firstNameMax'),
    last_name: z
      .string()
      .min(2, 'auth.lastNameMin')
      .max(50, 'auth.lastNameMax'),
    phone: phoneGESchema,
    role: z.enum(['citizen', 'business']).default('citizen'),
    address: z.string().max(200).optional(),
    city: z.string().max(100).optional(),
    preferred_language: z.enum(['es', 'fr', 'en']).optional(),
  })
  .refine((data) => data.password === data.confirm_password, {
    message: 'auth.passwordMismatch',
    path: ['confirm_password'],
  });

/** POST /auth/request-verification-code */
export const verificationCodeRequestSchema = z.object({
  email: emailSchema,
});

/** POST /auth/password/reset/request */
export const passwordResetRequestSchema = z.object({
  email: emailSchema,
});

/** POST /auth/password/reset/confirm */
export const passwordResetConfirmSchema = z
  .object({
    token: z.string().min(32).max(128),
    new_password: passwordStrengthSchema,
    confirm_password: z.string().min(1, 'auth.confirmPasswordRequired'),
  })
  .refine((data) => data.new_password === data.confirm_password, {
    message: 'auth.passwordMismatch',
    path: ['confirm_password'],
  });

/** POST /users/profile/change-password — aligned with web frontend */
export const passwordChangeSchema = z
  .object({
    old_password: z.string().min(1, 'auth.currentPasswordRequired'),
    new_password: passwordStrengthSchema,
    confirm_password: z.string().min(1, 'auth.confirmPasswordRequired'),
  })
  .refine((data) => data.new_password !== data.old_password, {
    message: 'auth.passwordMustBeDifferent',
    path: ['new_password'],
  })
  .refine((data) => data.new_password === data.confirm_password, {
    message: 'auth.passwordMismatch',
    path: ['confirm_password'],
  });

/** POST /auth/login/2fa-verify — 6-digit TOTP code or XXXX-XXXX backup code */
export const twoFactorVerifySchema = z.object({
  code: z
    .string()
    .min(1, 'auth.codeRequired')
    .refine(
      (val) => /^\d{6}$/.test(val) || /^\d{4}-\d{4}$/.test(val),
      'auth.invalidTwoFactorCode'
    ),
});

/** POST /auth/2fa/disable */
export const twoFactorDisableSchema = z.object({
  password: z.string().min(1, 'auth.passwordRequired'),
});

// ---------------------------------------------------------------------------
// Password Strength Utilities
// ---------------------------------------------------------------------------

export interface PasswordStrengthResult {
  score: number; // 0-5 (each criterion = 1 point)
  criteria: {
    minLength: boolean;
    hasUppercase: boolean;
    hasLowercase: boolean;
    hasDigit: boolean;
    hasSpecial: boolean;
  };
  errors: string[];
}

/**
 * Compute password strength score and unfulfilled criteria.
 * Returns i18n keys for error messages.
 */
export function getPasswordStrength(password: string): PasswordStrengthResult {
  const criteria = {
    minLength: password.length >= 8,
    hasUppercase: /[A-Z]/.test(password),
    hasLowercase: /[a-z]/.test(password),
    hasDigit: /[0-9]/.test(password),
    hasSpecial: /[^A-Za-z0-9]/.test(password),
  };

  const errors: string[] = [];
  if (!criteria.minLength) errors.push('auth.passwordRequirements.minLength');
  if (!criteria.hasUppercase) errors.push('auth.passwordRequirements.uppercase');
  if (!criteria.hasLowercase) errors.push('auth.passwordRequirements.lowercase');
  if (!criteria.hasDigit) errors.push('auth.passwordRequirements.digit');
  if (!criteria.hasSpecial) errors.push('auth.passwordRequirements.special');

  const score = Object.values(criteria).filter(Boolean).length;

  return { score, criteria, errors };
}

/**
 * Check if password meets all strength requirements.
 */
export function isPasswordStrong(password: string): boolean {
  return getPasswordStrength(password).score === 5;
}

// ---------------------------------------------------------------------------
// Inferred Types
// ---------------------------------------------------------------------------

export type LoginInput = z.infer<typeof loginSchema>;
export type RegisterInput = z.infer<typeof registerSchema>;
export type VerificationCodeRequestInput = z.infer<typeof verificationCodeRequestSchema>;
export type PasswordResetRequestInput = z.infer<typeof passwordResetRequestSchema>;
export type PasswordResetConfirmInput = z.infer<typeof passwordResetConfirmSchema>;
export type PasswordChangeInput = z.infer<typeof passwordChangeSchema>;
export type TwoFactorVerifyInput = z.infer<typeof twoFactorVerifySchema>;
export type TwoFactorDisableInput = z.infer<typeof twoFactorDisableSchema>;
