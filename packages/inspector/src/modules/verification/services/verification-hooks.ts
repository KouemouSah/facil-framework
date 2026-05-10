/**
 * Verification Hooks - React Query wrappers
 */

import { useQuery } from '@tanstack/react-query';
import { verificationApi } from './verification-api';
import { appConfig } from '@core/config/app';

const KEYS = {
  verify: (id: string) => ['verification', id] as const,
};

/** License verification by identifier (enabled when identifier is non-empty) */
export function useLicenseVerification(identifier: string) {
  return useQuery({
    queryKey: KEYS.verify(identifier),
    queryFn: () => verificationApi.verifyByIdentifier(identifier),
    enabled: identifier.length >= 3,
    staleTime: appConfig.cache.inspections,
    retry: false,
  });
}
