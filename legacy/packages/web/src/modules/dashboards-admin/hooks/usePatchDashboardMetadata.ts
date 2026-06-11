/**
 * usePatchDashboardMetadata — PATCH /dashboards/admin/configs/{id}/metadata.
 *
 * Partial update of i18n + presentation fields (title_*, description_*,
 * rls_mode, embed_mode, panel_id, display_order, default_time_range,
 * icon_name, category). NULL fields are left unchanged.
 */

import { useMutation, useQueryClient } from '@tanstack/react-query'

import { dashboardsAdminApi } from '../services/api'
import type {
  DashboardConfigDTO,
  DashboardMetadataPatchRequest,
} from '../types'

interface MutationVariables {
  dashboardId: string
  body: DashboardMetadataPatchRequest
}

export function usePatchDashboardMetadata() {
  const queryClient = useQueryClient()

  return useMutation<DashboardConfigDTO, Error, MutationVariables>({
    mutationFn: ({ dashboardId, body }) =>
      dashboardsAdminApi.patchAdminConfigMetadata(dashboardId, body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['dashboards-admin'] })
    },
  })
}
