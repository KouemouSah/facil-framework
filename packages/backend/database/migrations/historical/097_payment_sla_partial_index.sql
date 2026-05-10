-- Migration 097: Payment SLA partial index + set expires_at for existing cash payments
-- Purpose: Optimize SLA cron queries + initialize expires_at for cash payments missing it

-- Partial index for cash/check payments pending validation (used by SLA cron)
CREATE INDEX IF NOT EXISTS idx_service_payments_cash_pending_sla
ON service_payments (created_at)
WHERE payment_method IN ('cash', 'check')
  AND status = 'pending'
  AND validated_at IS NULL;

-- Set expires_at for existing cash payments that don't have it (15 days from creation)
UPDATE service_payments
SET expires_at = created_at + INTERVAL '15 days'
WHERE payment_method IN ('cash', 'check')
  AND status = 'pending'
  AND validated_at IS NULL
  AND expires_at IS NULL;
