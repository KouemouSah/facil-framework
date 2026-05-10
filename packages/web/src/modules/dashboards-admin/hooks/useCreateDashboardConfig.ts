/**
 * useCreateDashboardConfig — POST /dashboards/admin/configs (mig 323).
 *
 * On success invalidates the entire dashboards-admin query family so both
 * the embed listing (/reports-config) and the admin listing refetch.
 */

import { useMutation, useQueryClient } from '@tanstack/react-query'

import { dashboardsAdminApi } from '../services/api'
import type {
  DashboardConfigCreateRequest,
  DashboardConfigDTO,
} from '../types'

export function useCreateDashboardConfig() {
  const queryClient = useQueryClient()

  return useMutation<DashboardConfigDTO, Error, DashboardConfigCreateRequest>({
    mutationFn: (body) => dashboardsAdminApi.createAdminConfig(body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['dashboards-admin'] })
    },
  })
}
