/**
 * React Query hooks for Treasury Dashboard
 *
 * Provides cached data fetching for:
 * - Treasury statistics
 * - Pending payments for validation
 * - Payment history
 * - Revenue analytics
 *
 * Cache strategy:
 * - Stats: 2 min stale (updates frequently during work)
 * - Pending payments: 30 sec stale (real-time validation queue)
 * - Payment history: 5 min stale
 *
 * @module admin/hooks
 * @date 2026-01-25
 */

'use client';

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import apiClient from '@/core/api/client';

// =============================================================================
// TYPES
// =============================================================================

export interface TreasuryStats {
  pendingCount: number;
  pendingAmount: number;
  validatedToday: number;
  validatedAmountToday: number;
  rejectedToday: number;
  totalRevenue: number;
  revenueThisMonth: number;
  avgValidationTime: number; // in minutes
}

export interface TreasuryPayment {
  id: string;
  reference: string;
  amount: number;
  currency: string;
  payment_method: string;
  status: string;
  workflow_status: string;
  user_id: string;
  user_email?: string;
  user_name?: string;
  declaration_id?: string;
  service_request_id?: string;
  created_at: string;
  submitted_at?: string;
  locked_by?: string;
  locked_at?: string;
}

export interface TreasuryPaymentListResponse {
  payments: TreasuryPayment[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface TreasuryFilters {
  status?: string;
  workflow_status?: string;
  payment_method?: string;
  minAmount?: number;
  maxAmount?: number;
  startDate?: string;
  endDate?: string;
  search?: string;
  page?: number;
  pageSize?: number;
}

export interface RevenueData {
  date: string;
  amount: number;
  count: number;
}

export interface RevenueAnalytics {
  daily: RevenueData[];
  weekly: RevenueData[];
  monthly: RevenueData[];
  byPaymentMethod: { method: string; amount: number; count: number }[];
  byStatus: { status: string; amount: number; count: number }[];
}

// =============================================================================
// QUERY KEYS
// =============================================================================

export const treasuryQueryKeys = {
  all: ['treasury'] as const,
  stats: () => [...treasuryQueryKeys.all, 'stats'] as const,
  payments: () => [...treasuryQueryKeys.all, 'payments'] as const,
  paymentList: (filters: TreasuryFilters) =>
    [...treasuryQueryKeys.payments(), JSON.stringify(filters)] as const,
  pendingPayments: () => [...treasuryQueryKeys.payments(), 'pending'] as const,
  paymentDetail: (id: string) => [...treasuryQueryKeys.payments(), 'detail', id] as const,
  analytics: () => [...treasuryQueryKeys.all, 'analytics'] as const,
  revenueAnalytics: (period: string) => [...treasuryQueryKeys.analytics(), 'revenue', period] as const,
};

// =============================================================================
// CACHE CONFIGURATION
// =============================================================================

const CACHE_CONFIG = {
  // Stats - updates during work
  stats: {
    staleTime: 2 * 60 * 1000, // 2 minutes
    gcTime: 10 * 60 * 1000, // 10 minutes
  },
  // Pending payments - real-time queue
  pending: {
    staleTime: 30 * 1000, // 30 seconds
    gcTime: 5 * 60 * 1000, // 5 minutes
  },
  // Payment history
  history: {
    staleTime: 5 * 60 * 1000, // 5 minutes
    gcTime: 15 * 60 * 1000, // 15 minutes
  },
  // Analytics
  analytics: {
    staleTime: 10 * 60 * 1000, // 10 minutes
    gcTime: 30 * 60 * 1000, // 30 minutes
  },
};

// =============================================================================
// STATS HOOK
// =============================================================================

/**
 * Fetch treasury dashboard statistics
 */
export function useTreasuryStats(options?: { enabled?: boolean }) {
  return useQuery<TreasuryStats>({
    queryKey: treasuryQueryKeys.stats(),
    queryFn: async () => {
      const response = await apiClient.get('/treasury/stats');
      return response.data;
    },
    ...CACHE_CONFIG.stats,
    enabled: options?.enabled !== false,
    retry: 2,
  });
}

// =============================================================================
// PAYMENTS HOOKS
// =============================================================================

/**
 * Fetch pending payments for validation (real-time queue)
 */
export function usePendingPayments(options?: { enabled?: boolean }) {
  return useQuery<TreasuryPayment[]>({
    queryKey: treasuryQueryKeys.pendingPayments(),
    queryFn: async () => {
      const response = await apiClient.get('/treasury/payments/pending');
      return response.data.payments;
    },
    ...CACHE_CONFIG.pending,
    enabled: options?.enabled !== false,
    retry: 2,
    // Auto-refresh for real-time queue
    refetchInterval: 30 * 1000,
    refetchIntervalInBackground: false,
  });
}

/**
 * Fetch payments with filters and pagination
 */
export function useTreasuryPayments(filters: TreasuryFilters = {}) {
  const { page = 1, pageSize = 20, ...otherFilters } = filters;

  return useQuery<TreasuryPaymentListResponse>({
    queryKey: treasuryQueryKeys.paymentList(filters),
    queryFn: async () => {
      const params = new URLSearchParams();
      params.set('page', String(page));
      params.set('page_size', String(pageSize));

      Object.entries(otherFilters).forEach(([key, value]) => {
        if (value !== undefined && value !== null && value !== '') {
          params.set(key, String(value));
        }
      });

      const response = await apiClient.get(`/treasury/payments?${params}`);
      return response.data;
    },
    ...CACHE_CONFIG.history,
    placeholderData: (previousData) => previousData,
    retry: 2,
  });
}

/**
 * Fetch a single payment by ID
 */
export function useTreasuryPayment(paymentId: string, options?: { enabled?: boolean }) {
  return useQuery<TreasuryPayment>({
    queryKey: treasuryQueryKeys.paymentDetail(paymentId),
    queryFn: async () => {
      const response = await apiClient.get(`/treasury/payments/${paymentId}`);
      return response.data;
    },
    ...CACHE_CONFIG.history,
    enabled: options?.enabled !== false && !!paymentId,
    retry: 2,
  });
}

// =============================================================================
// ANALYTICS HOOKS
// =============================================================================

/**
 * Fetch revenue analytics
 */
export function useRevenueAnalytics(
  period: 'week' | 'month' | 'year' = 'month',
  options?: { enabled?: boolean }
) {
  return useQuery<RevenueAnalytics>({
    queryKey: treasuryQueryKeys.revenueAnalytics(period),
    queryFn: async () => {
      const response = await apiClient.get(`/treasury/analytics/revenue?period=${period}`);
      return response.data;
    },
    ...CACHE_CONFIG.analytics,
    enabled: options?.enabled !== false,
    retry: 2,
  });
}

// =============================================================================
// MUTATION HOOKS
// =============================================================================

/**
 * Validate (approve) a payment
 */
export function useValidatePayment() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({ paymentId, notes }: { paymentId: string; notes?: string }) => {
      const response = await apiClient.post(`/treasury/payments/${paymentId}/validate`, { notes });
      return response.data;
    },
    onSuccess: (_, variables) => {
      // Invalidate affected caches
      queryClient.invalidateQueries({ queryKey: treasuryQueryKeys.pendingPayments() });
      queryClient.invalidateQueries({ queryKey: treasuryQueryKeys.stats() });
      queryClient.invalidateQueries({ queryKey: treasuryQueryKeys.paymentDetail(variables.paymentId) });
    },
  });
}

