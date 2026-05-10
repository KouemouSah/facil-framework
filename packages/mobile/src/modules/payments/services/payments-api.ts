/**
 * Payments API — thin wrappers around the FastAPI payments routes.
 */

import { apiGet, apiPost } from '@core/api/client';
import { API_ENDPOINTS } from '@core/api/endpoints';
import type {
  Payment,
  PaymentListResponse,
  PaymentStatusPolled,
  PaymentsListFilters,
  RequestPaymentMethodsResponse,
  RetryPaymentRequest,
  RetryPaymentResponse,
} from '../types/payments.types';

/** GET /api/v1/payments — paginated list (filters scoped to current user by backend). */
export async function listPayments(
  filters: PaymentsListFilters,
): Promise<PaymentListResponse> {
  const params: Record<string, unknown> = {
    page: filters.page,
    page_size: filters.page_size,
  };
  if (filters.status) params.status = filters.status;
  return apiGet<PaymentListResponse>(API_ENDPOINTS.payments.list, params);
}

/** GET /api/v1/payments/{id} — detail with ownership check. */
export async function getPayment(paymentId: string): Promise<Payment> {
  return apiGet<Payment>(API_ENDPOINTS.payments.detail(paymentId));
}

/**
 * GET /api/v1/service-requests/{request_id}/payment/status — polling endpoint.
 * Used by `wizard/payment-result` and the in-flight payment detail UI.
 */
export async function getServiceRequestPaymentStatus(
  serviceRequestId: string,
): Promise<PaymentStatusPolled> {
  return apiGet<PaymentStatusPolled>(
    API_ENDPOINTS.payments.serviceRequestStatus(serviceRequestId),
  );
}

/**
 * GET /api/v1/service-requests/{id}/payment/methods — list of payment methods
 * accepted for this SR. Backend builds the list dynamically from
 * `payment_processor_registry`, so the mobile must not hardcode the catalogue.
 */
export async function getRequestPaymentMethods(
  serviceRequestId: string,
): Promise<RequestPaymentMethodsResponse> {
  return apiGet<RequestPaymentMethodsResponse>(
    API_ENDPOINTS.payments.serviceRequestPaymentMethods(serviceRequestId),
  );
}

/**
 * POST /api/v1/service-requests/{id}/payment/initiate — re-initiate a payment
 * for an existing SR (the "Retry payment" CTA when a previous attempt
 * failed/expired). Web parity with `dashboard/service-requests/[id]`.
 */
export async function retryRequestPayment(
  serviceRequestId: string,
  body: RetryPaymentRequest,
): Promise<RetryPaymentResponse> {
  return apiPost<RetryPaymentResponse>(
    API_ENDPOINTS.payments.serviceRequestInitiatePayment(serviceRequestId),
    body,
  );
}
