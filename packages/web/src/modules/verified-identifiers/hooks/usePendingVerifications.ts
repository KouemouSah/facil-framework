/**
 * Hook for fetching pending verifications list
 */

import { useQuery } from '@tanstack/react-query';
import { getPendingVerifications } from '../services/api';
import type { VerificationFilters, PendingVerificationListResponse } from '../types';

export const PENDING_VERIFICATIONS_KEY = 'pending-verifications';

interface UsePendingVerificationsOptions {
  enabled?: boolean;
}

export function usePendingVerifications(
  filters: VerificationFilters,
  options: UsePendingVerificationsOptions = {}
) {
  const { enabled = true } = options;

  return useQuery<PendingVerificationListResponse, Error>({
    queryKey: [
      PENDING_VERIFICATIONS_KEY,
      filters.entityCode,
      filters.verificationStatus,
      filters.page,
      filters.pageSize,
    ],
    queryFn: () => getPendingVerifications(filters),
    enabled: enabled && !!filters.entityCode,
    staleTime: 30 * 1000, // 30 seconds
    refetchOnWindowFocus: true,
  });
}
