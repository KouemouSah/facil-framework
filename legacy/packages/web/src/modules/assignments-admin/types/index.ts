/**
 * Assignments Admin Types
 * Type definitions for assignment management
 *
 * @module assignments-admin/types
 * @author Claude Code
 * @date 2026-01-20
 *
 * BACKEND ALIGNMENT:
 * Routes: /api/v1/assignments (from app/modules/assignment/api/assignment_routes.py)
 * Models: app/modules/assignment/models/assignment_history.py
 * Database: Migration 053 (assignments table), Migration 054 (agent_profile_id)
 *
 * Assignment states: assigned → in_progress → pending_review → completed/cancelled/reassigned/rejected
 */

// =============================================================================
// ENUMS - Aligned with backend Pydantic models and database enums
// =============================================================================

/**
 * AssignmentStatus - from assignment_status_enum (DATABASE_SCHEMA_REFERENCE.md)
 * DB values: assigned, in_progress, pending_review, completed, reassigned, cancelled, rejected
 */
export type AssignmentStatus =
  | 'assigned'
  | 'in_progress'
  | 'pending_review'
  | 'completed'
  | 'reassigned'
  | 'cancelled'
  | 'rejected'

/**
 * AssignmentMethod - from assignment_method_enum (DATABASE_SCHEMA_REFERENCE.md)
 * DB values: auto, manual, self_assigned, escalated
 */
export type AssignmentMethod = 'auto' | 'manual' | 'self_assigned' | 'escalated'

/**
 * ItemType - polymorphic type for assignable items (Migration 053)
 * DB column: item_type in assignments table
 */
export type ItemType =
  | 'tax_declaration'
  | 'service_request'
  | 'service_payment'
  | 'other'

/**
 * ReassignmentReason - from reassignment_reason_enum (DATABASE_SCHEMA_REFERENCE.md)
 * DB values: workload_imbalance, agent_unavailable, specialization_mismatch,
 *            quality_issue, deadline_missed, agent_request, supervisor_decision, complexity_change
 */
export type ReassignmentReason =
  | 'workload_imbalance'
  | 'agent_unavailable'
  | 'specialization_mismatch'
  | 'quality_issue'
  | 'deadline_missed'
  | 'agent_request'
  | 'supervisor_decision'
  | 'complexity_change'

/**
 * Priority level is an integer 1-10 in the database
 * - 1-3: Low priority
 * - 4-6: Medium/Normal priority
 * - 7-8: High priority
 * - 9-10: Urgent/Critical priority
 */
export type PriorityLevel = number

// Legacy string priority for backward compatibility (converted to int by backend)
export type LegacyPriority = 'low' | 'medium' | 'normal' | 'high' | 'urgent' | 'critical'

// =============================================================================
// ASSIGNMENT MODEL - Aligned with backend AssignmentResponse
// =============================================================================

/**
 * Assignment - Response model aligned with backend AssignmentResponse
 *
 * Key field changes from legacy:
 * - declaration_id → item_id (Migration 053)
 * - declaration_type → item_type (Migration 053)
 * - agent_id → agent_profile_id (Migration 054)
 * - assigned_by → assigned_by_profile_id (Migration 054)
 *
 * DB Schema reference: assignments table (DATABASE_SCHEMA_REFERENCE.md)
 */
export interface Assignment {
  id: string

  // Item reference (Migration 053 - polymorphic)
  // DB: item_id uuid NOT NULL, item_type varchar(50) NOT NULL
  item_id: string
  item_type: ItemType

  // Agent reference (Migration 054 - agent_profile_id)
  // DB: agent_profile_id uuid NOT NULL FK→agent_profiles
  agent_profile_id: string
  agent_name?: string  // Joined from agent_profiles→users (not in assignments table)

  // Supervisor/Assigner reference (Migration 054)
  // DB: assigned_by_profile_id uuid FK→agent_profiles
  assigned_by_profile_id?: string
  assigned_by_name?: string  // Joined from agent_profiles→users (not in assignments table)

  // Status and method
  // DB: status assignment_status_enum, assignment_method assignment_method_enum
  status: AssignmentStatus
  assignment_method: AssignmentMethod

  // Priority (integer 1-10)
  // DB: priority_level integer DEFAULT 5
  priority_level: PriorityLevel

  // Timestamps
  // DB: assigned_at, started_at, completed_at, deadline timestamptz
  assigned_at: string
  started_at?: string
  completed_at?: string
  deadline?: string

  // Performance tracking
  // DB: deadline_met boolean, processing_duration_hours numeric, quality_score numeric
  deadline_met?: boolean
  processing_duration_hours?: number
  quality_score?: number

  // Auto-assignment scoring
  // DB: auto_assignment_score numeric, score_breakdown jsonb, rule_applied_id uuid
  auto_assignment_score?: number
  score_breakdown?: Record<string, unknown>
  rule_applied_id?: string

  // Workflow data
  // DB: notes text, validation_status varchar(20)
  notes?: string
  validation_status?: string

  // Reassignment tracking
  // DB: reassigned_at timestamptz, reassignment_reason enum, reassignment_notes text
  // DB: reassigned_to_profile_id uuid FK→agent_profiles
  reassigned_at?: string
  reassigned_to_profile_id?: string
  reassigned_to_name?: string  // Joined from agent_profiles→users (not in assignments table)
  reassignment_reason?: ReassignmentReason
  reassignment_notes?: string

