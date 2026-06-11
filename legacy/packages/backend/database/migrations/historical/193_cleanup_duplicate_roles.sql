-- ============================================================================
-- Migration 193: Cleanup duplicate/phantom/legacy roles
-- ============================================================================
-- Problem:
--   1. admin (33 perms) vs ADMIN (29 perms) — divergent permission sets
--      Admin user (sah@emacsah.com) is linked to ADMIN role
--      Solution: merge ADMIN perms into admin, migrate user, delete ADMIN
--   2. pasaporte (21 perms) — legacy, 0 users assigned
--      Solution: delete (agent_cnedoge_pasaporte is the replacement)
--   3. supervisor (147 perms) — generic catch-all, 0 users, not in user_role_enum
--      Solution: delete
-- ============================================================================

-- ============================================================================
-- STEP 1: Merge ADMIN permissions into admin role
-- Copy any permissions from ADMIN that admin doesn't already have
-- ============================================================================

INSERT INTO role_permissions (role_id, permission_id, granted, created_at)
SELECT
    (SELECT id FROM roles WHERE code = 'admin'),
    rp.permission_id,
    rp.granted,
    NOW()
FROM role_permissions rp
JOIN roles r ON r.id = rp.role_id
WHERE r.code = 'ADMIN'
  AND NOT EXISTS (
    SELECT 1 FROM role_permissions rp2
    JOIN roles r2 ON r2.id = rp2.role_id
    WHERE r2.code = 'admin' AND rp2.permission_id = rp.permission_id
  );

-- ============================================================================
-- STEP 2: Migrate admin user from ADMIN role to admin role
-- ============================================================================

UPDATE users
SET role_id = (SELECT id FROM roles WHERE code = 'admin')
WHERE role_id = (SELECT id FROM roles WHERE code = 'ADMIN');

-- ============================================================================
-- STEP 3: Add 4 useful permissions from legacy pasaporte to all agent_* roles
-- These are: escalate, export, view_audit_log, view_available_slots
-- (reassign is supervisor-level, excluded)
-- ============================================================================

INSERT INTO role_permissions (role_id, permission_id, granted, created_at)
SELECT r.id, p.id, true, NOW()
FROM roles r
CROSS JOIN permissions p
WHERE r.code LIKE 'agent_%'
  AND r.code != 'agent_tesoro'  -- treasury agents don't process service requests
  AND p.name IN (
    'service_request.escalate',
    'service_request.export',
    'service_request.view_audit_log',
    'service_request.view_available_slots'
  )
  AND NOT EXISTS (
    SELECT 1 FROM role_permissions rp
    WHERE rp.role_id = r.id AND rp.permission_id = p.id
  );

-- ============================================================================
-- STEP 4: Enrich non-treasury supervisor roles (currently only 11 perms)
-- Add essential permissions they're missing
-- ============================================================================

INSERT INTO role_permissions (role_id, permission_id, granted, created_at)
SELECT r.id, p.id, true, NOW()
FROM roles r
CROSS JOIN permissions p
WHERE r.code IN (
    'supervisor_cnedoge_pasaporte',
    'supervisor_cnedoge_residencia',
    'supervisor_dgt',
    'supervisor_ofive',
    'supervisor_onrc'
  )
  AND p.name IN (
    -- View their agents
    'agent.list',
    'agent.view',
    'agent.view_performance',
    -- View documents
    'document.view',
    'document.download',
    -- View requests and queues
    'service_request.view',
    'service_request.view_queue',
    'service_request.view_queue_stats',
    -- Reports
    'reports.view',
    'reports.export_pdf',
    -- Escalation
    'service_request.escalate'
  )
  AND NOT EXISTS (
    SELECT 1 FROM role_permissions rp
    WHERE rp.role_id = r.id AND rp.permission_id = p.id
  );

-- ============================================================================
-- STEP 5: Delete phantom/legacy roles (0 users on each)
-- ============================================================================

-- Safety check: ensure no users still reference these roles
-- (STEP 2 should have migrated ADMIN users, pasaporte/supervisor should have 0)
DO $$
DECLARE
    remaining_count INT;
BEGIN
    SELECT COUNT(*) INTO remaining_count
    FROM users u
    JOIN roles r ON r.id = u.role_id
    WHERE r.code IN ('ADMIN', 'pasaporte', 'supervisor');

    IF remaining_count > 0 THEN
        RAISE EXCEPTION 'Cannot delete roles: % users still reference them', remaining_count;
    END IF;
END $$;

-- Delete role_permissions first (FK constraint)
DELETE FROM role_permissions WHERE role_id IN (
    SELECT id FROM roles WHERE code IN ('ADMIN', 'pasaporte', 'supervisor')
);

-- Delete the roles
DELETE FROM roles WHERE code IN ('ADMIN', 'pasaporte', 'supervisor');
