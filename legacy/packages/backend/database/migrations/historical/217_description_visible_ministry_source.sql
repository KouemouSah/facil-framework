-- Migration 217: description_visible toggle + ministry description_source
-- Date: 2026-03-13
-- Purpose:
--   F1: Admin can toggle visibility of service descriptions on public site
--   F2: Track source of ministry descriptions (manual vs AI draft)
--   F3: Enable ministry tasks in enrichment_queue (polymorphic entity_id)

BEGIN;

-- F1: description_visible on fiscal_services (default true = backward-compatible)
ALTER TABLE fiscal_services ADD COLUMN IF NOT EXISTS description_visible BOOLEAN DEFAULT true;

-- F2: description_source on ministries (NULL = unknown/legacy, 'manual', 'ai_draft', 'ai_generated')
ALTER TABLE ministries ADD COLUMN IF NOT EXISTS description_source VARCHAR(20) DEFAULT NULL;

-- Backfill: existing descriptions are manual
UPDATE ministries
SET description_source = 'manual'
WHERE description_es IS NOT NULL AND description_es != ''
  AND (description_source IS NULL);

-- F2: Expand enrichment_queue task_type CHECK to include ministry descriptions
ALTER TABLE enrichment_queue DROP CONSTRAINT IF EXISTS enrichment_queue_task_type_check;
ALTER TABLE enrichment_queue ADD CONSTRAINT enrichment_queue_task_type_check
  CHECK (task_type::text = ANY(ARRAY[
    'generate_description',
    'generate_keywords',
    'translate_fr',
    'translate_en',
    'generate_ministry_description'
  ]::text[]));

-- F3: Drop FK constraint on fiscal_service_id so it can store ministry IDs too.
-- The column becomes a polymorphic entity_id (type inferred from task_type).
-- Existing data integrity is preserved: all current rows reference fiscal_services.
ALTER TABLE enrichment_queue DROP CONSTRAINT IF EXISTS enrichment_queue_fiscal_service_id_fkey;

-- Add a comment documenting the polymorphic usage
COMMENT ON COLUMN enrichment_queue.fiscal_service_id IS
  'Polymorphic entity ID: fiscal_services.id for service tasks, ministries.id for ministry tasks. Type inferred from task_type column.';

COMMIT;
