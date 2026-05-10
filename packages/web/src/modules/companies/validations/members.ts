/**
 * Validation schemas for company members
 * Zod schemas for form validation
 *
 * @module companies/validations
 * @author Claude Code
 * @date 2025-12-03
 */

import { z } from 'zod'

/**
 * Add member schema
 * For inviting existing users to company
 */
export const addMemberSchema = z.object({
  memberUserId: z.string().min(1, 'User ID is required').uuid('Invalid user ID'),
  role: z.enum(
    ['company_owner', 'company_admin', 'company_accountant', 'company_member'],
    {
      errorMap: () => ({ message: 'Invalid role selected' }),
    }
  ),
})

/**
 * Invite member schema (future feature)
 * For inviting users by email
 */
export const inviteMemberSchema = z.object({
  email: z.string().min(1, 'Email required').email('Invalid email'),
  role: z.enum(
    ['company_owner', 'company_admin', 'company_accountant', 'company_member'],
    {
      errorMap: () => ({ message: 'Invalid role selected' }),
    }
  ),
  message: z.string().max(500, 'Message too long (max 500 characters)').optional(),
})

/**
 * Update member role schema
 */
export const updateMemberRoleSchema = z.object({
  role: z.enum(
    ['company_owner', 'company_admin', 'company_accountant', 'company_member'],
    {
      errorMap: () => ({ message: 'Invalid role selected' }),
    }
  ),
})

// Export types
export type AddMemberInput = z.infer<typeof addMemberSchema>
export type InviteMemberInput = z.infer<typeof inviteMemberSchema>
export type UpdateMemberRoleInput = z.infer<typeof updateMemberRoleSchema>
