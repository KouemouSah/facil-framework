/**
 * Dashboards admin API service.
 *
 * Aligned with packages/backend/app/modules/dashboards/api/dashboards_routes.py.
 *
 * Public:
 *   GET    /dashboards/reports-config         (dashboards.view_business)
 *
 * Admin (requires `dashboards.manage`):
 *   GET    /dashboards/admin/configs
 *   POST   /dashboards/admin/configs
 *   PUT    /dashboards/admin/configs/{id}
 *   PATCH  /dashboards/admin/configs/{id}/metadata
 *   DELETE /dashboards/admin/configs/{id}
 *   GET    /dashboards/admin/grafana/discover
 *   POST   /dashboards/admin/grafana/import
 */

import { fetchClient } from '@/core/api'
import type {
  DashboardConfigCreateRequest,
  DashboardConfigDTO,
  DashboardConfigUpdateRequest,
  DashboardConfigsListResponse,
  DashboardMetadataPatchRequest,
  DashboardReportsConfigResponse,
  GrafanaDiscoverResponse,
  GrafanaImportRequest,
  GrafanaImportResponse,
} from '../types'

export const dashboardsAdminApi = {
  getReportsConfig: async (): Promise<DashboardReportsConfigResponse> => {
    return fetchClient.get<DashboardReportsConfigResponse>('/dashboards/reports-config')
  },

  listAdminConfigs: async (): Promise<DashboardConfigsListResponse> => {
    return fetchClient.get<DashboardConfigsListResponse>('/dashboards/admin/configs')
  },

  /** POST — create a new dashboard from scratch (mig 323). 409 on conflict. */
  createAdminConfig: async (
    body: DashboardConfigCreateRequest,
  ): Promise<DashboardConfigDTO> => {
    return fetchClient.post<DashboardConfigDTO>('/dashboards/admin/configs', body)
  },

  /**
   * PUT — update provider/UID/active state. Backend invalidates the
   * /reports-config cache on success.
   *
   * Errors: 403 / 404 / 422 / 429.
   */
  updateAdminConfig: async (
    dashboardId: string,
    body: DashboardConfigUpdateRequest,
  ): Promise<DashboardConfigDTO> => {
    return fetchClient.put<DashboardConfigDTO>(
      `/dashboards/admin/configs/${dashboardId}`,
      body,
    )
  },

  /** PATCH — partial update of i18n + presentation metadata (mig 323). */
  patchAdminConfigMetadata: async (
    dashboardId: string,
    body: DashboardMetadataPatchRequest,
  ): Promise<DashboardConfigDTO> => {
    return fetchClient.patch<DashboardConfigDTO>(
      `/dashboards/admin/configs/${dashboardId}/metadata`,
      body,
    )
  },

  /** DELETE — soft-delete (sets is_active=false, preserves audit trail). */
  softDeleteAdminConfig: async (dashboardId: string): Promise<DashboardConfigDTO> => {
    return fetchClient.delete<DashboardConfigDTO>(
      `/dashboards/admin/configs/${dashboardId}`,
    )
  },

  /** GET — list Grafana workspace dashboards via the Grafana API (mig 323). */
  discoverGrafana: async (): Promise<GrafanaDiscoverResponse> => {
    return fetchClient.get<GrafanaDiscoverResponse>('/dashboards/admin/grafana/discover')
  },

  /** POST — bulk-import selected Grafana dashboards (mig 323). */
  importGrafana: async (body: GrafanaImportRequest): Promise<GrafanaImportResponse> => {
    return fetchClient.post<GrafanaImportResponse>(
      '/dashboards/admin/grafana/import',
      body,
    )
  },
}
