/**
 * Procedure Templates Hooks
 * React Query hooks for procedure template operations
 *
 * @module templates/hooks
 */

'use client'

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { procedureTemplatesApi, procedureStepsApi } from '../services/api'
import type {

  ProcedureTemplateCreate,
  ProcedureTemplateUpdate,


} from '../types'

// Query keys
export const procedureTemplatesKeys = {
  all: ['procedure-templates'] as const,
  lists: () => [...procedureTemplatesKeys.all, 'list'] as const,
  list: (filters: Record<string, any>) =>
    [...procedureTemplatesKeys.lists(), filters] as const,
  details: () => [...procedureTemplatesKeys.all, 'detail'] as const,
  detail: (id: string | number) =>
    [...procedureTemplatesKeys.details(), id] as const,
  steps: (templateId: string | number) =>
    [...procedureTemplatesKeys.detail(templateId), 'steps'] as const,
}

/**
 * Fetch all procedure templates with optional filters
 */
export function useProcedureTemplates(params?: {
  category?: string
  isActive?: boolean
  page?: number
  pageSize?: number
}) {
  return useQuery({
    queryKey: procedureTemplatesKeys.list(params || {}),
    queryFn: () => procedureTemplatesApi.list(params),
  })
}

/**
 * Fetch a single procedure template by ID
 */
export function useProcedureTemplate(templateId: string | number) {
  return useQuery({
    queryKey: procedureTemplatesKeys.detail(templateId),
    queryFn: () => procedureTemplatesApi.get(templateId),
    enabled: !!templateId,
  })
}

/**
 * Create a new procedure template
 */
export function useCreateProcedureTemplate() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (data: ProcedureTemplateCreate) =>
      procedureTemplatesApi.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: procedureTemplatesKeys.lists(),
      })
    },
  })
}

/**
 * Update an existing procedure template
 */
export function useUpdateProcedureTemplate() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({
      id,
      data,
    }: {
      id: string | number
      data: ProcedureTemplateUpdate
    }) => procedureTemplatesApi.update(id, data),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({
        queryKey: procedureTemplatesKeys.lists(),
      })
      queryClient.invalidateQueries({
        queryKey: procedureTemplatesKeys.detail(variables.id),
      })
    },
  })
}

/**
 * Delete a procedure template
 */
export function useDeleteProcedureTemplate() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (id: string | number) => procedureTemplatesApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: procedureTemplatesKeys.lists(),
      })
    },
  })
}

/**
 * Fetch procedure steps for a template
 */
export function useProcedureSteps(templateId: string | number) {
  return useQuery({
    queryKey: procedureTemplatesKeys.steps(templateId),
    queryFn: () => procedureStepsApi.list(templateId),
    enabled: !!templateId,
  })
}

/**
 * Reorder procedure steps
 */
export function useReorderProcedureSteps() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({
      templateId,
      stepIds,
    }: {
      templateId: string | number
      stepIds: number[]
    }) => procedureStepsApi.reorder(templateId, stepIds),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({
        queryKey: procedureTemplatesKeys.steps(variables.templateId),
      })
    },
  })
}
