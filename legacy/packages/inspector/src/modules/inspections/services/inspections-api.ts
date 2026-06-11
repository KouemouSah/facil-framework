/**
 * Inspections API - Full CRUD + workflow operations
 *
 * Matches backend: packages/backend/app/modules/inspections/api/inspection_routes.py
 */

import { apiGet, apiPost, apiPut, apiDelete, apiUpload } from '@core/api/client';
import { API_ENDPOINTS } from '@core/api/endpoints';
import { withIdempotencyKey } from '@core/api/idempotency';
import type {
  InspectionDetail,
  InspectionListResponse,
  InspectionListFilters,
  InspectionStats,
} from '@modules/inspections/types/inspection.types';

// ---------------------------------------------------------------------------
// Request types (matching backend Pydantic models)
// ---------------------------------------------------------------------------

export interface CreateInspectionRequest {
  license_id: string;
  company_id: string;
  notes?: string;
}

export interface UpdateInspectionRequest {
  activity_conforme?: boolean;
  activity_declared?: string;
  activity_observed?: string;
  photos?: string[];
  gps_latitude?: number;
  gps_longitude?: number;
  gps_accuracy?: number;
  notes?: string;
  agent_signature?: string;
}

export interface CompleteInspectionRequest {
  notes?: string;
}

export interface MiseEnDemeureRequest {
  obligation_ids: string[];
  deadline_hours?: number; // default 72, range 24-720
  notes?: string;
}

export interface SealProposeRequest {
  reason: string;
  notes?: string;
  photo?: string;
}

export interface SealApproveRequest {
  approved: boolean;
  notes?: string;
}

export interface FieldCollectRequest {
  obligation_ids: string[];
  method: 'cash' | 'mobile_money';
  amount: number;
  phone_number?: string;
  notes?: string;
}

export interface PhotoUploadResponse {
  url: string;
  file_path: string;
  file_size: number;
  photo_index: number;
}

export interface ReconciliationItem {
  id: string;
  inspection_date: string;
  company_name: string | null;
  company_nif: string | null;
  payment_amount: number | null;
  payment_receipt_number: string | null;
  created_at: string;
}

export interface ReconciliationResponse {
  items: ReconciliationItem[];
  total_amount: number;
  total_count: number;
}

// ---------------------------------------------------------------------------
// API
// ---------------------------------------------------------------------------

export const inspectionsApi = {
  // --- CRUD ---

  list: (filters?: InspectionListFilters) =>
    apiGet<InspectionListResponse>(
      API_ENDPOINTS.inspections.list,
      filters as Record<string, unknown>,
    ),

  detail: (id: string) =>
    apiGet<InspectionDetail>(API_ENDPOINTS.inspections.detail(id)),

  /**
   * Create a field inspection.
   * @param idempotencyKey Client-generated UUID (useRef) to make retries safe.
   *   Forwarded as `Idempotency-Key` header. Secondary defense — primary
   *   protection is the UNIQUE(agent_id, company_id, inspection_date) constraint.
   */
  create: (data: CreateInspectionRequest, idempotencyKey?: string) =>
    apiPost<InspectionDetail>(
      API_ENDPOINTS.inspections.create,
      data,
      idempotencyKey ? { headers: withIdempotencyKey(idempotencyKey) } : undefined,
    ),

  update: (id: string, data: UpdateInspectionRequest) =>
    apiPut<InspectionDetail>(API_ENDPOINTS.inspections.update(id), data),

  stats: (params?: { date_from?: string; date_to?: string }) =>
    apiGet<InspectionStats>(API_ENDPOINTS.inspections.stats, params as Record<string, unknown>),

  // --- Workflow ---

  complete: (id: string, data?: CompleteInspectionRequest) =>
    apiPost<InspectionDetail>(API_ENDPOINTS.inspections.complete(id), data ?? {}),

  miseEnDemeure: (id: string, data: MiseEnDemeureRequest) =>
    apiPost<InspectionDetail>(API_ENDPOINTS.inspections.miseEnDemeure(id), data),

  seal: (id: string, data: SealProposeRequest) =>
    apiPost<InspectionDetail>(API_ENDPOINTS.inspections.seal(id), data),

  sealApprove: (id: string, data: SealApproveRequest) =>
    apiPost<InspectionDetail>(API_ENDPOINTS.inspections.sealApprove(id), data),

  /**
   * Collect a field payment. CRITICAL — Idempotency-Key is strongly recommended
   * for retry safety on unstable field networks (OWASP A04).
   * @param idempotencyKey Client-generated UUID (useRef). If present, the
   *   backend will replay the cached response on retry within 24h.
   */
  collect: (id: string, data: FieldCollectRequest, idempotencyKey?: string) =>
    apiPost<Record<string, unknown>>(
      API_ENDPOINTS.inspections.collect(id),
      data,
      idempotencyKey ? { headers: withIdempotencyKey(idempotencyKey) } : undefined,
    ),

  // --- Photos ---

  uploadPhoto: (id: string, formData: FormData, onProgress?: (p: number) => void) =>
    apiUpload<PhotoUploadResponse>(API_ENDPOINTS.inspections.photos(id), formData, onProgress),

  deletePhoto: (id: string, photoIndex: number) =>
    apiDelete<{ removed: string; remaining: number }>(
      API_ENDPOINTS.inspections.photoDelete(id, photoIndex),
    ),

  // --- Reconciliation ---

  getReconciliation: (targetDate?: string) =>
    apiGet<ReconciliationResponse>(API_ENDPOINTS.inspections.reconcile, {
      ...(targetDate ? { target_date: targetDate } : {}),
    }),

  /** Supervisor: list pending field collections for entity */
  getSupervisorReconciliation: () =>
    apiGet<ReconciliationResponse>(API_ENDPOINTS.supervisor.reconcileList),

  /** Supervisor: validate a field cash collection (double-validation) */
  validateReconciliation: (paymentId: string) =>
    apiPost<{ payment_id: string; status: string; routed_obligations: number }>(
      API_ENDPOINTS.supervisor.reconcileValidate(paymentId),
      {},
    ),
};
