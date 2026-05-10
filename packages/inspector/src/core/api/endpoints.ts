/**
 * API Endpoint Constants - Facil Inspeccion
 *
 * Inspection-specific + shared auth endpoints.
 * Keep in sync with packages/backend/app/modules/inspections/api/inspection_routes.py
 */

export const API_ENDPOINTS = {
  auth: {
    login: '/auth/login',
    register: '/auth/register',
    refresh: '/auth/refresh',
    logout: '/auth/logout',
    profile: '/auth/profile',
    sessions: '/auth/sessions',
    twoFactorEnable: '/auth/2fa/enable',
    twoFactorVerify: '/auth/2fa/verify',
    twoFactorDisable: '/auth/2fa/disable',
    twoFactorStatus: '/auth/2fa/status',
    login2faVerify: '/auth/login/2fa-verify',
  },

  users: {
    profile: '/users/profile',
    updateProfile: '/users/profile',
    changePassword: '/users/profile/change-password',
    uploadAvatar: '/users/profile/avatar',
    deviceToken: '/users/profile/device-token',
  },

  permissions: {
    myPermissions: '/permissions/my-permissions',
  },

  agents: {
    profile: '/profiles/me',
  },

  inspections: {
    list: '/inspections/',
    create: '/inspections/',
    detail: (id: string) => `/inspections/${id}` as const,
    update: (id: string) => `/inspections/${id}` as const,
    complete: (id: string) => `/inspections/${id}/complete` as const,
    miseEnDemeure: (id: string) => `/inspections/${id}/mise-en-demeure` as const,
    seal: (id: string) => `/inspections/${id}/seal` as const,
    sealApprove: (id: string) => `/inspections/${id}/seal/approve` as const,
    collect: (id: string) => `/inspections/${id}/collect` as const,
    photos: (id: string) => `/inspections/${id}/photos` as const,
    photoDelete: (id: string, index: number) => `/inspections/${id}/photos/${index}` as const,
    downloadReport: (id: string) => `/inspections/${id}/download-report` as const,
    downloadMed: (id: string) => `/inspections/${id}/download-med` as const,
    downloadSeal: (id: string) => `/inspections/${id}/download-seal` as const,
    stats: '/inspections/stats',
    verify: '/inspections/verify',
    reconcile: '/inspections/reconcile',
  },

  missions: {
    list: '/inspections/missions/',
    create: '/inspections/missions/',
    suggestZones: '/inspections/missions/suggest-zones',
    agentAvailability: '/inspections/missions/agents/availability',
    detail: (id: string) => `/inspections/missions/${id}` as const,
    update: (id: string) => `/inspections/missions/${id}` as const,
    assignAgents: (id: string) => `/inspections/missions/${id}/agents` as const,
    removeAgent: (id: string, agentId: string) =>
      `/inspections/missions/${id}/agents/${agentId}` as const,
    complete: (id: string) => `/inspections/missions/${id}/complete` as const,
    autoAssign: (id: string) => `/inspections/missions/${id}/auto-assign` as const,
    agentStatus: (id: string, agentId: string) =>
      `/inspections/missions/${id}/agents/${agentId}/status` as const,
    report: (id: string) => `/inspections/missions/${id}/report` as const,
  },

  analytics: {
    agents: '/inspections/analytics/agents',
    agentDetail: (agentId: string) => `/inspections/analytics/agents/${agentId}` as const,
    zones: '/inspections/analytics/zones',
    trends: '/inspections/analytics/trends',
    compare: '/inspections/analytics/compare',
    priorityZones: '/inspections/analytics/priority-zones',
  },

  filterPresets: {
    list: '/inspections/filter-presets/',
    create: '/inspections/filter-presets/',
    update: (id: string) => `/inspections/filter-presets/${id}` as const,
    delete: (id: string) => `/inspections/filter-presets/${id}` as const,
  },

  export: {
    csv: '/inspections/export/csv',
    agentsCsv: '/inspections/export/agents-csv',
    pdf: '/inspections/export/pdf',
  },

  supervisor: {
    dashboard: '/inspections/supervisor/dashboard',
    liveStatus: '/inspections/supervisor/live-status',
    reconcileList: '/inspections/reconcile/supervisor',
    reconcileValidate: (paymentId: string) =>
      `/inspections/reconcile/supervisor/${paymentId}/validate` as const,
    autoApproveSeals: '/inspections/cron/auto-approve-seals',
  },

  translations: {
    frontend: (lang: string) => `/frontend-translations/${lang}` as const,
    enums: '/translations/enums',
  },
} as const;

export type EndpointUrl<T> = T extends (...args: never[]) => infer R ? R : T;
