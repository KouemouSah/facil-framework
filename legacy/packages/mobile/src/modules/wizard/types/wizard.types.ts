/**
 * Wizard Session Types — aligned with backend wizard_session_routes.py
 *
 * Cache-first architecture: all data in Redis (TTL 30min) until atomic payment.
 */

// ---------------------------------------------------------------------------
// Workflow Config (from GET /service-requests/workflows/{code})
// ---------------------------------------------------------------------------

export interface WorkflowStepConfig {
  number: number;
  id: string;
  type: string; // selection, document_upload, form_review_1..N, appointment, site_selection, payment, confirmation, custom, select_applicant_type
  title_es: string;
  description_es?: string;
  is_inherited: boolean;
  is_optional?: boolean;
  config?: Record<string, unknown>;
}

export interface WorkflowConfig {
  code: string;
  all_workflow_codes?: string[];
  category: string;
  entity_code: string;
  service_name_es: string;
  requires_nota_ingreso: boolean;
  requires_appointment: boolean;
  requires_agent_review: boolean;
  allowed_solicitud_types?: string[];
  allowed_sub_types: string[];
  total_steps?: number;
  steps?: WorkflowStepConfig[];
}

// ---------------------------------------------------------------------------
// Session
// ---------------------------------------------------------------------------

export interface WizardSessionCreate {
  workflow_code: string;
  solicitud_type?: string; // expedicion | renovacion | duplicado (default: expedicion)
  sub_type?: string;
  motivo?: string;
  is_minor?: boolean;
}

export interface WizardRequiredDocument {
  code: string;
  name_es: string;
  is_required: boolean;
  uploaded: boolean;
}

export interface WizardAppointmentData {
  entity_location_id: string;
  location_name: string;
  city: string;
  appointment_date: string;
  appointment_time: string;
  slot_config_id?: string;
}

export interface WizardSiteSelection {
  entity_location_id: string;
  location_name: string;
  city: string;
  entity_code?: string;
}

export interface WizardSession {
  session_id: string;
  workflow_code: string;
  solicitud_type: string;
  sub_type?: string;
  motivo?: string;
  is_minor: boolean;
  status: string; // ACTIVE, DOCUMENTS_UPLOADED, READY_FOR_PAYMENT, PAYMENT_INITIATED, PERSISTED, EXPIRED, CANCELLED
  current_step: number;
  current_step_id?: string;
  documents_count: number;
  documents_uploaded: string[];
  form_data: Record<string, unknown>;
  extracted_data: Record<string, unknown>;
  tariff?: TariffBreakdown;
  required_documents: WizardRequiredDocument[];
  requires_appointment: boolean;
  entity_code?: string;
  appointment_data?: WizardAppointmentData;
  site_selection?: WizardSiteSelection;
  created_at: string;
  updated_at: string;
  expires_at: string;
  ttl_seconds: number;
}

// ---------------------------------------------------------------------------
// Documents
// ---------------------------------------------------------------------------

export interface DocumentPreview {
  session_id: string;
  document_code: string;
  document_name?: string;
  file_name: string;
  file_size: number;
  extraction: Record<string, unknown>;
  confidence: number;
  processor: string; // gemini, tesseract, hybrid
  extraction_status: string; // pending, success, failed, manual_review
  needs_correction: boolean;
  risk_analysis?: Record<string, unknown>;
  cross_validation?: Record<string, unknown>;
  expires_at: string;
  ttl_seconds: number;
}

export interface DocumentConfirmRequest {
  document_code: string;
  confirmed_data: Record<string, unknown>;
  user_notes?: string;
}

// ---------------------------------------------------------------------------
// Form Config (Dynamic Forms)
// ---------------------------------------------------------------------------

export interface FormFieldOption {
  value: string;
  label_es: string;
}

export interface FormField {
  key: string;
  label_es: string;
  type: string; // text, textarea, select, radio, checkbox, date, number
  required: boolean;
  readonly: boolean;
  options?: FormFieldOption[];
  placeholder_es?: string;
  validation?: Record<string, unknown>;
  help_text_es?: string;
  show_when?: Record<string, unknown>;
  current_value?: unknown;
}

