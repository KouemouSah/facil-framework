/**
 * useNotificationTemplates Hook
 * React Query hooks for notification template management
 */

import { useQuery, useMutation, useQueryClient, type UseQueryResult, type UseMutationResult } from '@tanstack/react-query'
import { toast } from 'sonner'
import { notificationTemplateApi } from '../services/notification-template-api'
import type {
  NotificationTemplateCreate,
  NotificationTemplateUpdate,
  NotificationTemplateResponse,
  NotificationTemplateListResponse,
  NotificationTemplateListParams,
  NotificationPreviewRequest,
  NotificationPreviewResponse,
} from '../types/notification-template'

const QUERY_KEYS = {
  all: ['notification-templates'] as const,
  lists: () => [...QUERY_KEYS.all, 'list'] as const,
  list: (params?: NotificationTemplateListParams) => [...QUERY_KEYS.lists(), params] as const,
  details: () => [...QUERY_KEYS.all, 'detail'] as const,
  detail: (id: number) => [...QUERY_KEYS.details(), id] as const,
  byCode: (code: string) => [...QUERY_KEYS.all, 'code', code] as const,
  active: () => [...QUERY_KEYS.all, 'active'] as const,
}

/**
 * Hook to list notification templates
 */
export function useNotificationTemplates(
  params?: NotificationTemplateListParams
): UseQueryResult<NotificationTemplateListResponse, Error> {
  return useQuery({
    queryKey: QUERY_KEYS.list(params),
    queryFn: () => notificationTemplateApi.list(params),
    staleTime: 5 * 60 * 1000, // 5 minutes
  })
}

/**
 * Hook to get notification template by ID
 */
export function useNotificationTemplate(
  id: number | undefined
): UseQueryResult<NotificationTemplateResponse, Error> {
  return useQuery({
    queryKey: QUERY_KEYS.detail(id!),
    queryFn: () => notificationTemplateApi.getById(id!),
    enabled: !!id,
    staleTime: 5 * 60 * 1000, // 5 minutes
  })
}

/**
 * Hook to get notification template by code
 */
export function useNotificationTemplateByCode(
  code: string | undefined
): UseQueryResult<NotificationTemplateResponse, Error> {
  return useQuery({
    queryKey: QUERY_KEYS.byCode(code!),
    queryFn: () => notificationTemplateApi.getByCode(code!),
    enabled: !!code,
    staleTime: 5 * 60 * 1000, // 5 minutes
  })
}

/**
 * Hook to get active notification templates
 */
export function useActiveNotificationTemplates(): UseQueryResult<
  NotificationTemplateResponse[],
  Error
> {
  return useQuery({
    queryKey: QUERY_KEYS.active(),
    queryFn: () => notificationTemplateApi.getActive(),
    staleTime: 5 * 60 * 1000, // 5 minutes
  })
}

/**
 * Hook to create notification template
 */
export function useCreateNotificationTemplate(): UseMutationResult<
  NotificationTemplateResponse,
  Error,
  NotificationTemplateCreate
> {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (data: NotificationTemplateCreate) => notificationTemplateApi.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.lists() })
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.active() })
      toast.success('Notification template created successfully')
    },
    onError: (error: Error) => {
      toast.error(`Failed to create notification template: ${error.message}`)
    },
  })
}

/**
 * Hook to update notification template
 */
export function useUpdateNotificationTemplate(): UseMutationResult<
  NotificationTemplateResponse,
  Error,
  { id: number; data: NotificationTemplateUpdate }
> {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: NotificationTemplateUpdate }) =>
      notificationTemplateApi.update(id, data),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.lists() })
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.detail(variables.id) })
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.active() })
      toast.success('Notification template updated successfully')
    },
    onError: (error: Error) => {
      toast.error(`Failed to update notification template: ${error.message}`)
    },
  })
}

/**
 * Hook to delete notification template
 */
export function useDeleteNotificationTemplate(): UseMutationResult<void, Error, number> {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (id: number) => notificationTemplateApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.lists() })
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.active() })
      toast.success('Notification template deleted successfully')
    },
    onError: (error: Error) => {
      toast.error(`Failed to delete notification template: ${error.message}`)
    },
  })
}

/**
 * Hook to preview notification
 */
export function usePreviewNotification(): UseMutationResult<
  NotificationPreviewResponse,
  Error,
  NotificationPreviewRequest
> {
  return useMutation({
    mutationFn: (request: NotificationPreviewRequest) => notificationTemplateApi.preview(request),
    onError: (error: Error) => {
      toast.error(`Failed to preview notification: ${error.message}`)
    },
  })
}
