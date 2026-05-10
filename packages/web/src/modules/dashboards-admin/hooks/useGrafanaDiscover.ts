/**
 * useGrafanaDiscover — GET /dashboards/admin/grafana/discover.
 *
 * Lists Grafana workspace dashboards via the backend (which calls Grafana
 * /api/search). Each entry is tagged `already_imported=true` when its UID
 * is already in dashboard_registrations.
 *
 * `enabled=false` by default — the modal that uses this hook flips it to
 * true on open so the discovery only fires when actually needed.
 */

import { useQuery } from '@tanstack/react-query'
import { dashboardsAdminApi } from '../services/api'

export function useGrafanaDiscover(enabled = false) {
  return useQuery({
    queryKey: ['dashboards-admin', 'grafana-discover'],
    queryFn: dashboardsAdminApi.discoverGrafana,
    enabled,
    staleTime: 60 * 1000,
    gcTime: 5 * 60 * 1000,
  })
}