  // Audit
  // DB: created_at, updated_at timestamptz
  created_at: string
  updated_at: string
}

// =============================================================================
// REQUEST TYPES - Manual Assignment
// =============================================================================

/**
 * ManualAssignmentRequest - Create assignment via supervisor
 * Backend: ManualAssignmentCreate in assignment_routes.py
 */
export interface ManualAssignmentRequest {
  item_id: string
  item_type: ItemType
  agent_profile_id: string
  priority_level?: PriorityLevel | LegacyPriority // Backend accepts both
  notes?: string
  deadline_days?: number
}

// =============================================================================
// REQUEST TYPES - Auto Assignment
// =============================================================================

/**
 * AutoAssignmentRequest - Request auto-assignment by rules
 * Backend: AutoAssignmentRequest in assignment_routes.py
 */
export interface AutoAssignmentRequest {
  item_id: string
  item_type: ItemType
  item_data: Record<string, unknown>
  entity_type?: 'ministry' | 'entity'  // Backend pattern: ^(ministry|entity)$
  entity_id?: string
}

// =============================================================================
// REQUEST TYPES - Assignment Operations
// =============================================================================

/**
 * CompleteAssignmentRequest - Mark assignment as completed
 */
export interface CompleteAssignmentRequest {
  validation_status: 'approved' | 'rejected'
  quality_score?: number
  notes?: string
}

/**
 * ReassignmentRequest - Reassign to another agent
 * Backend: ReassignmentCreate in assignment_routes.py
 */
export interface ReassignmentRequest {
  new_agent_profile_id: string
  reason: ReassignmentReason
  notes?: string
  priority_level?: PriorityLevel | LegacyPriority
}

/**
 * UpdatePriorityRequest - Update assignment priority
 */
export interface UpdatePriorityRequest {
  priority_level: PriorityLevel | LegacyPriority
}

/**
 * ExtendDeadlineRequest - Extend assignment deadline
 */
export interface ExtendDeadlineRequest {
  additional_days: number
  reason?: string
}

/**
 * UpdateNotesRequest - Update assignment notes
 */
export interface UpdateNotesRequest {
  notes: string
}

/**
 * StartAssignmentRequest - Agent starts working on assignment
 */
export interface StartAssignmentRequest {
  notes?: string
}

// =============================================================================
// RESPONSE TYPES
// =============================================================================

export interface PaginatedAssignmentsResponse {
  items: Assignment[]
  total: number
  page: number
  page_size: number
}

export interface AssignmentStats {
  total_assigned: number
  total_completed: number
  total_pending: number
  average_processing_time_hours: number
  on_time_completion_rate: number
}

// =============================================================================
// FILTER TYPES
// =============================================================================

export interface AssignmentFilters {
  agent_profile_id?: string
  assigned_by_profile_id?: string  // DB column name (was supervisor_profile_id)
  status?: AssignmentStatus
  item_type?: ItemType
  item_id?: string
  priority_level_min?: PriorityLevel
  priority_level_max?: PriorityLevel
  assignment_method?: AssignmentMethod
  deadline_from?: string
  deadline_to?: string
  limit?: number
  offset?: number
}

// =============================================================================
// BULK OPERATIONS
// =============================================================================

/**
 * BulkReassignRequest - Reassign multiple assignments
 * Backend: AssignmentBulkReassign in assignment_history.py
 */
export interface BulkReassignRequest {
  assignment_ids: string[]
  new_agent_profile_id: string
  reason: ReassignmentReason
  notes?: string
}

export interface BulkReassignResult {
  successful: string[]
  failed: Array<{
    assignment_id: string
    error: string
  }>
  total_processed: number
  success_count: number
  failure_count: number
}

// =============================================================================
// LEGACY ALIASES (for backward compatibility during migration)
// =============================================================================

/** @deprecated Use item_id/item_type instead */
export type DeclarationType = ItemType

/** @deprecated Use PriorityLevel (number 1-10) instead */
export type AssignmentPriority = LegacyPriority

/** @deprecated Use ManualAssignmentRequest with new field names */
export interface LegacyManualAssignmentRequest {
  declaration_id: string
  declaration_type: DeclarationType
  agent_id: string
  priority?: AssignmentPriority
  notes?: string
  priority_level?: AssignmentPriority
  deadline_days?: number
}

/** @deprecated Use ReassignmentRequest with new field names */
export interface LegacyReassignmentRequest {
  new_agent_id: string
  reason: ReassignmentReason
  notes?: string
}

/** @deprecated Use AssignmentFilters with new field names */
export interface LegacyAssignmentFilters {
  agent_id?: string
  status?: AssignmentStatus
  priority?: AssignmentPriority
  declaration_id?: string
  limit?: number
  offset?: number
}

// Helper to convert legacy request to new format
export function convertLegacyManualRequest(
  legacy: LegacyManualAssignmentRequest
): ManualAssignmentRequest {
  return {
    item_id: legacy.declaration_id,
    item_type: legacy.declaration_type,
    agent_profile_id: legacy.agent_id,
    priority_level: legacy.priority_level || legacy.priority,
    notes: legacy.notes,
    deadline_days: legacy.deadline_days,
  }
}

// Helper to convert legacy filters to new format
export function convertLegacyFilters(
  legacy: LegacyAssignmentFilters
): AssignmentFilters {
  return {
    agent_profile_id: legacy.agent_id,
    status: legacy.status,
    item_id: legacy.declaration_id,
    limit: legacy.limit,
    offset: legacy.offset,
  }
}
