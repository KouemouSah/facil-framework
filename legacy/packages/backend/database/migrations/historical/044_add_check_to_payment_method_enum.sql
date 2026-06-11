-- ============================================================================
-- Migration 044: Add 'check' to payment_method_enum
-- ============================================================================
-- Purpose: The Python code defines PaymentMethod.CHECK = "check" but the
-- database enum doesn't have this value, causing payment failures.
-- ============================================================================

BEGIN;

-- Add 'check' to the enum if it doesn't exist
DO $$
BEGIN
    -- Check if 'check' already exists in the enum
    IF NOT EXISTS (
        SELECT 1 FROM pg_enum
        WHERE enumtypid = 'payment_method_enum'::regtype
        AND enumlabel = 'check'
    ) THEN
        ALTER TYPE payment_method_enum ADD VALUE 'check';
        RAISE NOTICE 'Added check to payment_method_enum';
    ELSE
        RAISE NOTICE 'check already exists in payment_method_enum';
    END IF;
END $$;

COMMIT;

-- Verify (outside transaction because ADD VALUE needs to commit first)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_enum
        WHERE enumtypid = 'payment_method_enum'::regtype
        AND enumlabel = 'check'
    ) THEN
        RAISE EXCEPTION 'check was not added to payment_method_enum!';
    END IF;
    RAISE NOTICE 'Migration 044 completed: check added to payment_method_enum';
END $$;
