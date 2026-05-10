/**
 * React Query hooks for Service Request Workflows
 *
 * Provides cached data fetching for:
 * - Workflow configurations
 * - Appointment locations
 * - Tariff calculations
 *
 * Cache strategy:
 * - Workflow configs: 1 hour stale (rarely changes)
 * - Appointment locations: 24 hours (very stable)
 * - Tariffs: 5 minutes (can vary by form data)
 *
 * @module service-requests/hooks
 * @date 2026-01-25
 */

'use client';

import { useQuery, useQueryClient } from '@tanstack/react-query';
import { serviceRequestsApi } from '../services/api';
import type {
  WorkflowConfig,
  ServiceRequest,
  ServiceRequestListResponse,
  ServiceRequestFilters,
  DetailViewResponse,
} from '../types';

// =============================================================================
// QUERY KEYS
// =============================================================================

export const workflowQueryKeys = {
  all: ['workflows'] as const,
  lists: () => [...workflowQueryKeys.all, 'list'] as const,
  listByCategory: (category?: string) =>
    [...workflowQueryKeys.lists(), category || 'all'] as const,
  detail: (code: string) => [...workflowQueryKeys.all, 'detail', code] as const,
  steps: (code: string) => [...workflowQueryKeys.all, 'steps', code] as const,
};

export const serviceRequestQueryKeys = {
  all: ['service-requests'] as const,
  lists: () => [...serviceRequestQueryKeys.all, 'list'] as const,
  myRequests: (page: number, filters?: ServiceRequestFilters) =>
    [...serviceRequestQueryKeys.lists(), 'my', page, JSON.stringify(filters || {})] as const,
  detail: (id: string) => [...serviceRequestQueryKeys.all, 'detail', id] as const,
  detailView: (id: string) => [...serviceRequestQueryKeys.all, 'detail-view', id] as const,
  documents: (id: string) => [...serviceRequestQueryKeys.all, 'documents', id] as const,
  tariff: (id: string) => [...serviceRequestQueryKeys.all, 'tariff', id] as const,
  appointments: (id: string) => [...serviceRequestQueryKeys.all, 'appointments', id] as const,
  appointmentLocations: (id: string) =>
    [...serviceRequestQueryKeys.appointments(id), 'locations'] as const,
};

// =============================================================================
// CACHE CONFIGURATION
// =============================================================================

const CACHE_CONFIG = {
  // Workflow configs - rarely change
  workflow: {
    staleTime: 60 * 60 * 1000, // 1 hour
    gcTime: 2 * 60 * 60 * 1000, // 2 hours
  },
  // Appointment locations - very stable
  appointmentLocations: {
    staleTime: 24 * 60 * 60 * 1000, // 24 hours
    gcTime: 48 * 60 * 60 * 1000, // 48 hours
  },
  // Tariffs - can change based on form data
  tariff: {
    staleTime: 5 * 60 * 1000, // 5 minutes
    gcTime: 30 * 60 * 1000, // 30 minutes
  },
  // User requests - moderate caching
  requests: {
    staleTime: 2 * 60 * 1000, // 2 minutes
    gcTime: 10 * 60 * 1000, // 10 minutes
  },
};

// =============================================================================
// WORKFLOW HOOKS
// =============================================================================

/**
 * Get all available workflows for a category
 */
export function useWorkflows(category?: string, options?: { enabled?: boolean }) {
  return useQuery<WorkflowConfig[]>({
    queryKey: workflowQueryKeys.listByCategory(category),
    queryFn: () => serviceRequestsApi.getWorkflows(category),
    ...CACHE_CONFIG.workflow,
    enabled: options?.enabled !== false,
    retry: 2,
  });
}

/**
 * Get a specific workflow configuration by code
 */
export function useWorkflow(workflowCode: string, options?: { enabled?: boolean }) {
  return useQuery<WorkflowConfig>({
    queryKey: workflowQueryKeys.detail(workflowCode),
    queryFn: () => serviceRequestsApi.getWorkflow(workflowCode),
    ...CACHE_CONFIG.workflow,
    enabled: options?.enabled !== false && !!workflowCode,
    retry: 2,
  });
}

