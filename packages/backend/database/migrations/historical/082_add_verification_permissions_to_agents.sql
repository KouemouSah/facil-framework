-- Migration: Add verification permissions to agent roles
-- Date: 2026-01-29
-- Description: Add service_request.verify_manually and service_request.view_extraction
--              to agent_cnedoge_pasaporte and agent_cnedoge_residencia roles
--              Required for the identity verification page functionality

BEGIN;

-- Add verify_manually permission to agent_cnedoge_pasaporte
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM roles r, permissions p
WHERE r.code = 'agent_cnedoge_pasaporte'
  AND p.name = 'service_request.verify_manually'
  AND NOT EXISTS (
    SELECT 1 FROM role_permissions rp
    WHERE rp.role_id = r.id AND rp.permission_id = p.id
  );

-- Add view_extraction permission to agent_cnedoge_pasaporte
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM roles r, permissions p
WHERE r.code = 'agent_cnedoge_pasaporte'
  AND p.name = 'service_request.view_extraction'
  AND NOT EXISTS (
    SELECT 1 FROM role_permissions rp
    WHERE rp.role_id = r.id AND rp.permission_id = p.id
  );

-- Add verify_manually permission to agent_cnedoge_residencia
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM roles r, permissions p
WHERE r.code = 'agent_cnedoge_residencia'
  AND p.name = 'service_request.verify_manually'
  AND NOT EXISTS (
    SELECT 1 FROM role_permissions rp
    WHERE rp.role_id = r.id AND rp.permission_id = p.id
  );

-- Add view_extraction permission to agent_cnedoge_residencia
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM roles r, permissions p
WHERE r.code = 'agent_cnedoge_residencia'
  AND p.name = 'service_request.view_extraction'
  AND NOT EXISTS (
    SELECT 1 FROM role_permissions rp
    WHERE rp.role_id = r.id AND rp.permission_id = p.id
  );

-- Also add to other agent roles that may need verification capabilities
-- agent_extranjeria (handles residence permits)
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM roles r, permissions p
WHERE r.code = 'agent_extranjeria'
  AND p.name = 'service_request.verify_manually'
  AND NOT EXISTS (
    SELECT 1 FROM role_permissions rp
    WHERE rp.role_id = r.id AND rp.permission_id = p.id
  );

INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM roles r, permissions p
WHERE r.code = 'agent_extranjeria'
  AND p.name = 'service_request.view_extraction'
  AND NOT EXISTS (
    SELECT 1 FROM role_permissions rp
    WHERE rp.role_id = r.id AND rp.permission_id = p.id
  );

COMMIT;

-- Verification query (run after migration)
-- SELECT r.code, p.name
-- FROM role_permissions rp
-- JOIN roles r ON r.id = rp.role_id
-- JOIN permissions p ON p.id = rp.permission_id
-- WHERE r.code IN ('agent_cnedoge_pasaporte', 'agent_cnedoge_residencia', 'agent_extranjeria')
--   AND p.name IN ('service_request.verify_manually', 'service_request.view_extraction')
-- ORDER BY r.code, p.name;
