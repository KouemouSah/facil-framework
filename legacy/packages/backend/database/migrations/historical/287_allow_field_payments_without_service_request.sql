-- Migration 287: Unified payment dossier — 1 licence/year = 1 service_request = N payments
--
-- Enables field collection to find-or-create a service_request per company/year.
-- Citizen payments and field collections share the same dossier.
--
-- Changes:
--   1. FIELD_INSPECTION workflow code (for dossiers created by field agents)
--   2. source column on service_requests (who created the dossier)
--   3. Index for fast company+year lookup

BEGIN;

-- 0. REVERT previous constraint modification (if applied)
-- Restore original: service_request_id required for all post-2026-01-11 payments
-- Field collections now always have a service_request_id (unified dossier)
ALTER TABLE service_payments
DROP CONSTRAINT IF EXISTS chk_service_request_required;

ALTER TABLE service_payments
ADD CONSTRAINT chk_service_request_required
CHECK (
    service_request_id IS NOT NULL
    OR created_at < '2026-01-11'::date
);

-- 1. Register FIELD_INSPECTION as a valid workflow code
INSERT INTO valid_workflow_codes (code, base_code, resolution_key, is_active)
VALUES ('FIELD_INSPECTION', NULL, 'FIELD', TRUE)
ON CONFLICT (code) DO NOTHING;

INSERT INTO workflows (code, name_es, is_active)
VALUES ('FIELD_INSPECTION', 'Inspeccion de Campo', TRUE)
ON CONFLICT (code) DO NOTHING;

-- 2. Add source column to track who created the dossier
ALTER TABLE service_requests
ADD COLUMN IF NOT EXISTS source VARCHAR(30) DEFAULT 'citizen_wizard';

-- Add check constraint only if it doesn't exist
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'chk_sr_source' AND conrelid = 'service_requests'::regclass
    ) THEN
        ALTER TABLE service_requests
        ADD CONSTRAINT chk_sr_source
        CHECK (source IN ('citizen_wizard', 'field_inspection', 'admin_import', 'batch'));
    END IF;
END $$;

COMMENT ON COLUMN service_requests.source IS
    'Origin of this dossier: citizen_wizard (online), field_inspection (agent terrain), admin_import (migration), batch (bulk)';

-- 3. Index for fast company+year lookup (find existing dossier)
CREATE INDEX IF NOT EXISTS idx_sr_company_year_active
ON service_requests (company_id, created_at DESC)
WHERE status NOT IN ('cancelled', 'rejected');

COMMIT;
