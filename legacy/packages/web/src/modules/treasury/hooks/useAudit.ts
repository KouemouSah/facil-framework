/**
 * Hooks for treasury audit and traceability (Phase 1A)
 *
 * @module treasury/hooks
 */

import { useQuery } from '@tanstack/react-query';
import { treasuryApi } from '../services/api';
import type { AuditParams, AuditListResponse, PaymentAuditDetail } from '../types';

export const AUDIT_ENTRIES_QUERY_KEY = 'treasury-audit-entries';
export const PAYMENT_AUDIT_QUERY_KEY = 'treasury-payment-audit';

/**
 * Fetch audit entries with optional filters
 */
export function useAuditEntries(params: AuditParams = {}) {
  return useQuery<AuditListResponse, Error>({
    queryKey: [AUDIT_ENTRIES_QUERY_KEY, params],
    queryFn: () => treasuryApi.getAuditEntries(params),
    staleTime: 60 * 1000, // 1 minute
    retry: 2,
  });
}

/**
 * Fetch complete audit history for a specific payment
 */
export function usePaymentAuditHistory(paymentId: string | undefined) {
  return useQuery<PaymentAuditDetail, Error>({
    queryKey: [PAYMENT_AUDIT_QUERY_KEY, paymentId],
    queryFn: () => treasuryApi.getPaymentAuditHistory(paymentId!),
    enabled: !!paymentId,
    staleTime: 30 * 1000, // 30 seconds
    retry: 2,
  });
}

export default useAuditEntries;
