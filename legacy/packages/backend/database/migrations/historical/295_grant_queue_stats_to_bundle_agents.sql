-- 295_grant_queue_stats_to_bundle_agents.sql
--
-- P8.2-B2: grant `service_request.view_queue_stats` permission to bundle
-- collection entity agents and supervisors. Observed on 2026-04-15:
-- AYUNT/CAMARA agent dashboards showed 0 everywhere because their role
-- lacked this permission, returning 403 on /queue/stats. Only Tesoro +
-- CNEDOGE + DGT + ITV etc. had it historically.
--
-- Roles granted by this migration:
--   - agent_ayuntamiento
--   - agent_camara
--   - agent_min_agricultura, agent_min_comercio, agent_min_electricidad,
--     agent_min_hacienda, agent_min_informacion, agent_min_turismo
--   - supervisor_ayuntamiento, supervisor_camara
--   - supervisor_min_* (same ministries)
--   - agent_oms_polyvalent (polyvalent OMS processor)
--
-- Idempotent: ON CONFLICT DO NOTHING.

BEGIN;

-- The `role_permissions` table has an AFTER INSERT trigger
-- (audit_role_permissions_change) that writes to `audit_logs.user_id`, which
-- requires `app.current_user_id` to point to a real user (FK constraint).
-- run_migrations.py does not set this session variable, so we seed it with
-- the first super_admin user found so the audit row resolves correctly.
DO $$
DECLARE
    v_admin_id UUID;
BEGIN
    SELECT u.id INTO v_admin_id
    FROM users u
    JOIN roles r ON r.id = u.role_id
    WHERE r.code IN ('super_admin', 'admin')
    ORDER BY u.created_at
    LIMIT 1;

    IF v_admin_id IS NOT NULL THEN
        PERFORM set_config('app.current_user_id', v_admin_id::text, true);
    END IF;
END $$;

INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM roles r
CROSS JOIN permissions p
WHERE p.name = 'service_request.view_queue_stats'
  AND r.code IN (
      'agent_ayuntamiento',
      'agent_camara',
      'agent_min_agricultura',
      'agent_min_comercio',
      'agent_min_electricidad',
      'agent_min_hacienda',
      'agent_min_informacion',
      'agent_min_turismo',
      'agent_oms_polyvalent',
      'supervisor_ayuntamiento',
      'supervisor_camara',
      'supervisor_min_agricultura',
      'supervisor_min_comercio',
      'supervisor_min_electricidad',
      'supervisor_min_hacienda',
      'supervisor_min_informacion',
      'supervisor_min_turismo'
  )
ON CONFLICT (role_id, permission_id) DO NOTHING;

COMMIT;

-- ============================================================================
-- ROLLBACK (manual, uncomment + execute if reverting)
-- ============================================================================
-- BEGIN;
-- DELETE FROM role_permissions rp
-- USING roles r, permissions p
-- WHERE rp.role_id = r.id
--   AND rp.permission_id = p.id
--   AND p.name = 'service_request.view_queue_stats'
--   AND r.code IN (
--       'agent_ayuntamiento','agent_camara',
--       'agent_min_agricultura','agent_min_comercio','agent_min_electricidad',
--       'agent_min_hacienda','agent_min_informacion','agent_min_turismo',
--       'agent_oms_polyvalent',
--       'supervisor_ayuntamiento','supervisor_camara',
--       'supervisor_min_agricultura','supervisor_min_comercio','supervisor_min_electricidad',
--       'supervisor_min_hacienda','supervisor_min_informacion','supervisor_min_turismo'
--   );
-- COMMIT;
