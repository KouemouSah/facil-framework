/**
 * useDashboardConfigs — fetches the admin view of dashboard configs
 * (with provenance: db / env_fallback / unset + audit fields).
 *
 * Used by the /admin/dashboards/config page. Low traffic (3 admins max
 * simultaneously) so 1-min staleness is plenty without spamming the BD.
 *
 * Backend endpoint requires `dashboards.manage`; a 403 is surfaced as
 * `error.response.status === 403` to the consumer.
 */

import { useQuery } from '@tanstack/react-query'
import { dashboardsAdminApi } from '../services/api'

export function useDashboardConfigs() {
  return useQuery({
    queryKey: ['dashboards-admin', 'admin-configs'],
    queryFn: dashboardsAdminApi.listAdminConfigs,
    staleTime: 60 * 1000,
    gcTime: 5 * 60 * 1000,
  })
}
