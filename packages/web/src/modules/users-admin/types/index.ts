/**
 * Users Admin Types
 * Type definitions for user management
 *
 * BACKEND ALIGNMENT:
 * - Backend uses 'status' (UserStatus enum) not 'is_active' (boolean)
 * - The API service transforms backend 'status' to frontend 'is_active'
 *
 * IMPORTANT: UserRole and UserStatus are imported from @/types/user
 * which is the CANONICAL source. Do NOT redefine them here.
 *
 * @module users-admin/types
 * @author Claude Code
 * @date 2025-11-19
 */

// Import from canonical source and re-export
import { UserRole, UserStatus } from '@/types/user'
export { UserRole, UserStatus }

/**
 * User interface for frontend display
 * Uses is_active boolean for simplicity (transformed from backend status)
 */
export interface User {
  id: string
  email: string
  first_name: string
  last_name: string
  role: UserRole
  role_id?: string | null  // Optional: custom role from roles table
  role_name?: string | null  // Role name if role_id is set
  is_active: boolean  // Transformed from backend 'status' field
  two_factor_enabled: boolean
  created_at: string
  updated_at?: string
  last_login?: string | null
  // Additional profile fields
  phone_number?: string | null
  address?: string | null
  city?: string | null
  country?: string | null
  preferred_language?: string | null
  email_verified?: boolean
  email_verified_at?: string | null
}

/**
 * Request for creating a new user
 * Backend uses UserCreate model with 'profile' containing first_name/last_name
 */
export interface CreateUserRequest {
  email: string
  first_name: string
  last_name: string
  role: UserRole
  password: string
  is_active?: boolean
  two_factor_enabled?: boolean
}

/**
 * Request for updating a user
 * Backend expects 'status' not 'is_active'
 */
export interface UpdateUserRequest {
  email?: string
  first_name?: string
  last_name?: string
  role?: UserRole
  role_id?: string | null  // Optional: assign a custom role from roles table
  status?: UserStatus  // Backend expects status, not is_active
  two_factor_enabled?: boolean
}

export interface PaginatedUsersResponse {
  items: User[]
  total: number
  page: number
  page_size: number
}
