/**
 * Shared types and helpers for Supervisor pages
 * Aligned with backend supervisor_routes.py + agent_workload.py response models
 *
 * Single source of truth — all supervisor pages import from here.
 *
 * IMPORTANT: success_rate from backend is 0.0-1.0 (ratio).
 * Display as percentage: (success_rate * 100).toFixed(0)%
 */

// =============================================================================
// AGENT
// =============================================================================

/** Backend: AgentListItem (supervisor_routes.py:168-180) */
export interface AgentListItem {
  agent_profile_id: string; // PRIMARY KEY — use this for all API calls
  agent_id: string | null; // DEPRECATED: user_id, kept for backward compat
  agent_name: string;
  agent_email: string;
  current_assignments: number;
  capacity_percentage: number;
  workload_status: 'available' | 'normal' | 'busy' | 'overloaded' | 'unavailable';
  availability: 'available' | 'on_leave' | 'sick_leave' | 'training' | 'mission' | 'temporarily_unavailable';
  specializations?: string[];
  avg_processing_time_hours?: number;
  success_rate: number; // 0.0-1.0
}

/** Backend: AgentAssignmentItem (supervisor_routes.py) */
export interface AgentAssignmentItem {
  assignment_id: string;
  request_id: string;
  request_reference: string | null;
  workflow_code: string | null;
  status: string;
  assigned_at: string | null;
}

/** Backend: AgentAssignmentStats (assignment_repository.py) */
export interface AgentStats {
  agent_id: string;
  period_days: number;
  total_assignments: number;
  completed_assignments: number;
  pending_assignments: number;
  rejected_assignments: number;
  avg_processing_time_hours: number;
  success_rate: number; // 0.0-1.0
  quality_score_avg: number; // 0.0-1.0
  deadline_compliance_rate: number; // 0.0-1.0
  by_status: Record<string, number>;
  by_type: Record<string, number>;
}

/** Backend: AgentTrendsResponse (supervisor_routes.py) */
export interface TrendPoint {
  period: string;
  processed: number;
  approved: number;
  rejected: number;
  avg_processing_hours: number;
  sla_compliance_pct: number;
}

export interface AgentTrendsResponse {
  agent_id: string;
  agent_name: string;
  period_days: number;
  granularity: string;
  data_points: TrendPoint[];
}

// =============================================================================
// ESCALATION
// =============================================================================

/** Backend: EscalationListItem (supervisor_routes.py:969-983) */
export interface Escalation {
  id: string;
  queue_id: string;
  reason: string;
  priority_score: number;
  status: string;
  escalation_status: 'pending' | 'in_review' | 'resolved' | 'reassigned';
  case_reference: string;
  case_type: string;
  escalated_by_name: string;
  escalated_by_email: string;
  escalated_at: string;
  created_at: string;
  assigned_to_name?: string;
}

export type PriorityLevel = 'low' | 'medium' | 'high' | 'critical';

export function getPriorityLevel(score: number): PriorityLevel {
  if (score >= 80) return 'critical';
  if (score >= 60) return 'high';
  if (score >= 40) return 'medium';
  return 'low';
}

export const PRIORITY_COLORS: Record<PriorityLevel, string> = {
  low: 'bg-gray-100 text-gray-800',
  medium: 'bg-yellow-100 text-yellow-800',
  high: 'bg-orange-100 text-orange-800',
  critical: 'bg-red-100 text-red-800',
};

// =============================================================================
// DASHBOARD
// =============================================================================

/** Backend: DashboardResponse (supervisor_routes.py:160-165) */
export interface SupervisorDashboardStats {
  team: { activeAgents: number; totalAgents: number; utilizationRate: number };
  escalations: { pending: number; resolvedToday: number; avgResolutionTime: number };
  assignments: { pending: number; inProgress: number; completedToday: number };
  performance: { avgResponseTime: number; slaCompliance: number; qualityScore: number };
}

// =============================================================================
// WORKLOAD
// =============================================================================

/**
 * Backend: WorkloadBalanceReport (agent_workload.py:80-100)
 * Fields aligned with actual Pydantic model — NO fictitious fields.
 */
export interface WorkloadBalanceReport {
  balance_score: number;
  total_agents: number;
  available_agents: number;
  busy_agents: number;
  overloaded_agents: number;
  unavailable_agents: number;
  total_assignments: number;
  avg_assignments_per_agent: number;
  min_assignments: number;
  max_assignments: number;
  rebalancing_needed: boolean;
}

export interface WorkloadRecommendation {
  type: string;
  priority: string;
  message: string;
}

export interface WorkloadBalanceResponse {
  report: WorkloadBalanceReport;
  agents: AgentListItem[];
  recommendations: WorkloadRecommendation[];
}

// =============================================================================
// RULES
// =============================================================================

/**
 * Backend: AssignmentRule (assignment_rule.py:49-72)
 * DB: assignment_rules table — conditions/actions JSONB, status enum
 */
export type RuleStatus = 'active' | 'inactive' | 'draft' | 'archived';

export interface RuleConditions {
  item_types?: string[];
  min_amount?: number;
  max_amount?: number;
  min_priority?: number;
  // Treasury-specific conditions (entity_type === 'treasury')
  payment_methods?: string[];
  payment_types?: string[];
  has_penalties?: boolean;
  entity_location_id?: string;
}

