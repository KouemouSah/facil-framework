-- Migration 122: Fix TESORO agent permissions
-- Bug: agent_tesoro missing service_request.view, service_request.process, service_request.escalate
-- Impact: 403 on widgets, my-queue, my-escalations endpoints
-- Also: supervisor_tesoro needs service_request.process and service_request.escalate

-- ============================================================================
-- PHASE 1: Add missing permissions to agent_tesoro
-- ============================================================================

INSERT INTO role_permissions (role_id, permission_id)
SELECT
  (SELECT id FROM roles WHERE code = 'agent_tesoro'),
  p.id
FROM permissions p
WHERE p.name IN (
  'service_request.view',
  'service_request.process',
  'service_request.escalate'
)
AND NOT EXISTS (
  SELECT 1 FROM role_permissions rp
  WHERE rp.role_id = (SELECT id FROM roles WHERE code = 'agent_tesoro')
    AND rp.permission_id = p.id
);

-- ============================================================================
-- PHASE 2: Add missing permissions to supervisor_tesoro
-- ============================================================================

INSERT INTO role_permissions (role_id, permission_id)
SELECT
  (SELECT id FROM roles WHERE code = 'supervisor_tesoro'),
  p.id
FROM permissions p
WHERE p.name IN (
  'service_request.process',
  'service_request.escalate'
)
AND NOT EXISTS (
  SELECT 1 FROM role_permissions rp
  WHERE rp.role_id = (SELECT id FROM roles WHERE code = 'supervisor_tesoro')
    AND rp.permission_id = p.id
);

-- ============================================================================
-- VERIFY
-- ============================================================================

DO $$
DECLARE
  agent_count INTEGER;
  sup_count INTEGER;
BEGIN
  SELECT COUNT(*) INTO agent_count
  FROM role_permissions rp
  JOIN roles r ON r.id = rp.role_id
  JOIN permissions p ON p.id = rp.permission_id
  WHERE r.code = 'agent_tesoro'
    AND p.name IN ('service_request.view', 'service_request.process', 'service_request.escalate');

  SELECT COUNT(*) INTO sup_count
  FROM role_permissions rp
  JOIN roles r ON r.id = rp.role_id
  JOIN permissions p ON p.id = rp.permission_id
  WHERE r.code = 'supervisor_tesoro'
    AND p.name IN ('service_request.view', 'service_request.process', 'service_request.escalate');

  RAISE NOTICE 'agent_tesoro: % / 3 required permissions assigned', agent_count;
  RAISE NOTICE 'supervisor_tesoro: % / 3 required permissions assigned', sup_count;
END $$;
