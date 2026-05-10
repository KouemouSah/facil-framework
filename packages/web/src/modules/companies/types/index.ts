/**
 * Companies Types — ALIGNED WITH DB (Migration 218 Phase 1.3)
 *
 * @module companies/types
 */

// =============================================================================
// ENUMS
// =============================================================================

export type CompanyMemberRole =
  | 'company_owner'
  | 'company_admin'
  | 'company_accountant'
  | 'company_member'

export type RegimenFiscal = 'bundle' | 'declarativo' | 'exento' | 'pendiente'

// =============================================================================
// COMPANY TYPES
// =============================================================================

export interface CompanyBase {
  // Required
  legal_name: string
  tax_id: string

  // Identity (OCR empresa)
  trade_name?: string | null
  nif?: string | null
  forma_juridica?: string | null
  nacionalidad?: string | null
  capital_social?: number | null
  registration_number?: string | null
  registration_date?: string | null

  // Activity (OCR actividad)
  sector_actividad?: string | null
  subsector_actividad?: string | null
  objeto_social?: string | null

  // Classification (LLM-derived)
  commerce_type?: string | null
  regimen_fiscal?: RegimenFiscal | null

  // Operational (OCR datos_operativos)
  employee_count?: number | null
  establishment_count?: number | null

  // Location
  address?: string | null
  phone?: string | null
  email?: string | null
  zone_id?: string | null
  city_id?: string | null

  // Status
  is_active?: boolean
  is_verified?: boolean
}

export interface CompanyCreate extends CompanyBase {}

export interface CompanyUpdate {
  legal_name?: string
  trade_name?: string | null
  nif?: string | null
  forma_juridica?: string | null
  nacionalidad?: string | null
  capital_social?: number | null
  registration_number?: string | null
  registration_date?: string | null
  sector_actividad?: string | null
  subsector_actividad?: string | null
  objeto_social?: string | null
  commerce_type?: string | null
  regimen_fiscal?: RegimenFiscal | null
  employee_count?: number | null
  establishment_count?: number | null
  address?: string | null
  phone?: string | null
  email?: string | null
  zone_id?: string | null
  city_id?: string | null
  is_active?: boolean
  is_verified?: boolean
}

export interface Company extends CompanyBase {
  id: string
  created_at: string
  updated_at: string

  // Related data (JOINs)
  owner_user_id?: string | null
  member_count?: number
  city_name?: string | null
  zone_code?: string | null

  // Soft-delete metadata (migration 314 / Phase 4 of SOFT_DELETE_COMPANIES_PLAN).
  // Populated by GET /admin/all when archived='archived' or 'all'.
  archived_at?: string | null
  archive_reason?: string | null
  archived_by?: string | null
  archived_by_email?: string | null
  archived_by_name?: string | null
}

export interface PaginatedCompaniesResponse {
  companies: Company[]
  total: number
  page: number
  page_size: number
}

// =============================================================================
// MEMBER TYPES
// =============================================================================

export interface CompanyMember {
  user_id: string
  company_id: string
  role: CompanyMemberRole
  is_active?: boolean
  assigned_at?: string
  user_email?: string | null
  user_name?: string | null
}

export interface AddMemberRequest {
  member_user_id: string
  role: CompanyMemberRole
}

export interface UpdateMemberRoleRequest {
  role: CompanyMemberRole
}

// =============================================================================
// ADMIN TYPES
// =============================================================================

export interface CompanyAdminListResponse {
  items: Company[]
  total: number
  page: number
  page_size: number
}

export interface CompanyStats {
  total: number
  active: number
  verified: number
  inactive: number
  with_licenses: number
  by_regimen: Record<string, number>
}

export interface CompanySearchResult {
  id: string
  legal_name: string
  tax_id: string
  nif?: string | null
  city_name?: string | null
  is_verified: boolean
}

export interface CompanyClassifyResult {
  regimen_fiscal: string
  confidence: number
  reason: string
}

// =============================================================================
// DASHBOARD TYPES
// =============================================================================

export interface ZoneStats {
  zone_id: string
  zone_code: string
  zone_tier: string
  zone_name: string
  total_companies: number
  active_companies: number
  verified_companies: number
  inactive_companies: number
  pending_verification: number
  bundle_count: number
  declarativo_count: number
  exento_count: number
  pendiente_count: number
  with_nif: number
  with_reg_number: number
  with_zone: number
  missing_identifier: number
  active_licenses: number
  total_obligations_amount: number
  total_paid_amount: number
  total_debt: number
  recovery_rate_pct: number
  refreshed_at?: string
}

