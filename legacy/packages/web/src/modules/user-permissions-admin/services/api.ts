/**
 * User Permissions Admin API Service
 * Handles all API calls to the backend user-permissions endpoints
 *
 * @module user-permissions-admin/services
 * @author Claude Code
 * @date 2025-12-04
 *
 * BACKEND ALIGNMENT:
 * Routes: /api/v1/user-permissions (from app/modules/permissions/api/user_permission_routes.py)
 * - GET    /api/v1/user-permissions                    → list_user_permissions
 * - GET    /api/v1/user-permissions/user/{user_id}     → get_user_permissions
 * - POST   /api/v1/user-permissions/grant              → grant_permission
 * - POST   /api/v1/user-permissions/revoke             → revoke_permission
 * - GET    /api/v1/user-permissions/check/{user_id}    → check_permission
 */

import { fetchClient } from '@/core/api'
import type {
  UserPermission,
  UserWithPermissions,
  GrantUserPermissionRequest,
  UserPermissionListParams,
  PaginatedUserPermissionsResponse,
  SimpleUser,
} from '../types'

// =============================================================================
// CONFIGURATION
// =============================================================================

const USER_PERMISSIONS_BASE = '/user-permissions'

// =============================================================================
// USER PERMISSIONS API
// =============================================================================

export const userPermissionsApi = {
  /**
   * List all user permission overrides with optional filters
   * BACKEND: GET /api/v1/user-permissions
   * PERMISSION: user_permissions.view_all
   */
  getAll: async (params?: UserPermissionListParams): Promise<PaginatedUserPermissionsResponse> => {
    return fetchClient.get<PaginatedUserPermissionsResponse>(USER_PERMISSIONS_BASE, {
      user_id: params?.user_id,
      permission_id: params?.permission_id,
      granted: params?.granted,
      include_expired: params?.include_expired,
      page: params?.page || 1,
      page_size: params?.page_size || 50,
    })
  },

  /**
   * Get all permission overrides for a specific user
   * BACKEND: GET /api/v1/user-permissions/user/{user_id}
   * PERMISSION: user_permissions.view
   */
  getUserPermissions: async (userId: string): Promise<UserWithPermissions> => {
    return fetchClient.get<UserWithPermissions>(`${USER_PERMISSIONS_BASE}/user/${userId}`)
  },

  /**
   * Grant a permission to a user (override)
   * BACKEND: POST /api/v1/user-permissions/grant
   * PERMISSION: user_permissions.grant (critical)
   */
  grantPermission: async (
    userId: string,
    data: GrantUserPermissionRequest
  ): Promise<UserPermission> => {
    return fetchClient.post<UserPermission>(`${USER_PERMISSIONS_BASE}/grant`, {
      user_id: userId,
      ...data,
    })
  },

  /**
   * Revoke a permission from a user
   * BACKEND: POST /api/v1/user-permissions/revoke
   * PERMISSION: user_permissions.revoke (critical)
   */
  revokePermission: async (userId: string, permissionId: string): Promise<void> => {
    await fetchClient.post(`${USER_PERMISSIONS_BASE}/revoke`, {
      user_id: userId,
      permission_id: permissionId,
    })
  },

  /**
   * Check if a user has a specific permission
   * BACKEND: GET /api/v1/user-permissions/check/{user_id}
   * PERMISSION: user_permissions.view
   */
  checkPermission: async (userId: string, permissionName: string): Promise<boolean> => {
    try {
      const response = await fetchClient.get<{ has_permission: boolean }>(
        `${USER_PERMISSIONS_BASE}/check/${userId}`,
        { permission: permissionName }
      )
      return response.has_permission
    } catch {
      return false
    }
  },

  /**
   * Search users for selection (uses admin users endpoint)
   * BACKEND: GET /api/v1/admin/users
   * @param query - Search query (name, email)
   * @param role - Optional role filter (e.g., 'agent')
   * @param limit - Max results
   */
  searchUsers: async (query?: string, role?: string, limit: number = 20): Promise<SimpleUser[]> => {
    const params: Record<string, string | number> = {
      size: limit,
    }
    if (query) params.search = query
    if (role) params.role = role

    const response = await fetchClient.get<{ items: SimpleUser[] }>('/admin/users', params)
    return response.items || []
  },

  /**
   * Search agents only (convenience method)
   * BACKEND: GET /api/v1/admin/users?role=agent
   */
  searchAgents: async (query?: string, limit: number = 20): Promise<SimpleUser[]> => {
    return userPermissionsApi.searchUsers(query, 'agent', limit)
  },
}

// =============================================================================
// EXPORTS
// =============================================================================

export default userPermissionsApi
