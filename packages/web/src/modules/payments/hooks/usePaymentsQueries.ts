/**
 * React Query hooks for Payments
 *
 * Provides cached data fetching for:
 * - User payments list (paginated)
 * - Payment details
 * - Payment plans
 *
 * Cache strategy:
 * - Payments list: 2 min stale (changes on user actions)
 * - Payment detail: 2 min stale
 * - Payment plans: 5 min stale (more stable)
 *
 * @module payments/hooks
 * @date 2026-01-25
 */

'use client';

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { paymentsApi } from '../services/api';
import type {
  PaymentResponse,
  PaymentListResponse,
  PaymentListParams,
} from '@/types/payment';

// Types for create/update (generic Record for API compatibility)
type PaymentCreateData = Record<string, unknown>;
type PaymentUpdateData = Record<string, unknown>;
type PaymentPlanData = Record<string, unknown>;

// =============================================================================
// QUERY KEYS
// =============================================================================

export const paymentQueryKeys = {
  all: ['payments'] as const,
  lists: () => [...paymentQueryKeys.all, 'list'] as const,
  list: (params: PaymentListParams) =>
    [...paymentQueryKeys.lists(), JSON.stringify(params)] as const,
  detail: (id: string) => [...paymentQueryKeys.all, 'detail', id] as const,
  plan: (paymentId: string) => [...paymentQueryKeys.all, 'plan', paymentId] as const,
};

// =============================================================================
// CACHE CONFIGURATION
// =============================================================================

const CACHE_CONFIG = {
  // Payments list - user-specific
  list: {
    staleTime: 2 * 60 * 1000, // 2 minutes
    gcTime: 10 * 60 * 1000, // 10 minutes
  },
  // Payment detail
  detail: {
    staleTime: 2 * 60 * 1000, // 2 minutes
    gcTime: 10 * 60 * 1000, // 10 minutes
  },
  // Payment plans - more stable
  plan: {
    staleTime: 5 * 60 * 1000, // 5 minutes
    gcTime: 15 * 60 * 1000, // 15 minutes
  },
};

// =============================================================================
// LIST HOOKS
// =============================================================================

/**
 * Fetch user payments with pagination and caching
 */
export function usePayments(params: PaymentListParams = {}) {
  return useQuery<PaymentListResponse>({
    queryKey: paymentQueryKeys.list(params),
    queryFn: () => paymentsApi.listPayments(params),
    ...CACHE_CONFIG.list,
    placeholderData: (previousData) => previousData,
    retry: 2,
  });
}

/**
 * Fetch recent payments (for dashboard)
 */
export function useRecentPayments(limit: number = 10) {
  return useQuery<PaymentResponse[]>({
    queryKey: [...paymentQueryKeys.lists(), 'recent', limit],
    queryFn: async () => {
      const response = await paymentsApi.listPayments({ pageSize: limit });
      return response.payments;
    },
    ...CACHE_CONFIG.list,
    retry: 2,
  });
}

// =============================================================================
// DETAIL HOOKS
// =============================================================================

/**
 * Fetch a single payment by ID
 */
export function usePayment(paymentId: string, options?: { enabled?: boolean }) {
  return useQuery<PaymentResponse>({
    queryKey: paymentQueryKeys.detail(paymentId),
    queryFn: () => paymentsApi.getPayment(paymentId),
    ...CACHE_CONFIG.detail,
    enabled: options?.enabled !== false && !!paymentId,
    retry: 2,
  });
}

/**
 * Fetch payment plan with installments
 */
export function usePaymentPlan(planId: string, options?: { enabled?: boolean }) {
  return useQuery<PaymentPlanData>({
    queryKey: paymentQueryKeys.plan(planId),
    queryFn: () => paymentsApi.getPaymentPlan(planId),
    ...CACHE_CONFIG.plan,
    enabled: options?.enabled !== false && !!planId,
    retry: 2,
  });
}

// =============================================================================
// MUTATION HOOKS
// =============================================================================

/**
 * Create a new payment
 */
export function useCreatePayment() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: PaymentCreateData) => paymentsApi.createPayment(data),
    onSuccess: () => {
      // Invalidate payments list
      queryClient.invalidateQueries({ queryKey: paymentQueryKeys.lists() });
    },
  });
}

/**
 * Update a payment
 */
export function useUpdatePayment() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: PaymentUpdateData }) =>
      paymentsApi.updatePayment(id, data),
    onSuccess: (_, variables) => {
      // Invalidate specific payment and list
      queryClient.invalidateQueries({ queryKey: paymentQueryKeys.detail(variables.id) });
      queryClient.invalidateQueries({ queryKey: paymentQueryKeys.lists() });
    },
  });
}

// =============================================================================
// PREFETCH UTILITIES
// =============================================================================

/**
 * Prefetch payment details for faster navigation
 */
export function usePrefetchPayment() {
  const queryClient = useQueryClient();

  const prefetch = (paymentId: string) => {
    queryClient.prefetchQuery({
      queryKey: paymentQueryKeys.detail(paymentId),
      queryFn: () => paymentsApi.getPayment(paymentId),
      ...CACHE_CONFIG.detail,
    });
  };

  return { prefetch };
}

// =============================================================================
// CACHE INVALIDATION
// =============================================================================

/**
 * Hook to invalidate payments caches
 */
export function useInvalidatePaymentsCache() {
  const queryClient = useQueryClient();

  const invalidateAll = () => {
    queryClient.invalidateQueries({ queryKey: paymentQueryKeys.all });
  };

  const invalidateLists = () => {
    queryClient.invalidateQueries({ queryKey: paymentQueryKeys.lists() });
  };

  const invalidatePayment = (paymentId: string) => {
    queryClient.invalidateQueries({ queryKey: paymentQueryKeys.detail(paymentId) });
  };

  return {
    invalidateAll,
    invalidateLists,
    invalidatePayment,
  };
}

export default usePayments;
