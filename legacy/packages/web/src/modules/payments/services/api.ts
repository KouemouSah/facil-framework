/**
 * Payments API Service
 * Handles payment API operations
 *
 * @module payments/services
 *
 * BACKEND ALIGNMENT:
 * Routes: /api/v1/payments (from app/modules/payments/api/payment_routes.py)
 * - GET    /api/v1/payments                    → list_payments
 * - GET    /api/v1/payments/{id}               → get_payment
 */

import { fetchClient } from '@/core/api'
import type { PaymentResponse, PaymentListResponse, PaymentListParams } from '@/types/payment'

// =============================================================================
// CONFIGURATION
// =============================================================================

const PAYMENTS_BASE = '/payments'

// =============================================================================
// HELPER FUNCTIONS
// =============================================================================

/**
 * Convert snake_case keys to camelCase
 */
function toCamelCase<T>(obj: Record<string, unknown>): T {
  const result: Record<string, unknown> = {}
  for (const [key, value] of Object.entries(obj)) {
    const camelKey = key.replace(/_([a-z])/g, (_, letter) => letter.toUpperCase())
    if (value && typeof value === 'object' && !Array.isArray(value)) {
      result[camelKey] = toCamelCase(value as Record<string, unknown>)
    } else if (Array.isArray(value)) {
      result[camelKey] = value.map((item) =>
        typeof item === 'object' && item !== null
          ? toCamelCase(item as Record<string, unknown>)
          : item
      )
    } else {
      result[camelKey] = value
    }
  }
  return result as T
}

/**
 * Transform API response to frontend format
 */
function transformPayment(data: Record<string, unknown>): PaymentResponse {
  return toCamelCase<PaymentResponse>(data)
}

function transformListResponse(data: Record<string, unknown>): PaymentListResponse {
  const payments = (data.payments as Record<string, unknown>[]) || []
  return {
    payments: payments.map(transformPayment),
    total: (data.total as number) || 0,
    page: (data.page as number) || 1,
    pageSize: (data.page_size as number) || 20,
  }
}

// =============================================================================
// PAYMENTS API
// =============================================================================

export const paymentsApi = {
  /**
   * List user's payments
   * BACKEND: GET /api/v1/payments
   */
  listPayments: async (params: PaymentListParams = {}): Promise<PaymentListResponse> => {
    const queryParams: Record<string, string | number | boolean | undefined> = {
      page: params.page || 1,
      page_size: params.pageSize || 20,
    }

    if (params.status) {
      queryParams.status = params.status
    }

    const response = await fetchClient.get<Record<string, unknown>>(
      PAYMENTS_BASE,
      queryParams
    )

    return transformListResponse(response)
  },

  /**
   * Get payment by ID
   * BACKEND: GET /api/v1/payments/{id}
   */
  getPayment: async (id: string): Promise<PaymentResponse> => {
    const response = await fetchClient.get<Record<string, unknown>>(
      `${PAYMENTS_BASE}/${id}`
    )
    return transformPayment(response)
  },

  /**
   * Create new payment
   * BACKEND: POST /api/v1/payments
   */
  createPayment: async (data: Record<string, unknown>): Promise<PaymentResponse> => {
    const response = await fetchClient.post<Record<string, unknown>>(
      PAYMENTS_BASE,
      data
    )
    return transformPayment(response)
  },

  /**
   * Update payment
   * BACKEND: PUT /api/v1/payments/{id}
   */
  updatePayment: async (id: string, data: Record<string, unknown>): Promise<PaymentResponse> => {
    const response = await fetchClient.put<Record<string, unknown>>(
      `${PAYMENTS_BASE}/${id}`,
      data
    )
    return transformPayment(response)
  },

  /**
   * Get payment plan with installments
   * BACKEND: GET /api/v1/payments/plans/{id}
   */
  getPaymentPlan: async (planId: string): Promise<Record<string, unknown>> => {
    return fetchClient.get<Record<string, unknown>>(
      `${PAYMENTS_BASE}/plans/${planId}`
    )
  },
}

export default paymentsApi
