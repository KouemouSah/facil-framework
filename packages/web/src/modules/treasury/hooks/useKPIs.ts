/**
 * Treasury KPIs Hooks (Phase 4)
 * Hooks for KPIs dashboard and agent performance
 */

import { useQuery } from '@tanstack/react-query';
import { treasuryApi } from '../services/api';
import type { KPIResponse, AgentPerformanceResponse, KPIParams } from '../types';

export const KPI_STATS_QUERY_KEY = 'treasury-kpis';
export const AGENT_PERFORMANCE_QUERY_KEY = 'treasury-agent-performance';

/**
 * Hook for fetching Treasury KPIs
 */
export function useKPIs(params: KPIParams = { period: 'month' }) {
  return useQuery<KPIResponse, Error>({
    queryKey: [KPI_STATS_QUERY_KEY, params],
    queryFn: () => treasuryApi.getKPIs({
      period: params.period,
      dateFrom: params.dateFrom,
      dateTo: params.dateTo,
    }),
    staleTime: 5 * 60 * 1000, // 5 minutes
    refetchInterval: 5 * 60 * 1000, // Auto-refresh every 5 minutes
  });
}

/**
 * Hook for fetching agent performance statistics
 */
export function useAgentPerformance(params: KPIParams = { period: 'month' }) {
  return useQuery<AgentPerformanceResponse, Error>({
    queryKey: [AGENT_PERFORMANCE_QUERY_KEY, params],
    queryFn: () => treasuryApi.getAgentPerformance({
      period: params.period,
      dateFrom: params.dateFrom,
      dateTo: params.dateTo,
    }),
    staleTime: 5 * 60 * 1000,
    refetchInterval: 5 * 60 * 1000,
  });
}
