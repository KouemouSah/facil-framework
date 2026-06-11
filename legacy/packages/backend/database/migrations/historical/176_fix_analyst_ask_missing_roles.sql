-- Migration 176: Fix analyst.ask permission for entity-specific supervisor roles
--
-- Migration 175 assigned analyst.ask based on agent.view_performance / agent.view / treasury_stat.view.
-- But 5 entity-specific supervisor roles only have operational permissions (queue.*, assignment.*, service_request.*).
-- They were silently missed.
--
-- Affected roles:
--   supervisor_cnedoge_pasaporte, supervisor_cnedoge_residencia,
--   supervisor_dgt, supervisor_ofive, supervisor_onrc

DO $$
DECLARE
    perm_id UUID;
    cnt INTEGER := 0;
BEGIN
    SELECT id INTO perm_id FROM permissions WHERE name = 'analyst.ask';
    IF perm_id IS NULL THEN
        RAISE NOTICE 'analyst.ask permission not found — skipping';
        RETURN;
    END IF;

    -- Assign to ALL supervisor_* and agent_* roles that don't already have it
    INSERT INTO role_permissions (role_id, permission_id)
    SELECT r.id, perm_id
    FROM roles r
    WHERE (r.code LIKE 'supervisor_%' OR r.code LIKE 'agent_%')
      AND NOT EXISTS (
          SELECT 1 FROM role_permissions rp
          WHERE rp.role_id = r.id AND rp.permission_id = perm_id
      );

    GET DIAGNOSTICS cnt = ROW_COUNT;
    RAISE NOTICE 'Migration 176: assigned analyst.ask to % additional roles', cnt;
END $$;
