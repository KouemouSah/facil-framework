export interface CommerceType {
  id: string;
  commerce_type: string;
  name_es: string;
  bundle_code: string;
  description_es?: string;
  installment_eligible: boolean;
}

export interface CommerceZone {
  id: string;
  zone_code: string;
  name_es: string;
  zone_tier: string;
  zone_rank?: number;
  description_es?: string;
  display_order?: number;
}

export interface SimulatorFeeItem {
  service_code: string;
  service_name: string;
  amount: string;
  fee_type: string;
  ministry_name?: string;
}

export interface SimulatorFeeGroup {
  fee_type: string;
  label_es?: string;
  items: SimulatorFeeItem[];
  subtotal: string;
}

export interface SimulatorDocument {
  document_template_id: number;
  document_name_es: string;
  is_required: boolean;
}

export interface SimulatorResponse {
  bundle: { name_es: string; commerce_type: string; installment_eligible: boolean };
  zone: { zone_code: string; name_es: string; zone_tier: string };
  fee_groups: SimulatorFeeGroup[];
  grand_total: string;
  currency: string;
  documents: SimulatorDocument[];
}

// ---------------------------------------------------------------------------
// Citizen — "Mes entreprises" : structures wired on
// GET /bundle-workflow/my-companies
// GET /bundle-workflow/my-companies/{id}
// GET /bundle-workflow/my-companies/{id}/payments
// (See bundle_workflow_service.my_companies_status / my_company_detail /
//  my_company_payments — exact field names mirrored.)
// ---------------------------------------------------------------------------

export interface MyCompanySummary {
  id: string;
  legal_name: string;
  tax_id: string | null;
  nif: string | null;
  registration_number: string | null;
  regimen_fiscal: string | null;
  commerce_type: string | null;
  zone_code: string | null;
  city_name: string | null;
  is_verified: boolean;
}

export interface MyCompanyStatusItem {
  company: MyCompanySummary;
  license_id: string | null;
  license_status: string | null;
  pending_obligations: number;
  fiscal_year: number;
  is_eligible: boolean;
}

export interface MyCompaniesResponse {
  companies: MyCompanyStatusItem[];
}

export interface LicenseInfo {
  id: string;
  status: string;
  fiscal_year: number;
  total_amount: number;
  amount_paid: number;
  amount_remaining: number;
  penalty_amount: number;
  obligations_total: number;
  obligations_paid: number;
  deadline: string | null;
  completed_at: string | null;
  expiry_date: string;
  certificate_number: string | null;
  certificate_url: string | null;
}

export interface LicenseObligation {
  id: string;
  fee_type: string;
  amount: number;
  penalty_amount: number;
  status: string; // pending | paid | overdue | cancelled
  due_date: string | null;
  paid_at: string | null;
  service_name: string | null;
  service_code: string | null;
  ministry_name: string | null;
}

export interface MyCompanyInspection {
  id: string;
  date: string | null;
  status: string | null;
  result: string | null;
  conforme: boolean | null;
  activity_declared: string | null;
  activity_observed: string | null;
  mise_en_demeure: boolean;
  mise_en_demeure_deadline: string | null;
  seal_applied: boolean;
  seal_reason: string | null;
  seal_approved_at: string | null;
  payment_collected: boolean;
  payment_receipt: string | null;
  payment_amount: number | null;
  notes: string | null;
  created_at: string | null;
}

export interface MyCompanyDetail {
  company: {
    id: string;
    legal_name: string;
    nif: string | null;
    registration_number: string | null;
    regimen_fiscal: string | null;
    commerce_type: string | null;
    objeto_social: string | null;
    forma_juridica: string | null;
    is_active: boolean;
    is_verified: boolean;
    representante_legal: string | null;
    zone_code: string | null;
    city_name: string | null;
  };
  license: LicenseInfo | null;
  obligations: LicenseObligation[];
  inspections: MyCompanyInspection[];
  fiscal_year: number;
}

export interface MyCompanyPayment {
  id: string;
  reference: string;
  sr_reference: string | null;
  amount: number;
  currency: string;
  method: string | null;
  status: string;
  fee_type: string | null;
  entity_code: string | null;
  receipt_number: string | null;
  receipt_url: string | null;
  created_at: string | null;
  validated_at: string | null;
}

export interface MyCompanyPaymentsResponse {
  payments: MyCompanyPayment[];
  total: number;
  page: number;
  page_size: number;
}
