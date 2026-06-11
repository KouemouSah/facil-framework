-- ============================================================================
-- MIGRATION 146: Add entity_code to service_payments (denormalization)
-- Date: 2026-03-01
-- Context: service_payments.ministry_id is ALWAYS NULL because the trigger
--          calculate_payment_ministry() derives ministry from fiscal_service_id
--          which is NULL for all modern service_requests (they use workflow_code).
--          The real organizational dimension is entity_code on service_requests.
--          This migration:
--            1. Adds entity_code VARCHAR(50) to service_payments
--            2. Backfills entity_code from service_requests
--            3. Backfills ministry_id from entities (where available)
--            4. Rewrites the trigger to populate both correctly
--            5. Replaces ministry-based index with entity-based index
-- ============================================================================

BEGIN;

-- Step 1: Add entity_code column (nullable first for backfill)
ALTER TABLE service_payments ADD COLUMN IF NOT EXISTS entity_code VARCHAR(50);

-- Step 2: Backfill entity_code from service_requests
UPDATE service_payments sp
SET entity_code = sr.entity_code
FROM service_requests sr
WHERE sr.id = sp.service_request_id
  AND sp.entity_code IS NULL;

-- Step 3: Backfill ministry_id from entities (fix the NULL issue)
-- Only update if entity has a ministry_id (4 out of 12 entities do)
UPDATE service_payments sp
SET ministry_id = e.ministry_id
FROM service_requests sr
JOIN entities e ON e.code = sr.entity_code
WHERE sr.id = sp.service_request_id
  AND e.ministry_id IS NOT NULL
  AND (sp.ministry_id IS NULL OR sp.ministry_id != e.ministry_id);

-- Step 4: For payments without service_request_id, default entity_code
-- (legacy payments or orphans — should be 0 in current data)
UPDATE service_payments
SET entity_code = 'UNKNOWN'
WHERE entity_code IS NULL AND service_request_id IS NULL;

-- Step 5: Verify backfill completeness
DO $$
DECLARE
    v_null_count INTEGER;
    v_total INTEGER;
BEGIN
    SELECT COUNT(*) INTO v_null_count FROM service_payments WHERE entity_code IS NULL;
    SELECT COUNT(*) INTO v_total FROM service_payments;

    IF v_null_count > 0 THEN
        RAISE EXCEPTION 'Migration 146: % payments still have NULL entity_code (out of %)', v_null_count, v_total;
    END IF;

    RAISE NOTICE 'Migration 146: Backfill complete — % payments, 0 NULL entity_code', v_total;
END $$;

-- Step 6: Set NOT NULL constraint
ALTER TABLE service_payments ALTER COLUMN entity_code SET NOT NULL;

-- Step 7: Rewrite trigger to populate entity_code + ministry_id from entities
CREATE OR REPLACE FUNCTION calculate_payment_ministry()
RETURNS TRIGGER AS $$
DECLARE
    v_entity_code VARCHAR(50);
    v_ministry_id INTEGER;
    v_is_manual_payment BOOLEAN;
    v_config ministry_validation_config%ROWTYPE;
    v_service_type TEXT;
