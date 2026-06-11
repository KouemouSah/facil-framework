-- ============================================================================
-- Migration 086: Drop unused menu_templates table
-- ============================================================================
-- Purpose: Clean up the menu_templates table that is no longer used
--
-- Background:
--   - menu_templates was created in migration 063 for reusable menu templates
--   - The feature was never implemented - all frontend/backend code was removed
--   - Menu configuration now uses:
--     1. workflow_menu_mapping table for auto-generated menus
--     2. roles.menu_config JSONB column for explicit configurations
--   - This migration removes the orphaned table, its indexes, trigger and function
--
-- Dependencies checked:
--   - No foreign keys reference menu_templates from other tables
--   - menu_templates.created_by references users(id) - will be dropped with table
--   - Trigger: tr_menu_templates_updated_at - must be dropped
--   - Function: update_menu_templates_updated_at() - must be dropped
--   - No views depend on this table
--
-- Author: Claude Code Expert
-- Date: 2026-01-31
-- ============================================================================

BEGIN;

-- =============================================================================
-- 1. DROP TRIGGER (must be dropped before table)
-- =============================================================================

DROP TRIGGER IF EXISTS tr_menu_templates_updated_at ON menu_templates;

-- =============================================================================
-- 2. DROP TABLE: menu_templates (indexes are dropped automatically)
-- =============================================================================

DROP TABLE IF EXISTS menu_templates;

-- =============================================================================
-- 3. DROP FUNCTION (only used by the trigger we just dropped)
-- =============================================================================

DROP FUNCTION IF EXISTS update_menu_templates_updated_at();

-- Log the action
DO $$
BEGIN
    RAISE NOTICE 'Migration 086: Dropped menu_templates table, trigger and function (unused feature)';
END $$;

COMMIT;