export interface FormSection {
  id: string;
  title_es: string;
  source_document?: string;
  description_es?: string;
  fields: FormField[];
}

export interface FormConfig {
  step_id: string;
  title_es: string;
  description_es?: string;
  sections: FormSection[];
}

export interface FormDataSaveRequest {
  form_data: Record<string, unknown>;
  step_id?: string;
}

// ---------------------------------------------------------------------------
// Payment
// ---------------------------------------------------------------------------

export interface TariffBreakdown {
  base_amount: number;
  supplements: { code?: string; label_es?: string; amount: number }[];
  total_amount: number;
  currency: string;
}

export interface PaymentMethod {
  code: string;
  label_es: string;
  label_en: string;
  label_fr: string;
  processor_type: string; // bange, manual
  requires_phone: boolean;
  requires_redirect: boolean;
  requires_agent_validation: boolean;
}

export interface ValidationError {
  rule_id: string;
  message_es: string;
  field?: string;
}

export interface PreparePaymentResult {
  session_id: string;
  ready_for_payment: boolean;
  tariff: TariffBreakdown;
  total_amount: number;
  currency: string;
  validation_passed: boolean;
  errors: ValidationError[];
  warnings: ValidationError[];
  all_documents_uploaded: boolean;
  missing_documents: string[];
  payment_methods: PaymentMethod[];
  default_payment_method?: string;
}

export interface InitiatePaymentRequest {
  payment_method: string;
  phone_number?: string;
  treasury_location_id?: string;
  /**
   * Optional client-supplied return URL for the BANGE redirect. Backend
   * whitelists `facil://*` schemes and same-origin URLs (cf. backend Pydantic
   * validator on `WizardInitiatePaymentRequest.return_url`).
   */
  return_url?: string;
}

export interface InitiatePaymentResult {
  success: boolean;
  service_request_id?: string;
  reference?: string;
  payment_id?: string;
  payment_reference?: string;
  payment_status?: string;
  redirect_url?: string;
  requires_action: boolean;
  action_type?: string; // redirect, agent_validation_cash, agent_validation_check
  message_es?: string;
  requires_appointment: boolean;
  appointment_confirmed: boolean;
  appointment_date?: string;
  appointment_time?: string;
  appointment_location?: string;
  error?: string;
  error_code?: string;
  expires_at?: string;
}

// ---------------------------------------------------------------------------
// Appointment
// ---------------------------------------------------------------------------

export interface AppointmentLocation {
  id: string;
  entity_code: string;
  location_code: string;
  location_name: string;
  city: string;
  province?: string;
  region?: string;
  address?: string;
  phone?: string;
  email?: string;
  is_main_office: boolean;
}

export interface AppointmentLocationsResponse {
  entity_code: string;
  locations: AppointmentLocation[];
  count: number;
}

export interface AvailableDay {
  slot_date: string;
  time_slot_count: number;
  total_slots_remaining: number;
}

export interface AvailableDaysResponse {
  entity_code: string;
  location_name: string;
  from_date: string;
  to_date: string;
  days: AvailableDay[];
  count: number;
  min_date?: string;
}

export interface AvailableSlot {
  slot_date: string;
  slot_time: string;
  location_name: string;
  location_address?: string;
  slots_remaining: number;
  city?: string;
}

export interface AvailableSlotsResponse {
  entity_code: string;
  location_name: string;
  from_date: string;
  slots: AvailableSlot[];
  count: number;
  has_availability: boolean;
}

export interface AppointmentSelectionRequest {
  entity_location_id: string;
  location_name?: string;
  city?: string;
  appointment_date: string;
  appointment_time: string;
  slot_config_id?: string;
}

// ---------------------------------------------------------------------------
// Site Selection
// ---------------------------------------------------------------------------

export interface SiteInfo {
  id: string;
  entity_code: string;
  city: string;
  location_name: string;
  location_address?: string;
  is_main_office: boolean;
}

export interface AvailableSitesResponse {
  workflow_code: string;
  sites: SiteInfo[];
  cities: Record<string, SiteInfo[]>;
  count: number;
}

export interface SiteSelectionRequest {
  entity_location_id: string;
  location_name?: string;
  city?: string;
  entity_code?: string;
}
