/**
 * useEntityStats Hook
 * Fetches queue statistics for an entity dashboard
 *
 * @module agent-dashboard/hooks
 * @date 2026-01-18
 *
 * Calls: GET /api/v1/agent/service-requests/queue/stats?entity_code={entityCode}
 */

'use client';

import { useQuery } from '@tanstack/react-query';
import { fetchClient } from '@/core/api';
import type { EntityCode } from '../types';

// =============================================================================
// TYPES
// =============================================================================

export interface EntityQueueStats {
  /** Number of pending items in queue */
  pending: number;
  /** Number of items assigned to agents */
  assigned: number;
  /** Number of items completed in last 24h */
  completedToday: number;
  /** Number of escalated items */
  escalated: number;
  /** Number of items with SLA violations */
  slaViolations: number;
  /** Average processing time in hours */
  avgProcessingHours: number;
}

export interface UseEntityStatsReturn {
  /** Loading state */
  isLoading: boolean;
  /** Error state */
  isError: boolean;
  /** Error object */
  error: Error | null;
  /** Queue statistics */
  stats: {
    pendingCount: number;
    inProgressCount: number;
    completedTodayCount: number;
    slaViolationsCount: number;
    escalatedCount: number;
  };
  /** Raw stats from API */
  rawStats: EntityQueueStats | null;
  /** Refetch function */
  refetch: () => void;
}

// =============================================================================
// QUERY KEY
// =============================================================================

export const ENTITY_STATS_QUERY_KEY = 'entity-queue-stats';

// =============================================================================
// API CALL
// =============================================================================

interface BackendStatsResponse {
  pending: number;
  assigned: number;
  completed_today: number;
  escalated: number;
  sla_violations: number;
  avg_processing_hours: number;
}

async function fetchEntityStats(entityCode: EntityCode): Promise<EntityQueueStats> {
  const response = await fetchClient.get<BackendStatsResponse>(
    '/agent/service-requests/queue/stats',
    { entity_code: entityCode }
  );

  return {
    pending: response.pending || 0,
    assigned: response.assigned || 0,
    completedToday: response.completed_today || 0,
    escalated: response.escalated || 0,
    slaViolations: response.sla_violations || 0,
    avgProcessingHours: response.avg_processing_hours || 0,
  };
}

// =============================================================================
// HOOK
// =============================================================================

/**
 * Hook to fetch queue statistics for an entity dashboard
 *
 * @param entityCode - The entity code (e.g., 'CNEDOGE_PASAPORTE', 'EXTRANJERIA')
 * @returns Entity queue statistics
 */
export function useEntityStats(entityCode: EntityCode): UseEntityStatsReturn {
  const {
    data,
    isLoading,
    isError,
    error,
    refetch,
  } = useQuery<EntityQueueStats, Error>({
    queryKey: [ENTITY_STATS_QUERY_KEY, entityCode],
    queryFn: () => fetchEntityStats(entityCode),
    staleTime: 30 * 1000, // 30 seconds
    refetchInterval: 60 * 1000, // Auto-refresh every minute
    retry: 2,
  });

  // Map to the format expected by GenericEntityDashboard
  const stats = {
    pendingCount: data?.pending || 0,
    inProgressCount: data?.assigned || 0,
    completedTodayCount: data?.completedToday || 0,
    slaViolationsCount: data?.slaViolations || 0,
    escalatedCount: data?.escalated || 0,
  };

  return {
    isLoading,
    isError,
    error: error as Error | null,
    stats,
    rawStats: data || null,
    refetch,
  };
}

export default useEntityStats;
