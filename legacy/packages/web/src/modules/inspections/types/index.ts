export type InspectionStatus =
  | 'in_progress'
  | 'completed'
  | 'mise_en_demeure'
  | 'seal_proposed'
  | 'seal_approved'
  | 'seal_rejected'
  | 'cancelled'

export type InspectionResult = 'conforme' | 'non_conforme' | 'pending'

export type SealReason =
  | 'non_paiement_apres_med'
  | 'activite_non_autorisee'
  | 'fraude_fiscale'
  | 'faux_documents'
  | 'refus_controle'
  | 'non_conformite_grave'
  | 'decision_judiciaire'
  | 'ordre_ministeriel'

export interface Inspection {
  id: string
  agent_id: string
  agent_profile_id: string
  entity_id: string
  entity_location_id: string
  license_id: string
  company_id: string
  inspection_date: string
  status: InspectionStatus
  result?: InspectionResult

  activity_conforme?: boolean
  activity_declared?: string
  activity_observed?: string

  unpaid_obligations_count: number
  unpaid_obligations_amount: number
  total_obligations_count: number

  photos: string[]
  gps_latitude?: number
  gps_longitude?: number
  gps_accuracy?: number
  notes?: string

  mise_en_demeure_issued: boolean
  mise_en_demeure_deadline?: string
  mise_en_demeure_obligations?: string[]

  seal_applied: boolean
  seal_reason?: SealReason
  seal_notes?: string
  seal_photo?: string
  seal_proposed_at?: string
  seal_approved_by?: string
  seal_approved_at?: string
  seal_rejection_reason?: string

  payment_collected: boolean
  payment_id?: string
  payment_receipt_number?: string
  payment_amount?: number

  created_at: string
  updated_at: string

  company_name?: string
  company_nif?: string
  agent_name?: string
  entity_code?: string
}

export interface InspectionListItem {
  id: string
  agent_id: string
  inspection_date: string
  status: InspectionStatus
  result?: InspectionResult
  company_name?: string
  company_nif?: string
  unpaid_obligations_count: number
  unpaid_obligations_amount: number
  seal_applied: boolean
  mise_en_demeure_issued: boolean
  payment_collected: boolean
  payment_amount?: number
  agent_name?: string
  entity_code?: string
  created_at: string
}

export interface InspectionListResponse {
  items: InspectionListItem[]
  total: number
  page: number
  page_size: number
}

export interface InspectionStats {
  total: number
  conforme: number
  non_conforme: number
  mise_en_demeure: number
  seals_proposed: number
  seals_approved: number
  payments_collected: number
  total_collected_amount: number
  avg_duration_minutes?: number
}

export interface PendingSeal {
  id: string
  inspection_date: string
  company_name?: string
  company_nif?: string
  seal_reason?: string
  seal_notes?: string
  seal_photo?: string
  seal_proposed_at?: string
  agent_name?: string
  photos: string[]
  gps_latitude?: number
  gps_longitude?: number
  unpaid_obligations_amount: number
  unpaid_obligations_count: number
}

export interface SupervisorDashboard {
  today: InspectionStats
  week: InspectionStats
  pending_seals: PendingSeal[]
  overdue_med: number
  unreconciled_cash_amount: number
  unreconciled_cash_count: number
  recent_inspections: InspectionListItem[]
}

export interface ReconciliationItem {
  id: string
  inspection_date: string
  company_name?: string
  company_nif?: string
  payment_amount?: number
  payment_receipt_number?: string
  created_at: string
}

export interface ReconciliationResponse {
  items: ReconciliationItem[]
  total_amount: number
  total_count: number
}

export interface LicenseObligation {
  id: string
  fee_type: string
  amount: number
  penalty_amount: number
  due_date?: string
  status: string
  service_name?: string
  ministry_name?: string
}

export interface LicenseVerification {
  license_id: string
  company_id: string
  company_name?: string
  company_nif?: string
  company_registration_number?: string
  forma_juridica?: string
  commerce_type?: string
  zone_code?: string
  city_name?: string
  fiscal_year: number
  license_status: string
  total_amount: number
  amount_paid: number
  compliance_score?: number
  obligations: LicenseObligation[]
  previous_inspections: InspectionListItem[]
  active_mise_en_demeure?: Record<string, unknown>
  seal_history: Record<string, unknown>[]
}

