/**
 * Payment Types - Aligned with Backend Pydantic Models
 *
 * Source: packages/backend/app/modules/payments/models/payment.py
 *
 * IMPORTANT: These types mirror the backend Pydantic schemas exactly
 * - Field names use camelCase (converted from snake_case in API layer)
 * - All enums match backend exactly
 */

/**
 * Payment Type Enum
 */
export enum PaymentType {
  FULL = 'full',              // Paiement complet
  PARTIAL = 'partial',        // Paiement partiel
  INSTALLMENT = 'installment' // Acompte (échéancier)
}

/**
 * Payment Status Enum
 */
export enum PaymentStatus {
  PENDING = 'pending',          // En attente
  PROCESSING = 'processing',    // En traitement BANGE
  COMPLETED = 'completed',      // Complété
  FAILED = 'failed',            // Échoué
  CANCELLED = 'cancelled',      // Annulé
  REFUNDED = 'refunded'         // Remboursé
}

/**
 * Payment Method Enum
 */
export enum PaymentMethod {
  BANK_TRANSFER = 'bank_transfer',  // Virement bancaire
  MOBILE_MONEY = 'mobile_money',    // Mobile money (BANGE)
  CASH = 'cash',                    // Espèces
  CARD = 'card',                    // Carte bancaire
  CHECK = 'check'                   // Chèque
}

/**
 * Payment Response Interface
 * Aligned with PaymentResponse Pydantic model
 */
export interface PaymentResponse {
  id: string
  userId: string

  // Polymorphic references
  taxDeclarationId?: string | null
  fiscalServiceId?: number | null

  // Payment plan references
  paymentPlanId?: string | null
  installmentId?: string | null

  // Amounts
  baseAmount: number
  penalties: number
  interest: number
  amount: number      // Total (base + penalties + interest)
  currency: string    // Default: XAF

  // Payment details
  paymentType: PaymentType
  paymentMethod: PaymentMethod
  status: PaymentStatus

  // BANGE integration
  bankReference?: string | null
  bankTransactionId?: string | null
  idempotencyKey: string

  // Timestamps
  createdAt: string
  updatedAt: string
  paidAt?: string | null

  // Related data (from joins)
  declarationType?: string | null
  fiscalServiceName?: string | null
  userEmail?: string | null
}

/**
 * Payment List Response (Paginated)
 */
export interface PaymentListResponse {
  payments: PaymentResponse[]
  total: number
  page: number
  pageSize: number
}

/**
 * Payment List Params
 */
export interface PaymentListParams {
  page?: number
  pageSize?: number
  status?: PaymentStatus
}

/**
 * Helper to get status label
 */
export const getPaymentStatusLabel = (status: PaymentStatus): string => {
  const labels: Record<PaymentStatus, string> = {
    [PaymentStatus.PENDING]: 'En attente',
    [PaymentStatus.PROCESSING]: 'En traitement',
    [PaymentStatus.COMPLETED]: 'Complété',
    [PaymentStatus.FAILED]: 'Échoué',
    [PaymentStatus.CANCELLED]: 'Annulé',
    [PaymentStatus.REFUNDED]: 'Remboursé'
  }
  return labels[status] || status
}

/**
 * Helper to get method label
 */
export const getPaymentMethodLabel = (method: PaymentMethod): string => {
  const labels: Record<PaymentMethod, string> = {
    [PaymentMethod.BANK_TRANSFER]: 'Virement',
    [PaymentMethod.MOBILE_MONEY]: 'Mobile Money',
    [PaymentMethod.CASH]: 'Espèces',
    [PaymentMethod.CARD]: 'Carte bancaire',
    [PaymentMethod.CHECK]: 'Chèque'
  }
  return labels[method] || method
}
