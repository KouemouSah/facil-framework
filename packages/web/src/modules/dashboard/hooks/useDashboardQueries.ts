/**
 * React Query hooks for User Dashboard
 *
 * Provides cached data fetching for:
 * - Dashboard statistics
 * - Recent declarations
 * - Recent payments
 * - Service requests
 *
 * Cache strategy:
 * - Dashboard stats: 2 min stale (user-specific, changes on actions)
 * - Recent lists: 2 min stale
 *
 * @module dashboard/hooks
 * @date 2026-01-25
 */

'use client';

import { useQuery, useQueryClient } from '@tanstack/react-query';
import { declarationsApi } from '@/modules/declarations/services/api';
import { paymentsApi } from '@/modules/payments/services/api';
import type { DeclarationResponse } from '@/types/declaration';
import type { PaymentResponse } from '@/types/payment';

// =============================================================================
// QUERY KEYS
// =============================================================================

export const dashboardQueryKeys = {
  all: ['dashboard'] as const,
  stats: () => [...dashboardQueryKeys.all, 'stats'] as const,
  recentDeclarations: () => [...dashboardQueryKeys.all, 'recent-declarations'] as const,
  recentPayments: () => [...dashboardQueryKeys.all, 'recent-payments'] as const,
};

// =============================================================================
// CACHE CONFIGURATION
// =============================================================================

const CACHE_CONFIG = {
  // Dashboard data - user-specific, changes on user actions
  dashboard: {
    staleTime: 2 * 60 * 1000, // 2 minutes
    gcTime: 10 * 60 * 1000, // 10 minutes
  },
};

// =============================================================================
// TYPES
// =============================================================================

export interface DashboardStats {
  declarationsInProgress: number;
  declarationsCompleted: number;
  totalPayments: number;
  unreadNotifications: number;
}

interface DashboardDataResponse {
  stats: DashboardStats;
  recentDeclarations: DeclarationResponse[];
  recentPayments: PaymentResponse[];
}

// =============================================================================
// HELPER FUNCTIONS
// =============================================================================

function calculateDeclarationStats(declarations: DeclarationResponse[]): {
  inProgress: number;
  completed: number;
} {
  let inProgress = 0;
  let completed = 0;

  for (const decl of declarations) {
    if (decl.status === 'draft' || decl.status === 'submitted' || decl.status === 'processing') {
      inProgress++;
    } else if (decl.status === 'accepted') {
      completed++;
    }
  }

  return { inProgress, completed };
}

function calculateTotalPayments(payments: PaymentResponse[]): number {
  return payments
    .filter(p => p.status === 'completed')
    .reduce((sum, p) => sum + (p.amount || 0), 0);
}

// =============================================================================
// DATA FETCHER
// =============================================================================

async function fetchDashboardData(): Promise<DashboardDataResponse> {
  // Fetch data in parallel
  const [declarationsResponse, paymentsResponse] = await Promise.all([
    declarationsApi.listDeclarations({ pageSize: 50 }),
    paymentsApi.listPayments({ pageSize: 10 }),
  ]);

  const allDeclarations = declarationsResponse.declarations;
  const declStats = calculateDeclarationStats(allDeclarations);
  const totalPaymentsAmount = calculateTotalPayments(paymentsResponse.payments);

  return {
    stats: {
      declarationsInProgress: declStats.inProgress,
      declarationsCompleted: declStats.completed,
      totalPayments: totalPaymentsAmount,
      unreadNotifications: 0,
    },
    recentDeclarations: allDeclarations.slice(0, 5),
    recentPayments: paymentsResponse.payments,
  };
}

// =============================================================================
// HOOKS
// =============================================================================

/**
 * Fetch dashboard data with caching
 * Combines stats, recent declarations, and recent payments
 */
export function useDashboardDataQuery(options?: { enabled?: boolean }) {
  return useQuery<DashboardDataResponse>({
    queryKey: dashboardQueryKeys.stats(),
    queryFn: fetchDashboardData,
    ...CACHE_CONFIG.dashboard,
    enabled: options?.enabled !== false,
    retry: 2,
  });
}

/**
 * Fetch only recent declarations
 */
export function useRecentDeclarations(options?: { enabled?: boolean; limit?: number }) {
  const limit = options?.limit || 5;

  return useQuery<DeclarationResponse[]>({
    queryKey: dashboardQueryKeys.recentDeclarations(),
    queryFn: async () => {
      const response = await declarationsApi.listDeclarations({ pageSize: limit });
      return response.declarations;
    },
    ...CACHE_CONFIG.dashboard,
    enabled: options?.enabled !== false,
    retry: 2,
  });
}

/**
 * Fetch only recent payments
 */
export function useRecentPayments(options?: { enabled?: boolean; limit?: number }) {
  const limit = options?.limit || 10;

  return useQuery<PaymentResponse[]>({
    queryKey: dashboardQueryKeys.recentPayments(),
    queryFn: async () => {
      const response = await paymentsApi.listPayments({ pageSize: limit });
      return response.payments;
    },
    ...CACHE_CONFIG.dashboard,
    enabled: options?.enabled !== false,
    retry: 2,
  });
}

// =============================================================================
// PREFETCH UTILITIES
// =============================================================================

/**
 * Prefetch dashboard data for faster navigation
 */
export function usePrefetchDashboard() {
  const queryClient = useQueryClient();

  const prefetch = () => {
    queryClient.prefetchQuery({
      queryKey: dashboardQueryKeys.stats(),
      queryFn: fetchDashboardData,
      ...CACHE_CONFIG.dashboard,
    });
  };

  return { prefetch };
}

// =============================================================================
// CACHE INVALIDATION
// =============================================================================

/**
 * Hook to invalidate dashboard caches
 * Use after creating/updating declarations or payments
 */
export function useInvalidateDashboardCache() {
  const queryClient = useQueryClient();

  const invalidateAll = () => {
    queryClient.invalidateQueries({ queryKey: dashboardQueryKeys.all });
  };

  const invalidateStats = () => {
    queryClient.invalidateQueries({ queryKey: dashboardQueryKeys.stats() });
  };

  const invalidateDeclarations = () => {
    queryClient.invalidateQueries({ queryKey: dashboardQueryKeys.recentDeclarations() });
    // Also invalidate stats since they depend on declarations
    queryClient.invalidateQueries({ queryKey: dashboardQueryKeys.stats() });
  };

  const invalidatePayments = () => {
    queryClient.invalidateQueries({ queryKey: dashboardQueryKeys.recentPayments() });
    // Also invalidate stats since they depend on payments
    queryClient.invalidateQueries({ queryKey: dashboardQueryKeys.stats() });
  };

  return {
    invalidateAll,
    invalidateStats,
    invalidateDeclarations,
    invalidatePayments,
  };
}

export default useDashboardDataQuery;
