/**
 * Users Module Types
 * Type definitions for user profile management (self-service)
 *
 * @module users/types
 * @author Emac Sah
 * @date 2025-11-26
 *
 * BACKEND ALIGNMENT:
 * - Schemas from: app/modules/users/models/user.py
 * - Routes from: app/modules/users/api/user_routes.py
 *
 * NOTE: This module is for USER SELF-SERVICE (profile management)
 * Admin user management is in users-admin module
 */

// =============================================================================
// ENUMS
// =============================================================================

/**
 * User roles
 * BACKEND: UserRole enum in user.py
 */
export type UserRole =
  | 'citizen'
  | 'business'
  | 'accountant'
  | 'admin'
  | 'dgi_agent'
  | 'supervisor_junior_dgi'
  | 'supervisor_readonly'
  | 'supervisor_senior'
  | 'ministry_agent'
  | 'supervisor_dgi';

/**
 * User status
 * BACKEND: UserStatus enum in user.py
 */
export type UserStatus =
  | 'active'
  | 'inactive'
  | 'suspended'
  | 'pending_verification';

// =============================================================================
// PROFILE TYPES
// =============================================================================

/**
 * User profile data
 * BACKEND: UserProfile in user.py
 */
export interface UserProfile {
  first_name: string;
  last_name: string;
  phone?: string;
  address?: string;
  city?: string;
  language: string; // 'es' | 'fr' | 'en'
  avatar_url?: string;
}

/**
 * Citizen profile extension
 * BACKEND: CitizenProfile in user.py
 */
export interface CitizenProfile {
  nif?: string;
  date_of_birth?: string;
  nationality?: string;
  gender?: 'male' | 'female' | 'other';
}

/**
 * Business profile extension
 * BACKEND: BusinessProfile in user.py
 */
export interface BusinessProfile {
  company_name?: string;
  company_nif?: string;
  business_type?: string;
  registration_number?: string;
  representative_name?: string;
  representative_nif?: string;
}

// =============================================================================
// USER RESPONSE
// =============================================================================

/**
 * Full user response from API
 * BACKEND: UserResponse in user.py
 */
export interface UserResponse {
  id: string;
  email: string;
  role: UserRole;
  status: UserStatus;
  first_name: string;
  last_name: string;
  phone?: string;
  address?: string;
  city?: string;
  language: string;
  avatar_url?: string;
  created_at: string;
  updated_at: string;
  last_login?: string;
  email_verified?: boolean;
  two_factor_enabled?: boolean;
  two_factor_secret?: string;
  two_factor_backup_codes?: string[];
  citizen_profile?: CitizenProfile;
  business_profile?: BusinessProfile;
}

// =============================================================================
// UPDATE REQUESTS
// =============================================================================

/**
 * Profile update request
 * BACKEND: UserUpdate in user.py
 * NOTE: Users cannot update their own status (admin only)
 */
export interface ProfileUpdateRequest {
  first_name?: string;
  last_name?: string;
  email?: string;
  phone?: string; // Format: +240XXXXXXXXX (E.164)
  address?: string;
  city?: string;
  language?: string; // 'es' | 'fr' | 'en'
  avatar_url?: string;
}

/**
 * Password change request
 * BACKEND: PasswordChange in user.py
 */
export interface PasswordChangeRequest {
  old_password: string; // min 8 chars
  new_password: string; // min 8 chars, must be different from old
}
