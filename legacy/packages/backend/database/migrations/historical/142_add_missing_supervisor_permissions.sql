-- Migration 142: Grant queue/assignment permissions to entity-specific supervisors
--
-- Backend was using non-existent permissions (escalations.*, agent.manage_assignments).
-- Fixed to use existing queue.* and assignment.reassign instead.
--
-- The generic 'supervisor' role already has these permissions.
-- Entity-specific supervisors (supervisor_cnedoge_*, supervisor_dgt, etc.) do NOT.
-- This migration grants them the same queue/assignment permissions they need
-- to manage escalations and reassignments.

BEGIN;

-- Grant queue + assignment permissions to entity-specific supervisor roles
-- (supervisor_cnedoge_pasaporte, supervisor_cnedoge_residencia, supervisor_dgt, supervisor_ofive, supervisor_onrc)
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM roles r, permissions p
WHERE r.code LIKE 'supervisor_%'
AND r.code NOT IN ('supervisor', 'supervisor_tesoro')  -- already have them
AND p.name IN (
    'queue.view',        -- view escalation queue
    'queue.assign',      -- assign escalated items
    'queue.complete',    -- resolve/approve/reject escalations
    'queue.escalate',    -- escalate items
    'queue.release',     -- release items
    'assignment.reassign',           -- reassign assignments (dead letters, etc.)
    'assignment.reassign_in_progress' -- reassign in-progress assignments
)
ON CONFLICT DO NOTHING;

COMMIT;