// ============================================================
// MISSIONS
// ============================================================

export type MissionStatus = 'planned' | 'in_progress' | 'completed' | 'cancelled'
export type MissionAgentStatus = 'assigned' | 'active' | 'completed' | 'absent'

export interface MissionAgent {
  id: string
  mission_id: string
  agent_id: string
  agent_profile_id: string
  agent_name: string
  assigned_zones?: string[]
  target_inspections: number
  actual_inspections: number
  status: MissionAgentStatus
  progress_pct: number
  working_days?: number[]
  availability_status: string
  notes?: string
  created_at: string
}

export interface Mission {
  id: string
  entity_id: string
  entity_location_id: string
  supervisor_id: string
  mission_date: string
  title?: string
  notes?: string
  zone_ids?: string[]
  status: MissionStatus
  entity_code: string
  location_name: string
  supervisor_name: string
  agents: MissionAgent[]
  agents_count: number
  total_inspections: number
  total_target: number
  started_at?: string
  completed_at?: string
  created_at: string
  updated_at: string
}

export interface MissionListItem {
  id: string
  mission_date: string
  title?: string
  status: MissionStatus
  agents_count: number
  inspections_done: number
  inspections_target: number
  entity_code: string
  location_name: string
  created_at: string
}

export interface MissionListResponse {
  items: MissionListItem[]
  total: number
}

export interface ZoneSuggestion {
  zone_id: string
  zone_code: string
  zone_name: string
  zone_tier: string
  days_since_last_inspection: number | null
  pending_obligations_count: number
  suggested_priority: 'high' | 'medium' | 'low'
}

export interface AgentAvailability {
  agent_id: string
  agent_profile_id: string
  agent_name: string
  is_available: boolean
  current_mission?: string
  working_days?: number[]
  availability_status: string
}

// ============================================================
// ANALYTICS
// ============================================================

export interface AgentPerformanceItem {
  agent_id: string
  agent_name: string
  entity_code: string
  inspections_total: number
  conforme: number
  non_conforme: number
  conformity_rate: number
  collections_count: number
  collected_amount: number
  med_count: number
  seal_count: number
  avg_duration_minutes?: number
  zones_covered: number
  days_active: number
}

export interface AgentPerformanceResponse {
  items: AgentPerformanceItem[]
  total: number
  period_start: string
  period_end: string
}

export interface AgentDetailResponse extends AgentPerformanceItem {
  recent_inspections: Array<{
    id: string
    inspection_date: string
    company_name: string
    company_nif: string
    result: string
    status: string
    payment_amount?: number
  }>
  zone_breakdown: Array<{
    zone_code: string
    zone_name: string
    inspections: number
    conforme: number
    collected_amount: number
  }>
  weekly_trend: Array<{
    week_start: string
    inspections: number
    conforme: number
    non_conforme: number
    collected_amount: number
  }>
}

export interface ZoneAnalyticsItem {
  zone_id?: string
  zone_code: string
  zone_name: string
  zone_tier: string
  inspections: number
  conforme: number
  non_conforme: number
  conformity_rate: number
  collections: number
  collected_amount: number
  med_count: number
  seal_count: number
  agents_active: number
  avg_duration_minutes?: number
  days_since_last_inspection?: number
  coverage_status: 'ok' | 'warning' | 'critical'
}

export interface ZoneAnalyticsResponse {
  items: ZoneAnalyticsItem[]
  total_zones: number
  covered_zones: number
  stale_zones: number
}

export interface TrendPoint {
  period: string
  period_start: string
  inspections: number
  conforme: number
  non_conforme: number
  conformity_rate: number
  collections: number
  collected_amount: number
  med_count: number
  seal_count: number
}

export interface TrendResponse {
  data: TrendPoint[]
  granularity: string
  date_from: string
  date_to: string
}

export interface CompareItem {
  label: string
  inspections: number
  conforme: number
  non_conforme: number
  conformity_rate: number
  collections: number
  collected_amount: number
  med_count: number
  seal_count: number
}

export interface CompareResponse {
  compare_type: string
  items: CompareItem[]
  date_from: string
  date_to: string
}

