/**
 * useUpdateDashboardConfig — mutation hook for the admin config form.
 *
 * On success invalidates the entire `dashboards-admin` query family so
 * both the embed listing (`reports-config`) and the admin configs list
 * refetch. The backend already invalidates its Redis cache on the same
 * event, so the next refetch sees the freshly-updated row.
 */

import { useMutation, useQueryClient } from '@tanstack/react-query'

import { dashboardsAdminApi } from '../services/api'
import type {
  DashboardConfigDTO,
  DashboardConfigUpdateRequest,
} from '../types'

interface MutationVariables {
  dashboardId: string
  body: DashboardConfigUpdateRequest
}

export function useUpdateDashboardConfig() {
  const queryClient = useQueryClient()

  return useMutation<DashboardConfigDTO, Error, MutationVariables>({
    mutationFn: ({ dashboardId, body }) =>
      dashboardsAdminApi.updateAdminConfig(dashboardId, body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['dashboards-admin'] })
    },
  })
}
