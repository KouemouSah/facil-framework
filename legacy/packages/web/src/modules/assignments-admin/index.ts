/**
 * Assignments Admin Module
 * Assignment management for administrators
 *
 * @module assignments-admin
 * @date 2026-01-20
 *
 * BACKEND ALIGNMENT:
 * Routes: /api/v1/assignments (from app/modules/assignment/api/assignment_routes.py)
 * Models: app/modules/assignment/models/assignment_history.py
 * Database: Migration 053 (assignments table), Migration 054 (agent_profile_id)
 */

// Components
export {
  AssignmentCard,
  AssignmentList,
  AssignmentForm,
  AssignmentFilters as AssignmentFiltersComponent,
  AssignmentStatusBadge,
} from './components'

// Hooks
export * from './hooks'

// Types - Re-export with explicit names to avoid conflicts
export type {
  // Enums (aligned with database)
  AssignmentStatus,
  AssignmentMethod,
  ItemType,
  ReassignmentReason,
  PriorityLevel,
  LegacyPriority,

  // Main model
  Assignment,

  // Request types
  ManualAssignmentRequest,
  AutoAssignmentRequest,
  CompleteAssignmentRequest,
  ReassignmentRequest,
  UpdatePriorityRequest,
  ExtendDeadlineRequest,
  StartAssignmentRequest,
  BulkReassignRequest,

  // Response types
  PaginatedAssignmentsResponse,
  AssignmentStats,
  BulkReassignResult,

  // Filter types
  AssignmentFilters,

  // Legacy types (deprecated - for backward compatibility)
  DeclarationType,
  AssignmentPriority,
  LegacyManualAssignmentRequest,
  LegacyReassignmentRequest,
  LegacyAssignmentFilters,
} from './types'

// Helper functions for legacy conversion
export {
  convertLegacyManualRequest,
  convertLegacyFilters,
} from './types'

// Services
export { assignmentsApi } from './services/api'
export { default as assignmentsAdminApi } from './services/api'
