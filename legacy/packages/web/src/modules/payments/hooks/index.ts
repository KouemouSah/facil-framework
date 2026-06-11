/**
 * Payments Hooks Exports
 *
 * Includes:
 * - Legacy hook: useUserPayments
 * - React Query hooks with caching (recommended)
 *
 * @module payments/hooks
 * @date 2026-01-25
 */

// Legacy hook (for backwards compatibility)
export { useUserPayments } from './useUserPayments';

// React Query hooks with caching (recommended)
export {
  usePayments,
  useRecentPayments,
  usePayment,
  usePaymentPlan,
  useCreatePayment,
  useUpdatePayment,
  usePrefetchPayment,
  useInvalidatePaymentsCache,
  paymentQueryKeys,
} from './usePaymentsQueries';
