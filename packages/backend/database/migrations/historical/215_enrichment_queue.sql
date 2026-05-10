-- Migration 215: Enrichment Queue for automatic Gemini-powered service enrichment
-- Adds description_source tracking + async enrichment task queue

-- 1. Add description_source to fiscal_services
ALTER TABLE fiscal_services ADD COLUMN IF NOT EXISTS description_source VARCHAR(20) DEFAULT 'manual';

-- Backfill: existing non-null descriptions are manual
UPDATE fiscal_services
SET description_source = 'manual'
WHERE description_es IS NOT NULL AND description_es != ''
  AND (description_source IS NULL OR description_source = 'manual');

-- 2. Enrichment queue table
CREATE TABLE IF NOT EXISTS enrichment_queue (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    fiscal_service_id INT NOT NULL REFERENCES fiscal_services(id) ON DELETE CASCADE,
    task_type VARCHAR(30) NOT NULL CHECK (task_type IN (
        'generate_description', 'generate_keywords',
        'translate_fr', 'translate_en'
    )),
    status VARCHAR(20) NOT NULL DEFAULT 'pending' CHECK (status IN (
        'pending', 'processing', 'completed', 'failed', 'skipped'
    )),
    priority INT NOT NULL DEFAULT 0,
    attempts INT NOT NULL DEFAULT 0,
    max_attempts INT NOT NULL DEFAULT 3,
    input_data JSONB,
    output_data JSONB,
    tokens_used INT,
    error_message TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    processed_at TIMESTAMPTZ
);

-- Partial index for efficient queue polling (only pending tasks)
CREATE INDEX IF NOT EXISTS idx_enrichment_pending
    ON enrichment_queue(status, priority DESC, created_at)
    WHERE status = 'pending';

-- Index for admin stats and lookups by service
CREATE INDEX IF NOT EXISTS idx_enrichment_service
    ON enrichment_queue(fiscal_service_id, task_type);

COMMENT ON TABLE enrichment_queue IS 'Async queue for Gemini-powered service enrichment (descriptions, translations, keywords)';
COMMENT ON COLUMN enrichment_queue.task_type IS 'generate_description | generate_keywords | translate_fr | translate_en';
COMMENT ON COLUMN enrichment_queue.status IS 'pending → processing → completed/failed/skipped';
COMMENT ON COLUMN fiscal_services.description_source IS 'manual (human) | ai_generated (Gemini) — ai_generated can be overwritten by manual';
