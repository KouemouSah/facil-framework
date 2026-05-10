-- Migration 140: Create supervisor roles for each entity
-- Currently only supervisor_tesoro exists. Each entity needs its own supervisor role
-- with proper permissions.
--
-- KEY DISTINCTION:
--   Workflow supervisors (CNEDOGE, ONRC, OFIVE, DGT) → service_request.process/escalate
--   Treasury supervisor (TESORO) → treasury.* permissions only (NO service_request.process)
--
-- Idempotent: ON CONFLICT DO NOTHING everywhere.

DO $$
DECLARE
  v_role_id UUID;
  v_perm_id UUID;
  v_inserted_roles INT := 0;
  v_inserted_perms INT := 0;
  v_perm TEXT;

  -- ============================================================
  -- SHARED supervisor permissions (ALL supervisors get these)
  -- ============================================================
  v_shared_permissions TEXT[] := ARRAY[
    -- Supervisor dashboard & team
    'supervisor.dashboard.view',
    'supervisor.team.view',
    'supervisor.team.manage',
    -- Supervisor workload
    'supervisor.workload.view',
    'supervisor.workload.balance',
    -- Supervisor assignment rules
    'supervisor.rules.view',
    'supervisor.rules.create',
    'supervisor.rules.update',
    'supervisor.rules.delete',
    'supervisor.rules.activate',
    -- Supervisor stats
    'supervisor.stats.view',
    'supervisor.stats.export',
    -- Escalations
    'escalations.view',
    'escalations.assign',
    'escalations.resolve',
    -- Agent self-management
    'agents.view_own_profile',
    'agents.update_availability',
    -- Assignment team visibility
    'assignments.view_own',
    'assignments.view_team',
    'assignments.reassign',
    'assignment.update_notes',
    'assignment.view_stats',
    -- Workload team visibility
    'workloads.view_own',
    'workloads.view_team',
    'workloads.manage',
    -- Notifications
    'notifications.log.read'
  ];

  -- ============================================================
  -- WORKFLOW-ONLY permissions (NOT for treasury)
  -- ============================================================
  v_workflow_permissions TEXT[] := ARRAY[
    'service_request.process',
    'service_request.escalate'
  ];

BEGIN
  -- ============================================================
  -- Step 1: Create workflow supervisor roles
  -- ============================================================
  INSERT INTO roles (id, code, name, description, entity_type, is_system, created_at, updated_at)
  VALUES
    (gen_random_uuid(), 'supervisor_cnedoge_pasaporte', 'Supervisor CNEDOGE Pasaportes', 'Supervisor del servicio de pasaportes - CNEDOGE', 'entity_agent', false, NOW(), NOW()),
    (gen_random_uuid(), 'supervisor_cnedoge_residencia', 'Supervisor CNEDOGE Residencias', 'Supervisor del servicio de residencias - CNEDOGE', 'entity_agent', false, NOW(), NOW()),
    (gen_random_uuid(), 'supervisor_onrc', 'Supervisor ONRC', 'Supervisor de la Oficina Nacional de Registro de Contratos', 'entity_agent', false, NOW(), NOW()),
    (gen_random_uuid(), 'supervisor_ofive', 'Supervisor OFIVE', 'Supervisor de la Oficina de Vehículos - CUVE', 'entity_agent', false, NOW(), NOW()),
    (gen_random_uuid(), 'supervisor_dgt', 'Supervisor DGT', 'Supervisor de la Dirección General de Tráfico', 'entity_agent', false, NOW(), NOW())
  ON CONFLICT (code) DO NOTHING;

  GET DIAGNOSTICS v_inserted_roles = ROW_COUNT;
  RAISE NOTICE '% new supervisor roles created', v_inserted_roles;

  -- ============================================================
  -- Step 2: Set default_agent_config for ALL supervisor roles
  -- ============================================================
  UPDATE roles
  SET default_agent_config = jsonb_build_object(
    'is_supervisor', true,
    'can_escalate', true,
    'can_assign_tasks', true,
    'can_reassign', true,
    'can_approve_unlimited', false
  )
  WHERE code LIKE 'supervisor_%'
  AND default_agent_config IS NULL;

  -- ============================================================
  -- Step 3: Assign SHARED permissions to ALL supervisor roles
  -- ============================================================
  FOR v_role_id IN
    SELECT id FROM roles WHERE code LIKE 'supervisor_%'
  LOOP
    FOREACH v_perm IN ARRAY v_shared_permissions LOOP
      SELECT id INTO v_perm_id FROM permissions WHERE name = v_perm LIMIT 1;
      IF v_perm_id IS NOT NULL THEN
        INSERT INTO role_permissions (role_id, permission_id, granted, created_at)
        VALUES (v_role_id, v_perm_id, TRUE, NOW())
        ON CONFLICT (role_id, permission_id) DO NOTHING;
        IF FOUND THEN v_inserted_perms := v_inserted_perms + 1; END IF;
      ELSE
        RAISE NOTICE 'Permission % not found — skipping', v_perm;
      END IF;
    END LOOP;
  END LOOP;

  -- ============================================================
  -- Step 4: Assign WORKFLOW permissions to non-treasury supervisors ONLY
  -- ============================================================
  FOR v_role_id IN
    SELECT id FROM roles
    WHERE code LIKE 'supervisor_%'
    AND code != 'supervisor_tesoro'
    AND code != 'supervisor_agent'
  LOOP
    FOREACH v_perm IN ARRAY v_workflow_permissions LOOP
      SELECT id INTO v_perm_id FROM permissions WHERE name = v_perm LIMIT 1;
      IF v_perm_id IS NOT NULL THEN
        INSERT INTO role_permissions (role_id, permission_id, granted, created_at)
        VALUES (v_role_id, v_perm_id, TRUE, NOW())
        ON CONFLICT (role_id, permission_id) DO NOTHING;
        IF FOUND THEN v_inserted_perms := v_inserted_perms + 1; END IF;
      END IF;
    END LOOP;
  END LOOP;

  -- ============================================================
  -- Step 5: Remove workflow permissions from supervisor_tesoro
  -- (may have been added incorrectly by migration 122)
  -- ============================================================
  DELETE FROM role_permissions
  WHERE role_id = (SELECT id FROM roles WHERE code = 'supervisor_tesoro' LIMIT 1)
  AND permission_id IN (
    SELECT id FROM permissions WHERE name IN ('service_request.process', 'service_request.escalate')
  );

  RAISE NOTICE 'Migration 140 complete: % roles created, % permission assignments added',
    v_inserted_roles, v_inserted_perms;
END $$;
