/**
 * useAgentPersonalStats Hook
 * Fetches personal performance statistics for the current agent
 *
 * @module agent-dashboard/hooks
 * @date 2026-01-25
 *
 * Calls: GET /api/v1/statistics/agent/{agent_profile_id}
 */

'use client';

import { useQuery } from '@tanstack/react-query';
import { fetchClient } from '@/core/api';
import { useAgentProfile } from './useAgentDashboard';

// =============================================================================
// TYPES
// =============================================================================

export interface AgentPersonalStats {
  /** Agent profile ID */
  agentProfileId: string;
  /** Period in days */
  periodDays: number;
  /** Total assignments in period */
  totalAssignments: number;
  /** Completed assignments */
  completedAssignments: number;
  /** Pending assignments */
  pendingAssignments: number;
  /** Rejected assignments */
  rejectedAssignments: number;
  /** Average processing time in hours */
  avgProcessingTimeHours: number;
  /** Success rate (0-1) */
  successRate: number;
  /** Quality score average (0-10) */
  qualityScoreAvg: number;
  /** Deadline compliance rate (0-1) */
  deadlineComplianceRate: number;
  /** Breakdown by status */
  byStatus: Record<string, number>;
  /** Breakdown by item type */
  byType: Record<string, number>;
}

export interface UseAgentPersonalStatsReturn {
  /** Loading state */
  isLoading: boolean;
  /** Error state */
  isError: boolean;
  /** Error object */
  error: Error | null;
  /** Statistics data */
  stats: AgentPersonalStats | null;
  /** Refetch function */
  refetch: () => void;
  /** Whether the agent profile is available */
  hasProfile: boolean;
}

// =============================================================================
// QUERY KEY
// =============================================================================

export const AGENT_PERSONAL_STATS_QUERY_KEY = 'agent-personal-stats';

// =============================================================================
// API CALL
// =============================================================================

interface BackendStatsResponse {
  agent_profile_id: string;
  period_days: number;
  total_assignments: number;
  completed_assignments: number;
  pending_assignments: number;
  rejected_assignments: number;
  avg_processing_time_hours: number;
  success_rate: number;
  quality_score_avg: number;
  deadline_compliance_rate: number;
  by_status: Record<string, number>;
  by_type: Record<string, number>;
}

async function fetchAgentPersonalStats(
  agentProfileId: string,
  periodDays: number = 30
): Promise<AgentPersonalStats> {
  const response = await fetchClient.get<BackendStatsResponse>(
    `/statistics/agent/${agentProfileId}`,
    { period_days: periodDays }
  );

  return {
    agentProfileId: response.agent_profile_id,
    periodDays: response.period_days,
    totalAssignments: response.total_assignments || 0,
    completedAssignments: response.completed_assignments || 0,
    pendingAssignments: response.pending_assignments || 0,
    rejectedAssignments: response.rejected_assignments || 0,
    avgProcessingTimeHours: response.avg_processing_time_hours || 0,
    successRate: response.success_rate || 0,
    qualityScoreAvg: response.quality_score_avg || 0,
    deadlineComplianceRate: response.deadline_compliance_rate || 0,
    byStatus: response.by_status || {},
    byType: response.by_type || {},
  };
}

// =============================================================================
// HOOK
// =============================================================================

/**
 * Hook to fetch personal performance statistics for the current agent
 *
 * @param periodDays - Number of days to fetch statistics for (default: 30)
 * @returns Agent personal statistics
 */
export function useAgentPersonalStats(periodDays: number = 30): UseAgentPersonalStatsReturn {
  // Get agent profile to retrieve agent_profile_id
  const { data: agentProfile, isLoading: profileLoading } = useAgentProfile();

  const agentProfileId = agentProfile?.id;

  const {
    data,
    isLoading: statsLoading,
    isError,
    error,
    refetch,
  } = useQuery<AgentPersonalStats, Error>({
    queryKey: [AGENT_PERSONAL_STATS_QUERY_KEY, agentProfileId, periodDays],
    queryFn: () => {
      if (!agentProfileId) throw new Error('Agent profile ID required');
      return fetchAgentPersonalStats(agentProfileId, periodDays);
    },
    enabled: !!agentProfileId,
    staleTime: 60 * 1000, // 1 minute
    refetchInterval: 5 * 60 * 1000, // Auto-refresh every 5 minutes
    retry: 2,
  });

  return {
    isLoading: profileLoading || statsLoading,
    isError,
    error: error as Error | null,
    stats: data || null,
    refetch,
    hasProfile: !!agentProfileId,
  };
}

export default useAgentPersonalStats;
