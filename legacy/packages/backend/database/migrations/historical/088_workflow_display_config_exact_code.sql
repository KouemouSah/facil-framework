-- Migration 088: Migrate workflow_display_config from pattern (LIKE) to exact code
-- Purpose: Enable exact workflow_code matching instead of SQL LIKE patterns
-- Date: 2026-02-02
-- Part of: Display Config Architecture Migration

-- =============================================================================
-- OVERVIEW
-- =============================================================================
-- This migration changes the display config system from pattern-based matching
-- (e.g., 'PASAPORTE_%' with LIKE) to exact workflow_code matching.
--
-- Benefits:
-- - More predictable and performant queries (= vs LIKE)
-- - Better integration with service_request_workflows table
-- - Cleaner configuration per exact workflow
--
-- Strategy:
-- - Rename column: workflow_pattern → workflow_code
-- - Archive existing pattern configs (set is_active = false)
-- - Create unique index on workflow_code
-- - Configs will be created on-demand when users customize
-- =============================================================================

BEGIN;

-- =============================================================================
-- STEP 1: Rename column
-- =============================================================================

-- Rename the column from workflow_pattern to workflow_code
ALTER TABLE workflow_display_config
RENAME COLUMN workflow_pattern TO workflow_code;

-- =============================================================================
-- STEP 2: Update column size (100 chars for longer workflow codes)
-- =============================================================================

ALTER TABLE workflow_display_config
ALTER COLUMN workflow_code TYPE VARCHAR(100);

-- =============================================================================
-- STEP 3: Drop old index and create new unique index
-- =============================================================================

-- Drop the old pattern-based index
DROP INDEX IF EXISTS idx_workflow_display_config_pattern;

-- Create new unique index on workflow_code (allows only one config per workflow)
CREATE UNIQUE INDEX idx_workflow_display_config_code
ON workflow_display_config(workflow_code)
WHERE is_active = true;

-- =============================================================================
-- STEP 4: Update comments
-- =============================================================================

COMMENT ON TABLE workflow_display_config IS
'Configuration for PendingPage display per exact workflow code. Replaced pattern-based system in migration 088.';

COMMENT ON COLUMN workflow_display_config.workflow_code IS
'Exact workflow code (e.g., PASAPORTE_EXPEDICION_ADULTO). No wildcard patterns. Must match service_request_workflows.code.';

-- =============================================================================
-- STEP 5: Archive old pattern-based configs
-- =============================================================================

-- Deactivate configs that contain SQL wildcard characters (%, _)
-- These were the old pattern-based configs that won't work with exact matching
UPDATE workflow_display_config
SET is_active = false,
    updated_at = NOW()
WHERE workflow_code LIKE '%\%%' ESCAPE '\'
   OR workflow_code LIKE '%\_%' ESCAPE '\';

-- Log what was archived (for debugging)
DO $$
DECLARE
    archived_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO archived_count
    FROM workflow_display_config
    WHERE is_active = false
      AND (workflow_code LIKE '%\%%' ESCAPE '\' OR workflow_code LIKE '%\_%' ESCAPE '\');

    IF archived_count > 0 THEN
        RAISE NOTICE 'Archived % pattern-based configs. They remain in DB but inactive.', archived_count;
    END IF;
END $$;

-- =============================================================================
-- STEP 6: Add deleted_at column for soft deletes (was missing)
-- =============================================================================

-- Add deleted_at column if not exists
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'workflow_display_config' AND column_name = 'deleted_at'
    ) THEN
        ALTER TABLE workflow_display_config ADD COLUMN deleted_at TIMESTAMPTZ DEFAULT NULL;
        COMMENT ON COLUMN workflow_display_config.deleted_at IS 'Soft delete timestamp';
    END IF;
END $$;

COMMIT;

-- =============================================================================
-- VERIFICATION QUERIES (run after migration)
-- =============================================================================

-- Check new column structure:
-- SELECT column_name, data_type, character_maximum_length
-- FROM information_schema.columns
-- WHERE table_name = 'workflow_display_config';

-- Check index:
-- SELECT indexname, indexdef FROM pg_indexes WHERE tablename = 'workflow_display_config';

-- Check archived configs:
-- SELECT workflow_code, is_active FROM workflow_display_config ORDER BY is_active DESC;

-- =============================================================================
-- ROLLBACK SCRIPT (if needed)
-- =============================================================================
-- BEGIN;
-- ALTER TABLE workflow_display_config RENAME COLUMN workflow_code TO workflow_pattern;
-- ALTER TABLE workflow_display_config ALTER COLUMN workflow_pattern TYPE VARCHAR(50);
-- DROP INDEX IF EXISTS idx_workflow_display_config_code;
-- CREATE INDEX idx_workflow_display_config_pattern ON workflow_display_config(workflow_pattern);
-- UPDATE workflow_display_config SET is_active = true WHERE workflow_pattern LIKE '%\%%' ESCAPE '\';
-- COMMIT;