/**
 * Get workflow steps for a specific workflow
 */
export function useWorkflowSteps(
  workflowCode: string,
  subType?: string,
  options?: { enabled?: boolean }
) {
  return useQuery<WorkflowConfig>({
    queryKey: workflowQueryKeys.steps(workflowCode),
    queryFn: () => serviceRequestsApi.getWorkflowSteps(workflowCode, subType),
    ...CACHE_CONFIG.workflow,
    enabled: options?.enabled !== false && !!workflowCode,
    retry: 2,
  });
}

// =============================================================================
// SERVICE REQUEST HOOKS
// =============================================================================

/**
 * Get user's service requests with pagination and filters
 */
export function useMyServiceRequests(
  page: number = 1,
  pageSize: number = 10,
  filters?: ServiceRequestFilters,
  options?: { enabled?: boolean }
) {
  return useQuery<ServiceRequestListResponse>({
    queryKey: serviceRequestQueryKeys.myRequests(page, filters),
    queryFn: () => serviceRequestsApi.listMyRequests(page, pageSize, filters),
    ...CACHE_CONFIG.requests,
    enabled: options?.enabled !== false,
    placeholderData: (previousData) => previousData,
    retry: 2,
  });
}

/**
 * Get a specific service request by ID
 */
export function useServiceRequest(requestId: string, options?: { enabled?: boolean }) {
  return useQuery<ServiceRequest>({
    queryKey: serviceRequestQueryKeys.detail(requestId),
    queryFn: () => serviceRequestsApi.getRequest(requestId),
    ...CACHE_CONFIG.requests,
    enabled: options?.enabled !== false && !!requestId,
    retry: 2,
  });
}

// =============================================================================
// PREFETCH UTILITIES
// =============================================================================

/**
 * Prefetch workflow configurations
 */
export function usePrefetchWorkflows() {
  const queryClient = useQueryClient();

  const prefetchWorkflow = (workflowCode: string) => {
    queryClient.prefetchQuery({
      queryKey: workflowQueryKeys.detail(workflowCode),
      queryFn: () => serviceRequestsApi.getWorkflow(workflowCode),
      ...CACHE_CONFIG.workflow,
    });
  };

  const prefetchWorkflowsByCategory = (category?: string) => {
    queryClient.prefetchQuery({
      queryKey: workflowQueryKeys.listByCategory(category),
      queryFn: () => serviceRequestsApi.getWorkflows(category),
      ...CACHE_CONFIG.workflow,
    });
  };

  return { prefetchWorkflow, prefetchWorkflowsByCategory };
}

// =============================================================================
// CACHE INVALIDATION
// =============================================================================

/**
 * Hook to invalidate workflow and request caches
 */
export function useInvalidateWorkflowCache() {
  const queryClient = useQueryClient();

  const invalidateWorkflows = () => {
    queryClient.invalidateQueries({ queryKey: workflowQueryKeys.all });
  };

  const invalidateMyRequests = () => {
    queryClient.invalidateQueries({ queryKey: serviceRequestQueryKeys.lists() });
  };

  const invalidateRequest = (requestId: string) => {
    queryClient.invalidateQueries({
      queryKey: serviceRequestQueryKeys.detail(requestId),
    });
  };

  return {
    invalidateWorkflows,
    invalidateMyRequests,
    invalidateRequest,
  };
}

export default useWorkflows;

// =============================================================================
// DETAIL VIEW HOOK (Mi Solicitud dynamic page)
// =============================================================================

/**
 * Hook for the citizen "Mi Solicitud" detail page.
 * Fetches all data in a single API call (stepper, sections, notifications).
 */
export function useDetailView(requestId: string | undefined) {
  return useQuery<DetailViewResponse>({
    queryKey: serviceRequestQueryKeys.detailView(requestId || ''),
    queryFn: () => serviceRequestsApi.getDetailView(requestId!),
    enabled: !!requestId,
    staleTime: 30 * 1000, // 30 seconds — notifications should be fresh
    gcTime: 5 * 60 * 1000, // 5 minutes
    refetchOnWindowFocus: true, // Refresh when user returns to tab
  });
}
