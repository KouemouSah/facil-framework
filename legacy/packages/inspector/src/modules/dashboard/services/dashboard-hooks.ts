/**
 * Dashboard Hooks - React Query
 */

import { useQuery } from '@tanstack/react-query';
import { dashboardApi } from './dashboard-api';
import { appConfig } from '@core/config/app';

const KEYS = {
  stats: ['dashboard', 'stats'] as const,
  recent: ['dashboard', 'recent'] as const,
  supervisor: ['dashboard', 'supervisor'] as const,
  liveStatus: ['dashboard', 'live-status'] as const,
};

/** Agent's own stats for today */
export function useAgentStats() {
  const today = new Date().toISOString().split('T')[0];
  return useQuery({
    queryKey: [...KEYS.stats, today],
    queryFn: () => dashboardApi.getStats({ date_from: today, date_to: today }),
    staleTime: appConfig.cache.dashboard,
  });
}

/** Agent's recent inspections */
export function useRecentInspections() {
  return useQuery({
    queryKey: KEYS.recent,
    queryFn: dashboardApi.getRecentInspections,
    staleTime: appConfig.cache.inspections,
  });
}

/** Supervisor full dashboard (only fetched when user is supervisor) */
export function useSupervisorDashboard(enabled = true) {
  return useQuery({
    queryKey: KEYS.supervisor,
    queryFn: dashboardApi.getSupervisorDashboard,
    staleTime: appConfig.cache.dashboard,
    enabled,
  });
}

/** Live agent status (auto-refresh 30s to match Redis cache) */
export function useLiveStatus(enabled = true) {
  return useQuery({
    queryKey: KEYS.liveStatus,
    queryFn: dashboardApi.getLiveStatus,
    staleTime: appConfig.cache.liveStatus,
    refetchInterval: enabled ? 30_000 : false,
    refetchIntervalInBackground: false,
    enabled,
  });
}
