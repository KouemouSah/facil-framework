/**
 * React Query hooks for Service Search
 *
 * Provides cached search functionality for:
 * - Full-text search with filters
 * - Faceted search results
 * - Search suggestions
 *
 * Cache strategy:
 * - Search results: 5 min stale, 30 min cache
 * - Facets: 30 min stale, 1 hour cache
 *
 * @module homepage/hooks
 * @date 2026-01-25
 */

'use client';

import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useLocale } from 'next-intl';
import { searchServices, type SearchFilters, type SearchResponse } from '@/core/api/services';

// =============================================================================
// QUERY KEYS
// =============================================================================

export const searchQueryKeys = {
  all: ['search'] as const,
  results: (filters: SearchFilters) =>
    [...searchQueryKeys.all, 'results', JSON.stringify(filters)] as const,
  suggestions: (query: string) => [...searchQueryKeys.all, 'suggestions', query] as const,
};

// =============================================================================
// CACHE CONFIGURATION
// =============================================================================

const SEARCH_CACHE_CONFIG = {
  // Search results - can change, moderate caching
  results: {
    staleTime: 5 * 60 * 1000, // 5 minutes
    gcTime: 30 * 60 * 1000, // 30 minutes
  },
  // Suggestions - short-lived
  suggestions: {
    staleTime: 2 * 60 * 1000, // 2 minutes
    gcTime: 10 * 60 * 1000, // 10 minutes
  },
};

// =============================================================================
// HOOKS
// =============================================================================

/**
 * Search services with filters and caching
 *
 * @param filters - Search filters
 * @param options - Query options
 */
export function useServiceSearch(
  filters: SearchFilters,
  options?: {
    enabled?: boolean;
  }
) {
  const locale = useLocale();

  // Merge locale into filters
  const filtersWithLocale: SearchFilters = {
    ...filters,
    language: filters.language || locale,
  };

  return useQuery<SearchResponse>({
    queryKey: searchQueryKeys.results(filtersWithLocale),
    queryFn: () => searchServices(filtersWithLocale),
    ...SEARCH_CACHE_CONFIG.results,
    enabled: options?.enabled !== false,
    retry: 2,
    // Keep previous data while fetching new results
    placeholderData: (previousData) => previousData,
  });
}

/**
 * Search with debounced query
 * Useful for real-time search as user types
 */
export function useDebouncedSearch(
  query: string,
  filters: Omit<SearchFilters, 'q'>,
  options?: {
    enabled?: boolean;
    debounceMs?: number;
  }
) {
  const locale = useLocale();

  const fullFilters: SearchFilters = {
    ...filters,
    q: query,
    language: filters.language || locale,
  };

  return useQuery<SearchResponse>({
    queryKey: searchQueryKeys.results(fullFilters),
    queryFn: () => searchServices(fullFilters),
    ...SEARCH_CACHE_CONFIG.results,
    // Only search if query has at least 2 characters or other filters are set
    enabled:
      options?.enabled !== false &&
      (query.length >= 2 ||
        !!filters.category_id ||
        !!filters.category_code ||
        !!filters.ministry_id ||
        !!filters.service_type),
    retry: 1,
    placeholderData: (previousData) => previousData,
  });
}

// =============================================================================
// PREFETCH UTILITIES
// =============================================================================

/**
 * Prefetch search results for common queries
 */
export function usePrefetchSearch() {
  const queryClient = useQueryClient();
  const locale = useLocale();

  const prefetch = (filters: SearchFilters) => {
    const filtersWithLocale: SearchFilters = {
      ...filters,
      language: filters.language || locale,
    };

    queryClient.prefetchQuery({
      queryKey: searchQueryKeys.results(filtersWithLocale),
      queryFn: () => searchServices(filtersWithLocale),
      ...SEARCH_CACHE_CONFIG.results,
    });
  };

  // Prefetch common category searches
  const prefetchPopularCategories = (categoryIds: number[]) => {
    categoryIds.forEach((categoryId) => {
      prefetch({ category_id: categoryId, limit: 20 });
    });
  };

  return { prefetch, prefetchPopularCategories };
}

// =============================================================================
// CACHE INVALIDATION
// =============================================================================

/**
 * Hook to invalidate search cache
 * Use after admin makes changes to services
 */
export function useInvalidateSearchCache() {
  const queryClient = useQueryClient();

  const invalidateAll = () => {
    queryClient.invalidateQueries({ queryKey: searchQueryKeys.all });
  };

  return { invalidateAll };
}

export default useServiceSearch;
