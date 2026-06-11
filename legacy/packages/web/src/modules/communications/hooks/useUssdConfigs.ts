/**
 * useUssdConfigs Hook
 * React Query hooks for managing USSD configurations
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useToast } from '@/hooks/use-toast'
import { ussdApi } from '../services/api'
import type {
  UssdConfigCreate,
  UssdConfigUpdate,
  UssdConfigListParams,
  MenuNode,
  MenuValidationResult,
} from '../types'

// Query keys
export const ussdQueryKeys = {
  all: ['ussd-configs'] as const,
  lists: () => [...ussdQueryKeys.all, 'list'] as const,
  list: (params?: UssdConfigListParams) => [...ussdQueryKeys.lists(), params] as const,
  details: () => [...ussdQueryKeys.all, 'detail'] as const,
  detail: (id: number) => [...ussdQueryKeys.details(), id] as const,
  byOperator: (operator: string) => [...ussdQueryKeys.all, 'operator', operator] as const,
  operators: () => [...ussdQueryKeys.all, 'operators'] as const,
}

/**
 * Hook to list USSD configurations
 */
export function useUssdConfigs(params?: UssdConfigListParams) {
  return useQuery({
    queryKey: ussdQueryKeys.list(params),
    queryFn: () => ussdApi.list(params),
    staleTime: 5 * 60 * 1000, // 5 minutes
  })
}

/**
 * Hook to get single USSD configuration
 */
export function useUssdConfig(configId: number | undefined) {
  return useQuery({
    queryKey: ussdQueryKeys.detail(configId!),
    queryFn: () => ussdApi.get(configId!),
    enabled: !!configId,
    staleTime: 5 * 60 * 1000,
  })
}

/**
 * Hook to get USSD configuration by operator
 */
export function useUssdConfigByOperator(operator: string | undefined) {
  return useQuery({
    queryKey: ussdQueryKeys.byOperator(operator!),
    queryFn: () => ussdApi.getByOperator(operator!),
    enabled: !!operator,
    staleTime: 5 * 60 * 1000,
  })
}

/**
 * Hook to list available operators
 */
export function useUssdOperators() {
  return useQuery({
    queryKey: ussdQueryKeys.operators(),
    queryFn: () => ussdApi.listOperators(),
    staleTime: 60 * 60 * 1000, // 1 hour (rarely changes)
  })
}

/**
 * Hook to create USSD configuration
 */
export function useCreateUssdConfig() {
  const queryClient = useQueryClient()
  const { toast } = useToast()

  return useMutation({
    mutationFn: (data: UssdConfigCreate) => ussdApi.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ussdQueryKeys.lists() })
      toast({
        title: 'Success',
        description: 'USSD configuration created successfully',
      })
    },
    onError: (error: Error) => {
      toast({
        title: 'Error',
        description: error.message || 'Failed to create USSD configuration',
        variant: 'destructive',
      })
    },
  })
}

/**
 * Hook to update USSD configuration
 */
export function useUpdateUssdConfig() {
  const queryClient = useQueryClient()
  const { toast } = useToast()

  return useMutation({
    mutationFn: ({ configId, data }: { configId: number; data: UssdConfigUpdate }) =>
      ussdApi.update(configId, data),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ussdQueryKeys.detail(variables.configId) })
      queryClient.invalidateQueries({ queryKey: ussdQueryKeys.lists() })
      toast({
        title: 'Success',
        description: 'USSD configuration updated successfully',
      })
    },
    onError: (error: Error) => {
      toast({
        title: 'Error',
        description: error.message || 'Failed to update USSD configuration',
        variant: 'destructive',
      })
    },
  })
}

/**
 * Hook to delete USSD configuration
 */
export function useDeleteUssdConfig() {
  const queryClient = useQueryClient()
  const { toast } = useToast()

  return useMutation({
    mutationFn: (configId: number) => ussdApi.delete(configId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ussdQueryKeys.lists() })
      toast({
        title: 'Success',
        description: 'USSD configuration deleted successfully',
      })
    },
    onError: (error: Error) => {
      toast({
        title: 'Error',
        description: error.message || 'Failed to delete USSD configuration',
        variant: 'destructive',
      })
    },
  })
}

/**
 * Hook to validate menu structure
 */
export function useValidateUssdMenu() {
  const { toast } = useToast()

  return useMutation({
    mutationFn: (menuStructure: MenuNode[]) => ussdApi.validateMenu(menuStructure),
    onSuccess: (result: MenuValidationResult) => {
      if (result.isValid) {
        toast({
          title: 'Validation Successful',
          description: `Menu structure is valid (${result.menuCount} menus, ${result.optionCount} options, max depth: ${result.maxDepth})`,
        })
      } else {
        toast({
          title: 'Validation Failed',
          description: `Found ${result.errors.length} errors`,
          variant: 'destructive',
        })
      }
    },
    onError: (error: Error) => {
      toast({
        title: 'Validation Error',
        description: error.message || 'Failed to validate menu structure',
        variant: 'destructive',
      })
    },
  })
}
