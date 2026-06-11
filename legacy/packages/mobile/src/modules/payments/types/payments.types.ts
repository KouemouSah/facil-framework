/**
 * Payment types — aligned with backend Pydantic models in
 * `packages/backend/app/modules/payments/models/payment.py` and
 * `packages/backend/app/modules/service_requests/models/service_request.py:626`
 * (PaymentStatusResponse).
 */

/** Matches `payment_status_enum` in DB + `PaymentStatus` in Pydantic. */
export type PaymentStatus =
  | 'pending'
  | 'processing'
  | 'completed'
  | 'failed'
  | 'cancelled'
  | 'refunded';

/**
 * Mirrors backend Pydantic `PaymentMethod` (payment.py:33-39).
 * Note: `bange_wallet` was dropped by migration 167 ("dead column, never used")
 * and is intentionally absent here despite still appearing as a display label
 * in `treasury_export_service.py`. Do NOT add it back without re-introducing
 * the enum value in Pydantic first.
 */
export type PaymentMethod =
  | 'mobile_money'
  | 'card'
  | 'bank_transfer'
  | 'cash'
  | 'check';

/** Matches `payment_type_enum` in DB + `PaymentType` in Pydantic. */
export type PaymentType = 'full' | 'partial' | 'installment' | 'complementary';

/** A single payment record. Mirrors `PaymentResponse` (payment.py:97-119). */
export interface Payment {
  id: string;
  user_id: string;
  tax_declaration_id: string | null;
  fiscal_service_id: number | null;
  payment_plan_id: string | null;
  installment_id: string | null;
  base_amount: number;
  penalties: number;
  interest: number;
  /** Total = base + penalties + interest. */
  amount: number;
  currency: string;
  payment_type: PaymentType;
  payment_method: PaymentMethod;
  bank_reference: string | null;
  bank_transaction_id: string | null;
  status: PaymentStatus;
  idempotency_key: string;
  created_at: string;
  updated_at: string;
  paid_at: string | null;
  declaration_type?: string | null;
  fiscal_service_name?: string | null;
  user_email?: string | null;
}

/** Mirrors `PaymentListResponse` (payment.py:121). */
export interface PaymentListResponse {
  payments: Payment[];
  total: number;
  page: number;
  page_size: number;
}

/**
 * Response of `GET /service-requests/{request_id}/payment/status`.
 * Mirrors `PaymentStatusResponse` (service_request.py:626).
 *
 * Note: `payment_method` is sourced from `service_requests.form_data.payment_method`
 * which is a free-form string the backend does not validate against the
 * `PaymentMethod` enum (`routes.py:1249`). We therefore type it as a raw string
 * and let the UI fall back gracefully when an unknown value comes through.
 */
export interface PaymentStatusPolled {
  status: PaymentStatus;
  paid: boolean;
  payment_id: string | null;
  amount: number | null;
  currency: string;
  payment_method: string | null;
  completed_at: string | null;
}

export interface PaymentsListFilters {
  page: number;
  page_size: number;
  status?: PaymentStatus;
}

/** Statuses considered terminal — polling stops as soon as one is reached. */
export const TERMINAL_PAYMENT_STATUSES: ReadonlySet<PaymentStatus> = new Set([
  'completed',
  'failed',
  'cancelled',
  'refunded',
]);

// ---------------------------------------------------------------------------
// Retry payment (POST /service-requests/{id}/payment/initiate)
// ---------------------------------------------------------------------------

/**
 * Mirrors backend `PaymentMethodInfo` (routes.py:1294). One entry per active
 * payment processor in the backend registry.
 */
export interface RequestPaymentMethodInfo {
  code: PaymentMethod;
  label_es: string;
  label_en: string;
  label_fr: string;
  processor_type: string;
  requires_phone: boolean;
  requires_redirect: boolean;
  requires_agent_validation: boolean;
}

/** Mirrors backend `PaymentMethodsResponse` (routes.py:1311). */
export interface RequestPaymentMethodsResponse {
  methods: RequestPaymentMethodInfo[];
  default_method: PaymentMethod | null;
}

/**
 * Body of `POST /service-requests/{id}/payment/initiate`. Mirrors backend
 * `PaymentInitiateRequest`. `phone_number` is required for `mobile_money`,
 * `return_url` is for BANGE redirect callbacks.
 */
export interface RetryPaymentRequest {
  payment_method: PaymentMethod;
  phone_number?: string;
  return_url?: string;
}

/**
 * Response of `POST /service-requests/{id}/payment/initiate`. Mirrors backend
 * `PaymentInitiateResponse`. `redirect_url` is set for BANGE methods,
 * `action_type='agent_validation'` for cash/check (the citizen waits for an
 * agent to confirm reception).
 */
export interface RetryPaymentResponse {
  success: boolean;
  payment_id?: string | null;
  payment_reference?: string | null;
  payment_status?: PaymentStatus | null;
  redirect_url?: string | null;
  action_type?: 'redirect' | 'agent_validation' | string | null;
  requires_action?: boolean;
  message_es?: string | null;
  message_fr?: string | null;
  message_en?: string | null;
}
