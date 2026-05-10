/**
 * Inspection Types - Facil Inspeccion
 *
 * Mirror of backend Pydantic models in:
 * packages/backend/app/modules/inspections/models/inspection.py
 */

export type InspectionStatus =
  | 'in_progress'
  | 'completed'
  | 'mise_en_demeure'
  | 'seal_proposed'
  | 'seal_approved'
  | 'seal_rejected'
  | 'cancelled';

export type InspectionResult = 'conforme' | 'non_conforme' | 'pending';

export type SealReason =
  | 'non_paiement_apres_med'
  | 'activite_non_autorisee'
  | 'fraude_fiscale'
  | 'faux_documents'
  | 'refus_controle'
  | 'non_conformite_grave'
  | 'decision_judiciaire'
  | 'ordre_ministeriel';

/** List item — used in dashboard recent + inspections list */
export interface InspectionListItem {
  id: string;
  inspection_date: string;
  status: InspectionStatus;
  result: InspectionResult | null;
  company_name: string | null;
  company_nif: string | null;
  unpaid_obligations_count: number;
  unpaid_obligations_amount: number;
  seal_applied: boolean;
  mise_en_demeure_issued: boolean;
  payment_collected: boolean;
  agent_name: string | null;
  entity_code: string | null;
  created_at: string;
}

/** Paginated list response */
export interface InspectionListResponse {
  items: InspectionListItem[];
  total: number;
  page: number;
  page_size: number;
}

/** Full inspection detail */
export interface InspectionDetail {
  id: string;
  agent_id: string;
  agent_profile_id: string;
  entity_id: string;
  entity_location_id: string;
  license_id: string;
  company_id: string;
  inspection_date: string;
  status: InspectionStatus;
  result: InspectionResult | null;
  activity_conforme: boolean | null;
  activity_declared: string | null;
  activity_observed: string | null;
  unpaid_obligations_count: number;
  unpaid_obligations_amount: number;
  total_obligations_count: number;
  photos: string[];
  gps_latitude: number | null;
  gps_longitude: number | null;
  gps_accuracy: number | null;
  notes: string | null;
  mise_en_demeure_issued: boolean;
  mise_en_demeure_deadline: string | null;
  mise_en_demeure_obligations: string[] | null;
  seal_applied: boolean;
  seal_reason: string | null;
  seal_notes: string | null;
  seal_photo: string | null;
  seal_proposed_at: string | null;
  seal_approved_by: string | null;
  seal_approved_at: string | null;
  seal_rejection_reason: string | null;
  payment_collected: boolean;
  payment_id: string | null;
  payment_receipt_number: string | null;
  payment_amount: number | null;
  agent_signature: string | null;
  created_at: string;
  updated_at: string;
  company_name: string | null;
  company_nif: string | null;
  agent_name: string | null;
  entity_code: string | null;
}

/** Stats for a time period */
export interface InspectionStats {
  total: number;
  conforme: number;
  non_conforme: number;
  mise_en_demeure: number;
  seals_proposed: number;
  seals_approved: number;
  payments_collected: number;
  total_collected_amount: number;
  avg_duration_minutes: number | null;
}

/** Pending seal item for supervisor */
export interface PendingSealItem {
  id: string;
  inspection_date: string;
  company_name: string | null;
  company_nif: string | null;
  seal_reason: string | null;
  seal_notes: string | null;
  seal_photo: string | null;
  seal_proposed_at: string | null;
  agent_name: string | null;
  photos: string[];
  gps_latitude: number | null;
  gps_longitude: number | null;
  unpaid_obligations_amount: number;
  unpaid_obligations_count: number;
}

/** Supervisor dashboard response */
export interface SupervisorDashboard {
  today: InspectionStats;
  week: InspectionStats;
  pending_seals: PendingSealItem[];
  overdue_med: number;
  unreconciled_cash_amount: number;
  unreconciled_cash_count: number;
  recent_inspections: InspectionListItem[];
}

