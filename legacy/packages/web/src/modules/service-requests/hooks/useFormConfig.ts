/**
 * React Query hooks for fetching dynamic form configuration
 *
 * Two variants:
 * 1. useFormConfig - For legacy wizard (uses requestId)
 *    GET /service-requests/{request_id}/form-config/{step_id}
 *
 * 2. useSessionFormConfig - For cache-first wizard (uses sessionId)
 *    GET /wizard-sessions/{session_id}/form-config/{step_id}
 *
 * The backend evaluates conditions and returns only the relevant
 * sections based on the request context (solicitud_type, motivo, is_minor, etc.)
 *
 * @module service-requests/hooks/useFormConfig
 * @date 2026-02-05
 */

'use client'

import { useQuery, useQueryClient } from '@tanstack/react-query'
import { getAuthData } from '@/core/auth/storage'
import type {
  FormConfig,
  FormConfigResponse,
} from '../types/form-config'
import { parseFormConfigResponse } from '../types/form-config'
import { wizardSessionApi } from '../services/wizard-session-api'

// =============================================================================
// CONSTANTS
// =============================================================================

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
const API_VERSION = '/api/v1'
const ENDPOINT_BASE = '/service-requests'

// =============================================================================
// QUERY KEYS
// =============================================================================

export const formConfigQueryKeys = {
  all: ['form-config'] as const,
  byRequest: (requestId: string) =>
    [...formConfigQueryKeys.all, 'request', requestId] as const,
  byStep: (requestId: string, stepId: string) =>
    [...formConfigQueryKeys.byRequest(requestId), 'step', stepId] as const,
}

// =============================================================================
// CACHE CONFIGURATION
// =============================================================================

const CACHE_CONFIG = {
  // Form config - moderate caching (can change if request state changes)
  staleTime: 5 * 60 * 1000, // 5 minutes
  gcTime: 30 * 60 * 1000, // 30 minutes
}

// =============================================================================
// API FETCH FUNCTION
// =============================================================================

/**
 * Fetch form config from the API
 */
async function fetchFormConfig(
  requestId: string,
  stepId: string
): Promise<FormConfig> {
  const authData = getAuthData()
  if (!authData?.access_token) {
    throw new Error('Authentication required')
  }

  const url = `${API_BASE_URL}${API_VERSION}${ENDPOINT_BASE}/${requestId}/form-config/${stepId}`

  const response = await fetch(url, {
    method: 'GET',
    headers: {
      Authorization: `Bearer ${authData.access_token}`,
      'Content-Type': 'application/json',
    },
  })

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}))
    throw new Error(errorData.detail || `Failed to fetch form config: ${response.status}`)
  }

  const data: FormConfigResponse = await response.json()
  return parseFormConfigResponse(data)
}

// =============================================================================
// HOOK
// =============================================================================

/**
 * Hook to fetch dynamic form configuration for a workflow step
 *
 * @param requestId - Service request ID
 * @param stepId - Workflow step ID (e.g., 'form_review_1', 'form_review_2')
 * @param options - Additional React Query options
 *
 * @example
 * ```tsx
 * const { data: formConfig, isLoading, error } = useFormConfig(
 *   requestId,
 *   'form_review_2'
 * );
 *
 * if (isLoading) return <Skeleton />;
 * if (error) return <ErrorMessage error={error} />;
 *
 * return (
 *   <DynamicFormRenderer
 *     config={formConfig}
 *     values={editedData}
 *     onChange={handleFieldChange}
 *   />
 * );
 * ```
 */
export function useFormConfig(
  requestId: string | undefined | null,
  stepId: string | undefined | null,
  options?: {
    enabled?: boolean
    onSuccess?: (data: FormConfig) => void
    onError?: (error: Error) => void
  }
) {
  return useQuery({
    queryKey: formConfigQueryKeys.byStep(requestId || '', stepId || ''),
    queryFn: () => fetchFormConfig(requestId!, stepId!),
    enabled: !!requestId && !!stepId && (options?.enabled !== false),
    staleTime: CACHE_CONFIG.staleTime,
    gcTime: CACHE_CONFIG.gcTime,
    retry: 2,
    retryDelay: (attemptIndex) => Math.min(1000 * 2 ** attemptIndex, 10000),
  })
}