export interface MinistryZoneStats {
  ministry_id: number
  fee_type: string
  zone_id: string | null
  zone_code: string | null
  companies_count: number
  obligations_count: number
  paid_count: number
  pending_count: number
  overdue_count: number
  total_amount: number
  paid_amount: number
  overdue_amount: number
  total_penalties: number
  recovery_rate_pct: number
}

export interface MinistryStatsResponse {
  ministry_id: number
  zones: MinistryZoneStats[]
  totals: {
    total_amount: number
    paid_amount: number
    overdue_amount: number
    recovery_rate_pct: number
  }
}

export interface GlobalStats {
  total_companies: number
  active_companies: number
  verified_companies: number
  inactive_companies: number
  bundle_count: number
  declarativo_count: number
  exento_count: number
  pendiente_count: number
  with_nif: number
  with_reg_number: number
  with_zone: number
  missing_identifier: number
  refreshed_at?: string
}

// =============================================================================
// MINISTRY DEBT TYPES
// =============================================================================

export interface CompanyObligation {
  id: string
  fee_type: string
  amount: number
  penalty_amount: number
  due_date: string
  status: string
  paid_at: string | null
  bundle_item_id: string
  fiscal_year: number
  license_status: string
}

export interface CompanyDebtResponse {
  company: {
    id: string
    legal_name: string
    nif: string | null
    registration_number: string | null
    regimen_fiscal: string
    commerce_type: string | null
    is_active: boolean
    city_name: string | null
    zone_code: string | null
  }
  ministry_id: number
  obligations: CompanyObligation[]
  totals: {
    total_due: number
    total_paid: number
    total_overdue: number
    total_penalties: number
    balance: number
    recovery_rate_pct: number
    obligation_count: number
  }
}

// =============================================================================
// PUBLIC DIRECTORY TYPES
// =============================================================================

export interface PublicCompany {
  id: string
  legal_name: string
  nif: string | null
  registration_number: string | null
  forma_juridica: string | null
  sector_actividad: string | null
  subsector_actividad: string | null
  objeto_social: string | null
  regimen_fiscal: string | null
  address: string | null
  city_name: string | null
  provincia: string | null
  zone_code: string | null
  zone_tier: string | null
}

export interface PublicDirectoryResponse {
  items: PublicCompany[]
  total: number
  page: number
  page_size: number
}

export interface PublicZone {
  id: string
  zone_code: string
  zone_tier: string
  name_es: string
}

// =============================================================================
// ANALYTICS TYPES (rich cross-tabulated data)
// =============================================================================

export interface ZoneRegimeData {
  zone_code: string | null
  zone_name: string | null
  regime: string
  count: number
  total_amount: number
  paid_amount: number
  debt: number
}

export interface FormaJuridicaData {
  forma_juridica: string
  count: number
  with_license: number
  total_amount: number
}

export interface CityStatsData {
  city_name: string
  provincia: string
  zone_code: string | null
  companies: number
  licenses: number
  debt: number
  recovery_pct: number
}

export interface FeeTypeDebtData {
  fee_type: string
  companies: number
  obligations: number
  total_amount: number
  paid: number
  overdue: number
  penalties: number
}

export interface TopDebtorData {
  id: string
  legal_name: string
  nif: string | null
  registration_number: string | null
  regimen_fiscal: string
  zone_code: string | null
  debt: number
  total_amount: number
  recovery_pct: number
}

export interface MonthlyTrendData {
  month: string
  created: number
  bundle: number
  declarativo: number
  verified: number
}

export interface CompanyAnalytics {
  by_zone_regime: ZoneRegimeData[]
  by_forma_juridica: FormaJuridicaData[]
  by_city: CityStatsData[]
  debt_by_fee_type: FeeTypeDebtData[]
  top_debtors: TopDebtorData[]
  monthly_trend: MonthlyTrendData[]
}

export interface LookupResult {
  id: string
  legal_name: string
  nif: string | null
  registration_number: string | null
  forma_juridica: string | null
  regimen_fiscal: string | null
  commerce_type: string | null
  is_active: boolean
  is_verified: boolean
  city_name: string | null
  zone_code: string | null
}