/**
 * Reject a payment
 */
export function useRejectPayment() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({ paymentId, reason }: { paymentId: string; reason: string }) => {
      const response = await apiClient.post(`/treasury/payments/${paymentId}/reject`, { reason });
      return response.data;
    },
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: treasuryQueryKeys.pendingPayments() });
      queryClient.invalidateQueries({ queryKey: treasuryQueryKeys.stats() });
      queryClient.invalidateQueries({ queryKey: treasuryQueryKeys.paymentDetail(variables.paymentId) });
    },
  });
}

/**
 * Lock a payment for review
 */
export function useLockPayment() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (paymentId: string) => {
      const response = await apiClient.post(`/treasury/payments/${paymentId}/lock`);
      return response.data;
    },
    onSuccess: (_, paymentId) => {
      queryClient.invalidateQueries({ queryKey: treasuryQueryKeys.pendingPayments() });
      queryClient.invalidateQueries({ queryKey: treasuryQueryKeys.paymentDetail(paymentId) });
    },
  });
}

/**
 * Unlock a payment (release lock)
 */
export function useUnlockPayment() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (paymentId: string) => {
      const response = await apiClient.post(`/treasury/payments/${paymentId}/unlock`);
      return response.data;
    },
    onSuccess: (_, paymentId) => {
      queryClient.invalidateQueries({ queryKey: treasuryQueryKeys.pendingPayments() });
      queryClient.invalidateQueries({ queryKey: treasuryQueryKeys.paymentDetail(paymentId) });
    },
  });
}

// =============================================================================
// PREFETCH UTILITIES
// =============================================================================

/**
 * Prefetch treasury data for faster navigation
 */
export function usePrefetchTreasuryData() {
  const queryClient = useQueryClient();

  const prefetchStats = () => {
    queryClient.prefetchQuery({
      queryKey: treasuryQueryKeys.stats(),
      queryFn: async () => {
        const response = await apiClient.get('/treasury/stats');
        return response.data;
      },
      ...CACHE_CONFIG.stats,
    });
  };

  const prefetchPendingPayments = () => {
    queryClient.prefetchQuery({
      queryKey: treasuryQueryKeys.pendingPayments(),
      queryFn: async () => {
        const response = await apiClient.get('/treasury/payments/pending');
        return response.data.payments;
      },
      ...CACHE_CONFIG.pending,
    });
  };

  return { prefetchStats, prefetchPendingPayments };
}

// =============================================================================
// CACHE INVALIDATION
// =============================================================================

/**
 * Hook to invalidate treasury caches
 */
export function useInvalidateTreasuryCache() {
  const queryClient = useQueryClient();

  const invalidateAll = () => {
    queryClient.invalidateQueries({ queryKey: treasuryQueryKeys.all });
  };

  const invalidateStats = () => {
    queryClient.invalidateQueries({ queryKey: treasuryQueryKeys.stats() });
  };

  const invalidatePending = () => {
    queryClient.invalidateQueries({ queryKey: treasuryQueryKeys.pendingPayments() });
  };

  const invalidatePayments = () => {
    queryClient.invalidateQueries({ queryKey: treasuryQueryKeys.payments() });
  };

  const invalidateAnalytics = () => {
    queryClient.invalidateQueries({ queryKey: treasuryQueryKeys.analytics() });
  };

  return {
    invalidateAll,
    invalidateStats,
    invalidatePending,
    invalidatePayments,
    invalidateAnalytics,
  };
}

export default useTreasuryStats;
