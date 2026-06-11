-- ============================================================================
-- Migration 043: Fix payment_type constraint
-- ============================================================================
-- Purpose: The CHECK constraint on payment_type only allows 'expedition' and
-- 'renewal', but the code uses the payment_type_enum values ('full', 'partial',
-- 'installment', 'complementary').
--
-- Fix: Drop the old CHECK and update to use the correct enum values.
-- ============================================================================

BEGIN;

-- Drop the incorrect CHECK constraint
ALTER TABLE service_payments
DROP CONSTRAINT IF EXISTS service_payments_payment_type_check;

-- Add new constraint with correct values from payment_type_enum
ALTER TABLE service_payments
ADD CONSTRAINT service_payments_payment_type_check
CHECK (payment_type IN ('full', 'partial', 'installment', 'complementary', 'expedition', 'renewal'));

-- Verification
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = 'service_payments'::regclass
        AND conname = 'service_payments_payment_type_check'
    ) THEN
        RAISE EXCEPTION 'Constraint was not created!';
    END IF;

    RAISE NOTICE 'Migration 043 completed: payment_type constraint updated';
END $$;

COMMIT;