/** Per-agent real-time status */
export interface AgentLiveStatus {
  agent_id: string;
  agent_profile_id: string;
  agent_name: string;
  status: 'active' | 'idle' | 'offline';
  last_activity_at: string | null;
  minutes_since_activity: number | null;
  inspections_today: number;
  cash_collected_today: number;
  current_inspection_id: string | null;
  last_gps_latitude: number | null;
  last_gps_longitude: number | null;
}

/** Entity-level counters */
export interface LiveStatusCounters {
  active_agents: number;
  idle_agents: number;
  offline_agents: number;
  total_agents: number;
  inspections_today: number;
  inspections_in_progress: number;
  cash_collected_today: number;
  cash_pending_reconciliation: number;
}

/** Full live status response */
export interface LiveStatusResponse {
  agents: AgentLiveStatus[];
  counters: LiveStatusCounters;
  cached_at: string | null;
}

/** List query filters */
export interface InspectionListFilters {
  inspection_date?: string;
  status?: InspectionStatus;
  result?: InspectionResult;
  date_from?: string;
  date_to?: string;
  search?: string;
  has_payment?: boolean;
  has_med?: boolean;
  has_seal?: boolean;
  sort_by?: 'inspection_date' | 'created_at' | 'payment_amount' | 'company_name' | 'status' | 'result';
  sort_dir?: 'asc' | 'desc';
  page?: number;
  page_size?: number;
}

/** P4: Existing service_request dossier linked to a licence (P3 backend) */
export interface ExistingDossier {
  service_request_id: string;
  reference: string;
  source: 'citizen_wizard' | 'field_inspection' | 'admin_import' | 'batch';
  status: string;
  created_at: string;
}

/** P4: Pending citizen online payment info (P3 backend) */
export interface PendingPaymentInfo {
  payment_reference: string;
  payment_method: string | null;
  total_amount: number | null;
  workflow_status: string;
  created_at: string;
}

/** P4: Agent collection scope computed server-side (P3 backend) */
export interface AgentScope {
  role_code: string | null;
  allowed_fee_types: string[] | null;
  required_ministry_id: number | null;
  is_polyvalent: boolean;
  is_independent: boolean;
  is_supervisor: boolean;
}

/** License verification response — enriched in P3/P4 */
export interface LicenseVerification {
  license_id: string;
  company_id: string;
  company_name: string | null;
  company_nif: string | null;
  company_registration_number: string | null;
  forma_juridica: string | null;
  commerce_type: string | null;
  zone_code: string | null;
  city_name: string | null;
  fiscal_year: number;
  license_status: string;
  total_amount: number;
  amount_paid: number;
  compliance_score: number | null;
  obligations: LicenseObligation[];
  previous_inspections: InspectionListItem[];
  active_mise_en_demeure: ActiveMiseEnDemeure | null;
  seal_history: SealHistoryItem[];

  // P3/P4: enriched fields (additive, backward-compatible)
  existing_dossier?: ExistingDossier | null;
  has_pending_citizen_payment?: boolean;
  pending_payment_info?: PendingPaymentInfo | null;
  restricted_obligations?: string[];
  agent_can_collect_all?: boolean;
  agent_scope?: AgentScope;
}

export interface LicenseObligation {
  id: string;
  fee_type: string;
  amount: number;
  penalty_amount: number;
  due_date: string;
  status: string;
  service_name: string | null;
  ministry_name: string | null;
  // P3/P4: added ministry_id (was missing — bug latent corrected in backend)
  ministry_id?: number | null;
  // P3/P4: agent scope flag (server computes whether this agent may collect)
  agent_restricted?: boolean;
  agent_restricted_reason?: string | null;
}

export interface ActiveMiseEnDemeure {
  id: string;
  mise_en_demeure_deadline: string;
  mise_en_demeure_obligations: string[];
  inspection_date: string;
  agent_id: string;
}

export interface SealHistoryItem {
  id: string;
  inspection_date: string;
  seal_reason: string;
  status: string;
  seal_approved_at: string | null;
  seal_approved_by: string | null;
}
