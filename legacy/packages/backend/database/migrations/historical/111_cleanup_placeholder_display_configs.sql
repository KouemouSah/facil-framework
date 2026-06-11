-- Migration 111: Soft-delete 34 placeholder display configs
--
-- Problem: 34 out of 35 workflow_display_config rows contain phantom data:
--   - list_columns = ["reference", "beneficiary", "status", "created_at"]
--     → "beneficiary" does NOT exist as a system column or extracted field
--     → "created_at" uses snake_case but frontend expects "createdAt" (camelCase)
--   - preview_sections = ["identity", "documents"]
--     → "identity" does NOT exist as a valid section (valid: info, extractedData, etc.)
--
-- These configs were created via direct SQL/API, NOT through the admin form.
-- The admin form (DisplayConfigForm.tsx) already prevents selecting invalid values.
--
-- Impact: Without these configs, the system falls back to DEFAULT_LIST_COLUMNS
-- and DEFAULT_PREVIEW_SECTIONS which provide a BETTER agent experience.
--
-- Preserved: PASAPORTE_DETERIORO (ID=13) — the only config with real extracted columns.
--
-- Date: 2026-02-18

BEGIN;

-- Soft-delete all placeholder configs (matching the phantom pattern)
UPDATE workflow_display_config
SET is_active = false,
    deleted_at = NOW(),
    updated_at = NOW()
WHERE list_columns = '["reference", "beneficiary", "status", "created_at"]'::jsonb
  AND is_active = true;

-- Verify: only PASAPORTE_DETERIORO should remain active
DO $$
DECLARE
    active_count INTEGER;
    deleted_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO active_count
    FROM workflow_display_config WHERE is_active = true;

    SELECT COUNT(*) INTO deleted_count
    FROM workflow_display_config WHERE is_active = false AND deleted_at >= NOW() - INTERVAL '1 minute';

    RAISE NOTICE 'Soft-deleted % placeholder configs. % active configs remaining.', deleted_count, active_count;

    IF active_count != 1 THEN
        RAISE WARNING 'Expected 1 active config (PASAPORTE_DETERIORO), got %. Please verify.', active_count;
    END IF;
END $$;

COMMIT;
