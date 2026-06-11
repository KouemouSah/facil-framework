/**
 * Roles Hooks
 * React Query hooks for role management operations
 *
 * @module roles-admin/hooks
 * @author Claude Code
 * @date 2025-12-04
 */

'use client'

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { rolesApi, permissionsSimulatorApi } from '../services/api'
import type { CreateRoleRequest, UpdateRoleRequest, AssignPermissionsRequest, RemovePermissionsRequest } from '../types'

// Query keys
export const rolesKeys = {
  all: ['roles'] as const,
  lists: () => [...rolesKeys.all, 'list'] as const,
  list: (filters: Record<string, unknown>) => [...rolesKeys.lists(), filters] as const,
  details: () => [...rolesKeys.all, 'detail'] as const,
  detail: (id: string) => [...rolesKeys.details(), id] as const,
  withPermissions: (id: string) => [...rolesKeys.detail(id), 'permissions'] as const,
  system: () => [...rolesKeys.all, 'system'] as const,
  custom: () => [...rolesKeys.all, 'custom'] as const,
  matrix: (module?: string) => [...rolesKeys.all, 'matrix', module] as const,
}

/**
 * Fetch all roles with optional filters
 */
export function useRoles(params?: {
  entity_type?: string | null
  is_system?: boolean
  page?: number
  page_size?: number
}) {
  return useQuery({
    queryKey: rolesKeys.list(params || {}),
    queryFn: () => rolesApi.getAll(params),
  })
}

/**
 * Fetch system roles only
 */
export function useSystemRoles() {
  return useQuery({
    queryKey: rolesKeys.system(),
    queryFn: () => rolesApi.getSystemRoles(),
  })
}

/**
 * Fetch custom roles only
 */
export function useCustomRoles() {
  return useQuery({
    queryKey: rolesKeys.custom(),
    queryFn: () => rolesApi.getCustomRoles(),
  })
}

/**
 * Fetch a single role by ID
 */
export function useRole(id: string) {
  return useQuery({
    queryKey: rolesKeys.detail(id),
    queryFn: () => rolesApi.getById(id),
    enabled: !!id,
  })
}

/**
 * Fetch a role with all permissions
 */
export function useRoleWithPermissions(id: string) {
  return useQuery({
    queryKey: rolesKeys.withPermissions(id),
    queryFn: () => rolesApi.getWithPermissions(id),
    enabled: !!id,
  })
}

/**
 * Create a new role
 */
export function useCreateRole() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (data: CreateRoleRequest) => rolesApi.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: rolesKeys.lists() })
      queryClient.invalidateQueries({ queryKey: rolesKeys.custom() })
    },
  })
}

/**
 * Update an existing role
 */
export function useUpdateRole() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: UpdateRoleRequest }) =>
      rolesApi.update(id, data),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: rolesKeys.lists() })
      queryClient.invalidateQueries({ queryKey: rolesKeys.detail(variables.id) })
    },
  })
}

/**
 * Delete a role
 */
export function useDeleteRole() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (id: string) => rolesApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: rolesKeys.lists() })
      queryClient.invalidateQueries({ queryKey: rolesKeys.custom() })
    },
  })
}

/**
 * Assign permissions to a role
 */
export function useAssignPermissions() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ roleId, data }: { roleId: string; data: AssignPermissionsRequest }) =>
      rolesApi.assignPermissions(roleId, data),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: rolesKeys.withPermissions(variables.roleId) })
    },
  })
}

/**
 * Remove permissions from a role
 */
export function useRemovePermissions() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ roleId, data }: { roleId: string; data: RemovePermissionsRequest }) =>
      rolesApi.removePermissions(roleId, data),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: rolesKeys.withPermissions(variables.roleId) })
    },
  })
}

/**
 * Fetch permission matrix (all roles × permissions)
 */
export function usePermissionMatrix(module?: string) {
  return useQuery({
    queryKey: rolesKeys.matrix(module),
    queryFn: () => rolesApi.getPermissionMatrix(module),
    staleTime: 2 * 60 * 1000, // 2 minutes
  })
}

/**
 * Clone a role with all its permissions
 */
export function useCloneRole() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ roleId, newName, newCode }: { roleId: string; newName?: string; newCode?: string }) =>
      rolesApi.clone(roleId, newName, newCode),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: rolesKeys.lists() })
      queryClient.invalidateQueries({ queryKey: rolesKeys.custom() })
    },
  })
}

/**
 * Bulk delete custom roles
 */
export function useBulkDeleteRoles() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (roleIds: string[]) => rolesApi.bulkDelete(roleIds),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: rolesKeys.lists() })
      queryClient.invalidateQueries({ queryKey: rolesKeys.custom() })
    },
  })
}

// =============================================================================
// PERMISSION SIMULATOR HOOKS
// =============================================================================

/**
 * Simulate granting/revoking permissions on a role
 */
export function useSimulateRolePermission() {
  return useMutation({
    mutationFn: (data: { role_id: string; permission_names: string[]; action: 'grant' | 'revoke' }) =>
      permissionsSimulatorApi.simulateRolePermission(data),
  })
}

/**
 * Simulate changing a user's role
 */
export function useSimulateUserRoleChange() {
  return useMutation({
    mutationFn: (data: { user_id: string; new_role_id: string }) =>
      permissionsSimulatorApi.simulateUserRoleChange(data),
  })
}

/**
 * Fetch overprivileged users (manual trigger only — not auto-fired)
 */
export function useOverprivilegedUsers(params?: {
  min_risk_score?: number
  risk_level?: string
  limit?: number
}) {
  return useQuery({
    queryKey: ['permissions', 'overprivileged', params],
    queryFn: () => permissionsSimulatorApi.getOverprivilegedUsers(params),
    staleTime: 5 * 60 * 1000,
    enabled: false, // Only fires via refetch() — prevents auto-fire on mount/keystroke
  })
}