export interface RuleActions {
  selection_strategy?: 'load_balance' | 'round_robin' | 'specialization';
  specializations?: string[];
  max_workload_pct?: number;
}

export interface AssignmentRule {
  id: string;
  name: string;
  description: string | null;
  entity_type: string;
  entity_id: string | null;
  conditions: RuleConditions;
  actions: RuleActions;
  priority: number;
  status: RuleStatus;
  times_applied: number;
  times_matched: number;
  successful_assignments: number;
  failed_assignments: number;
  success_rate: number;
  last_applied_at: string | null;
  created_by: string;
  created_at: string;
  updated_at: string | null;
  updated_by: string | null;
}

/** Backend: RuleEffectivenessItem (supervisor_routes.py:183-193) */
export interface RuleEffectivenessItem {
  rule_id: string;
  rule_name: string;
  priority: number;
  times_applied: number;
  times_matched: number;
  success_rate: number;
  effectiveness_score: number;
  application_rate: number;
  last_applied_at: string | null;
}

// =============================================================================
// INTELLIGENCE (Phase 2b)
// =============================================================================

/** Backend: GET /supervisor/proficiency-overview */
export interface AgentProficiency {
  agent_profile_id: string;
  agent_name: string;
  workflow_code: string;
  completions_total: number;
  escalations_total: number;
  success_rate: number; // 0-100 (NOT 0-1 — comes from agent_workflow_proficiency)
  avg_processing_hours: number;
  completions_30d: number;
  escalations_30d: number;
  last_completed_at: string | null;
}

/** Backend: GET /supervisor/anomalies */
export interface AnomalyAlert {
  type: string;
  message: string;
  severity: 'warning' | 'critical';
}

export interface AnomalyResponse {
  detected_at: string | null;
  anomalies: AnomalyAlert[];
  count: number;
}

/** Backend: GET /supervisor/skills-gap */
export interface SkillsGapItem {
  workflow_code: string;
  pending_count: number;
  specialist_count: number;
  avg_specialist_success: number;
  coverage_status: 'critical' | 'warning' | 'ok';
}

export const COVERAGE_STATUS_COLORS: Record<string, string> = {
  critical: 'bg-red-100 text-red-800',
  warning: 'bg-yellow-100 text-yellow-800',
  ok: 'bg-green-100 text-green-800',
};

// =============================================================================
// SHARED HELPERS
// =============================================================================

export const WORKLOAD_STATUS_COLORS: Record<string, string> = {
  available: 'bg-green-100 text-green-800',
  normal: 'bg-blue-100 text-blue-800',
  busy: 'bg-yellow-100 text-yellow-800',
  overloaded: 'bg-red-100 text-red-800',
  unavailable: 'bg-gray-100 text-gray-800',
};

export const AVAILABILITY_COLORS: Record<string, string> = {
  available: 'bg-green-100 text-green-800',
  on_leave: 'bg-purple-100 text-purple-800',
  sick_leave: 'bg-orange-100 text-orange-800',
  training: 'bg-blue-100 text-blue-800',
  mission: 'bg-indigo-100 text-indigo-800',
  temporarily_unavailable: 'bg-gray-100 text-gray-800',
};

export const RULE_STATUS_COLORS: Record<RuleStatus, string> = {
  active: 'bg-green-100 text-green-800',
  inactive: 'bg-gray-100 text-gray-800',
  draft: 'bg-yellow-100 text-yellow-800',
  archived: 'bg-red-100 text-red-800',
};

export const STRATEGY_COLORS: Record<string, string> = {
  load_balance: 'bg-green-100 text-green-800',
  round_robin: 'bg-blue-100 text-blue-800',
  specialization: 'bg-purple-100 text-purple-800',
};

export function getBalanceColor(score: number): string {
  if (score >= 80) return 'text-green-600';
  if (score >= 60) return 'text-blue-600';
  if (score >= 40) return 'text-yellow-600';
  return 'text-red-600';
}

export function getBalanceBadgeKey(score: number): { color: string; key: string } {
  if (score >= 80) return { color: 'bg-green-100 text-green-800', key: 'workload.excellent' };
  if (score >= 60) return { color: 'bg-blue-100 text-blue-800', key: 'workload.good' };
  if (score >= 40) return { color: 'bg-yellow-100 text-yellow-800', key: 'workload.moderate' };
  return { color: 'bg-red-100 text-red-800', key: 'workload.poor' };
}

/**
 * success_rate helpers — backend returns 0.0-1.0
 * Use these to display consistently across all pages.
 */
export function formatSuccessRate(rate: number): string {
  return `${(rate * 100).toFixed(0)}%`;
}

export function getSuccessRateColor(rate: number): string {
  if (rate >= 0.8) return 'text-green-600';
  if (rate >= 0.6) return 'text-yellow-600';
  return 'text-red-600';
}

export function getPerformanceBadge(rate: number): { color: string; key: string } {
  if (rate >= 0.9) return { color: 'bg-green-100 text-green-800', key: 'performance.excellent' };
  if (rate >= 0.8) return { color: 'bg-blue-100 text-blue-800', key: 'performance.good' };
  if (rate >= 0.7) return { color: 'bg-yellow-100 text-yellow-800', key: 'performance.average' };
  return { color: 'bg-red-100 text-red-800', key: 'performance.needsImprovement' };
}
