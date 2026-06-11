/**
 * Service Requests Hooks Exports
 *
 * Includes:
 * - useServiceRequests: Main hook for service request state management
 * - React Query hooks for cached workflow/request data
 *
 * @module service-requests/hooks
 * @date 2026-01-25
 */

// Main service request hook (stateful)
export { useServiceRequests } from './useServiceRequests'
export type { UseServiceRequestsReturn } from './useServiceRequests'

// React Query hooks for cached data fetching
export {
  useWorkflows,
  useWorkflow,
  useWorkflowSteps,
  useMyServiceRequests,
  useServiceRequest,
  usePrefetchWorkflows,
  useInvalidateWorkflowCache,
  useDetailView,
  workflowQueryKeys,
  serviceRequestQueryKeys,
} from './useWorkflowQueries'

// Dynamic Form Config hooks
export {
  useFormConfig,
  useInvalidateFormConfig,
  usePrefetchFormConfig,
  formConfigQueryKeys,
  // Session-based form config hooks (cache-first wizard)
  useSessionFormConfig,
  usePrefetchSessionFormConfig,
  useInvalidateSessionFormConfig,
  sessionFormConfigQueryKeys,
} from './useFormConfig'

// Cache-First Wizard Session hook
export { useWizardSession } from './useWizardSession'
export type { UseWizardSessionReturn } from './useWizardSession'
