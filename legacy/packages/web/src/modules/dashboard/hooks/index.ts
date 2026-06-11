/**
 * Dashboard Hooks Exports
 *
 * Includes:
 * - Legacy hook: useDashboardData (stateful)
 * - React Query hooks with caching (recommended)
 *
 * @module dashboard/hooks
 * @date 2026-01-25
 */

// Legacy hook (for backwards compatibility)
export { useDashboardData } from './useDashboardData';
export type { DashboardStats, DashboardData } from './useDashboardData';

// React Query hooks with caching (recommended)
export {
  useDashboardDataQuery,
  useRecentDeclarations,
  useRecentPayments,
  usePrefetchDashboard,
  useInvalidateDashboardCache,
  dashboardQueryKeys,
} from './useDashboardQueries';
export type { DashboardStats as DashboardStatsQuery } from './useDashboardQueries';
