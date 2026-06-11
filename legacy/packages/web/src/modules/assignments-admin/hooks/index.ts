/**
 * Assignments Admin Hooks
 * React Query hooks for assignment management
 *
 * @module assignments-admin/hooks
 * @author Claude Code
 * @date 2025-11-25
 *
 * BACKEND ALIGNMENT:
 * Routes: /api/v1/assignments
 */

// Query hooks
export {
  useAssignments,
  useAssignment,
  assignmentsKeys,
} from './useAssignments'

// Creation hooks
export {
  useCreateManualAssignment,
  useCreateAutoAssignment,
} from './useAssignments'

// Lifecycle hooks
export {
  useStartAssignment,
  useCompleteAssignment,
  useReassignAssignment,
  useCancelAssignment,
} from './useAssignments'

// Priority, Deadline & Notes hooks
export {
  useUpdateAssignmentPriority,
  useExtendAssignmentDeadline,
  useUpdateAssignmentNotes,
} from './useAssignments'

// Bulk operations hooks
export {
  useBulkReassignAssignments,
} from './useAssignments'

// Statistics hooks
export {
  useAssignmentStats,
  usePaginatedAssignments,
} from './useAssignments'

// Legacy exports (deprecated - for backward compatibility)
export {
  useCreateAssignment,
  useUpdateAssignment,
  useDeleteAssignment,
  useUpdateAssignmentStatus,
} from './useAssignments'
