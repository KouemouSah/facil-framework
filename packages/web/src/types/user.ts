/**
 * User Types
 * TypeScript types aligned with backend Pydantic models
 *
 * BACKEND ALIGNMENT:
 * - packages/backend/app/modules/users/models/user.py
 * - UserRole enum (10 roles) matches user_role_enum in database
 * - UserStatus enum (4 statuses) matches user_status in database
 * - Field mappings: phone_number → phoneNumber, preferred_language → preferredLanguage
 *
 * CRITICAL CONSTRAINTS:
 * - citizen/business users: SOFT DELETE only (status='inactive')
 * - Other 8 professional roles: Full CRUD with physical DELETE
 * - admin users: Cannot be deleted (protection layer)
 *
 * @module types/user
 * @author Claude Code
 * @date 2025-11-24
 */

/**
 * UserRole Enum - MUST match backend user_role_enum exactly
 * Simplified to 6 roles from migration 048
 * Supervisors are now handled via is_supervisor flag in agent_profiles
 */
export enum UserRole {
  CITIZEN = 'citizen',
  BUSINESS = 'business',
  ACCOUNTANT = 'accountant',
  ADMIN = 'admin',
  AGENT = 'agent',           // Unified agent role (replaces dgi_agent, ministry_agent, supervisors)
  FUNCIONARIO = 'funcionario', // Civil servant role
}

/**
 * UserStatus Enum - MUST match backend user_status exactly
 * 4 statuses total
 */
export enum UserStatus {
  ACTIVE = 'active',
  INACTIVE = 'inactive',
  PENDING = 'pending',
  SUSPENDED = 'suspended',
}

/**
 * UserProfile - Embedded profile data
 * Aligned with UserProfile Pydantic model
 */
export interface UserProfile {
  firstName: string // min 2, max 50
  lastName: string // min 2, max 50
  phoneNumber?: string | null // E.164 format: +240XXXXXXXXX, maps to phone_number in DB
  address?: string | null // max 255
  city?: string | null // max 100
  country?: string | null // max 100 (default: "GNQ")
  preferredLanguage?: string | null // "es" | "fr" | "en", maps to preferred_language in DB
  notificationPreferences?: Record<string, boolean> | null // JSONB, maps to notification_preferences
}

/**
 * UserBase - Base user fields
 * Aligned with UserBase Pydantic model
 */
export interface UserBase {
  email: string // EmailStr, unique, max 255
  role: UserRole // 10 possible roles
  status?: UserStatus // Default: ACTIVE
  profile?: UserProfile | null
  twoFactorEnabled?: boolean // Default: false, maps to two_factor_enabled
  ministry?: string | null // UUID reference to ministries table
  sector?: string | null // UUID reference to sectors table
}

/**
 * UserCreate - Input for creating a new user
 * Aligned with UserCreate Pydantic model
 */
export interface UserCreate extends UserBase {
  password: string // min 8, max 100
}

/**
 * UserUpdate - Input for updating a user (all fields optional)
 * Aligned with UserUpdate Pydantic model
 */
export interface UserUpdate {
  email?: string
  password?: string // If provided, will be hashed
  role?: UserRole
  status?: UserStatus
  profile?: UserProfile | null
  twoFactorEnabled?: boolean
  ministry?: string | null
  sector?: string | null
}

/**
 * UserResponse - User data returned from API
 * Aligned with UserResponse Pydantic model
 */
export interface UserResponse extends UserBase {
  id: string // UUID
  createdAt: string // ISO 8601 datetime, maps to created_at
  updatedAt: string // ISO 8601 datetime, maps to updated_at
  lastLogin?: string | null // ISO 8601 datetime, maps to last_login
  emailVerified: boolean // Default: false, maps to email_verified
  emailVerifiedAt?: string | null // ISO 8601 datetime, maps to email_verified_at
}

/**
 * UserListResponse - Paginated user list
 * Aligned with backend pagination response
 */
export interface UserListResponse {
  items: UserResponse[]
  total: number
  page: number
  size: number
  pages: number
}

/**
 * UserSearchFilter - Search and filter parameters
 * Aligned with backend query parameters
 */
export interface UserSearchFilter {
  q?: string // Search query (email, firstName, lastName)
  role?: UserRole | 'all'
  status?: UserStatus | 'all'
  twoFactorEnabled?: boolean
  ministry?: string // UUID
  sector?: string // UUID
  emailVerified?: boolean
  page?: number // Default: 1
  size?: number // Default: 20, max: 100
  sortBy?: 'createdAt' | 'updatedAt' | 'lastLogin' | 'email'
  sortOrder?: 'asc' | 'desc'
}

/**
 * UserStats - User statistics
 * For admin dashboard
 */
export interface UserStats {
  total: number
  byRole: Record<UserRole, number>
  byStatus: Record<UserStatus, number>
  twoFactorEnabled: number
  emailVerified: number
  newToday: number
  newThisWeek: number
  newThisMonth: number
}

/**
 * UserPermissions - User permission summary
 * Aggregated from role_permissions
 */
export interface UserPermissions {
  userId: string
  role: UserRole
  permissions: string[] // Array of permission codes (e.g., "users:read", "declarations:submit")
  canDelete: boolean // Computed: true for professional roles (NOT citizen/business)
  canPhysicallyDelete: boolean // Computed: true for non-citizen/business, false for admin
}

/**
 * UserActivity - User activity log entry
 * For audit purposes
 */
export interface UserActivity {
  id: string
  userId: string
  action: string // userLogin, userLogout, profileUpdate, passwordChange, etc.
  ipAddress?: string | null
  userAgent?: string | null
  timestamp: string // ISO 8601 datetime
  metadata?: Record<string, unknown> | null
}

