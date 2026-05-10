-- ============================================================================
-- Migration 085: Enable Auto Menu Generation - Phase 1
-- ============================================================================
-- Purpose:
--   Enable automatic menu generation for workflow-based agent roles.
--   Setting menu_config = NULL triggers the backend to generate menus
--   dynamically from entities.workflow_codes + workflow_menu_mapping table.
--
-- Phase 1 Roles (entity codes aligned):
--   - agent_cnedoge_pasaporte → CNEDOGE_PASAPORTE
--   - agent_cnedoge_residencia → CNEDOGE_RESIDENCIA
--   - agent_dgt → DGT
--   - agent_ofive → OFIVE
--   - agent_onrc → ONRC
--
-- NOT migrated (Phase 2/3 or permanent):
--   - agent_extranjeria → Entity code mismatch (COM_EXT vs EXTRANJERIA)
--   - agent_policia → Entity code mismatch + no workflows yet
--   - agent_tesoro → Module-based, no workflows (permanent)
--
-- Backup table: _backup_role_menu_config_phase1
--
-- Author: Claude Code
-- Date: 2026-01-30
-- ============================================================================

BEGIN;

-- =============================================================================
-- STEP 1: Create backup table
-- =============================================================================
CREATE TABLE IF NOT EXISTS _backup_role_menu_config_phase1 (
    role_code VARCHAR(50) PRIMARY KEY,
    menu_config JSONB,
    dashboard_config JSONB,
    backed_up_at TIMESTAMP DEFAULT NOW()
);

-- =============================================================================
-- STEP 2: Backup current configurations
-- =============================================================================
INSERT INTO _backup_role_menu_config_phase1 (role_code, menu_config, dashboard_config)
SELECT code, menu_config, dashboard_config
FROM roles
WHERE code IN (
    'agent_cnedoge_pasaporte',
    'agent_cnedoge_residencia',
    'agent_dgt',
    'agent_ofive',
    'agent_onrc'
)
ON CONFLICT (role_code) DO UPDATE SET
    menu_config = EXCLUDED.menu_config,
    dashboard_config = EXCLUDED.dashboard_config,
    backed_up_at = NOW();

-- =============================================================================
-- STEP 3: Enable auto-generation by setting menu_config to NULL
-- =============================================================================
UPDATE roles
SET menu_config = NULL,
    dashboard_config = NULL,
    updated_at = NOW()
WHERE code IN (
    'agent_cnedoge_pasaporte',
    'agent_cnedoge_residencia',
    'agent_dgt',
    'agent_ofive',
    'agent_onrc'
);

-- =============================================================================
-- STEP 4: Verification
-- =============================================================================
DO $$
DECLARE
    v_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO v_count
    FROM roles
    WHERE code IN (
        'agent_cnedoge_pasaporte',
        'agent_cnedoge_residencia',
        'agent_dgt',
        'agent_ofive',
        'agent_onrc'
    )
    AND menu_config IS NULL;

    IF v_count != 5 THEN
        RAISE EXCEPTION 'Migration verification failed: expected 5 roles with NULL menu_config, found %', v_count;
    END IF;

    RAISE NOTICE 'Migration 085 Phase 1 completed: % roles now use auto-generation', v_count;
END;
$$;

COMMIT;

-- =============================================================================
-- ROLLBACK SCRIPT (if needed)
-- =============================================================================
-- To rollback, run:
/*
UPDATE roles r
SET menu_config = b.menu_config,
    dashboard_config = b.dashboard_config,
    updated_at = NOW()
FROM _backup_role_menu_config_phase1 b
WHERE r.code = b.role_code;
*/
