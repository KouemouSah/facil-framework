-- ============================================================================
-- MIGRATION 067: Assignation des permissions Treasury aux rôles concernés
-- Date: 2026-01-24
-- Description: Assigne les permissions Treasury au rôle agent_tesoro
--              pour permettre la validation des paiements
-- ============================================================================

BEGIN;

-- ============================================================================
-- 1. PERMISSIONS POUR AGENT_TESORO (Treasury Agent)
-- ============================================================================

-- Récupérer l'ID du rôle agent_tesoro
DO $$
DECLARE
    v_role_id UUID;
    v_permission_id UUID;
    v_permissions TEXT[] := ARRAY[
        -- Treasury core
        'treasury.validate_payment',
        'treasury.reject_payment',
        'treasury.view_payment',
        'treasury.process_payment',
        -- Treasury audit
        'treasury_audit.view',
        -- Treasury stats
        'treasury_stat.view',
        -- Treasury anomalies
        'treasury_anomaly.view',
        'treasury_anomaly.create',
        -- Treasury exports
        'treasury_export.view',
        'treasury_export.download',
        -- Service request (pour voir les demandes associées)
        'service_request.view',
        'service_request.view_documents',
        'service_request.view_queue',
        'service_request.view_my_queue',
        -- Payment view
        'payment.view',
        -- Dashboard
        'dashboard.view',
        'dashboard.view_own',
        'dashboard.view_own_stats',
        -- User
        'user.view'
    ];
    v_perm TEXT;
BEGIN
    -- Trouver le rôle agent_tesoro
    SELECT id INTO v_role_id FROM roles WHERE code = 'agent_tesoro';

    IF v_role_id IS NULL THEN
        RAISE NOTICE 'Role agent_tesoro not found, skipping...';
        RETURN;
    END IF;

    RAISE NOTICE 'Assigning permissions to agent_tesoro (role_id: %)', v_role_id;

    -- Assigner chaque permission
    FOREACH v_perm IN ARRAY v_permissions
    LOOP
        SELECT id INTO v_permission_id FROM permissions WHERE name = v_perm;

        IF v_permission_id IS NOT NULL THEN
            INSERT INTO role_permissions (role_id, permission_id, created_at)
            VALUES (v_role_id, v_permission_id, NOW())
            ON CONFLICT (role_id, permission_id) DO NOTHING;

            RAISE NOTICE 'Assigned permission: %', v_perm;
        ELSE
            RAISE NOTICE 'Permission not found: %', v_perm;
        END IF;
    END LOOP;
END $$;

-- ============================================================================
-- 2. PERMISSIONS POUR SUPERVISOR (peut superviser les agents tesoro)
-- ============================================================================

DO $$
DECLARE
    v_role_id UUID;
    v_permission_id UUID;
    v_permissions TEXT[] := ARRAY[
        -- Toutes les permissions treasury
        'treasury.validate_payment',
        'treasury.reject_payment',
        'treasury.view_payment',
        'treasury.process_payment',
        'treasury_audit.view',
        'treasury_audit.export',
        'treasury_stat.view',
        'treasury_stat.export',
        'treasury_anomaly.view',
        'treasury_anomaly.create',
        'treasury_anomaly.update',
        'treasury_anomaly.resolve',
        'treasury_export.view',
        'treasury_export.create',
        'treasury_export.download',
        'treasury.reconcile',
        'treasury.view_reconciliation',
        'treasury.manage_settings',
        -- Agent management
        'agent.view',
        'agent.list',
        'agent.view_workload',
        'agent.view_performance',
        -- Dashboard
        'dashboard.view',
        'dashboard.view_realtime',
        'dashboard.team_stats',
        'dashboard.team_performance',
        'dashboard.team_workload'
    ];
    v_perm TEXT;
BEGIN
    -- Trouver le rôle supervisor
    SELECT id INTO v_role_id FROM roles WHERE code = 'supervisor';

    IF v_role_id IS NULL THEN
        RAISE NOTICE 'Role supervisor not found, skipping...';
        RETURN;
    END IF;

    RAISE NOTICE 'Assigning permissions to supervisor (role_id: %)', v_role_id;

    FOREACH v_perm IN ARRAY v_permissions
    LOOP
        SELECT id INTO v_permission_id FROM permissions WHERE name = v_perm;

        IF v_permission_id IS NOT NULL THEN
            INSERT INTO role_permissions (role_id, permission_id, created_at)
            VALUES (v_role_id, v_permission_id, NOW())
            ON CONFLICT (role_id, permission_id) DO NOTHING;
        END IF;
    END LOOP;
END $$;

-- ============================================================================
-- 3. PERMISSIONS POUR ADMIN (toutes les permissions treasury)
-- ============================================================================

DO $$
DECLARE
    v_role_id UUID;
    v_permission_id UUID;
    v_permissions TEXT[] := ARRAY[
        -- Toutes les permissions treasury
        'treasury.validate_payment',
        'treasury.reject_payment',
        'treasury.view_payment',
        'treasury.process_payment',
        'treasury_audit.view',
        'treasury_audit.export',
        'treasury_stat.view',
        'treasury_stat.export',
        'treasury_anomaly.view',
        'treasury_anomaly.create',
        'treasury_anomaly.update',
        'treasury_anomaly.resolve',
        'treasury_export.view',
        'treasury_export.create',
        'treasury_export.download',
        'treasury.reconcile',
        'treasury.view_reconciliation',
        'treasury.manage_settings'
    ];
    v_perm TEXT;
BEGIN
    -- Trouver le rôle admin
    SELECT id INTO v_role_id FROM roles WHERE code = 'admin';

    IF v_role_id IS NULL THEN
        RAISE NOTICE 'Role admin not found, skipping...';
        RETURN;
    END IF;

    RAISE NOTICE 'Assigning permissions to admin (role_id: %)', v_role_id;

    FOREACH v_perm IN ARRAY v_permissions
    LOOP
        SELECT id INTO v_permission_id FROM permissions WHERE name = v_perm;

        IF v_permission_id IS NOT NULL THEN
            INSERT INTO role_permissions (role_id, permission_id, created_at)
            VALUES (v_role_id, v_permission_id, NOW())
            ON CONFLICT (role_id, permission_id) DO NOTHING;
        END IF;
    END LOOP;
END $$;

-- ============================================================================
-- VERIFICATION
-- ============================================================================

-- Vérifier les permissions assignées à agent_tesoro
DO $$
DECLARE
    v_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO v_count
    FROM role_permissions rp
    JOIN roles r ON r.id = rp.role_id
    JOIN permissions p ON p.id = rp.permission_id
    WHERE r.code = 'agent_tesoro'
    AND p.name LIKE 'treasury%';

    RAISE NOTICE 'Treasury permissions for agent_tesoro: %', v_count;
END $$;

COMMIT;
