-- Migration 297: Relax bundle SR unique index for partial payments
--
-- Problem: idx_sr_commercial_license_unique enforces 1 SR per license
-- regardless of SR status. A citizen who fully paid 8/10 obligations
-- (SR status = PAID) cannot create a 2nd bundle for the remaining 2
-- because the index blocks the INSERT.
--
-- Fix: Scope the unique index to non-terminal SR statuses only.
-- Terminal statuses (PAID, EXPIRED, CANCELLED, REJECTED) allow a new SR.
--
-- Idempotent: safe to run multiple times.

-- Drop the old unconditional index
DROP INDEX IF EXISTS idx_sr_commercial_license_unique;

-- Recreate with terminal-status exclusion
-- Only enforce uniqueness for in-flight bundle SRs
CREATE UNIQUE INDEX idx_sr_commercial_license_unique
    ON service_requests (commercial_license_id)
    WHERE commercial_license_id IS NOT NULL
      AND status NOT IN ('PAID', 'EXPIRED');
