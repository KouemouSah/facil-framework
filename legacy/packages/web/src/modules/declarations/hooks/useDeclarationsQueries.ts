/**
 * React Query hooks for Declarations
 *
 * Provides cached data fetching for:
 * - User declarations list (paginated)
 * - Declaration details
 * - Declaration workflow status
 *
 * Cache strategy:
 * - Declarations list: 2 min stale (changes on user actions)
 * - Declaration detail: 2 min stale
 * - Workflow status: 30 sec stale (updates more frequently)
 *
 * @module declarations/hooks
 * @date 2026-01-25
 */

'use client';

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { declarationsApi } from '../services/api';
import type {
  DeclarationResponse,
  DeclarationListResponse,
  DeclarationStatus,
} from '@/types/declaration';

// Types for create/update (generic Record for API compatibility)
type DeclarationCreateData = Record<string, unknown>;
type DeclarationUpdateData = Record<string, unknown>;

// =============================================================================
// QUERY KEYS
// =============================================================================

export const declarationQueryKeys = {
  all: ['declarations'] as const,
  lists: () => [...declarationQueryKeys.all, 'list'] as const,
  list: (page: number, pageSize: number, status?: DeclarationStatus) =>
    [...declarationQueryKeys.lists(), page, pageSize, status || 'all'] as const,
  detail: (id: string) => [...declarationQueryKeys.all, 'detail', id] as const,
  workflow: (id: string) => [...declarationQueryKeys.all, 'workflow', id] as const,
};

// =============================================================================
// CACHE CONFIGURATION
// =============================================================================

const CACHE_CONFIG = {
  // Declarations list - user-specific
  list: {
    staleTime: 2 * 60 * 1000, // 2 minutes
    gcTime: 10 * 60 * 1000, // 10 minutes
  },
  // Declaration detail
  detail: {
    staleTime: 2 * 60 * 1000, // 2 minutes
    gcTime: 10 * 60 * 1000, // 10 minutes
  },
  // Workflow status - updates more frequently
  workflow: {
    staleTime: 30 * 1000, // 30 seconds
    gcTime: 5 * 60 * 1000, // 5 minutes
  },
};

// =============================================================================
// LIST HOOKS
// =============================================================================

interface UseDeclarationsOptions {
  page?: number;
  pageSize?: number;
  status?: DeclarationStatus;
  enabled?: boolean;
}

/**
 * Fetch user declarations with pagination and caching
 */
export function useDeclarations(options: UseDeclarationsOptions = {}) {
  const { page = 1, pageSize = 20, status, enabled = true } = options;

  return useQuery<DeclarationListResponse>({
    queryKey: declarationQueryKeys.list(page, pageSize, status),
    queryFn: () => declarationsApi.listDeclarations({ page, pageSize, status }),
    ...CACHE_CONFIG.list,
    enabled,
    placeholderData: (previousData) => previousData,
    retry: 2,
  });
}

/**
 * Fetch all declarations (for stats calculation)
 */
export function useAllDeclarations(options?: { enabled?: boolean }) {
  return useQuery<DeclarationListResponse>({
    queryKey: declarationQueryKeys.list(1, 100, undefined),
    queryFn: () => declarationsApi.listDeclarations({ page: 1, pageSize: 100 }),
    ...CACHE_CONFIG.list,
    enabled: options?.enabled !== false,
    retry: 2,
  });
}

// =============================================================================
// DETAIL HOOKS
// =============================================================================

/**
 * Fetch a single declaration by ID
 */
export function useDeclaration(declarationId: string, options?: { enabled?: boolean }) {
  return useQuery<DeclarationResponse>({
    queryKey: declarationQueryKeys.detail(declarationId),
    queryFn: () => declarationsApi.getDeclaration(declarationId),
    ...CACHE_CONFIG.detail,
    enabled: options?.enabled !== false && !!declarationId,
    retry: 2,
  });
}

/**
 * Fetch declaration workflow status
 */
export function useDeclarationWorkflow(declarationId: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: declarationQueryKeys.workflow(declarationId),
    queryFn: () => declarationsApi.getDeclarationWorkflow(declarationId),
    ...CACHE_CONFIG.workflow,
    enabled: options?.enabled !== false && !!declarationId,
    retry: 2,
    // Poll for updates every 30 seconds when visible
    refetchInterval: 30 * 1000,
    refetchIntervalInBackground: false,
  });
}

// =============================================================================
// MUTATION HOOKS
// =============================================================================

/**
 * Create a new declaration
 */
export function useCreateDeclaration() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: DeclarationCreateData) => declarationsApi.createDeclaration(data),
    onSuccess: () => {
      // Invalidate declarations list
      queryClient.invalidateQueries({ queryKey: declarationQueryKeys.lists() });
    },
  });
}

/**
 * Update a declaration
 */
export function useUpdateDeclaration() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: DeclarationUpdateData }) =>
      declarationsApi.updateDeclaration(id, data),
    onSuccess: (_, variables) => {
      // Invalidate specific declaration and list
      queryClient.invalidateQueries({ queryKey: declarationQueryKeys.detail(variables.id) });
      queryClient.invalidateQueries({ queryKey: declarationQueryKeys.lists() });
    },
  });
}

/**
 * Submit a declaration
 */
export function useSubmitDeclaration() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (declarationId: string) => declarationsApi.submitDeclaration(declarationId),
    onSuccess: (_, declarationId) => {
      // Invalidate declaration and list
      queryClient.invalidateQueries({ queryKey: declarationQueryKeys.detail(declarationId) });
      queryClient.invalidateQueries({ queryKey: declarationQueryKeys.workflow(declarationId) });
      queryClient.invalidateQueries({ queryKey: declarationQueryKeys.lists() });
    },
  });
}

/**
 * Delete a declaration
 */
export function useDeleteDeclaration() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (declarationId: string) => declarationsApi.deleteDeclaration(declarationId),
    onSuccess: (_, declarationId) => {
      // Remove from cache and invalidate list
      queryClient.removeQueries({ queryKey: declarationQueryKeys.detail(declarationId) });
      queryClient.invalidateQueries({ queryKey: declarationQueryKeys.lists() });
    },
  });
}

// =============================================================================
// PREFETCH UTILITIES
// =============================================================================

/**
 * Prefetch declaration details for faster navigation
 */
export function usePrefetchDeclaration() {
  const queryClient = useQueryClient();

  const prefetch = (declarationId: string) => {
    queryClient.prefetchQuery({
      queryKey: declarationQueryKeys.detail(declarationId),
      queryFn: () => declarationsApi.getDeclaration(declarationId),
      ...CACHE_CONFIG.detail,
    });
  };

  return { prefetch };
}

// =============================================================================
// CACHE INVALIDATION
// =============================================================================

/**
 * Hook to invalidate declarations caches
 */
export function useInvalidateDeclarationsCache() {
  const queryClient = useQueryClient();

  const invalidateAll = () => {
    queryClient.invalidateQueries({ queryKey: declarationQueryKeys.all });
  };

  const invalidateLists = () => {
    queryClient.invalidateQueries({ queryKey: declarationQueryKeys.lists() });
  };

  const invalidateDeclaration = (declarationId: string) => {
    queryClient.invalidateQueries({ queryKey: declarationQueryKeys.detail(declarationId) });
  };

  return {
    invalidateAll,
    invalidateLists,
    invalidateDeclaration,
  };
}

export default useDeclarations;
