/**
 * User Permissions Hooks
 * React Query hooks for user permission management
 *
 * @module user-permissions-admin/hooks
 * @author Claude Code
 * @date 2025-12-04
 */

'use client'

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { userPermissionsApi } from '../services/api'
import type { GrantUserPermissionRequest, UserPermissionListParams } from '../types'

// Query keys
export const userPermissionsKeys = {
  all: ['user-permissions'] as const,
  lists: () => [...userPermissionsKeys.all, 'list'] as const,
  list: (filters: UserPermissionListParams) => [...userPermissionsKeys.lists(), filters] as const,
  user: (userId: string) => [...userPermissionsKeys.all, 'user', userId] as const,
  users: () => ['users', 'search'] as const,
  usersSearch: (query: string) => [...userPermissionsKeys.users(), query] as const,
}

/**
 * Fetch all user permission overrides with optional filters
 */
export function useUserPermissionsList(params?: UserPermissionListParams) {
  return useQuery({
    queryKey: userPermissionsKeys.list(params || {}),
    queryFn: () => userPermissionsApi.getAll(params),
  })
}

/**
 * Fetch all permissions for a specific user
 */
export function useUserPermissions(userId: string | null) {
  return useQuery({
    queryKey: userPermissionsKeys.user(userId || ''),
    queryFn: () => userPermissionsApi.getUserPermissions(userId!),
    enabled: !!userId,
  })
}

/**
 * Search users for selection
 * @param query - Search query
 * @param role - Optional role filter
 */
export function useSearchUsers(query: string, role?: string) {
  return useQuery({
    queryKey: [...userPermissionsKeys.usersSearch(query), role],
    queryFn: () => userPermissionsApi.searchUsers(query, role),
    enabled: query.length >= 2,
    staleTime: 30 * 1000, // 30 seconds
  })
}

/**
 * Search agents only for selection
 */
export function useSearchAgents(query: string) {
  return useQuery({
    queryKey: ['agents', 'search', query],
    queryFn: () => userPermissionsApi.searchAgents(query),
    enabled: query.length >= 2,
    staleTime: 30 * 1000, // 30 seconds
  })
}

/**
 * Grant permission to a user
 */
export function useGrantPermission() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ userId, data }: { userId: string; data: GrantUserPermissionRequest }) =>
      userPermissionsApi.grantPermission(userId, data),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: userPermissionsKeys.user(variables.userId) })
      queryClient.invalidateQueries({ queryKey: userPermissionsKeys.lists() })
    },
  })
}

/**
 * Revoke permission from a user
 */
export function useRevokePermission() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ userId, permissionId }: { userId: string; permissionId: string }) =>
      userPermissionsApi.revokePermission(userId, permissionId),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: userPermissionsKeys.user(variables.userId) })
      queryClient.invalidateQueries({ queryKey: userPermissionsKeys.lists() })
    },
  })
}

/**
 * Check if user has a specific permission
 */
export function useCheckPermission(userId: string | null, permissionName: string) {
  return useQuery({
    queryKey: [...userPermissionsKeys.user(userId || ''), 'check', permissionName],
    queryFn: () => userPermissionsApi.checkPermission(userId!, permissionName),
    enabled: !!userId && !!permissionName,
  })
}
