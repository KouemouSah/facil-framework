/**
 * Hook for fetching user payments
 *
 * @module payments/hooks
 */

import { useQuery } from '@tanstack/react-query'
import { paymentsApi } from '../services/api'
import type { PaymentListParams, PaymentListResponse } from '@/types/payment'

export function useUserPayments(params: PaymentListParams = {}) {
  return useQuery<PaymentListResponse, Error>({
    queryKey: ['user-payments', params],
    queryFn: () => paymentsApi.listPayments(params),
    staleTime: 2 * 60 * 1000, // 2 minutes
    retry: 2,
  })
}

export default useUserPayments
