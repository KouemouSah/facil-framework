/**
 * useReportsConfig — fetches the Looker reports the caller can embed.
 *
 * Cached 5 min on the client (matches the connector's user-scoped cache
 * tier; reports config rarely changes). React Query handles refetching
 * on window focus.
 */

import { useQuery } from '@tanstack/react-query'
import { dashboardsAdminApi } from '../services/api'

export function useReportsConfig() {
  return useQuery({
    queryKey: ['dashboards-admin', 'reports-config'],
    queryFn: dashboardsAdminApi.getReportsConfig,
    staleTime: 5 * 60 * 1000,
    gcTime: 10 * 60 * 1000,
  })
}
