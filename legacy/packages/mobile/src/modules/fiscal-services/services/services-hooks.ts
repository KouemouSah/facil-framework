/**
 * Fiscal Services React Query Hooks
 *
 * Tuning rationale (slow-network friendliness)
 * --------------------------------------------
 * Equatorial Guinea has a non-trivial number of users on 3G / patchy LTE.
 * The catalog data here (ministries / categories / popular services) is
 * effectively reference data — it changes a few times per year, not per
 * request. We push the staleTime to 24 h so that as long as the user has
 * something in the persisted React Query cache (configured in
 * app/_layout.tsx with a 24 h maxAge / gcTime) the screen renders
 * **instantly** on cold start, and we only refetch in background when
 * stale. Combined with `placeholderData: keepPreviousData`, the UI never
 * shows a spinner once the user has run the app once on Wi-Fi.
 *
 * Mobile-data degraded UX flow:
 *   - cold start, has persisted cache  -> renders cached list, refetches silently
 *   - cold start, no persisted cache   -> renders ActivityIndicator + retry
 *                                          fallback (cf. (tabs)/services/index.tsx)
 *   - cache stale (>24 h) on cellular  -> still serves the cached list while
 *                                          refetching in background
 *
 * If the catalog truly needs to be fresher (admin update window), call
 * `queryClient.invalidateQueries({ queryKey: ['fiscal-services'] })` from
 * the admin surface to force a refetch.
 */

import { useQuery, keepPreviousData } from '@tanstack/react-query';
import { useState, useCallback, useRef, useEffect } from 'react';
import * as servicesApi from './services-api';
import { logger } from '@core/logging/logger';
import type { ServiceSearchFilters, ServiceSearchResponse } from '../types/services.types';

export const SERVICES_QUERY_KEYS = {
  list: ['fiscal-services'] as const,
  detail: (id: number) => ['fiscal-services', 'detail', id] as const,
  ministries: ['fiscal-services', 'ministries'] as const,
  categories: ['fiscal-services', 'categories'] as const,
  popular: ['fiscal-services', 'popular'] as const,
  search: (q: string) => ['fiscal-services', 'search', q] as const,
} as const;

/** 24 hours — see file-level rationale. */
const CATALOG_STALE_TIME = 24 * 60 * 60 * 1000;

/** Ministries list — reference data, cached 24 h, served-while-revalidate. */
export function useMinistries(language = 'es') {
  return useQuery({
    queryKey: [...SERVICES_QUERY_KEYS.ministries, language],
    queryFn: () => servicesApi.getMinistries(language),
    staleTime: CATALOG_STALE_TIME,
    placeholderData: keepPreviousData,
  });
}

/** Categories list — reference data, cached 24 h. */
export function useCategories(language = 'es') {
  return useQuery({
    queryKey: [...SERVICES_QUERY_KEYS.categories, language],
    queryFn: () => servicesApi.getCategories(language),
    staleTime: CATALOG_STALE_TIME,
    placeholderData: keepPreviousData,
  });
}

/** Popular services — refresh more often than ministries (admin-curated). */
export function usePopularServices(limit = 10) {
  return useQuery({
    queryKey: [...SERVICES_QUERY_KEYS.popular, limit],
    queryFn: () => servicesApi.getPopularServices(limit),
    staleTime: 6 * 60 * 60 * 1000, // 6 h — popular ranking shifts during the day
    placeholderData: keepPreviousData,
  });
}

/** Service detail — long stale, instant re-open. */
export function useServiceDetail(id: number, language = 'es', enabled = true) {
  return useQuery({
    queryKey: [...SERVICES_QUERY_KEYS.detail(id), language],
    queryFn: () => servicesApi.getServiceDetail(id, language),
    enabled: enabled && id > 0,
    staleTime: CATALOG_STALE_TIME,
    placeholderData: keepPreviousData,
  });
}

/**
 * Debounced service search hook.
 * Returns search results with facets, auto-triggers after 300ms of inactivity.
 */
export function useServiceSearch(debounceMs = 300, language = 'es') {
  const [query, setQuery] = useState('');
  const [filters, setFilters] = useState<ServiceSearchFilters>({});
  const [results, setResults] = useState<ServiceSearchResponse | null>(null);
  const [isSearching, setIsSearching] = useState(false);
  const [isLoadingMore, setIsLoadingMore] = useState(false);
  const [searchError, setSearchError] = useState<string | null>(null);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const currentPageRef = useRef(1);
  const hasMoreRef = useRef(true);
  const currentFiltersRef = useRef<ServiceSearchFilters>({});

  const search = useCallback(
    (q: string, extraFilters: Partial<ServiceSearchFilters> = {}) => {
      setQuery(q);
      const merged = { ...filters, ...extraFilters, q };
      currentFiltersRef.current = merged;
      currentPageRef.current = 1;
      hasMoreRef.current = true;

      if (timerRef.current) clearTimeout(timerRef.current);

      if (!q && !merged.category_id && !merged.ministry_id) {
        setResults(null);
        setIsSearching(false);
        return;
      }

      setIsSearching(true);
      timerRef.current = setTimeout(async () => {
        try {
          const data = await servicesApi.searchServices({
            ...merged,
            language: merged.language ?? language,
            include_facets: true,
            limit: 30,
            page: 1,
          });
          setResults(data);
          const items = data.results || data.services || [];
          const total = data.total_results ?? data.total ?? 0;
          hasMoreRef.current = items.length < total;
        } catch (error) {
          logger.error('ServiceSearch', error, 'Search failed');
          setSearchError(error instanceof Error ? error.message : 'Search failed');
        } finally {
          setIsSearching(false);
        }
      }, debounceMs);
    },
    [filters, debounceMs, language],
  );

  const loadMore = useCallback(async () => {
    if (isLoadingMore || !hasMoreRef.current || !results) return;
    setIsLoadingMore(true);
    const nextPage = currentPageRef.current + 1;
    try {
      const data = await servicesApi.searchServices({
        ...currentFiltersRef.current,
        language: currentFiltersRef.current.language ?? language,
        include_facets: false,
        limit: 30,
        page: nextPage,
      });
      const newItems = data.results || data.services || [];
      if (newItems.length === 0) {
        hasMoreRef.current = false;
      } else {
        currentPageRef.current = nextPage;
        setResults((prev) => {
          if (!prev) return data;
          const existingItems = prev.results || prev.services || [];
          return {
            ...prev,
            results: [...existingItems, ...newItems],
            services: [...existingItems, ...newItems],
          };
        });
      }
    } catch {
      // Silently fail on load more
    } finally {
      setIsLoadingMore(false);
    }
  }, [isLoadingMore, results, language]);

  const updateFilters = useCallback((newFilters: Partial<ServiceSearchFilters>) => {
    setFilters((prev) => ({ ...prev, ...newFilters }));
  }, []);

  useEffect(() => {
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, []);

  return { query, search, results, isSearching, isLoadingMore, loadMore, searchError, filters, updateFilters };
}
