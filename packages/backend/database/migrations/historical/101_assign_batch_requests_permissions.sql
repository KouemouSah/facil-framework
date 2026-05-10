-- ============================================================================
-- Migration 101: Assign batch_requests permissions to roles
-- ============================================================================
-- Permissions were created in migration 100.
-- This assigns them to the appropriate roles.
-- ============================================================================

BEGIN;

-- Citizen, business, accountant: create + read own batches
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM roles r, permissions p
WHERE r.code IN ('citizen', 'business', 'accountant')
  AND p.name IN ('batch_requests.create', 'batch_requests.read')
  AND NOT EXISTS (
    SELECT 1 FROM role_permissions rp
    WHERE rp.role_id = r.id AND rp.permission_id = p.id
  );

-- Supervisor: create + read + manage
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM roles r, permissions p
WHERE r.code = 'supervisor'
  AND p.name IN ('batch_requests.create', 'batch_requests.read', 'batch_requests.manage')
  AND NOT EXISTS (
    SELECT 1 FROM role_permissions rp
    WHERE rp.role_id = r.id AND rp.permission_id = p.id
  );

-- Admin: all batch_requests permissions (create + read + manage + admin)
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM roles r, permissions p
WHERE r.code IN ('admin', 'ADMIN')
  AND p.name IN ('batch_requests.create', 'batch_requests.read', 'batch_requests.manage', 'batch_requests.admin')
  AND NOT EXISTS (
    SELECT 1 FROM role_permissions rp
    WHERE rp.role_id = r.id AND rp.permission_id = p.id
  );

-- Agent roles: read + manage (view and process batches assigned to their entity)
-- Real role codes from BD: agent_cnedoge_pasaporte, agent_cnedoge_residencia,
-- agent_dgt, agent_extranjeria, agent_ofive, agent_onrc, agent_policia, agent_tesoro
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM roles r, permissions p
WHERE r.code IN (
    'agent_cnedoge_pasaporte', 'agent_cnedoge_residencia',
    'agent_dgt', 'agent_extranjeria', 'agent_ofive',
    'agent_onrc', 'agent_policia', 'agent_tesoro'
  )
  AND p.name IN ('batch_requests.read', 'batch_requests.manage')
  AND NOT EXISTS (
    SELECT 1 FROM role_permissions rp
    WHERE rp.role_id = r.id AND rp.permission_id = p.id
  );

COMMIT;
