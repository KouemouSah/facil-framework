import apiClient from '@/core/api/client'
import type {
  Inspection,
  InspectionListResponse,
  InspectionStats,
  SupervisorDashboard,
  ReconciliationResponse,
  LicenseVerification,
  Mission,
  MissionListResponse,
  ZoneSuggestion,
  AgentAvailability,
  AgentPerformanceResponse,
  AgentDetailResponse,
  ZoneAnalyticsResponse,
  TrendResponse,
  CompareResponse,
  PriorityZonesResponse,
  FilterPreset,
  FilterPresetListResponse,
  LiveStatusResponse,
} from '../types'

export const inspectionApi = {
  // ============================================================
  // CRUD
  // ============================================================

  create: (data: { license_id: string; company_id: string; notes?: string }) =>
    apiClient.post<Inspection>('/inspections/', data).then(r => r.data),

  get: (id: string) =>
    apiClient.get<Inspection>(`/inspections/${id}`).then(r => r.data),

  update: (id: string, data: {
    activity_conforme?: boolean
    activity_declared?: string
    activity_observed?: string
    photos?: string[]
    gps_latitude?: number
    gps_longitude?: number
    gps_accuracy?: number
    notes?: string
    agent_signature?: string
  }) =>
    apiClient.put<Inspection>(`/inspections/${id}`, data).then(r => r.data),

  list: (params?: {
    inspection_date?: string
    status?: string
    agent_id?: string
    zone_code?: string
    result?: string
    date_from?: string
    date_to?: string
    search?: string
    has_payment?: boolean
    has_med?: boolean
    has_seal?: boolean
    sort_by?: string
    sort_dir?: 'asc' | 'desc'
    page?: number
    page_size?: number
  }) => {
    const sp = new URLSearchParams()
    if (params) {
      Object.entries(params).forEach(([k, v]) => {
        if (v !== undefined && v !== null && v !== '') sp.set(k, String(v))
      })
    }
    const q = sp.toString()
    return apiClient
      .get<InspectionListResponse>(`/inspections/${q ? `?${q}` : ''}`)
      .then(r => r.data)
  },

  // ============================================================
  // ACTIONS
  // ============================================================

  complete: (id: string, data?: { notes?: string }) =>
    apiClient.post<Inspection>(`/inspections/${id}/complete`, data || {}).then(r => r.data),

  miseEnDemeure: (id: string, data: {
    obligation_ids: string[]
    deadline_hours?: number
    notes?: string
  }) =>
    apiClient.post<Inspection>(`/inspections/${id}/mise-en-demeure`, data).then(r => r.data),

  proposeSeal: (id: string, data: {
    reason: string
    notes?: string
    photo?: string
  }) =>
    apiClient.post<Inspection>(`/inspections/${id}/seal`, data).then(r => r.data),

  approveSeal: (id: string, data: { approved: boolean; notes?: string }) =>
    apiClient.post<Inspection>(`/inspections/${id}/seal/approve`, data).then(r => r.data),

  collectPayment: (id: string, data: {
    obligation_ids: string[]
    method: 'cash' | 'mobile_money'
    amount: number
    phone_number?: string
    notes?: string
  }) =>
    apiClient.post(`/inspections/${id}/collect`, data).then(r => r.data),

  // ============================================================
  // STATS & DASHBOARD
  // ============================================================

  getStats: (params?: { date_from?: string; date_to?: string }) => {
    const sp = new URLSearchParams()
    if (params?.date_from) sp.set('date_from', params.date_from)
    if (params?.date_to) sp.set('date_to', params.date_to)
    const q = sp.toString()
    return apiClient
      .get<InspectionStats>(`/inspections/stats${q ? `?${q}` : ''}`)
      .then(r => r.data)
  },

  getSupervisorDashboard: (entityLocationId?: string) =>
    apiClient.get<SupervisorDashboard>('/inspections/supervisor/dashboard', {
      params: entityLocationId ? { entity_location_id: entityLocationId } : undefined,
    }).then(r => r.data),

  getLiveStatus: () =>
    apiClient.get<LiveStatusResponse>('/inspections/supervisor/live-status').then(r => r.data),

  getReconciliation: (targetDate?: string) => {
    const sp = new URLSearchParams()
    if (targetDate) sp.set('target_date', targetDate)
    const q = sp.toString()
    return apiClient
      .get<ReconciliationResponse>(`/inspections/reconcile${q ? `?${q}` : ''}`)
      .then(r => r.data)
  },

  // ============================================================
  // VERIFY LICENSE
  // ============================================================

  verifyLicense: (params: { license_id?: string; nif?: string }) => {
    const sp = new URLSearchParams()
    if (params.license_id) sp.set('license_id', params.license_id)
    if (params.nif) sp.set('nif', params.nif)
    return apiClient
      .get<LicenseVerification>(`/inspections/verify?${sp.toString()}`)
      .then(r => r.data)
  },

  // ============================================================
  // SUPERVISOR RECONCILIATION (double validation)
  // ============================================================

  getSupervisorReconciliation: () =>
    apiClient
      .get<{
        items: Array<{
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
        }>
        total_amount: number
        total_count: number
        entity_code: string
      }>('/inspections/reconcile/supervisor')
      .then(r => r.data),

  validateFieldReconciliation: (paymentId: string) =>
    apiClient
      .post<{ payment_id: string; status: string; routed_obligations: number }>(
        `/inspections/reconcile/supervisor/${paymentId}/validate`
      )
      .then(r => r.data),

  // ============================================================
  // PHOTO UPLOAD (Firebase Storage)
  // ============================================================

  uploadPhoto: (inspectionId: string, file: File) => {
    const formData = new FormData()
    formData.append('file', file)
    return apiClient
      .post<{ url: string; file_path: string; file_size: number; photo_index: number }>(
        `/inspections/${inspectionId}/photos`,
        formData,
        { headers: { 'Content-Type': 'multipart/form-data' } },
      )
      .then(r => r.data)
  },

  deletePhoto: (inspectionId: string, photoIndex: number) =>
    apiClient.delete(`/inspections/${inspectionId}/photos/${photoIndex}`).then(r => r.data),

  // ============================================================
  // PDF DOWNLOADS
  // ============================================================

  downloadReport: (id: string, language = 'es') =>
    apiClient
      .get(`/inspections/${id}/download-report?language=${language}`, { responseType: 'blob' })
      .then(r => r.data as Blob),

  downloadMed: (id: string, language = 'es') =>
    apiClient
      .get(`/inspections/${id}/download-med?language=${language}`, { responseType: 'blob' })
      .then(r => r.data as Blob),

  downloadSeal: (id: string, language = 'es') =>
    apiClient
      .get(`/inspections/${id}/download-seal?language=${language}`, { responseType: 'blob' })
      .then(r => r.data as Blob),

  // ============================================================
  // MISSIONS
  // ============================================================

  createMission: (data: { mission_date: string; entity_location_id?: string; title?: string; notes?: string; zone_ids?: string[] }) =>
    apiClient.post<Mission>('/inspections/missions/', data).then(r => r.data),

  listMissions: (params?: { date_from?: string; date_to?: string; status?: string; page?: number; page_size?: number; entity_location_id?: string }) => {
    const sp = new URLSearchParams()
    if (params?.date_from) sp.set('date_from', params.date_from)
    if (params?.date_to) sp.set('date_to', params.date_to)
    if (params?.status) sp.set('status', params.status)
    if (params?.page) sp.set('page', String(params.page))
    if (params?.page_size) sp.set('page_size', String(params.page_size))
    if (params?.entity_location_id) sp.set('entity_location_id', params.entity_location_id)
    const q = sp.toString()
    return apiClient.get<MissionListResponse>(`/inspections/missions${q ? `?${q}` : ''}`).then(r => r.data)
  },

  getMission: (id: string) =>
    apiClient.get<Mission>(`/inspections/missions/${id}`).then(r => r.data),

  updateMission: (id: string, data: { title?: string; notes?: string; zone_ids?: string[]; status?: string }) =>
    apiClient.put<Mission>(`/inspections/missions/${id}`, data).then(r => r.data),

  assignAgents: (missionId: string, agents: Array<{ agent_id: string; agent_profile_id: string; assigned_zones?: string[]; target_inspections?: number; notes?: string }>) =>
    apiClient.post(`/inspections/missions/${missionId}/agents`, { agents }).then(r => r.data),

  removeAgent: (missionId: string, agentId: string) =>
    apiClient.delete(`/inspections/missions/${missionId}/agents/${agentId}`),

  completeMission: (id: string, notes?: string) =>
    apiClient.post(`/inspections/missions/${id}/complete`, { notes }).then(r => r.data),

  suggestZones: () =>
    apiClient.get<ZoneSuggestion[]>('/inspections/missions/suggest-zones').then(r => r.data),

  getAgentsAvailability: (missionDate: string, entityLocationId?: string) => {
    const sp = new URLSearchParams({ mission_date: missionDate })
    if (entityLocationId) sp.set('entity_location_id', entityLocationId)
    return apiClient.get<AgentAvailability[]>(`/inspections/missions/agents/availability?${sp}`).then(r => r.data)
  },

  autoAssignMission: (missionId: string, targetTotal = 50) =>
    apiClient.post<{ mission_id: string; target_total: number; agents_proposed: number; proposals: Array<{ agent_id: string; agent_profile_id: string; target_inspections: number }> }>(
      `/inspections/missions/${missionId}/auto-assign?target_total=${targetTotal}`
    ).then(r => r.data),

  // ============================================================
  // TEMPLATES
  // ============================================================

  listTemplates: () =>
    apiClient.get<import('../types').MissionTemplate[]>('/inspections/missions/templates').then(r => r.data),

  createTemplate: (data: {
    name: string; recurrence: string; day_of_week?: number; day_of_month?: number;
    zone_ids?: string[]; default_agent_ids?: string[]; target_inspections_per_agent?: number; notes?: string;
  }) =>
    apiClient.post<import('../types').MissionTemplate>('/inspections/missions/templates', data).then(r => r.data),

  updateTemplate: (id: string, data: Record<string, unknown>) =>
    apiClient.put<import('../types').MissionTemplate>(`/inspections/missions/templates/${id}`, data).then(r => r.data),

  deleteTemplate: (id: string) =>
    apiClient.delete(`/inspections/missions/templates/${id}`),

  runTemplate: (id: string, missionDate?: string) =>
    apiClient.post<{ mission_id: string; mission_date: string; agents_assigned: number; template_name: string }>(
      `/inspections/missions/templates/${id}/run`,
      missionDate ? { mission_date: missionDate } : {},
    ).then(r => r.data),

  // ============================================================
  // ANALYTICS
  // ============================================================

  getAgentPerformance: (params?: { date_from?: string; date_to?: string; page?: number; page_size?: number }) => {
    const sp = new URLSearchParams()
    if (params?.date_from) sp.set('date_from', params.date_from)
    if (params?.date_to) sp.set('date_to', params.date_to)
    if (params?.page) sp.set('page', String(params.page))
    if (params?.page_size) sp.set('page_size', String(params.page_size))
    const q = sp.toString()
    return apiClient.get<AgentPerformanceResponse>(`/inspections/analytics/agents${q ? `?${q}` : ''}`).then(r => r.data)
  },

  getAgentDetail: (agentId: string, params?: { date_from?: string; date_to?: string }) => {
    const sp = new URLSearchParams()
    if (params?.date_from) sp.set('date_from', params.date_from)
    if (params?.date_to) sp.set('date_to', params.date_to)
    const q = sp.toString()
    return apiClient.get<AgentDetailResponse>(`/inspections/analytics/agents/${agentId}${q ? `?${q}` : ''}`).then(r => r.data)
  },

  getZoneAnalytics: (params?: { date_from?: string; date_to?: string }) => {
    const sp = new URLSearchParams()
    if (params?.date_from) sp.set('date_from', params.date_from)
    if (params?.date_to) sp.set('date_to', params.date_to)
    const q = sp.toString()
    return apiClient.get<ZoneAnalyticsResponse>(`/inspections/analytics/zones${q ? `?${q}` : ''}`).then(r => r.data)
  },

  getTrends: (params?: { date_from?: string; date_to?: string; granularity?: string }) => {
    const sp = new URLSearchParams()
    if (params?.date_from) sp.set('date_from', params.date_from)
    if (params?.date_to) sp.set('date_to', params.date_to)
    if (params?.granularity) sp.set('granularity', params.granularity)
    const q = sp.toString()
    return apiClient.get<TrendResponse>(`/inspections/analytics/trends${q ? `?${q}` : ''}`).then(r => r.data)
  },

  getComparison: (params: { compare_type: string; id1: string; id2: string; date_from?: string; date_to?: string }) => {
    const sp = new URLSearchParams()
    sp.set('compare_type', params.compare_type)
    sp.set('id1', params.id1)
    sp.set('id2', params.id2)
    if (params.date_from) sp.set('date_from', params.date_from)
    if (params.date_to) sp.set('date_to', params.date_to)
    return apiClient.get<CompareResponse>(`/inspections/analytics/compare?${sp.toString()}`).then(r => r.data)
  },

  getPriorityZones: (limit = 20) =>
    apiClient.get<PriorityZonesResponse>(`/inspections/analytics/priority-zones?limit=${limit}`).then(r => r.data),

  // ============================================================
  // FILTER PRESETS
  // ============================================================

  createPreset: (data: { preset_name: string; table_key: string; filters: Record<string, unknown>; column_visibility?: Record<string, boolean>; sort_config?: { column: string; direction: string }; is_default?: boolean }) =>
    apiClient.post<FilterPreset>('/inspections/filter-presets', data).then(r => r.data),

  listPresets: (tableKey?: string) => {
    const sp = new URLSearchParams()
    if (tableKey) sp.set('table_key', tableKey)
    const q = sp.toString()
    return apiClient.get<FilterPresetListResponse>(`/inspections/filter-presets${q ? `?${q}` : ''}`).then(r => r.data)
  },

  updatePreset: (id: string, data: { preset_name?: string; filters?: Record<string, unknown>; column_visibility?: Record<string, boolean>; sort_config?: { column: string; direction: string }; is_default?: boolean }) =>
    apiClient.put<FilterPreset>(`/inspections/filter-presets/${id}`, data).then(r => r.data),

  deletePreset: (id: string) =>
    apiClient.delete(`/inspections/filter-presets/${id}`),

  // ============================================================
  // EXPORT (CSV + PDF)
  // ============================================================

  exportCSV: (filters?: Record<string, string | boolean>) => {
    const sp = new URLSearchParams()
    if (filters) {
      Object.entries(filters).forEach(([k, v]) => {
        if (v !== undefined && v !== null && v !== '') sp.set(k, String(v))
      })
    }
    const q = sp.toString()
    return apiClient
      .get(`/inspections/export/csv${q ? `?${q}` : ''}`, { responseType: 'blob' })
      .then(r => r.data as Blob)
  },

  exportAgentsCSV: (params?: { date_from?: string; date_to?: string }) => {
    const sp = new URLSearchParams()
    if (params?.date_from) sp.set('date_from', params.date_from)
    if (params?.date_to) sp.set('date_to', params.date_to)
    const q = sp.toString()
    return apiClient
      .get(`/inspections/export/agents-csv${q ? `?${q}` : ''}`, { responseType: 'blob' })
      .then(r => r.data as Blob)
  },

  exportPDF: (filters?: Record<string, string>) => {
    const sp = new URLSearchParams()
    if (filters) {
      Object.entries(filters).forEach(([k, v]) => {
        if (v !== undefined && v !== null && v !== '') sp.set(k, String(v))
      })
    }
    const q = sp.toString()
    return apiClient
      .get(`/inspections/export/pdf${q ? `?${q}` : ''}`, { responseType: 'blob' })
      .then(r => r.data as Blob)
  },

  // --- Mission Analytics ---
  getMissionAnalytics: (params?: { date_from?: string; date_to?: string; entity_location_id?: string }) =>
    apiClient.get<import('../types').MissionAnalyticsResponse>('/inspections/analytics/missions', {
      params: params ?? undefined,
    }).then(r => r.data),
}
