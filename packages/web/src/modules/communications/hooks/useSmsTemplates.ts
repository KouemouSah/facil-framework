/**
 * useSmsTemplates Hook
 * React Query hooks for SMS templates management
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useToast } from '@/hooks/use-toast'
import { smsTemplatesApi } from '../services/api'
import type {
  SmsTemplateCreate,
  SmsTemplateUpdate,
  SmsTemplateListParams,
  SmsTemplateRenderRequest,
} from '../types'

// Query keys
export const SMS_TEMPLATES_KEYS = {
  all: ['sms-templates'] as const,
  lists: () => [...SMS_TEMPLATES_KEYS.all, 'list'] as const,
  list: (params?: SmsTemplateListParams) => [...SMS_TEMPLATES_KEYS.lists(), params] as const,
  details: () => [...SMS_TEMPLATES_KEYS.all, 'detail'] as const,
  detail: (id: number) => [...SMS_TEMPLATES_KEYS.details(), id] as const,
  byCode: (code: string) => [...SMS_TEMPLATES_KEYS.all, 'code', code] as const,
  categories: () => [...SMS_TEMPLATES_KEYS.all, 'categories'] as const,
}

/**
 * Hook to list SMS templates with pagination and filters
 */
export function useSmsTemplatesList(params?: SmsTemplateListParams) {
  return useQuery({
    queryKey: SMS_TEMPLATES_KEYS.list(params),
    queryFn: () => smsTemplatesApi.list(params),
    staleTime: 5 * 60 * 1000, // 5 minutes
  })
}

/**
 * Hook to get a single SMS template by ID
 */
export function useSmsTemplate(templateId: number | null) {
  return useQuery({
    queryKey: SMS_TEMPLATES_KEYS.detail(templateId!),
    queryFn: () => smsTemplatesApi.get(templateId!),
    enabled: templateId !== null && templateId > 0,
    staleTime: 5 * 60 * 1000,
  })
}

/**
 * Hook to get SMS template by code
 */
export function useSmsTemplateByCode(code: string | null) {
  return useQuery({
    queryKey: SMS_TEMPLATES_KEYS.byCode(code!),
    queryFn: () => smsTemplatesApi.getByCode(code!),
    enabled: code !== null && code.length > 0,
    staleTime: 5 * 60 * 1000,
  })
}

/**
 * Hook to get SMS template categories with counts
 */
export function useSmsTemplateCategories() {
  return useQuery({
    queryKey: SMS_TEMPLATES_KEYS.categories(),
    queryFn: () => smsTemplatesApi.getCategories(),
    staleTime: 10 * 60 * 1000, // 10 minutes
  })
}

/**
 * Hook to create a new SMS template
 */
export function useCreateSmsTemplate() {
  const queryClient = useQueryClient()
  const { toast } = useToast()

  return useMutation({
    mutationFn: (data: SmsTemplateCreate) => smsTemplatesApi.create(data),
    onSuccess: () => {
      // Invalidate all lists
      queryClient.invalidateQueries({ queryKey: SMS_TEMPLATES_KEYS.lists() })
      queryClient.invalidateQueries({ queryKey: SMS_TEMPLATES_KEYS.categories() })

      toast({
        title: 'Success',
        description: 'SMS template created successfully',
      })
    },
    onError: (error: Error) => {
      toast({
        title: 'Error',
        description: error.message || 'Failed to create SMS template',
        variant: 'destructive',
      })
    },
  })
}

/**
 * Hook to update an SMS template
 */
export function useUpdateSmsTemplate() {
  const queryClient = useQueryClient()
  const { toast } = useToast()

  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: SmsTemplateUpdate }) =>
      smsTemplatesApi.update(id, data),
    onSuccess: (_, variables) => {
      // Invalidate specific template and all lists
      queryClient.invalidateQueries({ queryKey: SMS_TEMPLATES_KEYS.detail(variables.id) })
      queryClient.invalidateQueries({ queryKey: SMS_TEMPLATES_KEYS.lists() })
      queryClient.invalidateQueries({ queryKey: SMS_TEMPLATES_KEYS.categories() })

      toast({
        title: 'Success',
        description: 'SMS template updated successfully',
      })
    },
    onError: (error: Error) => {
      toast({
        title: 'Error',
        description: error.message || 'Failed to update SMS template',
        variant: 'destructive',
      })
    },
  })
}

/**
 * Hook to delete an SMS template
 */
export function useDeleteSmsTemplate() {
  const queryClient = useQueryClient()
  const { toast } = useToast()

  return useMutation({
    mutationFn: (templateId: number) => smsTemplatesApi.delete(templateId),
    onSuccess: (_, templateId) => {
      // Remove from cache and invalidate lists
      queryClient.removeQueries({ queryKey: SMS_TEMPLATES_KEYS.detail(templateId) })
      queryClient.invalidateQueries({ queryKey: SMS_TEMPLATES_KEYS.lists() })
      queryClient.invalidateQueries({ queryKey: SMS_TEMPLATES_KEYS.categories() })

      toast({
        title: 'Success',
        description: 'SMS template deleted successfully',
      })
    },
    onError: (error: Error) => {
      toast({
        title: 'Error',
        description: error.message || 'Failed to delete SMS template',
        variant: 'destructive',
      })
    },
  })
}

/**
 * Hook to render SMS template with variables (preview)
 */
export function useRenderSmsTemplate() {
  const { toast } = useToast()

  return useMutation({
    mutationFn: (request: SmsTemplateRenderRequest) => smsTemplatesApi.render(request),
    onError: (error: Error) => {
      toast({
        title: 'Error',
        description: error.message || 'Failed to render SMS template',
        variant: 'destructive',
      })
    },
  })
}

/**
 * Hook to calculate character count for SMS content
 */
export function useCalculateSmsChars() {
  return useMutation({
    mutationFn: (content: string) => smsTemplatesApi.calculateChars(content),
  })
}
