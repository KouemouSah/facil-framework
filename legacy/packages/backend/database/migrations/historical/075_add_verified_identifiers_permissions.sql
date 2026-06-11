-- Migration: 075_add_verified_identifiers_permissions.sql
-- Date: 2026-01-29
-- Description: Add missing permissions for verified_identifiers module
-- Author: Claude Code
-- Issue: Backend routes use permissions that don't exist in database

-- ============================================================================
-- 1. ADD MISSING PERMISSIONS
-- ============================================================================

INSERT INTO permissions (name, resource, action, description, module_name)
VALUES
    -- Verification permissions (used by agent endpoints)
    ('requests.verify', 'requests', 'verify', 'Verify service request identifiers manually', 'verified_identifiers'),
    ('requests.reverify', 'requests', 'reverify', 'Trigger re-verification of service request', 'verified_identifiers'),

    -- Admin permissions (batch import, stats, config)
    ('identifiers.import', 'identifiers', 'import', 'Import verified identifiers from external sources', 'verified_identifiers'),
    ('identifiers.stats', 'identifiers', 'stats', 'View verified identifiers statistics', 'verified_identifiers'),
    ('identifiers.config', 'identifiers', 'config', 'Manage document verification configuration', 'verified_identifiers')
ON CONFLICT (name) DO NOTHING;

-- ============================================================================
-- 2. GRANT PERMISSIONS TO PASAPORTE ROLE (CNEDOGE agents)
-- ============================================================================

INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM roles r, permissions p
WHERE r.code = 'pasaporte'
  AND p.name IN ('requests.verify', 'requests.reverify')
ON CONFLICT DO NOTHING;

-- ============================================================================
-- 3. GRANT PERMISSIONS TO SUPERVISOR ROLE
-- ============================================================================

INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM roles r, permissions p
WHERE r.code = 'supervisor'
  AND p.name IN ('requests.verify', 'requests.reverify', 'identifiers.stats')
ON CONFLICT DO NOTHING;

-- ============================================================================
-- 4. GRANT ADMIN PERMISSIONS TO ADMIN ROLE
-- ============================================================================

INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM roles r, permissions p
WHERE r.code = 'admin'
  AND p.name IN ('requests.verify', 'requests.reverify', 'identifiers.import', 'identifiers.stats', 'identifiers.config')
ON CONFLICT DO NOTHING;

-- ============================================================================
-- 5. VERIFICATION
-- ============================================================================

DO $$
DECLARE
    v_count INTEGER;
BEGIN
    -- Count new permissions
    SELECT COUNT(*) INTO v_count
    FROM permissions
    WHERE name IN ('requests.verify', 'requests.reverify', 'identifiers.import', 'identifiers.stats', 'identifiers.config');

    RAISE NOTICE 'Verified identifiers permissions count: %', v_count;

    -- Count role assignments
    SELECT COUNT(*) INTO v_count
    FROM role_permissions rp
    JOIN permissions p ON p.id = rp.permission_id
    WHERE p.name LIKE 'requests.%' OR p.name LIKE 'identifiers.%';

    RAISE NOTICE 'Role permission assignments: %', v_count;
END $$;

-- ============================================================================
-- MIGRATION COMPLETE
-- ============================================================================
