/**
 * Email Templates React Query Hooks
 * Custom hooks for email template data fetching and mutations
 */

import { useQuery, useMutation, useQueryClient, type UseQueryResult, type UseMutationResult } from '@tanstack/react-query'
import { emailTemplatesApi } from '../services/api'
import type {
  EmailTemplateCreate,
  EmailTemplateUpdate,
  EmailTemplateResponse,
  EmailTemplateListResponse,
  EmailTemplatePreview,
  EmailTemplateListParams,
  EmailTemplateSearchParams,
} from '../types'

// =============================================================================
// QUERY KEYS
// =============================================================================

export const emailTemplateKeys = {
  all: ['email-templates'] as const,
  lists: () => [...emailTemplateKeys.all, 'list'] as const,
  list: (params?: EmailTemplateListParams) => [...emailTemplateKeys.lists(), params] as const,
  searches: () => [...emailTemplateKeys.all, 'search'] as const,
  search: (params: EmailTemplateSearchParams) => [...emailTemplateKeys.searches(), params] as const,
  details: () => [...emailTemplateKeys.all, 'detail'] as const,
  detail: (id: number) => [...emailTemplateKeys.details(), id] as const,
  preview: (id: number) => [...emailTemplateKeys.all, 'preview', id] as const,
}

// =============================================================================
// QUERY HOOKS
// =============================================================================

/**
 * Hook to list email templates with pagination and filters
 */
export function useEmailTemplates(
  params?: EmailTemplateListParams
): UseQueryResult<EmailTemplateListResponse, Error> {
  return useQuery({
    queryKey: emailTemplateKeys.list(params),
    queryFn: () => emailTemplatesApi.list(params),
    staleTime: 5 * 60 * 1000, // 5 minutes
  })
}

/**
 * Hook to search email templates
 */
export function useSearchEmailTemplates(
  params: EmailTemplateSearchParams,
  enabled: boolean = true
): UseQueryResult<EmailTemplateListResponse, Error> {
  return useQuery({
    queryKey: emailTemplateKeys.search(params),
    queryFn: () => emailTemplatesApi.search(params),
    enabled: enabled && !!params.q,
    staleTime: 2 * 60 * 1000, // 2 minutes
  })
}

/**
 * Hook to get a single email template by ID
 */
export function useEmailTemplate(
  templateId: number,
  enabled: boolean = true
): UseQueryResult<EmailTemplateResponse, Error> {
  return useQuery({
    queryKey: emailTemplateKeys.detail(templateId),
    queryFn: () => emailTemplatesApi.get(templateId),
    enabled: enabled && templateId > 0,
    staleTime: 5 * 60 * 1000, // 5 minutes
  })
}

/**
 * Hook to get email template HTML preview
 */
export function useEmailTemplatePreview(
  templateId: number,
  enabled: boolean = true
): UseQueryResult<EmailTemplatePreview, Error> {
  return useQuery({
    queryKey: emailTemplateKeys.preview(templateId),
    queryFn: () => emailTemplatesApi.preview(templateId),
    enabled: enabled && templateId > 0,
    staleTime: 10 * 60 * 1000, // 10 minutes
  })
}

// =============================================================================
// MUTATION HOOKS
// =============================================================================

/**
 * Hook to create a new email template
 */
export function useCreateEmailTemplate(): UseMutationResult<
  EmailTemplateResponse,
  Error,
  EmailTemplateCreate
> {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (data: EmailTemplateCreate) => emailTemplatesApi.create(data),
    onSuccess: () => {
      // Invalidate all lists to refetch
      queryClient.invalidateQueries({ queryKey: emailTemplateKeys.lists() })
    },
  })
}

/**
 * Hook to update an email template
 */
export function useUpdateEmailTemplate(): UseMutationResult<
  EmailTemplateResponse,
  Error,
  { templateId: number; data: EmailTemplateUpdate }
> {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ templateId, data }) => emailTemplatesApi.update(templateId, data),
    onSuccess: (_, { templateId }) => {
      // Invalidate the specific template and all lists
      queryClient.invalidateQueries({ queryKey: emailTemplateKeys.detail(templateId) })
      queryClient.invalidateQueries({ queryKey: emailTemplateKeys.preview(templateId) })
      queryClient.invalidateQueries({ queryKey: emailTemplateKeys.lists() })
    },
  })
}

/**
 * Hook to delete an email template
 */
export function useDeleteEmailTemplate(): UseMutationResult<
  void,
  Error,
  number
> {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (templateId: number) => emailTemplatesApi.delete(templateId),
    onSuccess: (_, templateId) => {
      // Invalidate all lists and remove the specific template from cache
      queryClient.invalidateQueries({ queryKey: emailTemplateKeys.lists() })
      queryClient.removeQueries({ queryKey: emailTemplateKeys.detail(templateId) })
      queryClient.removeQueries({ queryKey: emailTemplateKeys.preview(templateId) })
    },
  })
}
