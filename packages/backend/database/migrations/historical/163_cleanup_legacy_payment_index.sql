-- ================================================================
-- Migration 163: Cleanup duplicate legacy index
--
-- After migration 162 renamed bank_transactions.payment_id to
-- service_payment_id, PostgreSQL auto-renamed the old index
-- idx_bank_transactions_payment_id to point at service_payment_id.
-- This duplicates idx_bank_transactions_service_payment_id.
-- ================================================================

DROP INDEX IF EXISTS idx_bank_transactions_payment_id;