BEGIN
    -- Check if this is a manual payment (cash/check)
    v_is_manual_payment := NEW.payment_method IN ('cash', 'check');

    -- If no service_request_id, set defaults only for manual payments
    IF NEW.service_request_id IS NULL THEN
        NEW.entity_code := COALESCE(NEW.entity_code, 'UNKNOWN');
        IF v_is_manual_payment THEN
            NEW.requires_agent_validation := COALESCE(NEW.requires_agent_validation, true);
            NEW.auto_approval_eligible := COALESCE(NEW.auto_approval_eligible, false);
            NEW.workflow_status := COALESCE(NEW.workflow_status, 'pending_agent_review');
            NEW.sla_target_date := COALESCE(NEW.sla_target_date, NOW() + INTERVAL '24 hours');
        END IF;
        RETURN NEW;
    END IF;

    -- Get entity_code from service_request (source of truth)
    SELECT sr.entity_code INTO v_entity_code
    FROM service_requests sr
    WHERE sr.id = NEW.service_request_id;

    IF v_entity_code IS NOT NULL THEN
        NEW.entity_code := v_entity_code;

        -- Get ministry_id from entity (if entity has one)
        SELECT e.ministry_id INTO v_ministry_id
        FROM entities e
        WHERE e.code = v_entity_code;

        IF v_ministry_id IS NOT NULL THEN
            NEW.ministry_id := v_ministry_id;
        END IF;
    ELSE
        NEW.entity_code := COALESCE(NEW.entity_code, 'UNKNOWN');
    END IF;

    -- Apply ministry validation config for manual payments (existing logic preserved)
    IF v_is_manual_payment AND NEW.ministry_id IS NOT NULL THEN
        -- Try to get service_type for ministry config lookup
        SELECT fs.service_type INTO v_service_type
        FROM service_requests sr
        LEFT JOIN fiscal_services fs ON fs.id = sr.fiscal_service_id
        WHERE sr.id = NEW.service_request_id;

        IF v_service_type IS NOT NULL THEN
            SELECT * INTO v_config
            FROM ministry_validation_config mvc
            WHERE mvc.ministry_id = NEW.ministry_id
              AND mvc.service_type = v_service_type
              AND mvc.is_active = true;

            IF FOUND THEN
                NEW.auto_approval_eligible := (
                    v_config.auto_approval_enabled = true
                    AND NEW.total_amount <= v_config.auto_approval_max_amount
                );
                NEW.requires_agent_validation := NOT NEW.auto_approval_eligible;
                NEW.sla_target_date := NOW() + (v_config.target_review_hours || ' hours')::INTERVAL;
                NEW.workflow_status := CASE
                    WHEN NEW.auto_approval_eligible THEN 'auto_processing'
                    ELSE 'pending_agent_review'
                END;
                RETURN NEW;
            END IF;
        END IF;
    END IF;

    -- Default behavior ONLY for manual payments if no ministry config found
    IF v_is_manual_payment THEN
        NEW.requires_agent_validation := COALESCE(NEW.requires_agent_validation, true);
        NEW.auto_approval_eligible := COALESCE(NEW.auto_approval_eligible, false);
        NEW.workflow_status := COALESCE(NEW.workflow_status, 'pending_agent_review');
        NEW.sla_target_date := COALESCE(NEW.sla_target_date, NOW() + INTERVAL '24 hours');
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Step 8: Replace ministry-based index with entity-based indexes
DROP INDEX IF EXISTS idx_service_payments_workflow_ministry;

-- Primary index: entity + status + date (covers most treasury queries)
CREATE INDEX idx_sp_entity_status_date
    ON service_payments (entity_code, workflow_status, created_at);

-- Completed payments by entity (for KPIs and exports)
CREATE INDEX idx_sp_entity_completed
    ON service_payments (entity_code, validated_at, total_amount)
    WHERE workflow_status = 'completed';

-- Step 9: Verify final state
DO $$
DECLARE
    v_groups TEXT;
    v_ministry_filled INTEGER;
BEGIN
    SELECT string_agg(entity_code || ':' || cnt::text, ', ')
    INTO v_groups
    FROM (
        SELECT entity_code, COUNT(*) as cnt
        FROM service_payments
        GROUP BY entity_code
        ORDER BY cnt DESC
    ) sub;

    SELECT COUNT(*) INTO v_ministry_filled
    FROM service_payments WHERE ministry_id IS NOT NULL;

    RAISE NOTICE 'Migration 146: entity_code groups = %', v_groups;
    RAISE NOTICE 'Migration 146: % payments now have ministry_id (from entities)', v_ministry_filled;
    RAISE NOTICE 'Migration 146: Trigger rewritten, indexes replaced';
END $$;

COMMIT;
