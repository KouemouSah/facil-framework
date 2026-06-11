/**
 * Hook for fetching pending payments for treasury validation
 *
 * @module treasury/hooks
 */

import { useQuery } from '@tanstack/react-query';
import { treasuryApi } from '../services/api';
import type { PendingPaymentsParams, PendingPaymentsListResponse } from '../types';

export const PENDING_PAYMENTS_QUERY_KEY = 'treasury-pending-payments';

export function usePendingPayments(params: PendingPaymentsParams = {}) {
  return useQuery<PendingPaymentsListResponse, Error>({
    queryKey: [PENDING_PAYMENTS_QUERY_KEY, params],
    queryFn: () => treasuryApi.getPendingPayments(params),
    staleTime: 30 * 1000, // 30 seconds - payments can change quickly
    refetchInterval: 60 * 1000, // Auto-refresh every minute
    retry: 2,
  });
}

export default usePendingPayments;
