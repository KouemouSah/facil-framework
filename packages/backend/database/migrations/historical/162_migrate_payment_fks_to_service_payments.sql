-- ================================================================
-- Migration 162: Migrate ALL payment FKs from payments → service_payments
--
-- SAFETY: ALL tables have 0 rows with payment_id values. Zero data loss.
--
-- Tables migrated:
--   1. bank_transactions.payment_id  → service_payment_id (renamed + FK)
--   2. payment_receipts.payment_id   → service_payment_id (renamed + FK)
--   3. uploaded_files.payment_id     → service_payment_id (renamed + FK)
--   4. fiscal_service_data.payment_id → DROPPED (no longer relevant)
--
-- NOT touched (dormant, 0 rows):
--   - payment_plans.payment_id → payments.id (installments feature, unused)
--   - payment_installments → depends on payment_plans
-- ================================================================

BEGIN;

-- ===== 1. bank_transactions =====
ALTER TABLE bank_transactions DROP CONSTRAINT fk_bank_transactions_payment;
ALTER TABLE bank_transactions RENAME COLUMN payment_id TO service_payment_id;
ALTER TABLE bank_transactions
  ADD CONSTRAINT fk_bank_transactions_service_payment
  FOREIGN KEY (service_payment_id) REFERENCES service_payments(id);

-- ===== 2. payment_receipts =====
ALTER TABLE payment_receipts DROP CONSTRAINT payment_receipts_payment_id_fkey;
ALTER TABLE payment_receipts RENAME COLUMN payment_id TO service_payment_id;
ALTER TABLE payment_receipts
  ADD CONSTRAINT payment_receipts_service_payment_id_fkey
  FOREIGN KEY (service_payment_id) REFERENCES service_payments(id);

-- ===== 3. uploaded_files =====
ALTER TABLE uploaded_files DROP CONSTRAINT uploaded_files_payment_id_fkey;
ALTER TABLE uploaded_files RENAME COLUMN payment_id TO service_payment_id;
ALTER TABLE uploaded_files
  ADD CONSTRAINT uploaded_files_service_payment_id_fkey
  FOREIGN KEY (service_payment_id) REFERENCES service_payments(id);

-- ===== 4. fiscal_service_data: DROP column =====
ALTER TABLE fiscal_service_data DROP CONSTRAINT fiscal_service_data_payment_id_fkey;
ALTER TABLE fiscal_service_data DROP COLUMN payment_id;

-- ===== Indexes for reconciliation performance =====
CREATE INDEX idx_bank_transactions_service_payment_id
  ON bank_transactions(service_payment_id) WHERE service_payment_id IS NOT NULL;

CREATE INDEX idx_bank_transactions_unreconciled
  ON bank_transactions(bank_transaction_date DESC)
  WHERE status = 'unreconciled';

CREATE INDEX idx_service_payments_reconciliation
  ON service_payments(currency, workflow_status, validated_at DESC)
  WHERE workflow_status = 'completed';

COMMIT;
