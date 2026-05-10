-- ============================================================================
-- Migration 167: Payment Architecture Coherence Corrections
--
-- Fixes 10 DB inconsistencies discovered during multi-gateway audit:
-- 1. Renames bange_transaction_id → gateway_transaction_id (multi-gateway)
-- 2. Drops dead bange_wallet_id column
-- 3. Adds missing batch_requests.gateway_transaction_id (latent crash fix)
-- 4. Fixes bank_configurations: real treasury accounts, gateway flags
-- 5. Fixes payment_method_configurations: processor_type + requires_redirect
-- 6. Adds performance indexes for 1M+ payment scale
--
-- ECOBANK = primary gateway, BANGE = fallback
-- Supersedes migration 166 (never applied)
-- ============================================================================

-- ==========================================================================
-- 1. Rename bange_transaction_id → gateway_transaction_id (service_payments)
--    PostgreSQL RENAME COLUMN = metadata-only, instant regardless of table size
-- ==========================================================================
ALTER TABLE service_payments
    RENAME COLUMN bange_transaction_id TO gateway_transaction_id;

ALTER INDEX service_payments_bange_transaction_id_key
    RENAME TO idx_service_payments_gateway_txn_id;

COMMENT ON COLUMN service_payments.gateway_transaction_id
    IS 'External transaction ID from bank gateway (BANGE, Ecobank, etc.)';

-- ==========================================================================
-- 2. Drop dead column bange_wallet_id (never used, no non-null values)
-- ==========================================================================
ALTER TABLE service_payments
    DROP COLUMN IF EXISTS bange_wallet_id;

-- ==========================================================================
-- 3. Add gateway_transaction_id to batch_requests (fix latent crash)
--    Code writes to this column but it never existed in the table
-- ==========================================================================
ALTER TABLE batch_requests
    ADD COLUMN IF NOT EXISTS gateway_transaction_id VARCHAR(255);

CREATE UNIQUE INDEX IF NOT EXISTS idx_batch_gateway_txn
    ON batch_requests(gateway_transaction_id)
    WHERE gateway_transaction_id IS NOT NULL;

-- ==========================================================================
-- 4. Add multi-gateway columns to bank_configurations
-- ==========================================================================
ALTER TABLE bank_configurations
    ADD COLUMN IF NOT EXISTS gateway_type VARCHAR(50),
    ADD COLUMN IF NOT EXISTS supported_payment_methods JSONB DEFAULT '[]'::jsonb,
    ADD COLUMN IF NOT EXISTS is_primary BOOLEAN DEFAULT false;

-- ==========================================================================
-- 5. Fix bank_configurations: real treasury accounts + correct flags
-- ==========================================================================

-- ECOBANK: PRIMARY gateway
UPDATE bank_configurations SET
    treasury_account_number = '39360000063-01',
    supports_direct_integration = true,
    supports_webhooks = true,
    gateway_type = 'ecobank',
    supported_payment_methods = '["mobile_money","card","bank_transfer"]'::jsonb,
    is_primary = true,
    updated_at = NOW()
WHERE bank_code = 'ECOBANK';

-- BANGE: fallback gateway
UPDATE bank_configurations SET
    treasury_account_number = '37100036801-37',
    supports_direct_integration = true,
    supports_webhooks = true,
    gateway_type = 'bange',
    supported_payment_methods = '["mobile_money","card","bank_transfer"]'::jsonb,
    is_primary = false,
    updated_at = NOW()
WHERE bank_code = 'BANGE';

-- BGFI: not integrated, real account
UPDATE bank_configurations SET
    treasury_account_number = '00106046001-15',
    gateway_type = NULL,
    supported_payment_methods = '[]'::jsonb,
    is_primary = false,
    updated_at = NOW()
WHERE bank_code = 'BGFI';

-- CCEIBANK: not integrated, real account
UPDATE bank_configurations SET
    treasury_account_number = '00000161001-22',
    gateway_type = NULL,
    supported_payment_methods = '[]'::jsonb,
    is_primary = false,
    updated_at = NOW()
WHERE bank_code = 'CCEIBANK';

-- SGBGE: not integrated, real account
UPDATE bank_configurations SET
    treasury_account_number = '27110104801-87',
    gateway_type = NULL,
    supported_payment_methods = '[]'::jsonb,
    is_primary = false,
    updated_at = NOW()
WHERE bank_code = 'SGBGE';

-- Column comments
COMMENT ON COLUMN bank_configurations.gateway_type
    IS 'Gateway implementation type: bange, ecobank, null (not integrated)';
COMMENT ON COLUMN bank_configurations.supported_payment_methods
    IS 'JSON array of payment methods: mobile_money, card, bank_transfer';
COMMENT ON COLUMN bank_configurations.is_primary
    IS 'If true, this gateway is the primary processor for its supported methods';

-- ==========================================================================
-- 6. Fix payment_method_configurations: processor_type + requires_redirect
-- ==========================================================================

-- Update processor_type from legacy 'bange_api' to generic 'gateway_api'
UPDATE payment_method_configurations
SET processor_type = 'gateway_api', updated_at = NOW()
WHERE processor_type = 'bange_api';

-- Fix requires_redirect for electronic methods (they redirect to bank page)
UPDATE payment_method_configurations
SET requires_redirect = true, updated_at = NOW()
WHERE code IN ('mobile_money', 'card', 'bank_transfer')
  AND requires_redirect = false;

-- ==========================================================================
-- 7. Performance indexes for 1M+ payment scale
-- ==========================================================================

-- Partial index for pending gateway payments (SLA monitoring, cron jobs)
CREATE INDEX IF NOT EXISTS idx_sp_gateway_pending
    ON service_payments(created_at)
    WHERE status IN ('pending', 'processing')
      AND gateway_transaction_id IS NOT NULL;

-- Composite index for reconciliation lookups (webhook handler)
CREATE INDEX IF NOT EXISTS idx_sp_reference_status
    ON service_payments(payment_reference, status);

-- Partial index for unreconciled bank transactions
CREATE INDEX IF NOT EXISTS idx_bt_unreconciled
    ON bank_transactions(created_at)
    WHERE status = 'unreconciled';
