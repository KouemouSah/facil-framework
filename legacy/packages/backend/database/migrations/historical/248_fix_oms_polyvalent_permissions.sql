-- Migration 248: Fix agent_oms_polyvalent missing OMS permissions
-- Date: 2026-03-20
-- Issue: agent_oms_polyvalent role is missing fiscal_service.process_obligations
--        and fiscal_service.view_bundles, making the agent unable to process obligations
-- All other OMS agent/supervisor roles already have these permissions (fixed in migration 227/245)

BEGIN;

-- Add missing permissions to agent_oms_polyvalent
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM roles r
CROSS JOIN permissions p
WHERE r.code = 'agent_oms_polyvalent'
  AND p.name IN ('fiscal_service.process_obligations', 'fiscal_service.view_bundles')
ON CONFLICT DO NOTHING;

-- Verify: agent_oms_polyvalent should now have at least 4 permissions
-- (company.view, company.view_all, fiscal_service.process_obligations, fiscal_service.view_bundles)
DO $$
DECLARE
  perm_count INTEGER;
BEGIN
  SELECT COUNT(*) INTO perm_count
  FROM role_permissions rp
  JOIN roles r ON r.id = rp.role_id
  JOIN permissions p ON p.id = rp.permission_id
  WHERE r.code = 'agent_oms_polyvalent'
    AND p.name IN ('fiscal_service.process_obligations', 'fiscal_service.view_bundles');

  IF perm_count < 2 THEN
    RAISE EXCEPTION 'Migration 248 verification failed: agent_oms_polyvalent should have 2 fiscal_service permissions, found %', perm_count;
  END IF;

  RAISE NOTICE 'Migration 248: agent_oms_polyvalent now has % fiscal_service permissions', perm_count;
END $$;

COMMIT;
