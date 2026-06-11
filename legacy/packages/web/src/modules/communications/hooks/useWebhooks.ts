/**
 * useWebhooks Hook
 * React Query hooks for webhook configurations management
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { webhooksApi } from '../services/api'
import type {
  WebhookCreate,
  WebhookUpdate,
  WebhookListParams,
  WebhookTestRequest,
  WebhookLogParams,
} from '../types'

// =============================================================================
// QUERY KEYS
// =============================================================================

export const webhookKeys = {
  all: ['webhooks'] as const,
  lists: () => [...webhookKeys.all, 'list'] as const,
  list: (params?: WebhookListParams) => [...webhookKeys.lists(), params] as const,
  details: () => [...webhookKeys.all, 'detail'] as const,
  detail: (id: number) => [...webhookKeys.details(), id] as const,
  logs: (id: number, params?: WebhookLogParams) => [...webhookKeys.detail(id), 'logs', params] as const,
}

// =============================================================================
// QUERY HOOKS
// =============================================================================

/**
 * Hook to fetch list of webhooks
 */
export function useWebhooks(params?: WebhookListParams) {
  return useQuery({
    queryKey: webhookKeys.list(params),
    queryFn: () => webhooksApi.list(params),
    staleTime: 1000 * 60 * 5, // 5 minutes
  })
}

/**
 * Hook to fetch single webhook by ID
 */
export function useWebhook(webhookId: number) {
  return useQuery({
    queryKey: webhookKeys.detail(webhookId),
    queryFn: () => webhooksApi.get(webhookId),
    enabled: !!webhookId,
    staleTime: 1000 * 60 * 5, // 5 minutes
  })
}

/**
 * Hook to fetch webhook execution logs
 */
export function useWebhookLogs(webhookId: number, params?: WebhookLogParams) {
  return useQuery({
    queryKey: webhookKeys.logs(webhookId, params),
    queryFn: () => webhooksApi.logs(webhookId, params),
    enabled: !!webhookId,
    staleTime: 1000 * 30, // 30 seconds (logs are more dynamic)
  })
}

// =============================================================================
// MUTATION HOOKS
// =============================================================================

/**
 * Hook to create new webhook
 */
export function useCreateWebhook() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (data: WebhookCreate) => webhooksApi.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: webhookKeys.lists() })
      toast.success('Webhook created successfully')
    },
    onError: (error: Error) => {
      toast.error(`Failed to create webhook: ${error.message}`)
    },
  })
}

/**
 * Hook to update webhook
 */
export function useUpdateWebhook() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: WebhookUpdate }) =>
      webhooksApi.update(id, data),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: webhookKeys.lists() })
      queryClient.invalidateQueries({ queryKey: webhookKeys.detail(variables.id) })
      toast.success('Webhook updated successfully')
    },
    onError: (error: Error) => {
      toast.error(`Failed to update webhook: ${error.message}`)
    },
  })
}

/**
 * Hook to delete webhook
 */
export function useDeleteWebhook() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (webhookId: number) => webhooksApi.delete(webhookId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: webhookKeys.lists() })
      toast.success('Webhook deleted successfully')
    },
    onError: (error: Error) => {
      toast.error(`Failed to delete webhook: ${error.message}`)
    },
  })
}

/**
 * Hook to test webhook
 */
export function useTestWebhook() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: WebhookTestRequest }) =>
      webhooksApi.test(id, data),
    onSuccess: (result, variables) => {
      // Invalidate logs to show the new test execution
      queryClient.invalidateQueries({ queryKey: webhookKeys.logs(variables.id) })
      queryClient.invalidateQueries({ queryKey: webhookKeys.detail(variables.id) })

      if (result.success) {
        toast.success(`Webhook test successful (${result.statusCode})`)
      } else {
        toast.error(`Webhook test failed: ${result.errorMessage || 'Unknown error'}`)
      }
    },
    onError: (error: Error) => {
      toast.error(`Failed to test webhook: ${error.message}`)
    },
  })
}

// =============================================================================
// UTILITY HOOKS
// =============================================================================

/**
 * Hook to toggle webhook active status
 */
export function useToggleWebhook() {
  const updateMutation = useUpdateWebhook()

  return {
    toggle: (id: number, currentStatus: boolean) => {
      return updateMutation.mutate({
        id,
        data: { isActive: !currentStatus },
      })
    },
    isLoading: updateMutation.isPending,
  }
}
