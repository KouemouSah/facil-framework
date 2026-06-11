/**
 * Bundle Workflow Types — verified against backend bundle_workflow_service.py
 * Every field name matches backend snake_case response exactly.
 */

export enum BundleStep {
  COMPANY_IDENTIFICATION = 0,
  DOCUMENT_UPLOAD = 1,
  CLASSIFICATION = 2,
  OBLIGATIONS_REVIEW = 3,
  PAYMENT = 4,
  CONFIRMATION = 5,
}

export const BUNDLE_STEP_LABELS: Record<number, Record<string, string>> = {
  [BundleStep.COMPANY_IDENTIFICATION]: { es: 'Empresa', fr: 'Entreprise', en: 'Company' },
  [BundleStep.DOCUMENT_UPLOAD]: { es: 'Documentos', fr: 'Documents', en: 'Documents' },
  [BundleStep.CLASSIFICATION]: { es: 'Clasificación', fr: 'Classification', en: 'Classification' },
  [BundleStep.OBLIGATIONS_REVIEW]: { es: 'Obligaciones', fr: 'Obligations', en: 'Obligations' },
  [BundleStep.PAYMENT]: { es: 'Pago', fr: 'Paiement', en: 'Payment' },
  [BundleStep.CONFIRMATION]: { es: 'Confirmación', fr: 'Confirmation', en: 'Confirmation' },
};

export type ProcessingMode = 'per_line' | 'consolidated';
export type PaymentMethod = 'mobile_money' | 'cash' | 'card';

// ---------------------------------------------------------------------------
// Company — matches _format_company() in bundle_workflow_service.py
// ---------------------------------------------------------------------------

export interface CompanySummary {
  id: string;
  legal_name: string;
  tax_id?: string;
  nif?: string;
  registration_number?: string;
  commerce_type?: string;
  regimen_fiscal?: string;
  zone_code?: string;
  city_name?: string;
  is_verified?: boolean;
  verified?: boolean;
}

// matches GET /my-companies response element
export interface MyCompanyWithStatus {
  company: CompanySummary;
  license_id?: string;
  license_status?: string;
  pending_obligations: number;
  fiscal_year?: number;
  is_eligible: boolean;
}

export interface CompanySearchResult extends CompanySummary {
  registered_by_current_user?: boolean;
}

// ---------------------------------------------------------------------------
// Obligation — matches initiate() response obligation format exactly
// Fields: id, bundle_item_id, fiscal_service_name, fee_type, ministry_name,
//         amount, penalty_amount, total, status, is_payable, due_date, paid_at
// ---------------------------------------------------------------------------

export interface ObligationItem {
  id: string;
  bundle_item_id?: string;
  fiscal_service_name: string;
  fee_type: string;
  ministry_name?: string;
  amount: number;
  penalty_amount: number;
  total: number;
  status: string;
  is_payable: boolean;
  due_date?: string;
  paid_at?: string;
}

// ---------------------------------------------------------------------------
// API Responses — matches backend return dicts exactly
// ---------------------------------------------------------------------------

export interface MyCompaniesResponse {
  companies: MyCompanyWithStatus[];
}

export interface SearchCompanyResponse {
  companies: CompanySearchResult[];
  total: number;
}

// matches initiate() and initiate_from_upload() return dict
export interface BundleInitiateResponse {
  license_id: string;
  already_complete: boolean;
  license_status: string;
  total_amount: number;
  amount_paid: number;
  amount_remaining: number;
  obligations: ObligationItem[];
  company?: CompanySummary;
  bundle?: { id: string; commerce_type: string; name_es: string };
  fiscal_year: number;
  currency: string;
  processing_modes_available: ProcessingMode[];
  // Extra fields from initiate_from_upload
  company_created?: boolean;
  company_already_existed?: boolean;
}

// matches classify_preview() return dict
export interface ClassifyPreviewResponse {
  extracted_data: Record<string, any>;
  zone_resolved: boolean;
  zone?: { id: string; code: string; name: string; tier: string };
  detected_tier?: string;
  detected_city?: string;
  tier_zones: { id: string; code: string; tier: string; rank: number; name: string; description?: string }[];
  available_zones: { id: string; code: string; tier: string; rank: number; name: string; description?: string }[];
  classification?: { regimen_fiscal?: string; commerce_type?: string; confidence?: number };
  available_categories: { commerce_type: string; bundle_name: string }[];
  available_commerce_types: { commerce_type: string; bundle_name: string }[];
  needs_manual_zone: boolean;
  needs_manual_category: boolean;
}

// matches initiate_payment() return dict
export interface BundlePaymentResult {
  success: boolean;
  service_request_id: string;
  payment_id: string;
  payment_ids?: string[];
  payment_reference: string;
  redirect_url?: string;
  requires_action?: boolean;
  action_type?: string;
  total_amount: number;
  obligations_count: number;
  processing_mode: string;
  entity_payments?: Record<string, { count: number; amount: number }>;
  message_es?: string;
  message_fr?: string;
  message_en?: string;
}

// matches validate_selection() return dict
export interface BundleValidateResponse {
  valid: boolean;
  processing_mode: string;
  selected_count: number;
  total_amount: number;
  selected_obligation_ids: string[];
  currency: string;
}

// Document preview (from wizard session)
export interface DocumentPreview {
  extraction: Record<string, any>;
  confidence?: number;
  document_type?: string;
}
