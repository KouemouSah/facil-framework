/**
 * Hook for fetching verification details with navigation
 */

import { useQuery } from '@tanstack/react-query';
import { getVerificationDetails } from '../services/api';
import type { VerificationDetail } from '../types';

export const VERIFICATION_DETAILS_KEY = 'verification-details';

interface UseVerificationDetailsOptions {
  enabled?: boolean;
}

export function useVerificationDetails(
  requestId: string | null,
  entityCode: string,
  options: UseVerificationDetailsOptions = {}
) {
  const { enabled = true } = options;

  return useQuery<VerificationDetail, Error>({
    queryKey: [VERIFICATION_DETAILS_KEY, requestId, entityCode],
    queryFn: () => getVerificationDetails(requestId!, entityCode),
    enabled: enabled && !!requestId && !!entityCode,
    staleTime: 10 * 1000, // 10 seconds
    refetchOnWindowFocus: true,
  });
}
