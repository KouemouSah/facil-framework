import { useInfiniteQuery, useQuery } from '@tanstack/react-query';

import * as api from './directory-api';
import type { DirectorySearchResponse } from '../types/directory.types';

/**
 * Default page size when the caller doesn't specify one.
 * Backend caps page_size at 50 (company_public_routes.py:68).
 */
const DEFAULT_PAGE_SIZE = 20;

/**
 * Paginated public directory search.
 *
 * Returns React Query's standard `useInfiniteQuery` shape — the screen
 * flattens `data.pages.flatMap(p => p.items)` and fires `fetchNextPage()`
 * via FlatList's `onEndReached`.
 *
 * `getNextPageParam` returns `undefined` when:
 * - the last page returned fewer items than `page_size` (backend exhausted)
 * - or `page * page_size >= total` (cumulative coverage reached the total)
 */
export function useDirectorySearch(params: Record<string, string>, enabled = true) {
  const pageSize = Number.parseInt(params.page_size ?? `${DEFAULT_PAGE_SIZE}`, 10) || DEFAULT_PAGE_SIZE;

  return useInfiniteQuery<
    DirectorySearchResponse,
    Error,
    { pages: DirectorySearchResponse[]; pageParams: number[] },
    readonly unknown[],
    number
  >({
    queryKey: ['directory', 'search', params] as const,
    queryFn: ({ pageParam = 1 }) =>
      api.searchDirectory({
        ...params,
        page: String(pageParam),
        page_size: String(pageSize),
      }),
    initialPageParam: 1,
    getNextPageParam: (lastPage, allPages) => {
      if (!lastPage?.items?.length) return undefined;
      if (lastPage.items.length < pageSize) return undefined;
      const fetched = allPages.reduce((acc, p) => acc + p.items.length, 0);
      if (fetched >= lastPage.total) return undefined;
      return (lastPage.page ?? allPages.length) + 1;
    },
    enabled,
    staleTime: 30_000,
  });
}

/**
 * Directory reference data (zones / sectors / provinces / legal forms) is
 * effectively immutable for a session — bump staleTime to 1h to avoid
 * pointless refetches on every screen mount. P8.5 review.
 */
const REFERENCE_STALE_TIME_MS = 60 * 60_000;

export function useDirectoryFilters() {
  const zones = useQuery({ queryKey: ['directory', 'zones'], queryFn: api.getZones, staleTime: REFERENCE_STALE_TIME_MS });
  const sectors = useQuery({ queryKey: ['directory', 'sectors'], queryFn: api.getSectors, staleTime: REFERENCE_STALE_TIME_MS });
  const provincias = useQuery({ queryKey: ['directory', 'provincias'], queryFn: api.getProvincias, staleTime: REFERENCE_STALE_TIME_MS });
  const formas = useQuery({ queryKey: ['directory', 'formas'], queryFn: api.getFormasJuridicas, staleTime: REFERENCE_STALE_TIME_MS });

  return { zones, sectors, provincias, formas };
}
