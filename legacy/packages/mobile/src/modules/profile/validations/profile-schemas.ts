/**
 * Profile Zod Validation Schemas
 *
 * Aligned with backend models:
 * - packages/backend/app/modules/users/models/user.py (UserUpdate)
 * - packages/backend/app/modules/users/api/user_routes.py (change-password)
 */

import { z } from 'zod';
import { phoneGESchema, passwordStrengthSchema } from '@modules/auth/validations';

// ---------------------------------------------------------------------------
// Profile Update Schema
// ---------------------------------------------------------------------------

/** PUT /users/profile — UserUpdate model */
export const profileUpdateSchema = z.object({
  first_name: z
    .string()
    .min(2, 'profile.firstNameMin')
    .max(50, 'profile.firstNameMax'),
  last_name: z
    .string()
    .min(2, 'profile.lastNameMin')
    .max(50, 'profile.lastNameMax'),
  phone_number: phoneGESchema.optional().or(z.literal('')),
  address: z.string().max(200, 'profile.addressMax').optional().or(z.literal('')),
  city: z.string().max(100, 'profile.cityMax').optional().or(z.literal('')),
  preferred_language: z.enum(['es', 'fr', 'en']).optional(),
});

// ---------------------------------------------------------------------------
// Password Change Schema (via /users/profile/change-password)
// ---------------------------------------------------------------------------

/** POST /users/profile/change-password */
export const profilePasswordChangeSchema = z
  .object({
    old_password: z.string().min(1, 'profile.oldPasswordRequired'),
    new_password: passwordStrengthSchema,
    confirm_password: z.string().min(1, 'auth.confirmPasswordRequired'),
  })
  .refine((data) => data.new_password !== data.old_password, {
    message: 'profile.passwordSameAsOld',
    path: ['new_password'],
  })
  .refine((data) => data.new_password === data.confirm_password, {
    message: 'auth.passwordMismatch',
    path: ['confirm_password'],
  });

// ---------------------------------------------------------------------------
// Inferred Types
// ---------------------------------------------------------------------------

export type ProfileUpdateInput = z.infer<typeof profileUpdateSchema>;
export type ProfilePasswordChangeInput = z.infer<typeof profilePasswordChangeSchema>;
