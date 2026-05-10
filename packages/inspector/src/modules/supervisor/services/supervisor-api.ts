/**
 * Supervisor API — Analytics, Missions, Export
 */

import { apiGet, apiPost, apiPut, apiDelete } from '@core/api/client';
import { API_ENDPOINTS } from '@core/api/endpoints';

// ---------------------------------------------------------------------------
// Analytics types (mirrors backend Pydantic models)
// ---------------------------------------------------------------------------

export interface AgentPerformanceItem {
  agent_id: string;
  agent_name: string;
  entity_code: string;
  inspections_count: number;
  conforme_count: number;
  non_conforme_count: number;
  conformity_rate: number;
  avg_duration_minutes: number;
  total_collected: number;
  seals_proposed: number;
  med_issued: number;
}

export interface AgentPerformanceResponse {
  items: AgentPerformanceItem[];
  total: number;
  period: { date_from: string; date_to: string };
}

export interface ZoneItem {
  zone_code: string;
  zone_name: string | null;
  inspections_count: number;
  conformity_rate: number;
  total_collected: number;
  companies_inspected: number;
}

export interface TrendPoint {
  date: string;
  inspections: number;
  conforme: number;
  non_conforme: number;
  collected: number;
}

export interface TrendResponse {
  points: TrendPoint[];
  granularity: string;
}

export interface PriorityZone {
  zone_code: string;
  zone_name: string | null;
  priority_score: number;
  uninspected_companies: number;
  overdue_obligations_amount: number;
  last_inspection_date: string | null;
}

// ---------------------------------------------------------------------------
// Mission types
// ---------------------------------------------------------------------------

export interface Mission {
  id: string;
  mission_date: string;
  title: string | null;
  notes: string | null;
  status: 'planned' | 'in_progress' | 'completed' | 'cancelled';
  entity_id: string;
  entity_location_id: string;
  agents: MissionAgent[];
  created_at: string;
}

export interface MissionAgent {
  agent_id: string;
  agent_name: string;
  status: 'assigned' | 'active' | 'completed' | 'absent';
  assigned_zones: string[] | null;
  target_inspections: number | null;
  actual_inspections: number;
}

export interface MissionListResponse {
  items: Mission[];
  total: number;
}

export interface ZoneSuggestion {
  zone_id: string;
  zone_code: string;
  zone_name: string | null;
  priority_score: number;
  suggested_priority: string;
  days_since_last_inspection: number | null;
  pending_obligations_count: number;
}

export interface AgentAvailability {
  agent_id: string;
  agent_profile_id: string;
  agent_name: string;
  is_available: boolean;
  current_mission: string | null;
  working_days: number[] | null;
  availability_status: string;
  entity_location_id: string | null;
  location_city: string | null;
}

export interface AutoAssignProposal {
  agent_id: string;
  agent_profile_id: string;
  agent_name: string;
  score: number;
  zone_expertise: number;
  recent_workload: number;
  conformity_rate: number;
  target_inspections: number;
  assigned_zones: string[];
}

export interface AutoAssignResponse {
  mission_id: string;
  target_total: number;
  agents_proposed: number;
  proposals: AutoAssignProposal[];
}

// ---------------------------------------------------------------------------
// API
// ---------------------------------------------------------------------------

export const supervisorApi = {
  // --- Analytics ---
  getAgentPerformance: (params?: { date_from?: string; date_to?: string }) =>
    apiGet<AgentPerformanceResponse>(API_ENDPOINTS.analytics.agents, params as Record<string, unknown>),

  getZoneAnalytics: (params?: { date_from?: string; date_to?: string }) =>
    apiGet<{ items: ZoneItem[] }>(API_ENDPOINTS.analytics.zones, params as Record<string, unknown>),

  getTrends: (params?: { date_from?: string; date_to?: string; granularity?: string }) =>
    apiGet<TrendResponse>(API_ENDPOINTS.analytics.trends, params as Record<string, unknown>),

  getPriorityZones: (limit = 10) =>
    apiGet<{ items: PriorityZone[] }>(API_ENDPOINTS.analytics.priorityZones, { limit }),

  // --- Export ---
  exportCsv: (params?: Record<string, string>) =>
    apiGet<Blob>(API_ENDPOINTS.export.csv, params),

  exportPdf: (params?: Record<string, string>) =>
    apiGet<Blob>(API_ENDPOINTS.export.pdf, params),

  // --- Missions ---
  listMissions: (params?: { date_from?: string; date_to?: string; status?: string }) =>
    apiGet<MissionListResponse>(API_ENDPOINTS.missions.list, params as Record<string, unknown>),

  createMission: (data: { mission_date: string; title?: string; notes?: string; zone_ids?: string[] }) =>
    apiPost<Mission>(API_ENDPOINTS.missions.create, data),

  getMission: (id: string) =>
    apiGet<Mission>(API_ENDPOINTS.missions.detail(id)),

  completeMission: (id: string, notes?: string) =>
    apiPost<Mission>(API_ENDPOINTS.missions.complete(id), { notes }),

  suggestZones: () =>
    apiGet<ZoneSuggestion[]>(API_ENDPOINTS.missions.suggestZones),

  getAgentsAvailability: (missionDate: string, entityLocationId?: string) =>
    apiGet<AgentAvailability[]>(API_ENDPOINTS.missions.agentAvailability, {
      mission_date: missionDate,
      ...(entityLocationId ? { entity_location_id: entityLocationId } : {}),
    } as Record<string, unknown>),

  updateMission: (id: string, data: { title?: string; notes?: string; zone_ids?: string[]; status?: string }) =>
    apiPut<Mission>(API_ENDPOINTS.missions.update(id), data),

  assignAgents: (missionId: string, agents: Array<{
    agent_id: string;
    agent_profile_id: string;
    assigned_zones?: string[];
    target_inspections?: number;
  }>) =>
    apiPost<MissionAgent[]>(API_ENDPOINTS.missions.assignAgents(missionId), { agents }),

  removeAgent: (missionId: string, agentId: string) =>
    apiDelete(API_ENDPOINTS.missions.removeAgent(missionId, agentId)),

  updateAgentStatus: (missionId: string, agentId: string, status: string, reason?: string) =>
    apiPut(API_ENDPOINTS.missions.agentStatus(missionId, agentId), { status, reason }),

  autoAssign: (missionId: string, targetTotal?: number) =>
    apiPost<AutoAssignResponse>(API_ENDPOINTS.missions.autoAssign(missionId), {}, {
      params: targetTotal ? { target_total: targetTotal } : undefined,
    } as Record<string, unknown>),
};
