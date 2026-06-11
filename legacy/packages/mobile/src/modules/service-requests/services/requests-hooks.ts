/**
 * Service Requests React Query Hooks
 */

import { useQuery, useInfiniteQuery } from '@tanstack/react-query';
import * as requestsApi from './requests-api';
import type { ServiceRequestFilters } from '../types/requests.types';

export const REQUESTS_QUERY_KEYS = {
  list: ['requests'] as const,
  listFiltered: (filters: ServiceRequestFilters) => ['requests', filters] as const,
  detail: (id: string) => ['requests', 'detail', id] as const,
  detailView: (id: string) => ['requests', 'detail-view', id] as const,
} as const;

/**
 * Infinite query for paginated service requests list.
 */
export function useRequests(filters: Omit<ServiceRequestFilters, 'page'>) {
  return useInfiniteQuery({
    queryKey: REQUESTS_QUERY_KEYS.listFiltered({ ...filters, page: 1, page_size: filters.page_size ?? 20 }),
    queryFn: ({ pageParam = 1 }) =>
      requestsApi.getRequests({ ...filters, page: pageParam as number, page_size: filters.page_size ?? 20 }),
    initialPageParam: 1,
    getNextPageParam: (lastPage) =>
      lastPage.page < lastPage.total_pages ? lastPage.page + 1 : undefined,
    staleTime: 60_000,
  });
}

/**
 * Fetch detailed view for a single service request.
 */
export function useRequestDetailView(id: string, enabled = true) {
  return useQuery({
    queryKey: REQUESTS_QUERY_KEYS.detailView(id),
    queryFn: () => requestsApi.getRequestDetailView(id),
    enabled: enabled && !!id,
    staleTime: 30_000,
  });
}

/**
 * Fetch available workflows (grouped by category on frontend).
 * Cached 1h — workflows rarely change.
 */
export function useAvailableWorkflows(category?: string) {
  return useQuery({
    queryKey: ['workflows', category ?? 'all'] as const,
    queryFn: () => requestsApi.getAvailableWorkflows(category),
    staleTime: 60 * 60_000,
  });
}
