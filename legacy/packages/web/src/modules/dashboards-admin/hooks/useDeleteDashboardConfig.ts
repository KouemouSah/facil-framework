/**
 * useDeleteDashboardConfig — DELETE /dashboards/admin/configs/{id} (mig 323).
 *
 * Soft-delete: backend sets is_active=false and preserves the audit trail.
 * Re-enable by editing via PUT with is_active=true.
 */

import { useMutation, useQueryClient } from '@tanstack/react-query'

import { dashboardsAdminApi } from '../services/api'
import type { DashboardConfigDTO } from '../types'

export function useDeleteDashboardConfig() {
  const queryClient = useQueryClient()

  return useMutation<DashboardConfigDTO, Error, string>({
    mutationFn: (dashboardId) => dashboardsAdminApi.softDeleteAdminConfig(dashboardId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['dashboards-admin'] })
    },
  })
}
