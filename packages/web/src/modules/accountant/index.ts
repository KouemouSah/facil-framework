/**
 * Accountant Module
 * Multi-client dashboard for accountants managing multiple companies
 *
 * @module accountant
 * @author Claude Code
 * @date 2025-12-03
 *
 * FEATURES:
 * - Client list with quick stats (declarations, deadlines, financials)
 * - Deadline calendar (month/week/list views)
 * - Client switcher for quick navigation
 * - Task queue with filtering and prioritization
 * - React Query hooks for efficient data fetching
 *
 * USAGE:
 * ```tsx
 * import {
 *   ClientList,
 *   DeadlineCalendar,
 *   ClientSwitcher,
 *   TaskQueue,
 *   useAccountantClients,
 *   usePendingTasks,
 * } from '@/modules/accountant'
 * ```
 */

// Components
export * from './components'

// Hooks
export * from './hooks'

// Types
export * from './types'

// Services (not typically exported, but available if needed)
export { default as accountantApi } from './services/api'
