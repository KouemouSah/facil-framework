/**
 * Roles Admin API Service
 * Handles all API calls to the backend roles endpoints
 *
 * @module roles-admin/services
 * @author Claude Code
 * @date 2025-12-04
 *
 * BACKEND ALIGNMENT:
 * Routes: /api/v1/roles (from app/modules/permissions/api/role_routes.py)
 * - GET    /api/v1/roles                     → get_all_roles (paginated)
 * - GET    /api/v1/roles/system              → get_system_roles
 * - GET    /api/v1/roles/custom              → get_custom_roles
 * - GET    /api/v1/roles/{role_id}           → get_role_by_id
 * - GET    /api/v1/roles/{role_id}/with-permissions → get_role_with_permissions
 * - GET    /api/v1/roles/code/{code}         → get_role_by_code
 * - POST   /api/v1/roles                     → create_role
 * - PUT    /api/v1/roles/{role_id}           → update_role
 * - DELETE /api/v1/roles/{role_id}           → delete_role
 * - POST   /api/v1/roles/{role_id}/permissions     → assign_permissions_to_role
 * - DELETE /api/v1/roles/{role_id}/permissions     → remove_permissions_from_role
 * - GET    /api/v1/roles/{role_id}/permissions     → get_role_permissions
 */

import { fetchClient } from '@/core/api'
import type {
  Role,
  RoleWithPermissions,
  CreateRoleRequest,
  UpdateRoleRequest,
  PaginatedRolesResponse,
  AssignPermissionsRequest,
  RemovePermissionsRequest,
  PermissionMatrixResponse,
  SimulateRolePermissionResponse,
  SimulateUserRoleChangeResponse,
  OverprivilegedUsersResponse,
} from '../types'

// =============================================================================
// CONFIGURATION
// =============================================================================

const ROLES_BASE = '/roles'

// =============================================================================
// ROLES API
// =============================================================================

