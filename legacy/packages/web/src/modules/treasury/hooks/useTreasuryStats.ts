/**
 * Hook for treasury dashboard statistics
 *
 * @module treasury/hooks
 */

import { useQuery } from '@tanstack/react-query';
import { treasuryApi } from '../services/api';
import type { TreasuryStats } from '../types';

export const TREASURY_STATS_QUERY_KEY = 'treasury-stats';

export function useTreasuryStats() {
  return useQuery<TreasuryStats, Error>({
    queryKey: [TREASURY_STATS_QUERY_KEY],
    queryFn: () => treasuryApi.getDashboardStats(),
    staleTime: 60 * 1000, // 1 minute
    refetchInterval: 2 * 60 * 1000, // Auto-refresh every 2 minutes
    retry: 2,
  });
}

export default useTreasuryStats;
