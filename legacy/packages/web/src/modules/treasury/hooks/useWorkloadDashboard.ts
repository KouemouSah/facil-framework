/**
 * Hook for Treasury Workload Dashboard data (Carga de Trabajo page).
 * Fetches 7 datasets in a single endpoint call with cache.
 */
import { useQuery } from '@tanstack/react-query';
import { treasuryApi } from '../services';
import type { WorkloadDashboardResponse } from '../types';

export const WORKLOAD_DASHBOARD_QUERY_KEY = 'treasury-workload-dashboard';

export function useWorkloadDashboard(days: number = 30) {
  return useQuery<WorkloadDashboardResponse>({
    queryKey: [WORKLOAD_DASHBOARD_QUERY_KEY, days],
    queryFn: () => treasuryApi.getWorkloadDashboard(days),
    staleTime: 2 * 60 * 1000,
    refetchInterval: 3 * 60 * 1000,
  });
}
