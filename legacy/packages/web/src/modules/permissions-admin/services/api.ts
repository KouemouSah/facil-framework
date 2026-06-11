/**
 * Permissions Admin API Service
 * Handles all API calls to the backend permissions endpoints
 *
 * @module permissions-admin/services
 * @author Claude Code
 * @date 2025-11-17
 */

import { fetchClient } from '@/core/api'
import type {
  Permission,
  Role,
  RolePermission,
  UserPermission,
  CreateRoleRequest,
  UpdateRoleRequest,
  GrantUserPermissionRequest,
  RoleWithPermissions,
  UserWithPermissions,
} from "../types";

// =============================================================================
// PERMISSIONS API
// =============================================================================

export const permissionsApi = {
  /**
   * Get all permissions
   */
  getAll: async (params?: {
    module_name?: string;
    resource?: string;
    is_critical?: boolean;
  }): Promise<Permission[]> => {
    const response = await fetchClient.get<{ permissions: Permission[]; total: number; page: number; page_size: number }>('/permissions', {
      module_name: params?.module_name,
      resource: params?.resource,
      is_critical: params?.is_critical,
      page_size: 500, // Fetch all permissions (312 total across 20 modules)
    });

    // Extract permissions array from paginated response (backend returns "permissions" not "items")
    return response.permissions || [];
  },

  /**
   * Get permission by ID
   */
  getById: async (id: string): Promise<Permission> => {
    return fetchClient.get<Permission>(`/permissions/${id}`);
  },

  /**
   * Get permissions grouped by resource
   */
  getByResource: async (): Promise<Record<string, Permission[]>> => {
    const permissions = await permissionsApi.getAll();
    return permissions.reduce((acc, perm) => {
      if (!acc[perm.resource]) {
        acc[perm.resource] = [];
      }
      acc[perm.resource].push(perm);
      return acc;
    }, {} as Record<string, Permission[]>);
  },
};

// =============================================================================
// ROLES API
// =============================================================================

export const rolesApi = {
  /**
   * Get all roles
   */
  getAll: async (params?: {
    entity_type?: string;
    is_system?: boolean;
  }): Promise<Role[]> => {
    const response = await fetchClient.get<{ roles: Role[]; total: number; page: number; page_size: number }>('/roles', {
      entity_type: params?.entity_type,
      is_system: params?.is_system,
    });

    // Extract roles array from paginated response (backend returns "roles" not "items")
    return response.roles || [];
  },

  /**
   * Get role by ID with permissions
   */
  getById: async (id: string): Promise<RoleWithPermissions> => {
    return fetchClient.get<RoleWithPermissions>(`/roles/${id}`);
  },

  /**
   * Create new role
   */
  create: async (data: CreateRoleRequest): Promise<Role> => {
    return fetchClient.post<Role>("/roles", data);
  },

  /**
   * Update role
   */
  update: async (id: string, data: UpdateRoleRequest): Promise<Role> => {
    return fetchClient.put<Role>(`/roles/${id}`, data);
  },

  /**
   * Delete role (only custom roles, not system roles)
   */
  delete: async (id: string): Promise<void> => {
    return fetchClient.delete<void>(`/roles/${id}`);
  },

  /**
   * Get permissions for a role
   */
  getPermissions: async (roleId: string): Promise<Permission[]> => {
    return fetchClient.get<Permission[]>(`/roles/${roleId}/permissions`);
  },

  /**
   * Grant permission to role
   */
  grantPermission: async (
    roleId: string,
    permissionId: string
  ): Promise<RolePermission> => {
    return fetchClient.post<RolePermission>(
      `/roles/${roleId}/permissions/${permissionId}`,
      { granted: true }
    );
  },

  /**
   * Revoke permission from role
   */
  revokePermission: async (
    roleId: string,
    permissionId: string
  ): Promise<void> => {
    return fetchClient.delete<void>(
      `/roles/${roleId}/permissions/${permissionId}`
    );
  },
};

// =============================================================================
// USER PERMISSIONS API
// =============================================================================

export const userPermissionsApi = {
  /**
   * Get all permissions for a user (role + individual)
   */
  getUserPermissions: async (userId: string): Promise<UserWithPermissions> => {
    return fetchClient.get<UserWithPermissions>(`/users/${userId}/permissions`);
  },

  /**
   * Grant permission to user (temporary or permanent)
   */
  grantPermission: async (
    userId: string,
    data: GrantUserPermissionRequest
  ): Promise<UserPermission> => {
    return fetchClient.post<UserPermission>(
      `/users/${userId}/permissions`,
      data
    );
  },

  /**
   * Revoke permission from user
   */
  revokePermission: async (
    userId: string,
    permissionId: string
  ): Promise<void> => {
    return fetchClient.delete<void>(
      `/users/${userId}/permissions/${permissionId}`
    );
  },

  /**
   * Check if user has specific permission
   */
  hasPermission: async (
    userId: string,
    permissionName: string
  ): Promise<boolean> => {
    try {
      const result = await fetchClient.get<{ has_permission: boolean }>(
        `/users/${userId}/permissions/check`,
        { permission: permissionName }
      );
      return result.has_permission;
    } catch {
      return false;
    }
  },
};

// =============================================================================
// EXPORTS
// =============================================================================

export const permissionsAdminApi = {
  permissions: permissionsApi,
  roles: rolesApi,
  userPermissions: userPermissionsApi,
};

export default permissionsAdminApi;
