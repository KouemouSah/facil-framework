-- Migration 250: Add field collection columns to service_payments + receipt sequence
-- Date: 2026-03-20
-- Fixes: C1 (missing columns), C2 (receipt sequence), m10 (collection_type)

BEGIN;

-- 1. Add field collection columns to service_payments
ALTER TABLE service_payments ADD COLUMN IF NOT EXISTS collection_type VARCHAR(20)
    DEFAULT 'office'
    CHECK (collection_type IN ('office', 'field', 'online'));

ALTER TABLE service_payments ADD COLUMN IF NOT EXISTS collected_by UUID REFERENCES users(id);

ALTER TABLE service_payments ADD COLUMN IF NOT EXISTS field_inspection_id UUID REFERENCES field_inspections(id);

-- Index for treasury reconciliation queries
CREATE INDEX IF NOT EXISTS idx_sp_collection_type
    ON service_payments(collection_type, created_at DESC)
    WHERE collection_type = 'field';

-- 2. Add agent_signature column for digital signature capture
ALTER TABLE field_inspections ADD COLUMN IF NOT EXISTS agent_signature TEXT;

-- 3. Create a proper sequence for field receipt numbers (fix C2)
CREATE SEQUENCE IF NOT EXISTS field_receipt_seq START 1;

COMMIT;
