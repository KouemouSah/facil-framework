/**
 * useGrafanaImport — POST /dashboards/admin/grafana/import.
 *
 * Bulk-imports a list of Grafana dashboards into dashboard_registrations.
 * Per-item transaction isolation on the backend: one bad item does NOT
 * roll back the others. The response splits results into imported / skipped
 * / errors so the UI can surface partial success.
 */

import { useMutation, useQueryClient } from '@tanstack/react-query'

import { dashboardsAdminApi } from '../services/api'
import type { GrafanaImportRequest, GrafanaImportResponse } from '../types'

export function useGrafanaImport() {
  const queryClient = useQueryClient()

  return useMutation<GrafanaImportResponse, Error, GrafanaImportRequest>({
    mutationFn: (body) => dashboardsAdminApi.importGrafana(body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['dashboards-admin'] })
    },
  })
}
