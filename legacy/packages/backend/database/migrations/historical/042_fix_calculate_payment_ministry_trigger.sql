-- ============================================================================
-- Migration 042: Fix calculate_payment_ministry trigger
-- ============================================================================
-- Purpose: Update the trigger to use service_request_id instead of
-- fiscal_service_code which was dropped in migration 041.
--
-- Root cause: The trigger was referencing NEW.fiscal_service_code but that
-- column no longer exists after migration 041.
--
-- Fix: Rewrite the trigger to get ministry_id from:
--   service_payments.service_request_id -> service_requests.fiscal_service_id -> fiscal_services
-- ============================================================================

BEGIN;

-- Drop the old trigger first
DROP TRIGGER IF EXISTS trigger_calculate_payment_ministry ON service_payments;

-- Recreate the function to use service_request_id
CREATE OR REPLACE FUNCTION public.calculate_payment_ministry()
 RETURNS trigger
 LANGUAGE plpgsql
AS $function$
DECLARE
    v_ministry_id INTEGER;
    v_fiscal_service_id INTEGER;
    v_service_type TEXT;
    v_config ministry_validation_config%ROWTYPE;
BEGIN
    -- If no service_request_id, skip ministry calculation
    -- (legacy payments before 2026-01-11 may not have service_request_id)
    IF NEW.service_request_id IS NULL THEN
        -- Set defaults for legacy payments
        NEW.requires_agent_validation := true;
        NEW.auto_approval_eligible := false;
        NEW.workflow_status := 'pending_agent_review';
        NEW.sla_target_date := NOW() + INTERVAL '24 hours';
        RETURN NEW;
    END IF;

    -- Get fiscal_service_id from service_request
    SELECT sr.fiscal_service_id INTO v_fiscal_service_id
    FROM service_requests sr
    WHERE sr.id = NEW.service_request_id;

    -- If service_request has a fiscal_service_id, calculate ministry
    IF v_fiscal_service_id IS NOT NULL THEN
        -- Calcul ministère via fiscal_services
        SELECT COALESCE(sm.id, cm.id), fs.service_type
        INTO v_ministry_id, v_service_type
        FROM fiscal_services fs
        JOIN categories c ON fs.category_id = c.id
        LEFT JOIN sectors s ON c.sector_id = s.id
        LEFT JOIN ministries sm ON s.ministry_id = sm.id
        LEFT JOIN ministries cm ON c.ministry_id = cm.id
        WHERE fs.id = v_fiscal_service_id
        AND fs.status = 'active';

        IF v_ministry_id IS NOT NULL THEN
            NEW.ministry_id := v_ministry_id;

            -- Config validation
            SELECT * INTO v_config
            FROM ministry_validation_config mvc
            WHERE mvc.ministry_id = v_ministry_id
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

    -- Default behavior if no ministry config found
    NEW.requires_agent_validation := true;
    NEW.auto_approval_eligible := false;
    NEW.workflow_status := 'pending_agent_review';
    NEW.sla_target_date := NOW() + INTERVAL '24 hours';

    RETURN NEW;
END;
$function$;

-- Recreate the trigger
CREATE TRIGGER trigger_calculate_payment_ministry
    BEFORE INSERT ON service_payments
    FOR EACH ROW
    EXECUTE FUNCTION calculate_payment_ministry();

-- ============================================================================
-- Verification
-- ============================================================================
DO $$
BEGIN
    -- Check trigger exists
    IF NOT EXISTS (
        SELECT 1 FROM pg_trigger
        WHERE tgname = 'trigger_calculate_payment_ministry'
        AND tgrelid = 'service_payments'::regclass
    ) THEN
        RAISE EXCEPTION 'Trigger trigger_calculate_payment_ministry was not created!';
    END IF;

    -- Check function doesn't reference fiscal_service_code anymore
    IF EXISTS (
        SELECT 1 FROM pg_proc
        WHERE proname = 'calculate_payment_ministry'
        AND prosrc LIKE '%fiscal_service_code%'
    ) THEN
        RAISE EXCEPTION 'Function still references fiscal_service_code!';
    END IF;

    RAISE NOTICE 'Migration 042 completed successfully: trigger updated to use service_request_id';
END $$;

COMMIT;
