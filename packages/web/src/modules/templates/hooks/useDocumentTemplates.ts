/**
 * Document Templates Hooks
 * React Query hooks for document template operations
 *
 * @module templates/hooks
 */

'use client'

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { documentTemplatesApi } from '../services/api'
import type {

  DocumentTemplateCreate,
  DocumentTemplateUpdate,
} from '../types'

// Query keys
export const documentTemplatesKeys = {
  all: ['document-templates'] as const,
  lists: () => [...documentTemplatesKeys.all, 'list'] as const,
  list: (filters: Record<string, any>) =>
    [...documentTemplatesKeys.lists(), filters] as const,
  details: () => [...documentTemplatesKeys.all, 'detail'] as const,
  detail: (id: string | number) =>
    [...documentTemplatesKeys.details(), id] as const,
}

/**
 * Fetch all document templates with optional filters
 */
export function useDocumentTemplates(params?: {
  category?: string
  isActive?: boolean
  page?: number
  pageSize?: number
}) {
  return useQuery({
    queryKey: documentTemplatesKeys.list(params || {}),
    queryFn: () => documentTemplatesApi.list(params),
  })
}

/**
 * Fetch a single document template by ID
 */
export function useDocumentTemplate(templateId: string | number) {
  return useQuery({
    queryKey: documentTemplatesKeys.detail(templateId),
    queryFn: () => documentTemplatesApi.get(templateId),
    enabled: !!templateId,
  })
}

/**
 * Create a new document template
 */
export function useCreateDocumentTemplate() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (data: DocumentTemplateCreate) =>
      documentTemplatesApi.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: documentTemplatesKeys.lists(),
      })
    },
  })
}

/**
 * Update an existing document template
 */
export function useUpdateDocumentTemplate() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({
      id,
      data,
    }: {
      id: string | number
      data: DocumentTemplateUpdate
    }) => documentTemplatesApi.update(id, data),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({
        queryKey: documentTemplatesKeys.lists(),
      })
      queryClient.invalidateQueries({
        queryKey: documentTemplatesKeys.detail(variables.id),
      })
    },
  })
}

/**
 * Delete a document template
 */
export function useDeleteDocumentTemplate() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (id: string | number) => documentTemplatesApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: documentTemplatesKeys.lists(),
      })
    },
  })
}
