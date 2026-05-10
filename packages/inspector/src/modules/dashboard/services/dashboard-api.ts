/**
 * Dashboard API - Facil Inspeccion
 */

import { apiGet } from '@core/api/client';
import { API_ENDPOINTS } from '@core/api/endpoints';
import type {
  InspectionStats,
  InspectionListResponse,
  SupervisorDashboard,
  LiveStatusResponse,
} from '@modules/inspections/types/inspection.types';

export const dashboardApi = {
  /** Agent stats for a date range */
  getStats: (params?: { date_from?: string; date_to?: string }) =>
    apiGet<InspectionStats>(API_ENDPOINTS.inspections.stats, params as Record<string, unknown>),

  /** Recent inspections (page 1, 5 items) */
  getRecentInspections: () =>
    apiGet<InspectionListResponse>(API_ENDPOINTS.inspections.list, {
      page: 1,
      page_size: 5,
      sort_by: 'created_at',
      sort_dir: 'desc',
    }),

  /** Supervisor dashboard (stats + seals + alerts) */
  getSupervisorDashboard: () =>
    apiGet<SupervisorDashboard>(API_ENDPOINTS.supervisor.dashboard),

  /** Real-time agent status (cached 30s backend) */
  getLiveStatus: () =>
    apiGet<LiveStatusResponse>(API_ENDPOINTS.supervisor.liveStatus),
};
