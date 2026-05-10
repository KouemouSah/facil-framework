/**
 * React Query hook for Service Details
 *
 * Provides cached service details fetching including:
 * - Service information
 * - Required documents
 * - Procedures with steps
 * - Pricing information
 * - Related services
 *
 * Cache strategy:
 * - Service details: 1 hour stale, 2 hour cache (rarely changes)
 *
 * @module homepage/hooks
 * @date 2026-01-25
 */

'use client';

import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useLocale } from 'next-intl';
import { getServiceDetails, type ServiceDetailsResponse } from '@/core/api/serviceDetails';

// =============================================================================
// QUERY KEYS
// =============================================================================

export const serviceDetailsQueryKeys = {
  all: ['service-details'] as const,
  detail: (serviceId: number, language: string) =>
    [...serviceDetailsQueryKeys.all, serviceId, language] as const,
};

// =============================================================================
// CACHE CONFIGURATION
// =============================================================================

const CACHE_CONFIG = {
  staleTime: 60 * 60 * 1000, // 1 hour
  gcTime: 2 * 60 * 60 * 1000, // 2 hours
};

// =============================================================================
// HOOKS
// =============================================================================

/**
 * Fetch complete service details with caching
 *
 * @param serviceId - Service ID
 * @param options - Optional parameters
 */
export function useServiceDetails(
  serviceId: number,
  options?: {
    language?: string;
    enabled?: boolean;
  }
) {
  const locale = useLocale();
  const lang = options?.language || locale;

  return useQuery<ServiceDetailsResponse>({
    queryKey: serviceDetailsQueryKeys.detail(serviceId, lang),
    queryFn: () => getServiceDetails(serviceId, lang),
    ...CACHE_CONFIG,
    enabled: options?.enabled !== false && serviceId > 0,
    retry: 2,
  });
}

// =============================================================================
// PREFETCH UTILITIES
// =============================================================================

/**
 * Prefetch service details for faster navigation
 * Call this when hovering over service cards
 */
export function usePrefetchServiceDetails() {
  const queryClient = useQueryClient();
  const locale = useLocale();

  const prefetch = (serviceId: number, language?: string) => {
    const lang = language || locale;

    queryClient.prefetchQuery({
      queryKey: serviceDetailsQueryKeys.detail(serviceId, lang),
      queryFn: () => getServiceDetails(serviceId, lang),
      ...CACHE_CONFIG,
    });
  };

  // Prefetch multiple services (e.g., for related services)
  const prefetchMultiple = (serviceIds: number[], language?: string) => {
    serviceIds.forEach((id) => prefetch(id, language));
  };

  return { prefetch, prefetchMultiple };
}

// =============================================================================
// CACHE INVALIDATION
// =============================================================================

/**
 * Hook to invalidate service details cache
 * Use after admin makes changes to a service
 */
export function useInvalidateServiceDetails() {
  const queryClient = useQueryClient();

  const invalidateService = (serviceId: number) => {
    queryClient.invalidateQueries({
      queryKey: [...serviceDetailsQueryKeys.all, serviceId],
    });
  };

  const invalidateAll = () => {
    queryClient.invalidateQueries({ queryKey: serviceDetailsQueryKeys.all });
  };

  return { invalidateService, invalidateAll };
}

export default useServiceDetails;