/**
 * Role Categories - Helper for grouping roles
 * Updated for simplified role structure (migration 048)
 */
export const ROLE_CATEGORIES = {
  citizens: [UserRole.CITIZEN, UserRole.BUSINESS] as const,
  professionals: [
    UserRole.ACCOUNTANT,
    UserRole.FUNCIONARIO,
  ] as const,
  agents: [UserRole.AGENT] as const,
  admins: [UserRole.ADMIN] as const,
}

/**
 * Helper: Check if role is citizen/business (soft delete only)
 */
export function isCitizenOrBusiness(role: UserRole): boolean {
  return role === UserRole.CITIZEN || role === UserRole.BUSINESS
}

/**
 * Helper: Check if role can be physically deleted
 */
export function canPhysicallyDelete(role: UserRole): boolean {
  // Admin cannot be deleted (protection), citizen/business use soft delete
  return role !== UserRole.ADMIN && !isCitizenOrBusiness(role)
}

/**
 * Helper: Check if user can be soft deleted
 */
export function canSoftDelete(role: UserRole): boolean {
  // Only citizen/business use soft delete
  return isCitizenOrBusiness(role)
}

/**
 * Helper: Get role display category
 */
export function getRoleCategory(
  role: UserRole
): 'citizens' | 'professionals' | 'agents' | 'admins' {
  if ((ROLE_CATEGORIES.citizens as readonly string[]).includes(role)) return 'citizens'
  if ((ROLE_CATEGORIES.admins as readonly string[]).includes(role)) return 'admins'
  if ((ROLE_CATEGORIES.agents as readonly string[]).includes(role)) return 'agents'
  return 'professionals'
}

/**
 * Type guard: Check if value is valid UserRole
 */
export function isUserRole(value: unknown): value is UserRole {
  return (
    typeof value === 'string' &&
    Object.values(UserRole).includes(value as UserRole)
  )
}

/**
 * Type guard: Check if value is valid UserStatus
 */
export function isUserStatus(value: unknown): value is UserStatus {
  return (
    typeof value === 'string' &&
    Object.values(UserStatus).includes(value as UserStatus)
  )
}

/**
 * Convert snake_case to camelCase for API responses
 */
export function toCamelCase(str: string): string {
  return str.replace(/_([a-z])/g, (_, letter) => letter.toUpperCase())
}

/**
 * Convert camelCase to snake_case for API requests
 */
export function toSnakeCase(str: string): string {
  return str.replace(/[A-Z]/g, (letter) => `_${letter.toLowerCase()}`)
}

/**
 * Transform backend user response to frontend format
 */
export function transformUserResponse(backendUser: any): UserResponse {
  return {
    id: backendUser.id,
    email: backendUser.email,
    role: backendUser.role as UserRole,
    status: backendUser.status as UserStatus,
    profile: backendUser.profile
      ? {
          firstName: backendUser.profile.first_name,
          lastName: backendUser.profile.last_name,
          phoneNumber: backendUser.profile.phone_number,
          address: backendUser.profile.address,
          city: backendUser.profile.city,
          country: backendUser.profile.country,
          preferredLanguage: backendUser.profile.preferred_language,
          notificationPreferences: backendUser.profile.notification_preferences,
        }
      : null,
    twoFactorEnabled: backendUser.two_factor_enabled,
    ministry: backendUser.ministry,
    sector: backendUser.sector,
    createdAt: backendUser.created_at,
    updatedAt: backendUser.updated_at,
    lastLogin: backendUser.last_login,
    emailVerified: backendUser.email_verified,
    emailVerifiedAt: backendUser.email_verified_at,
  }
}

/**
 * Transform frontend user create to backend format
 */
export function transformUserCreate(frontendUser: UserCreate): any {
  return {
    email: frontendUser.email,
    password: frontendUser.password,
    role: frontendUser.role,
    status: frontendUser.status,
    profile: frontendUser.profile
      ? {
          first_name: frontendUser.profile.firstName,
          last_name: frontendUser.profile.lastName,
          phone_number: frontendUser.profile.phoneNumber,
          address: frontendUser.profile.address,
          city: frontendUser.profile.city,
          country: frontendUser.profile.country,
          preferred_language: frontendUser.profile.preferredLanguage,
          notification_preferences: frontendUser.profile.notificationPreferences,
        }
      : null,
    two_factor_enabled: frontendUser.twoFactorEnabled,
    ministry: frontendUser.ministry,
    sector: frontendUser.sector,
  }
}

/**
 * Transform frontend user update to backend format
 */
export function transformUserUpdate(frontendUser: UserUpdate): any {
  const result: any = {}

  if (frontendUser.email !== undefined) result.email = frontendUser.email
  if (frontendUser.password !== undefined) result.password = frontendUser.password
  if (frontendUser.role !== undefined) result.role = frontendUser.role
  if (frontendUser.status !== undefined) result.status = frontendUser.status
  if (frontendUser.twoFactorEnabled !== undefined)
    result.two_factor_enabled = frontendUser.twoFactorEnabled
  if (frontendUser.ministry !== undefined) result.ministry = frontendUser.ministry
  if (frontendUser.sector !== undefined) result.sector = frontendUser.sector

  if (frontendUser.profile !== undefined) {
    result.profile = frontendUser.profile
      ? {
          first_name: frontendUser.profile.firstName,
          last_name: frontendUser.profile.lastName,
          phone_number: frontendUser.profile.phoneNumber,
          address: frontendUser.profile.address,
          city: frontendUser.profile.city,
          country: frontendUser.profile.country,
          preferred_language: frontendUser.profile.preferredLanguage,
          notification_preferences: frontendUser.profile.notificationPreferences,
        }
      : null
  }

  return result
}
