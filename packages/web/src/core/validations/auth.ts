/**
 * Schémas de validation Zod pour l'authentification
 * Basé sur les contrats API backend
 */

import { z } from 'zod';

/**
 * Schéma de validation pour le login
 */
export const loginSchema = z.object({
  email: z.string().min(1, 'Email requis').email('Email invalide'),
  password: z.string().min(1, 'Mot de passe requis').min(6, 'Minimum 6 caractères'),
  remember_me: z.boolean().optional(),
});

/**
 * Schéma de validation pour l'inscription
 * Phone: Guinée Équatoriale format (222|555|551|333 + 6 chiffres = 9 total)
 * Role: citizen (défaut) ou business
 */
export const registerSchema = z.object({
  email: z.string().min(1, 'Email requis').email('Email invalide'),
  password: z
    .string()
    .min(8, 'Minimum 8 caractères')
    .regex(/[A-Z]/, 'Au moins 1 majuscule requise')
    .regex(/[a-z]/, 'Au moins 1 minuscule requise')
    .regex(/[0-9]/, 'Au moins 1 chiffre requis')
    .regex(/[^A-Za-z0-9]/, 'Au moins 1 caractère spécial requis'),
  first_name: z.string().min(2, 'Minimum 2 caractères').max(50, 'Maximum 50 caractères'),
  last_name: z.string().min(2, 'Minimum 2 caractères').max(50, 'Maximum 50 caractères'),
  phone: z
    .string()
    .regex(
      /^(222|555|551|333)\d{6}$/,
      'Le numéro doit commencer par 222, 555, 551 ou 333 et contenir 9 chiffres au total'
    )
    .length(9, 'Le numéro doit contenir exactement 9 chiffres'),
  role: z
    .enum(['citizen', 'business'], {
      errorMap: () => ({ message: 'Rôle invalide' }),
    })
    .default('citizen'),
  verification_code: z.string().min(6, 'Code de vérification requis'),
});

/**
 * Schéma pour demande de code de vérification
 */
export const verificationCodeRequestSchema = z.object({
  email: z.string().min(1, 'Email requis').email('Email invalide'),
});

/**
 * Schéma pour réinitialisation de mot de passe
 */
export const passwordResetSchema = z.object({
  email: z.string().min(1, 'Email requis').email('Email invalide'),
});

/**
 * Schéma pour confirmation de réinitialisation
 */
export const passwordResetConfirmSchema = z.object({
  token: z.string().min(1, 'Token requis'),
  new_password: z
    .string()
    .min(8, 'Minimum 8 caractères')
    .regex(/[A-Z]/, 'Au moins 1 majuscule requise')
    .regex(/[a-z]/, 'Au moins 1 minuscule requise')
    .regex(/[0-9]/, 'Au moins 1 chiffre requis')
    .regex(/[^A-Za-z0-9]/, 'Au moins 1 caractère spécial requis'),
});

/**
 * Schéma pour vérification 2FA
 */
export const twoFactorVerifySchema = z.object({
  temp_token: z.string().min(1, 'Token temporaire requis'),
  code: z.string().length(6, 'Le code doit contenir 6 chiffres'),
});

/**
 * Shared password strength check (matches Zod rules above)
 * Use for real-time validation in forms that don't use Zod (e.g., activation pages)
 */
export function isPasswordStrong(password: string): boolean {
  return (
    password.length >= 8 &&
    /[A-Z]/.test(password) &&
    /[a-z]/.test(password) &&
    /[0-9]/.test(password) &&
    /[^A-Za-z0-9]/.test(password)
  );
}

export type LoginInput = z.infer<typeof loginSchema>;
export type RegisterInput = z.infer<typeof registerSchema>;
export type VerificationCodeRequestInput = z.infer<typeof verificationCodeRequestSchema>;
export type PasswordResetInput = z.infer<typeof passwordResetSchema>;
export type PasswordResetConfirmInput = z.infer<typeof passwordResetConfirmSchema>;
export type TwoFactorVerifyInput = z.infer<typeof twoFactorVerifySchema>;
