-- ============================================================================
-- Migration 091: Add entity_code to appointment_delay_rules
-- ============================================================================
-- Purpose:
--   Enable 3-level delay cascade: workflow > entity > global default
--   This allows different entities (CNEDOGE_PASAPORTE, DGT, EXTRANJERIA)
--   to have different appointment delay rules without creating per-workflow rules.
--
-- Cascade logic in _get_delay_days():
--   P1: workflow_code specific (most precise)
--   P2: entity_code specific, workflow_code IS NULL (entity-level)
--   P3: both NULL (global default)
--
-- Date: 2026-02-10
-- ============================================================================

BEGIN;

-- 1. Add entity_code column (nullable = global rules keep NULL)
ALTER TABLE appointment_delay_rules
ADD COLUMN IF NOT EXISTS entity_code VARCHAR(50);

-- 2. Drop old unique constraint and create new one including entity_code
ALTER TABLE appointment_delay_rules
DROP CONSTRAINT IF EXISTS unique_delay_rule;

ALTER TABLE appointment_delay_rules
ADD CONSTRAINT unique_delay_rule UNIQUE (entity_code, workflow_code, priority);

-- 3. Index for entity-specific lookups
CREATE INDEX IF NOT EXISTS idx_adr_entity
ON appointment_delay_rules(entity_code)
WHERE entity_code IS NOT NULL;

-- 4. Seed entity-specific delay rules for entities with active appointments
-- CNEDOGE_PASAPORTE: standard processing (3 days)
INSERT INTO appointment_delay_rules (entity_code, workflow_code, priority, delay_business_days, is_active) VALUES
('CNEDOGE_PASAPORTE', NULL, 'URGENT', 1, TRUE),
('CNEDOGE_PASAPORTE', NULL, 'NORMAL', 3, TRUE),
('CNEDOGE_PASAPORTE', NULL, 'LOW', 5, TRUE)
ON CONFLICT (entity_code, workflow_code, priority) DO NOTHING;

-- DGT: faster processing for vehicle services (2 days normal)
INSERT INTO appointment_delay_rules (entity_code, workflow_code, priority, delay_business_days, is_active) VALUES
('DGT', NULL, 'URGENT', 1, TRUE),
('DGT', NULL, 'NORMAL', 2, TRUE),
('DGT', NULL, 'LOW', 4, TRUE)
ON CONFLICT (entity_code, workflow_code, priority) DO NOTHING;

-- EXTRANJERIA: longer processing for immigration (5 days normal)
INSERT INTO appointment_delay_rules (entity_code, workflow_code, priority, delay_business_days, is_active) VALUES
('EXTRANJERIA', NULL, 'URGENT', 2, TRUE),
('EXTRANJERIA', NULL, 'NORMAL', 5, TRUE),
('EXTRANJERIA', NULL, 'LOW', 7, TRUE)
ON CONFLICT (entity_code, workflow_code, priority) DO NOTHING;

-- MINFP: civil service standard (3 days)
INSERT INTO appointment_delay_rules (entity_code, workflow_code, priority, delay_business_days, is_active) VALUES
('MINFP', NULL, 'URGENT', 1, TRUE),
('MINFP', NULL, 'NORMAL', 3, TRUE),
('MINFP', NULL, 'LOW', 5, TRUE)
ON CONFLICT (entity_code, workflow_code, priority) DO NOTHING;

COMMENT ON COLUMN appointment_delay_rules.entity_code IS 'NULL = global default. When set, applies to all workflows of this entity unless overridden by workflow-specific rule.';

COMMIT;
