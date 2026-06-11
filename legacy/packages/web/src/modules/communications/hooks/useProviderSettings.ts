/**
 * useProviderSettings Hook
 * React Query hooks for communication provider settings management
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useToast } from '@/hooks/use-toast'
import { providerSettingsApi } from '../services/api'
import type {
  ProviderSettingsCreate,
  ProviderSettingsUpdate,
  ProviderSettingsListParams,
  ProviderTestRequest,
  CommunicationProviderType,
} from '../types'

// Query keys
export const PROVIDER_SETTINGS_KEYS = {
  all: ['provider-settings'] as const,
  lists: () => [...PROVIDER_SETTINGS_KEYS.all, 'list'] as const,
  list: (params?: ProviderSettingsListParams) => [...PROVIDER_SETTINGS_KEYS.lists(), params] as const,
  details: () => [...PROVIDER_SETTINGS_KEYS.all, 'detail'] as const,
  detail: (id: number) => [...PROVIDER_SETTINGS_KEYS.details(), id] as const,
  byCode: (code: string) => [...PROVIDER_SETTINGS_KEYS.all, 'code', code] as const,
  defaultByType: (type: CommunicationProviderType) => [...PROVIDER_SETTINGS_KEYS.all, 'default', type] as const,
}

/**
 * Hook to list provider settings with filters
 */
export function useProviderSettingsList(params?: ProviderSettingsListParams) {
  return useQuery({
    queryKey: PROVIDER_SETTINGS_KEYS.list(params),
    queryFn: () => providerSettingsApi.list(params),
    staleTime: 5 * 60 * 1000, // 5 minutes
  })
}

/**
 * Hook to get a single provider by ID
 */
export function useProviderSettings(providerId: number | null) {
  return useQuery({
    queryKey: PROVIDER_SETTINGS_KEYS.detail(providerId!),
    queryFn: () => providerSettingsApi.get(providerId!),
    enabled: providerId !== null && providerId > 0,
    staleTime: 5 * 60 * 1000,
  })
}

/**
 * Hook to get provider by code
 */
export function useProviderSettingsByCode(code: string | null) {
  return useQuery({
    queryKey: PROVIDER_SETTINGS_KEYS.byCode(code!),
    queryFn: () => providerSettingsApi.getByCode(code!),
    enabled: code !== null && code.length > 0,
    staleTime: 5 * 60 * 1000,
  })
}

/**
 * Hook to get default provider for a type
 */
export function useDefaultProvider(providerType: CommunicationProviderType | null) {
  return useQuery({
    queryKey: PROVIDER_SETTINGS_KEYS.defaultByType(providerType!),
    queryFn: () => providerSettingsApi.getDefault(providerType!),
    enabled: providerType !== null,
    staleTime: 5 * 60 * 1000,
  })
}

/**
 * Hook to create a new provider configuration
 */
export function useCreateProviderSettings() {
  const queryClient = useQueryClient()
  const { toast } = useToast()

  return useMutation({
    mutationFn: (data: ProviderSettingsCreate) => providerSettingsApi.create(data),
    onSuccess: () => {
      // Invalidate all lists
      queryClient.invalidateQueries({ queryKey: PROVIDER_SETTINGS_KEYS.lists() })

      toast({
        title: 'Success',
        description: 'Provider configuration created successfully',
      })
    },
    onError: (error: Error) => {
      toast({
        title: 'Error',
        description: error.message || 'Failed to create provider configuration',
        variant: 'destructive',
      })
    },
  })
}

/**
 * Hook to update a provider configuration
 */
export function useUpdateProviderSettings() {
  const queryClient = useQueryClient()
  const { toast } = useToast()

  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: ProviderSettingsUpdate }) =>
      providerSettingsApi.update(id, data),
    onSuccess: (_, variables) => {
      // Invalidate specific provider and all lists
      queryClient.invalidateQueries({ queryKey: PROVIDER_SETTINGS_KEYS.detail(variables.id) })
      queryClient.invalidateQueries({ queryKey: PROVIDER_SETTINGS_KEYS.lists() })

      toast({
        title: 'Success',
        description: 'Provider configuration updated successfully',
      })
    },
    onError: (error: Error) => {
      toast({
        title: 'Error',
        description: error.message || 'Failed to update provider configuration',
        variant: 'destructive',
      })
    },
  })
}

/**
 * Hook to delete a provider configuration
 */
export function useDeleteProviderSettings() {
  const queryClient = useQueryClient()
  const { toast } = useToast()

  return useMutation({
    mutationFn: (providerId: number) => providerSettingsApi.delete(providerId),
    onSuccess: (_, providerId) => {
      // Remove from cache and invalidate lists
      queryClient.removeQueries({ queryKey: PROVIDER_SETTINGS_KEYS.detail(providerId) })
      queryClient.invalidateQueries({ queryKey: PROVIDER_SETTINGS_KEYS.lists() })

      toast({
        title: 'Success',
        description: 'Provider configuration deleted successfully',
      })
    },
    onError: (error: Error) => {
      toast({
        title: 'Error',
        description: error.message || 'Failed to delete provider configuration',
        variant: 'destructive',
      })
    },
  })
}

/**
 * Hook to test provider connection
 */
export function useTestProviderConnection() {
  const { toast } = useToast()

  return useMutation({
    mutationFn: (request: ProviderTestRequest) => providerSettingsApi.test(request),
    onSuccess: (result) => {
      if (result.success) {
        toast({
          title: 'Connection Successful',
          description: result.message,
        })
      } else {
        toast({
          title: 'Connection Failed',
          description: result.message,
          variant: 'destructive',
        })
      }
    },
    onError: (error: Error) => {
      toast({
        title: 'Error',
        description: error.message || 'Failed to test provider connection',
        variant: 'destructive',
      })
    },
  })
}
