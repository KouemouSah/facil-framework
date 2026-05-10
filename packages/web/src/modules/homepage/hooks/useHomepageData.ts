/**
 * React Query hooks for Homepage data
 *
 * Provides cached data fetching for:
 * - Homepage statistics
 * - Category directory
 * - Ministry directory/details
 * - Services by type
 *
 * All hooks use staleTime/gcTime for optimal caching:
 * - Static data (categories, ministries): 1 hour stale, 2 hour cache
 * - Dynamic data (stats): 30 min stale, 1 hour cache
 *
 * @module homepage/hooks
 * @date 2026-01-25
 */

'use client';

import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useLocale } from 'next-intl';
import {
  getHomepageStats,
  getCategoryDirectory,
  getMinistryDirectory,
  getMinistryDetails,
  getServicesByType,
  type HomepageStats,
  type CategoryDirectory,
  type MinistryDirectory,
  type MinistryDetails,
  type ServicesByTypeResponse,
  type ServiceType,
} from '@/core/api/homepage';

// =============================================================================
// QUERY KEYS
// =============================================================================

export const homepageQueryKeys = {
  all: ['homepage'] as const,
  stats: () => [...homepageQueryKeys.all, 'stats'] as const,
  categories: (language: string) => [...homepageQueryKeys.all, 'categories', language] as const,
  ministries: (language: string) => [...homepageQueryKeys.all, 'ministries', language] as const,
  ministryDetail: (id: number, language: string, page: number) =>
    [...homepageQueryKeys.all, 'ministry', id, language, page] as const,
  servicesByType: (type: ServiceType, language: string, letter?: string) =>
    [...homepageQueryKeys.all, 'services-by-type', type, language, letter || 'all'] as const,
};

// =============================================================================
// CACHE CONFIGURATION
// =============================================================================

const CACHE_CONFIG = {
  // Static data - rarely changes
  static: {
    staleTime: 60 * 60 * 1000, // 1 hour
    gcTime: 2 * 60 * 60 * 1000, // 2 hours
  },
  // Dynamic data - changes more frequently
  dynamic: {
    staleTime: 30 * 60 * 1000, // 30 minutes
    gcTime: 60 * 60 * 1000, // 1 hour
  },
};

// =============================================================================
// HOOKS
// =============================================================================

/**
 * Fetch homepage statistics with caching
 */
export function useHomepageStats() {
  return useQuery<HomepageStats>({
    queryKey: homepageQueryKeys.stats(),
    queryFn: getHomepageStats,
    ...CACHE_CONFIG.dynamic,
    retry: 2,
  });
}

/**
 * Fetch category directory with caching
 * @param language - Optional language override (uses locale by default)
 */
export function useCategoryDirectory(language?: string) {
  const locale = useLocale();
  const lang = language || locale;

  return useQuery<CategoryDirectory>({
    queryKey: homepageQueryKeys.categories(lang),
    queryFn: () => getCategoryDirectory(lang),
    ...CACHE_CONFIG.static,
    retry: 2,
  });
}

/**
 * Fetch ministry directory with caching
 * @param language - Optional language override (uses locale by default)
 */
export function useMinistryDirectory(language?: string) {
  const locale = useLocale();
  const lang = language || locale;

  return useQuery<MinistryDirectory>({
    queryKey: homepageQueryKeys.ministries(lang),
    queryFn: () => getMinistryDirectory(lang),
    ...CACHE_CONFIG.static,
    retry: 2,
  });
}

/**
 * Fetch ministry details with paginated services
 * @param ministryId - Ministry ID
 * @param options - Optional parameters
 */
export function useMinistryDetails(
  ministryId: number,
  options?: {
    language?: string;
    page?: number;
    limit?: number;
    enabled?: boolean;
  }
) {
  const locale = useLocale();
  const lang = options?.language || locale;
  const page = options?.page || 1;

  return useQuery<MinistryDetails>({
    queryKey: homepageQueryKeys.ministryDetail(ministryId, lang, page),
    queryFn: () =>
      getMinistryDetails(ministryId, {
        language: lang,
        page,
        limit: options?.limit,
      }),
    ...CACHE_CONFIG.static,
    enabled: options?.enabled !== false && ministryId > 0,
    retry: 2,
  });
}

/**
 * Fetch services by type with optional letter filter
 * @param type - Service type
 * @param options - Optional parameters
 */
export function useServicesByType(
  type: ServiceType,
  options?: {
    letter?: string;
    language?: string;
    limit?: number;
    enabled?: boolean;
  }
) {
  const locale = useLocale();
  const lang = options?.language || locale;

  return useQuery<ServicesByTypeResponse>({
    queryKey: homepageQueryKeys.servicesByType(type, lang, options?.letter),
    queryFn: () =>
      getServicesByType(type, {
        letter: options?.letter,
        language: lang,
        limit: options?.limit,
      }),
    ...CACHE_CONFIG.static,
    enabled: options?.enabled !== false,
    retry: 2,
  });
}

// =============================================================================
// PREFETCH UTILITIES
// =============================================================================

/**
 * Prefetch homepage data for faster navigation
 * Call this on the homepage to preload category/ministry data
 */
export function usePrefetchHomepageData() {
  const queryClient = useQueryClient();
  const locale = useLocale();

  const prefetchAll = async () => {
    await Promise.all([
      queryClient.prefetchQuery({
        queryKey: homepageQueryKeys.stats(),
        queryFn: getHomepageStats,
        ...CACHE_CONFIG.dynamic,
      }),
      queryClient.prefetchQuery({
        queryKey: homepageQueryKeys.categories(locale),
        queryFn: () => getCategoryDirectory(locale),
        ...CACHE_CONFIG.static,
      }),
      queryClient.prefetchQuery({
        queryKey: homepageQueryKeys.ministries(locale),
        queryFn: () => getMinistryDirectory(locale),
        ...CACHE_CONFIG.static,
      }),
    ]);
  };

  return { prefetchAll };
}

/**
 * Prefetch ministry details for faster navigation
 */
export function usePrefetchMinistryDetails() {
  const queryClient = useQueryClient();
  const locale = useLocale();

  const prefetch = (ministryId: number, page: number = 1) => {
    queryClient.prefetchQuery({
      queryKey: homepageQueryKeys.ministryDetail(ministryId, locale, page),
      queryFn: () => getMinistryDetails(ministryId, { language: locale, page }),
      ...CACHE_CONFIG.static,
    });
  };

  return { prefetch };
}

// =============================================================================
// CACHE INVALIDATION
// =============================================================================

/**
 * Hook to invalidate homepage cache
 * Use after admin makes changes to services/ministries/categories
 */
export function useInvalidateHomepageCache() {
  const queryClient = useQueryClient();

  const invalidateAll = () => {
    queryClient.invalidateQueries({ queryKey: homepageQueryKeys.all });
  };

  const invalidateCategories = () => {
    queryClient.invalidateQueries({ queryKey: [...homepageQueryKeys.all, 'categories'] });
  };

  const invalidateMinistries = () => {
    queryClient.invalidateQueries({ queryKey: [...homepageQueryKeys.all, 'ministries'] });
  };

  const invalidateStats = () => {
    queryClient.invalidateQueries({ queryKey: homepageQueryKeys.stats() });
  };

  return {
    invalidateAll,
    invalidateCategories,
    invalidateMinistries,
    invalidateStats,
  };
}

export default useHomepageStats;
