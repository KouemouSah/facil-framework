/**
 * OMS Types — Obligations Management System
 * Aligned with backend models: fiscal_services/models/licenses.py
 */

// =============================================================================
// ENUMS
// =============================================================================

export type LicenseStatus = 'open' | 'partial' | 'overdue' | 'complete' | 'cancelled'
export type ObligationStatus = 'pending' | 'paid' | 'processing' | 'completed' | 'overdue' | 'cancelled'

// =============================================================================
// QUEUE TYPES (oms_agent_routes)
// =============================================================================

export interface AgentQueueItem {
  id: string
  license_id: string
  bundle_item_id: string
  fiscal_service_id: number
  ministry_id: number | null
  fee_type: string
  amount: number
  penalty_amount: number
  due_date: string | null
  status: string
  created_at: string
  // Enriched JOINs
  service_name: string | null
  service_code: string | null
  ministry_name: string | null
  company_name: string | null
  company_nif: string | null
  company_registration_number: string | null
  fiscal_year: number | null
  zone_code: string | null
  processing_mode: string | null
}

export interface AgentQueueResponse {
  items: AgentQueueItem[]
  total: number
  page: number
  page_size: number
}

export interface AgentQueueStats {
  pending_count: number
  completed_today: number
  total_amount_pending: number
  total_amount_completed_today: number
  awaiting_document: number
  not_started: number
}

// =============================================================================
// LICENSE TYPES (license_routes)
// =============================================================================

export interface LicenseResponse {
  id: string
  company_id: string
  bundle_id: string | null
  zone_id: string | null
  fiscal_year: number
  total_amount: number
  amount_paid: number
  status: LicenseStatus
  created_at: string
  updated_at: string
  // Enriched
  company_name: string | null
  company_nif: string | null
  company_registration_number: string | null
  zone_code: string | null
  bundle_name: string | null
  obligations_count: number
  paid_count: number
  overdue_count: number
}

export interface LicenseListResponse {
  items: LicenseResponse[]
  total: number
  page: number
  page_size: number
}

export interface LicenseStats {
  total_licenses: number
  active_licenses: number
  overdue_licenses: number
  total_amount: number
  total_paid: number
  total_debt: number
  recovery_rate: number
}

// =============================================================================
// OBLIGATION TYPES
// =============================================================================

export interface ObligationResponse {
  id: string
  license_id: string
  bundle_item_id: string
  fiscal_service_id: number
  ministry_id: number | null
  fee_type: string
  amount: number
  penalty_amount: number
  due_date: string | null
  status: ObligationStatus
  paid_at: string | null
  processed_at: string | null
  processed_by: string | null
  notes: string | null
  created_at: string
  // Enriched
  service_name: string | null
  ministry_name: string | null
}

export interface ObligationListResponse {
  items: ObligationResponse[]
  total: number
  page: number
  page_size: number
  // Server-side KPIs aggregated from ALL matching obligations (not just page)
  total_amount: number
  paid_amount: number
  penalty_amount: number
  paid_count: number
  pending_count: number
  overdue_count: number
}

// =============================================================================
// COMPLIANCE EVENTS
// =============================================================================

export interface ComplianceEvent {
  id: string
  license_id: string
  obligation_id: string | null
  event_type: string
  event_data: Record<string, unknown> | null
  triggered_by: string | null
  created_at: string
}

export interface ComplianceEventListResponse {
  items: ComplianceEvent[]
  total: number
  page: number
  page_size: number
}

// =============================================================================
// COMPLIANCE SUMMARY (pre-aggregated by fee_type)
// =============================================================================

export interface ComplianceSummaryCompany {
  company_name: string
  company_nif: string | null
  zone: string | null
  license_id: string
  amount: number
  penalty: number
}

export interface ComplianceSummaryGroup {
  fee_type: string
  total_obligations: number
  paid: number
  pending: number
  overdue: number
  total_amount: number
  paid_amount: number
  overdue_amount: number
  overdue_penalty: number
  recovery_pct: number
  overdue_companies: ComplianceSummaryCompany[]
}

export interface ComplianceSummaryResponse {
  items: ComplianceSummaryGroup[]
  fiscal_year: number
}

// =============================================================================
// TEAM PERFORMANCE (supervisor)
// =============================================================================

export interface AgentPerformance {
  agent_profile_id: string
  agent_name: string
  role_code: string
  entity_code: string
  availability: string
  obligations_assigned: number
  obligations_completed: number
  obligations_pending: number
  obligations_rejected: number
  amount_processed: number
  avg_processing_minutes: number
  completion_rate: number
  rejection_rate: number
}

export interface TeamPerformanceResponse {
  agents: AgentPerformance[]
  team_totals: {
    total_agents: number
    total_assigned: number
    total_completed: number
    total_pending: number
    total_amount_processed: number
    avg_completion_rate: number
  }
  period_days: number
  fiscal_year: number
}
