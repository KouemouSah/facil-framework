/**
 * Service Request Types — aligned with backend ServiceRequestResponse + DetailViewResponse
 */

import type { CitizenNotification } from '@modules/dashboard/types/dashboard.types';

export interface ServiceRequestListItem {
  id: string;
  reference: string;
  workflow_code: string;
  workflow_label?: string;
  status: string;
  priority: string;
  solicitud_type: string;
  created_at: string;
  updated_at: string;
  total_amount?: number;
  payment_status?: string;
  cita_date?: string;
  cita_time?: string;
  cita_location?: string;
}

export interface ServiceRequestListResponse {
  requests: ServiceRequestListItem[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface ServiceRequestFilters {
  status?: string;
  workflow_code?: string;
  category?: string;
  search?: string;
  date_from?: string;
  date_to?: string;
  page: number;
  page_size: number;
}

export interface StepperPhase {
  id: string;
  title_es: string;
  step_type: string;
  number: number;
  is_optional: boolean;
}

export interface DataSectionField {
  label: string;
  value?: string;
}

export interface DataSection {
  title: string;
  fields: DataSectionField[];
}

export interface DocumentInfo {
  id: string;
  document_code: string;
  document_name: string;
  file_name: string;
  mime_type?: string;
  file_url?: string;
}

export interface TariffBreakdown {
  base_amount: number;
  supplements: { label?: string; amount: number }[];
  supplements_total: number;
  penalties_amount?: number;
  total_amount: number;
  currency: string;
}

export interface AppointmentInfo {
  date: string;
  time: string;
  location: string;
}

// ---------------------------------------------------------------------------
// Bundle (commercial license) detail
// Matches the `bundle_details` payload built by
// service_requests/api/routes.py:1785 when workflow_code === 'BUNDLE_PAYMENT'.
// ---------------------------------------------------------------------------

export interface BundlePaymentSplit {
  /** Backend code: AYUNTAMIENTO, CAMARA_COMERCIO, MIN_HACIENDA, etc. */
  entity_code: string | null;
  entity_name: string | null;
  amount: number;
  /** payment_workflow_status enum value (e.g. 'completed', 'submitted', 'pending_agent_review'). */
  status: string | null;
  payment_reference: string | null;
  receipt_number: string | null;
}

export interface BundleObligationDetail {
  service_name: string;
  amount: number;
  /** license_obligation status (e.g. 'pending', 'paid', 'overdue'). */
  status: string;
  fee_type: string;
}

export interface BundleDetails {
  company_name: string | null;
  registration_number: string | null;
  /** commercial_licenses.status — 'open', 'partial', 'complete', 'overdue'. */
  license_status: string | null;
  certificate_url: string | null;
  certificate_number: string | null;
  company_id: string | null;
  splits: BundlePaymentSplit[];
  obligations: BundleObligationDetail[];
  /** Sum of split amounts — used as the "Total" KPI. */
  total_amount: number;
}

export interface DetailViewResponse {
  request: ServiceRequestListItem & {
    form_data?: Record<string, unknown>;
    extracted_data?: Record<string, unknown>;
    notes?: string;
    rejection_reason?: string;
    entity_code?: string;
  };
  stepper_phases: StepperPhase[];
  current_phase_index: number;
  data_sections: DataSection[];
  citizen_notifications: CitizenNotification[];
  unread_notification_count: number;
  photo_url?: string;
  tariff?: TariffBreakdown;
  payment_status?: string;
  payment_reference?: string;
  receipt_number?: string;
  appointment?: AppointmentInfo;
  documents: DocumentInfo[];
  workflow_name_es: string;
  solicitud_type_display?: string;
  /** Present only when `request.workflow_code === 'BUNDLE_PAYMENT'`. */
  bundle_details?: BundleDetails | null;
}

// ---------------------------------------------------------------------------
// Workflow Catalog
// ---------------------------------------------------------------------------

export interface WorkflowInfo {
  code: string;
  all_workflow_codes?: string[];
  category: string;
  entity_code: string;
  service_name_es: string;
  requires_appointment: boolean;
  requires_agent_review: boolean;
  allowed_solicitud_types: string[];
  allowed_sub_types?: string[];
  total_steps: number;
}
