-- Migration 139: Assign missing dashboard permissions to admin role
-- Fixes: "Roles Activos: 0" and "Error retrieving audit logs" on admin dashboard
-- Root cause: permissions created in 066 but never assigned to admin role
--
-- The admin dashboard StatsCards call 4 APIs in parallel:
--   1. GET /admin/users/stats     → requires users.view_stats
--   2. GET /audit-logs/stats      → requires audit.view_stats
--   3. GET /roles                 → requires roles.view
--   4. GET /permissions           → requires permissions.view
-- Plus RecentActivity: GET /audit-logs → requires audit.view
-- Plus fiscal services charts: GET /fiscal-services/admin/stats → requires fiscal_services.view_stats

DO $$
DECLARE
  v_admin_role_id UUID;
  v_permissions TEXT[] := ARRAY[
    'roles.view',
    'audit.view',
    'audit.view_stats',
    'fiscal_services.view_stats'
  ];
  v_perm TEXT;
  v_perm_id UUID;
  v_inserted INT := 0;
BEGIN
  -- Find admin role
  SELECT id INTO v_admin_role_id FROM roles WHERE code = 'admin' LIMIT 1;

  IF v_admin_role_id IS NULL THEN
    RAISE NOTICE 'Admin role not found, skipping';
    RETURN;
  END IF;

  FOREACH v_perm IN ARRAY v_permissions LOOP
    -- Find permission ID
    SELECT id INTO v_perm_id FROM permissions WHERE name = v_perm LIMIT 1;

    IF v_perm_id IS NOT NULL THEN
      -- Insert if not already assigned
      INSERT INTO role_permissions (role_id, permission_id, granted, created_at)
      VALUES (v_admin_role_id, v_perm_id, TRUE, NOW())
      ON CONFLICT (role_id, permission_id) DO NOTHING;

      IF FOUND THEN
        v_inserted := v_inserted + 1;
        RAISE NOTICE 'Assigned % to admin role', v_perm;
      ELSE
        RAISE NOTICE '% already assigned to admin role', v_perm;
      END IF;
    ELSE
      RAISE NOTICE 'Permission % not found in permissions table', v_perm;
    END IF;
  END LOOP;

  RAISE NOTICE 'Migration 139 complete: % permissions assigned to admin', v_inserted;
END $$;
