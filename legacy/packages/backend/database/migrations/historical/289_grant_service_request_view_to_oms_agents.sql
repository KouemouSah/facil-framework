-- Migration 289: Grant service_request.view to OMS agent & supervisor roles
--
-- BUG FIX: OMS agents (agent_ayuntamiento, agent_camara, agent_min_*, agent_oms_polyvalent)
-- were created in migration 272 with only fiscal_service.* permissions.
-- They need service_request.view to access the entity dashboard
-- (GET /api/v1/agent/service-requests/entity/{code}/requests).
-- Without this permission, agents get 403 Forbidden on the "Dossiers en Attente" page.
--
-- Also grants to supervisor roles for consistency.
--
-- Safety: ON CONFLICT DO NOTHING (idempotent)

BEGIN;

-- Set session user for audit trigger (audit_role_permissions_change)
SET LOCAL app.current_user_id = '7c6073e3-66b0-45ba-be8d-80fcf98b7ad2';

-- Verify roles and permission exist before INSERT
DO $$
DECLARE
    v_perm_id UUID;
    v_role_count INT;
BEGIN
    -- Check permission exists
    SELECT id INTO v_perm_id FROM permissions WHERE name = 'service_request.view';
    IF v_perm_id IS NULL THEN
        RAISE EXCEPTION 'Permission service_request.view not found — aborting';
    END IF;

    -- Check at least some OMS roles exist
    SELECT COUNT(*) INTO v_role_count FROM roles
    WHERE code IN ('agent_ayuntamiento', 'agent_camara', 'agent_oms_polyvalent');
    IF v_role_count = 0 THEN
        RAISE EXCEPTION 'No OMS agent roles found — aborting';
    END IF;

    RAISE NOTICE 'Permission service_request.view (%) found, % OMS roles present', v_perm_id, v_role_count;
END $$;

-- Grant service_request.view to OMS agent roles (9 roles)
INSERT INTO role_permissions (role_id, permission_id, granted, created_by)
SELECT r.id, p.id, true, '7c6073e3-66b0-45ba-be8d-80fcf98b7ad2'::uuid
FROM roles r
CROSS JOIN permissions p
WHERE r.code IN (
    'agent_ayuntamiento', 'agent_camara',
    'agent_min_comercio', 'agent_min_hacienda', 'agent_min_informacion',
    'agent_min_turismo', 'agent_min_agricultura', 'agent_min_electricidad',
    'agent_oms_polyvalent'
)
AND p.name = 'service_request.view'
ON CONFLICT DO NOTHING;

-- Grant service_request.view to OMS supervisor roles (8 roles)
INSERT INTO role_permissions (role_id, permission_id, granted, created_by)
SELECT r.id, p.id, true, '7c6073e3-66b0-45ba-be8d-80fcf98b7ad2'::uuid
FROM roles r
CROSS JOIN permissions p
WHERE r.code IN (
    'supervisor_ayuntamiento', 'supervisor_camara',
    'supervisor_min_comercio', 'supervisor_min_hacienda', 'supervisor_min_informacion',
    'supervisor_min_turismo', 'supervisor_min_agricultura', 'supervisor_min_electricidad'
)
AND p.name = 'service_request.view'
ON CONFLICT DO NOTHING;

-- Also grant to agent_tesoro and supervisor_tesoro if not already present
INSERT INTO role_permissions (role_id, permission_id, granted, created_by)
SELECT r.id, p.id, true, '7c6073e3-66b0-45ba-be8d-80fcf98b7ad2'::uuid
FROM roles r
CROSS JOIN permissions p
WHERE r.code IN ('agent_tesoro', 'supervisor_tesoro')
AND p.name = 'service_request.view'
ON CONFLICT DO NOTHING;

COMMIT;
