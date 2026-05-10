/**
 * useDashboardData Hook
 * Fetches citizen dashboard summary via React Query (TanStack Query)
 *
 * @module dashboard/hooks
 */

import { useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { serviceRequestsApi } from '@/modules/service-requests/services'
import type { DashboardSummary } from '@/modules/service-requests/services'

// =============================================================================
// TYPES
// =============================================================================

export interface DashboardStats {
  active: number
  completed: number
  pendingAction: number
  totalPaid: number
  unreadNotifications: number
}

export interface DashboardData {
  stats: DashboardStats
  summary: DashboardSummary | null
  isLoading: boolean
  error: string | null
  refetch: () => void
}

// =============================================================================
// QUERY KEY
// =============================================================================

const DASHBOARD_QUERY_KEY = ['citizen-dashboard-summary'] as const

// =============================================================================
// HOOK
// =============================================================================

export function useDashboardData(): DashboardData {
  const {
    data: summary,
    isLoading,
    error,
    refetch,
  } = useQuery<DashboardSummary, Error>({
    queryKey: DASHBOARD_QUERY_KEY,
    queryFn: () => serviceRequestsApi.getDashboardSummary(),
    staleTime: 60_000,            // 1 minute before considered stale
    refetchOnWindowFocus: true,   // Refresh when user returns to tab
    retry: 2,
  })

  const stats = useMemo<DashboardStats>(() => {
    if (!summary) {
      return { active: 0, completed: 0, pendingAction: 0, totalPaid: 0, unreadNotifications: 0 }
    }
    return {
      active: summary.stats.active,
      completed: summary.stats.completed,
      pendingAction: summary.stats.pendingAction,
      totalPaid: summary.stats.totalPaid,
      unreadNotifications: summary.unreadCount,
    }
  }, [summary])

  return {
    stats,
    summary: summary ?? null,
    isLoading,
    error: error?.message ?? null,
    refetch: () => { refetch() },
  }
}

export default useDashboardData