/**
 * Hook to invalidate form config cache
 *
 * Use this when the request state changes (e.g., after saving form data)
 */
export function useInvalidateFormConfig() {
  const queryClient = useQueryClient()

  return {
    /**
     * Invalidate all form configs for a specific request
     */
    invalidateRequest: (requestId: string) => {
      return queryClient.invalidateQueries({
        queryKey: formConfigQueryKeys.byRequest(requestId),
      })
    },

    /**
     * Invalidate a specific step's form config
     */
    invalidateStep: (requestId: string, stepId: string) => {
      return queryClient.invalidateQueries({
        queryKey: formConfigQueryKeys.byStep(requestId, stepId),
      })
    },

    /**
     * Invalidate all form configs
     */
    invalidateAll: () => {
      return queryClient.invalidateQueries({
        queryKey: formConfigQueryKeys.all,
      })
    },
  }
}

/**
 * Hook to prefetch form config
 *
 * Use this to preload the next step's form config while user is on current step
 */
export function usePrefetchFormConfig() {
  const queryClient = useQueryClient()

  return {
    prefetch: async (requestId: string, stepId: string) => {
      await queryClient.prefetchQuery({
        queryKey: formConfigQueryKeys.byStep(requestId, stepId),
        queryFn: () => fetchFormConfig(requestId, stepId),
        staleTime: CACHE_CONFIG.staleTime,
      })
    },
  }
}

// =============================================================================
// SESSION-BASED HOOKS (Cache-First Wizard)
// =============================================================================

export const sessionFormConfigQueryKeys = {
  all: ['form-config', 'session'] as const,
  bySession: (sessionId: string) =>
    [...sessionFormConfigQueryKeys.all, sessionId] as const,
  byStep: (sessionId: string, stepId: string) =>
    [...sessionFormConfigQueryKeys.bySession(sessionId), 'step', stepId] as const,
}

/**
 * Fetch session form config from the wizard-sessions API
 */
async function fetchSessionFormConfig(
  sessionId: string,
  stepId: string
): Promise<FormConfig> {
  const data = await wizardSessionApi.getFormConfig(sessionId, stepId)
  return parseFormConfigResponse(data)
}

/**
 * Hook to fetch dynamic form configuration for a session wizard step
 *
 * @param sessionId - Wizard session ID
 * @param stepId - Workflow step ID (e.g., 'form_review_1')
 */
export function useSessionFormConfig(
  sessionId: string | undefined | null,
  stepId: string | undefined | null,
  options?: {
    enabled?: boolean
  }
) {
  return useQuery({
    queryKey: sessionFormConfigQueryKeys.byStep(sessionId || '', stepId || ''),
    queryFn: () => fetchSessionFormConfig(sessionId!, stepId!),
    enabled: !!sessionId && !!stepId && (options?.enabled !== false),
    staleTime: CACHE_CONFIG.staleTime,
    gcTime: CACHE_CONFIG.gcTime,
    retry: 2,
    retryDelay: (attemptIndex) => Math.min(1000 * 2 ** attemptIndex, 10000),
  })
}

/**
 * Hook to prefetch session form config for the next step
 */
export function usePrefetchSessionFormConfig() {
  const queryClient = useQueryClient()

  return {
    prefetch: async (sessionId: string, stepId: string) => {
      await queryClient.prefetchQuery({
        queryKey: sessionFormConfigQueryKeys.byStep(sessionId, stepId),
        queryFn: () => fetchSessionFormConfig(sessionId, stepId),
        staleTime: CACHE_CONFIG.staleTime,
      })
    },
  }
}

/**
 * Hook to invalidate session form config cache
 */
export function useInvalidateSessionFormConfig() {
  const queryClient = useQueryClient()

  return {
    invalidateSession: (sessionId: string) => {
      return queryClient.invalidateQueries({
        queryKey: sessionFormConfigQueryKeys.bySession(sessionId),
      })
    },
    invalidateStep: (sessionId: string, stepId: string) => {
      return queryClient.invalidateQueries({
        queryKey: sessionFormConfigQueryKeys.byStep(sessionId, stepId),
      })
    },
  }
}