export interface PriorityZoneItem {
  zone_id?: string
  zone_code: string
  zone_name: string
  zone_tier: string
  days_since_last_inspection: number
  pending_obligations: number
  pending_amount: number
  priority_score: number
  recommended_agents: number
}

export interface PriorityZonesResponse {
  items: PriorityZoneItem[]
  total: number
}

// ============================================================
// FILTER PRESETS
// ============================================================

export interface FilterPreset {
  id: string
  user_id: string
  preset_name: string
  table_key: string
  filters: Record<string, unknown>
  column_visibility?: Record<string, boolean>
  sort_config?: { column: string; direction: 'asc' | 'desc' }
  is_default: boolean
  created_at: string
  updated_at: string
}

export interface FilterPresetListResponse {
  items: FilterPreset[]
  total: number
}

// ============================================================
// FIELD PAYMENT (for reconciliation table)
// ============================================================

export interface FieldPayment {
  id: string
  payment_reference: string
  total_amount: number
  agent_name: string
  company_name?: string
  company_nif?: string
  entity_code: string
  fee_type?: string
  inspection_date?: string
  created_at: string
}

// ============================================================
// LIVE STATUS (Phase 8 — Real-Time View)
// ============================================================

export type AgentOnlineStatus = 'active' | 'idle' | 'offline'

export interface AgentLiveStatus {
  agent_id: string
  agent_profile_id: string
  agent_name: string
  status: AgentOnlineStatus
  last_activity_at?: string
  minutes_since_activity?: number
  inspections_today: number
  cash_collected_today: number
  current_inspection_id?: string
  last_gps_latitude?: number
  last_gps_longitude?: number
}

export interface LiveStatusCounters {
  active_agents: number
  idle_agents: number
  offline_agents: number
  total_agents: number
  inspections_today: number
  inspections_in_progress: number
  cash_collected_today: number
  cash_pending_reconciliation: number
}

export interface LiveStatusResponse {
  agents: AgentLiveStatus[]
  counters: LiveStatusCounters
  cached_at?: string
}

// ============================================================
// MISSION ANALYTICS
// ============================================================

export interface MissionAnalyticsSummary {
  total_missions: number
  completed: number
  cancelled: number
  in_progress: number
  planned: number
  completion_rate: number
  avg_duration_hours: number
  total_inspections_actual: number
  total_inspections_target: number
  target_achievement_rate: number
  conformity_rate: number
  total_collected: number
}

export interface MissionTrendPoint {
  week: string
  missions: number
  inspections: number
  conformity: number | null
}

export interface MissionTopAgent {
  agent_name: string
  missions_count: number
  inspections: number
  avg_target_pct: number | null
}

export interface MissionStaleZone {
  zone_code: string
  zone_name: string | null
  days_since: number | null
  pending_count: number
}

export interface MissionDeltas {
  missions: number
  completion: number
  inspections: number
  collected: number
}

export interface MissionStatusBreakdown {
  planned: number
  in_progress: number
  completed: number
  cancelled: number
}

export interface AgentZoneCell {
  agent_name: string
  zone_code: string
  inspections: number
}

export interface ZoneConformity {
  zone_code: string
  zone_name: string | null
  total: number
  conforme: number
  non_conforme: number
  conformity_rate: number | null
}

export interface MissionAnalyticsResponse {
  period: { date_from: string; date_to: string }
  summary: MissionAnalyticsSummary
  trends: MissionTrendPoint[]
  top_agents: MissionTopAgent[]
  stale_zones: MissionStaleZone[]
  deltas: MissionDeltas
  status_breakdown: MissionStatusBreakdown
  agent_zone_matrix: AgentZoneCell[]
  zone_conformity: ZoneConformity[]
}

// ============================================================
// MISSION TEMPLATES
// ============================================================

export interface MissionTemplate {
  id: string
  name: string
  recurrence: 'daily' | 'weekly' | 'biweekly' | 'monthly'
  day_of_week: number | null
  day_of_month: number | null
  zone_ids: string[] | null
  default_agent_ids: string[] | null
  target_inspections_per_agent: number
  notes: string | null
  is_active: boolean
  last_created_at: string | null
  last_created_mission_id: string | null
  created_by_name?: string
  created_at: string
}
