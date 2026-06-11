/**
 * Users Hooks
 * React Query hooks for user management operations
 *
 * @module users-admin/hooks
 */

'use client'

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { usersApi } from '../services/api'
import type {

  CreateUserRequest,
  UpdateUserRequest,
  UserRole,
} from '../types'

// Query keys
export const usersKeys = {
  all: ['users'] as const,
  lists: () => [...usersKeys.all, 'list'] as const,
  list: (filters: Record<string, any>) =>
    [...usersKeys.lists(), filters] as const,
  details: () => [...usersKeys.all, 'detail'] as const,
  detail: (id: string) => [...usersKeys.details(), id] as const,
  search: (query: string) => [...usersKeys.all, 'search', query] as const,
  stats: () => [...usersKeys.all, 'stats'] as const,
  activities: (userId: string) =>
    [...usersKeys.detail(userId), 'activities'] as const,
}

/**
 * Fetch all users with optional filters
 */
export function useUsers(params?: {
  role?: UserRole
  status?: string
  search?: string
  page?: number
  size?: number
}) {
  return useQuery({
    queryKey: usersKeys.list(params || {}),
    queryFn: () => usersApi.getAll(params),
  })
}

/**
 * Fetch a single user by ID
 */
export function useUser(id: string) {
  return useQuery({
    queryKey: usersKeys.detail(id),
    queryFn: () => usersApi.getById(id),
    enabled: !!id,
  })
}

/**
 * Create a new user
 */
export function useCreateUser() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (data: CreateUserRequest) => usersApi.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: usersKeys.lists() })
      queryClient.invalidateQueries({ queryKey: usersKeys.stats() })
    },
  })
}

/**
 * Update an existing user
 */
export function useUpdateUser() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: UpdateUserRequest }) =>
      usersApi.update(id, data),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: usersKeys.lists() })
      queryClient.invalidateQueries({
        queryKey: usersKeys.detail(variables.id),
      })
    },
  })
}

/**
 * Delete a user
 */
export function useDeleteUser() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (id: string) => usersApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: usersKeys.lists() })
      queryClient.invalidateQueries({ queryKey: usersKeys.stats() })
    },
  })
}

/**
 * Set user active/inactive status
 */
export function useSetUserActive() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ id, isActive }: { id: string; isActive: boolean }) =>
      usersApi.setActive(id, isActive),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: usersKeys.lists() })
      queryClient.invalidateQueries({
        queryKey: usersKeys.detail(variables.id),
      })
    },
  })
}

/**
 * Search users
 */
export function useSearchUsers(params?: {
  q?: string
  role?: UserRole
  status?: string
  country?: string
  limit?: number
}) {
  return useQuery({
    queryKey: usersKeys.search(JSON.stringify(params)),
    queryFn: () => usersApi.search(params),
    enabled: !!params?.q && params.q.length >= 2,
  })
}

/**
 * Get user statistics
 */
export function useUserStats() {
  return useQuery({
    queryKey: usersKeys.stats(),
    queryFn: () => usersApi.getStats(),
  })
}

/**
 * Get user activity history
 */
export function useUserActivities(userId: string, limit: number = 50) {
  return useQuery({
    queryKey: usersKeys.activities(userId),
    queryFn: () => usersApi.getActivities(userId, limit),
    enabled: !!userId,
  })
}
