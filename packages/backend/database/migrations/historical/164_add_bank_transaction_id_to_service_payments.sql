-- ================================================================
-- Migration 164: Add bank_transaction_id to service_payments
--
-- PROBLEM: webhook_repository.py:reconcile() does
--   UPDATE service_payments SET bank_transaction_id = $2
-- but the column does NOT exist -> crashes every reconciliation.
--
-- FIX: Add the column with FK to bank_transactions + unique index.
-- Backfill any already-reconciled links (currently 0 rows).
-- ================================================================

-- 1. Add the column
ALTER TABLE service_payments
  ADD COLUMN bank_transaction_id UUID REFERENCES bank_transactions(id);

-- 2. Unique partial index: one bank_transaction can link to at most one service_payment
CREATE UNIQUE INDEX idx_service_payments_bank_transaction_id
  ON service_payments(bank_transaction_id)
  WHERE bank_transaction_id IS NOT NULL;

-- 3. Backfill: for any already-reconciled bank_transactions, set the reverse link
UPDATE service_payments sp
SET bank_transaction_id = bt.id
FROM bank_transactions bt
WHERE bt.service_payment_id = sp.id
  AND bt.status = 'reconciled'
  AND sp.bank_transaction_id IS NULL;
