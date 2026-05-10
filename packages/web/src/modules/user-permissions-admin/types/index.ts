/**
 * User Permissions Admin Types
 * Type definitions for user permission overrides management
 *
 * @module user-permissions-admin/types
 * @author Claude Code
 * @date 2025-12-04
 *
 * BACKEND ALIGNMENT:
 * Routes: /api/v1/user-permissions (from app/modules/permissions/api/user_permission_routes.py)
 */

export interface UserPermission {
  id: string
  user_id: string
  permission_id: string
  permission_name: string
  permission_description: string
  granted: boolean
  granted_by: string | null
  granted_at: string
  expires_at: string | null
  reason: string | null
  is_critical: boolean
}

export interface UserWithPermissions {
  user_id: string
  email: string
  full_name: string
  role: string
  role_id: string | null
  role_name: string | null
  role_permissions: string[]
  user_permissions: UserPermission[]
  effective_permissions: string[]
}

export interface GrantUserPermissionRequest {
  permission_id: string
  granted: boolean
  expires_at?: string | null
  reason?: string
}

export interface RevokeUserPermissionRequest {
  permission_id: string
}

export interface UserPermissionListParams {
  user_id?: string
  permission_id?: string
  granted?: boolean
  include_expired?: boolean
  page?: number
  page_size?: number
}

export interface PaginatedUserPermissionsResponse {
  items: UserPermission[]
  total: number
  page: number
  page_size: number
}

// Simplified user for selection
export interface SimpleUser {
  id: string
  email: string
  first_name: string
  last_name: string
  role: string
}
