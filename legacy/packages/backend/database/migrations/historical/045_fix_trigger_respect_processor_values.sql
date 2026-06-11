-- ============================================================================
-- Migration 045: Fix trigger to respect processor-set values
-- ============================================================================
-- Problem: The calculate_payment_ministry trigger was overwriting values
-- set by the BANGE processor (workflow_status, requires_agent_validation).
--
-- Fix: Only set default values for fields that are NULL or for manual
-- payment methods (cash, check).
-- ============================================================================

BEGIN;

CREATE OR REPLACE FUNCTION public.calculate_payment_ministry()
 RETURNS trigger
 LANGUAGE plpgsql
AS $function$
DECLARE
    v_ministry_id INTEGER;
    v_fiscal_service_id INTEGER;
    v_service_type TEXT;
    v_config ministry_validation_config%ROWTYPE;
    v_is_manual_payment BOOLEAN;
BEGIN
    -- Check if this is a manual payment (cash/check)
    v_is_manual_payment := NEW.payment_method IN ('cash', 'check');

    -- If no service_request_id, set defaults only for manual payments
    IF NEW.service_request_id IS NULL THEN
        IF v_is_manual_payment THEN
            NEW.requires_agent_validation := COALESCE(NEW.requires_agent_validation, true);
            NEW.auto_approval_eligible := COALESCE(NEW.auto_approval_eligible, false);
            NEW.workflow_status := COALESCE(NEW.workflow_status, 'pending_agent_review');
            NEW.sla_target_date := COALESCE(NEW.sla_target_date, NOW() + INTERVAL '24 hours');
        END IF;
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
            -- Always set ministry_id if found
            NEW.ministry_id := v_ministry_id;

            -- Only apply ministry config for manual payments
            IF v_is_manual_payment THEN
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
$function$;

-- Verification
DO $$
BEGIN
    RAISE NOTICE 'Migration 045 completed: trigger now respects processor-set values for BANGE payments';
END $$;

COMMIT;
