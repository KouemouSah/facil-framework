/**
 * Dashboard React Query Hooks
 */

import { useQuery } from '@tanstack/react-query';
import * as dashboardApi from './dashboard-api';

export const DASHBOARD_QUERY_KEYS = {
  summary: ['dashboard', 'summary'] as const,
} as const;

/**
 * Fetch dashboard summary. staleTime 2min, refetch on app focus.
 */
export function useDashboard(enabled = true) {
  return useQuery({
    queryKey: DASHBOARD_QUERY_KEYS.summary,
    queryFn: () => dashboardApi.getDashboardSummary(),
    enabled,
    staleTime: 2 * 60_000,
    refetchOnWindowFocus: true,
  });
}
