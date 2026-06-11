/**
 * Company Members Hooks
 * React Query hooks for company member management operations
 *
 * @module companies/hooks
 * @author Claude Code
 * @date 2025-12-03
 */

'use client'

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { companyMembersApi } from '../services/api'
import type { CompanyMember, CompanyMemberRole } from '../types'
import { toast } from 'sonner'

// =============================================================================
// QUERY KEYS
// =============================================================================

export const companyMembersKeys = {
  all: ['company-members'] as const,
  lists: () => [...companyMembersKeys.all, 'list'] as const,
  list: (companyId: string) => [...companyMembersKeys.lists(), companyId] as const,
}

// =============================================================================
// HOOKS
// =============================================================================

/**
 * Fetch all members for a company
 */
export function useCompanyMembers(companyId: string) {
  return useQuery({
    queryKey: companyMembersKeys.list(companyId),
    queryFn: () => companyMembersApi.getAll(companyId),
    enabled: !!companyId,
  })
}

/**
 * Add member to company
 * Includes optimistic update
 */
export function useAddCompanyMember(companyId: string) {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({
      memberUserId,
      role,
    }: {
      memberUserId: string
      role: CompanyMemberRole
    }) => companyMembersApi.add(companyId, memberUserId, role),

    // Optimistic update
    onMutate: async ({ memberUserId, role }) => {
      // Cancel outgoing refetches
      await queryClient.cancelQueries({
        queryKey: companyMembersKeys.list(companyId),
      })

      // Snapshot previous value
      const previousMembers = queryClient.getQueryData<CompanyMember[]>(
        companyMembersKeys.list(companyId)
      )

      // Optimistically update
      if (previousMembers) {
        const optimisticMember: CompanyMember = {
          user_id: memberUserId,
          company_id: companyId,
          role,
          is_active: true,
          assigned_at: new Date().toISOString(),
        }

        queryClient.setQueryData<CompanyMember[]>(
          companyMembersKeys.list(companyId),
          [...previousMembers, optimisticMember]
        )
      }

      return { previousMembers }
    },

    onError: (error, _variables, context) => {
      // Rollback on error
      if (context?.previousMembers) {
        queryClient.setQueryData(
          companyMembersKeys.list(companyId),
          context.previousMembers
        )
      }
      toast.error('Failed to add member', {
        description: error instanceof Error ? error.message : 'Unknown error',
      })
    },

    onSuccess: () => {
      // Invalidate to ensure data consistency
      queryClient.invalidateQueries({
        queryKey: companyMembersKeys.list(companyId),
      })
      toast.success('Member added successfully')
    },
  })
}

/**
 * Remove member from company
 * Includes optimistic update
 */
export function useRemoveCompanyMember(companyId: string) {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (userId: string) => companyMembersApi.remove(companyId, userId),

    // Optimistic update
    onMutate: async (userId) => {
      // Cancel outgoing refetches
      await queryClient.cancelQueries({
        queryKey: companyMembersKeys.list(companyId),
      })

      // Snapshot previous value
      const previousMembers = queryClient.getQueryData<CompanyMember[]>(
        companyMembersKeys.list(companyId)
      )

      // Optimistically remove member
      if (previousMembers) {
        queryClient.setQueryData<CompanyMember[]>(
          companyMembersKeys.list(companyId),
          previousMembers.filter((member) => member.user_id !== userId)
        )
      }

      return { previousMembers }
    },

    onError: (error, _variables, context) => {
      // Rollback on error
      if (context?.previousMembers) {
        queryClient.setQueryData(
          companyMembersKeys.list(companyId),
          context.previousMembers
        )
      }
      toast.error('Failed to remove member', {
        description: error instanceof Error ? error.message : 'Unknown error',
      })
    },

    onSuccess: () => {
      // Invalidate to ensure data consistency
      queryClient.invalidateQueries({
        queryKey: companyMembersKeys.list(companyId),
      })
      toast.success('Member removed successfully')
    },
  })
}

/**
 * Update member role
 * Includes optimistic update
 * NOTE: Backend endpoint not yet implemented, will throw error
 */
export function useUpdateMemberRole(companyId: string) {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({
      userId,
      role,
    }: {
      userId: string
      role: CompanyMemberRole
    }) => companyMembersApi.updateRole(companyId, userId, role),

    // Optimistic update
    onMutate: async ({ userId, role }) => {
      // Cancel outgoing refetches
      await queryClient.cancelQueries({
        queryKey: companyMembersKeys.list(companyId),
      })

      // Snapshot previous value
      const previousMembers = queryClient.getQueryData<CompanyMember[]>(
        companyMembersKeys.list(companyId)
      )

      // Optimistically update role
      if (previousMembers) {
        queryClient.setQueryData<CompanyMember[]>(
          companyMembersKeys.list(companyId),
          previousMembers.map((member) =>
            member.user_id === userId ? { ...member, role } : member
          )
        )
      }

      return { previousMembers }
    },

    onError: (error, _variables, context) => {
      // Rollback on error
      if (context?.previousMembers) {
        queryClient.setQueryData(
          companyMembersKeys.list(companyId),
          context.previousMembers
        )
      }
      toast.error('Failed to update member role', {
        description: error instanceof Error ? error.message : 'Unknown error',
      })
    },

    onSuccess: () => {
      // Invalidate to ensure data consistency
      queryClient.invalidateQueries({
        queryKey: companyMembersKeys.list(companyId),
      })
      toast.success('Member role updated successfully')
    },
  })
}