export const rolesApi = {
  /**
   * Get all roles with optional filters and pagination
   * BACKEND: GET /api/v1/roles
   * PERMISSION: roles.view
   */
  getAll: async (params?: {
    entity_type?: string | null
    is_system?: boolean
    page?: number
    page_size?: number
  }): Promise<PaginatedRolesResponse> => {
    return fetchClient.get<PaginatedRolesResponse>(ROLES_BASE, {
      entity_type: params?.entity_type ?? undefined,
      is_system: params?.is_system,
      page: params?.page || 1,
      page_size: params?.page_size || 50,
    })
  },

  /**
   * Get all system (built-in) roles
   * BACKEND: GET /api/v1/roles/system
   * PERMISSION: roles.view
   */
  getSystemRoles: async (): Promise<Role[]> => {
    return fetchClient.get<Role[]>(`${ROLES_BASE}/system`)
  },

  /**
   * Get all custom (user-created) roles
   * BACKEND: GET /api/v1/roles/custom
   * PERMISSION: roles.view
   */
  getCustomRoles: async (): Promise<Role[]> => {
    return fetchClient.get<Role[]>(`${ROLES_BASE}/custom`)
  },

  /**
   * Get all predefined RBAC roles for agents
   * BACKEND: GET /api/v1/roles/agent-roles
   * PERMISSION: roles.view
   *
   * Returns roles like: dgi_validator, dgi_approver, ministry_validator, etc.
   * These should be assigned to agents during creation to define their permissions.
   */
  getAgentRbacRoles: async (): Promise<Role[]> => {
    return fetchClient.get<Role[]>(`${ROLES_BASE}/agent-roles`)
  },

  /**
   * Get role by ID
   * BACKEND: GET /api/v1/roles/{role_id}
   * PERMISSION: roles.view
   */
  getById: async (id: string): Promise<Role> => {
    return fetchClient.get<Role>(`${ROLES_BASE}/${id}`)
  },

  /**
   * Get role with all associated permissions
   * BACKEND: GET /api/v1/roles/{role_id}/with-permissions
   * PERMISSION: roles.view
   */
  getWithPermissions: async (id: string): Promise<RoleWithPermissions> => {
    return fetchClient.get<RoleWithPermissions>(`${ROLES_BASE}/${id}/with-permissions`)
  },

  /**
   * Get role by code
   * BACKEND: GET /api/v1/roles/code/{code}
   * PERMISSION: roles.view
   */
  getByCode: async (code: string): Promise<Role> => {
    return fetchClient.get<Role>(`${ROLES_BASE}/code/${code}`)
  },

  /**
   * Get permission matrix: all roles × permissions with assignment data
   * BACKEND: GET /api/v1/roles/permission-matrix
   * PERMISSION: roles.view
   */
  getPermissionMatrix: async (module_name?: string): Promise<PermissionMatrixResponse> => {
    const params = module_name ? `?module_name=${encodeURIComponent(module_name)}` : ''
    return fetchClient.get<PermissionMatrixResponse>(`${ROLES_BASE}/permission-matrix${params}`)
  },

  /**
   * Create a new custom role
   * BACKEND: POST /api/v1/roles
   * PERMISSION: roles.create (critical)
   */
  create: async (data: CreateRoleRequest): Promise<Role> => {
    return fetchClient.post<Role>(ROLES_BASE, data)
  },

  /**
   * Update a role
   * BACKEND: PUT /api/v1/roles/{role_id}
   * PERMISSION: roles.update (critical)
   */
  update: async (id: string, data: UpdateRoleRequest): Promise<Role> => {
    return fetchClient.put<Role>(`${ROLES_BASE}/${id}`, data)
  },

  /**
   * Delete a role
   * BACKEND: DELETE /api/v1/roles/{role_id}
   * PERMISSION: roles.delete (critical)
   */
  delete: async (id: string): Promise<void> => {
    await fetchClient.delete(`${ROLES_BASE}/${id}`)
  },

  /**
   * Assign permissions to a role
   * BACKEND: POST /api/v1/roles/{role_id}/permissions
   * PERMISSION: roles.assign_permissions (critical)
   */
  assignPermissions: async (roleId: string, data: AssignPermissionsRequest): Promise<{ assigned: number; failed: number }> => {
    return fetchClient.post(`${ROLES_BASE}/${roleId}/permissions`, data)
  },

  /**
   * Remove permissions from a role
   * BACKEND: DELETE /api/v1/roles/{role_id}/permissions
   * PERMISSION: roles.assign_permissions (critical)
   * Note: Uses POST with _method=DELETE since DELETE with body is problematic
   */
  removePermissions: async (roleId: string, data: RemovePermissionsRequest): Promise<{ removed: number; failed: number }> => {
    // Use POST with data since DELETE doesn't support body in fetchClient
    // Backend should accept both DELETE with query params or POST with body
    return fetchClient.post(`${ROLES_BASE}/${roleId}/permissions/remove`, data)
  },

  /**
   * Get list of permission IDs for a role
   * BACKEND: GET /api/v1/roles/{role_id}/permissions
   * PERMISSION: roles.view
   */
  getPermissions: async (roleId: string): Promise<string[]> => {
    return fetchClient.get<string[]>(`${ROLES_BASE}/${roleId}/permissions`)
  },

  /**
   * Clone a role with all its permissions
   * BACKEND: POST /api/v1/roles/{role_id}/clone
   * PERMISSION: roles.create
   */
  clone: async (roleId: string, newName?: string, newCode?: string): Promise<Role> => {
    const params = new URLSearchParams()
    if (newName) params.set('new_name', newName)
    if (newCode) params.set('new_code', newCode)
    const qs = params.toString() ? `?${params.toString()}` : ''
    return fetchClient.post<Role>(`${ROLES_BASE}/${roleId}/clone${qs}`, {})
  },

  /**
   * Bulk delete custom roles
   * BACKEND: POST /api/v1/roles/bulk-delete
   * PERMISSION: roles.delete
   */
  bulkDelete: async (roleIds: string[]): Promise<{ deleted_count: number; failed_count: number; failed: Array<{ id: string; reason: string }> }> => {
    return fetchClient.post(`${ROLES_BASE}/bulk-delete`, roleIds)
  },

  /**
   * Export roles as CSV
   * BACKEND: GET /api/v1/roles/export/csv
   * PERMISSION: roles.view
   */
  exportCsv: async (): Promise<void> => {
    const response = await fetch(`/api/v1/roles/export/csv`, {
      headers: {
        'Authorization': `Bearer ${localStorage.getItem('access_token') || ''}`,
      },
    })
    if (!response.ok) throw new Error('Export failed')
    const blob = await response.blob()
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'roles_export.csv'
    a.click()
    URL.revokeObjectURL(url)
  },
}

// =============================================================================
// PERMISSIONS SIMULATOR API
// =============================================================================

const PERMISSIONS_BASE = '/permissions'

export const permissionsSimulatorApi = {
  /**
   * Simulate granting/revoking permissions on a role
   * BACKEND: POST /api/v1/permissions/simulate/role-permission
   * PERMISSION: roles.view
   */
  simulateRolePermission: async (data: {
    role_id: string
    permission_names: string[]
    action: 'grant' | 'revoke'
  }): Promise<SimulateRolePermissionResponse> => {
    return fetchClient.post<SimulateRolePermissionResponse>(
      `${PERMISSIONS_BASE}/simulate/role-permission`,
      data,
    )
  },

  /**
   * Simulate changing a user's role
   * BACKEND: POST /api/v1/permissions/simulate/user-role-change
   * PERMISSION: roles.view
   */
  simulateUserRoleChange: async (data: {
    user_id: string
    new_role_id: string
  }): Promise<SimulateUserRoleChangeResponse> => {
    return fetchClient.post<SimulateUserRoleChangeResponse>(
      `${PERMISSIONS_BASE}/simulate/user-role-change`,
      data,
    )
  },

  /**
   * Detect overprivileged users
   * BACKEND: GET /api/v1/permissions/anomalies/overprivileged
   * PERMISSION: admin.view_security
   */
  getOverprivilegedUsers: async (params?: {
    min_risk_score?: number
    risk_level?: string
    limit?: number
  }): Promise<OverprivilegedUsersResponse> => {
    return fetchClient.get<OverprivilegedUsersResponse>(
      `${PERMISSIONS_BASE}/anomalies/overprivileged`,
      params,
    )
  },
}

// =============================================================================
// EXPORTS
// =============================================================================

export default rolesApi
