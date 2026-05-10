/**
 * Hook for SLA statistics (Phase 1B)
 *
 * @module treasury/hooks
 */

import { useQuery } from '@tanstack/react-query';
import { treasuryApi } from '../services/api';
import type { SLAStats } from '../types';

export const SLA_STATS_QUERY_KEY = 'treasury-sla-stats';

/**
 * Fetch SLA statistics
 * @param paymentMethod - Optional filter by payment method
 */
export function useSLAStats(paymentMethod?: string) {
  return useQuery<SLAStats, Error>({
    queryKey: [SLA_STATS_QUERY_KEY, paymentMethod],
    queryFn: () => treasuryApi.getSLAStats(paymentMethod),
    staleTime: 60 * 1000, // 1 minute
    refetchInterval: 2 * 60 * 1000, // Auto-refresh every 2 minutes
    retry: 2,
  });
}

export default useSLAStats;
