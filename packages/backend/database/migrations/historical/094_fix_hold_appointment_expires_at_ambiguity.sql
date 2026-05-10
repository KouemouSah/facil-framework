-- ============================================================================
-- Migration 094: Fix 'expires_at' Column Reference Ambiguity in hold_appointment_slot()
-- ============================================================================
-- Problem:
--   hold_appointment_slot() RETURNS TABLE declares 'expires_at' as an output column.
--   This creates a PL/pgSQL variable named 'expires_at'.
--   Inside the function body, line:
--       AND (status = 'confirmed' OR expires_at > NOW())
--   is ambiguous because PostgreSQL can't determine if 'expires_at' refers to:
--     (a) the PL/pgSQL output variable, or
--     (b) the appointment_holds.expires_at table column.
--
-- Fix:
--   Qualify the column reference: appointment_holds.expires_at
--   Also qualify in the INSERT RETURNING clause for safety.
--
-- Date: 2026-02-10
-- ============================================================================

-- Recreate hold_appointment_slot with qualified column references
CREATE OR REPLACE FUNCTION hold_appointment_slot(
    p_service_request_id UUID,
    p_slot_config_id UUID,
    p_appointment_date DATE,
    p_appointment_time TIME,
    p_entity_location_id UUID
)
RETURNS TABLE (
    success BOOLEAN,
    hold_id UUID,
    expires_at TIMESTAMP WITH TIME ZONE,
    error_message TEXT
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_slot_config RECORD;
    v_current_holds INTEGER;
    v_hold_id UUID;
    v_expires_at TIMESTAMP WITH TIME ZONE;
BEGIN
    -- Verify location exists
    IF NOT EXISTS (SELECT 1 FROM entity_locations WHERE id = p_entity_location_id AND is_active = TRUE) THEN
        RETURN QUERY SELECT FALSE, NULL::UUID, NULL::TIMESTAMP WITH TIME ZONE,
            'Location not found or inactive'::TEXT;
        RETURN;
    END IF;

    -- Get slot configuration
    SELECT * INTO v_slot_config
    FROM appointment_slot_configs
    WHERE id = p_slot_config_id AND is_active = TRUE;

    IF NOT FOUND THEN
        RETURN QUERY SELECT FALSE, NULL::UUID, NULL::TIMESTAMP WITH TIME ZONE,
            'Slot configuration not found or inactive'::TEXT;
        RETURN;
    END IF;

    -- Count current active holds for this slot/date/time
    -- FIX: Qualify expires_at with table name to avoid ambiguity with RETURNS TABLE column
    SELECT COUNT(*) INTO v_current_holds
    FROM appointment_holds ah
    WHERE ah.slot_config_id = p_slot_config_id
      AND ah.appointment_date = p_appointment_date
      AND ah.appointment_time = p_appointment_time
      AND ah.status IN ('held', 'confirmed')
      AND (ah.status = 'confirmed' OR ah.expires_at > NOW());

    -- Check capacity
    IF v_current_holds >= v_slot_config.max_appointments_per_slot THEN
        RETURN QUERY SELECT FALSE, NULL::UUID, NULL::TIMESTAMP WITH TIME ZONE,
            'No slots available for this time'::TEXT;
        RETURN;
    END IF;

    -- Release any existing hold for this service request
    UPDATE appointment_holds
    SET status = 'released', released_at = NOW(), updated_at = NOW()
    WHERE service_request_id = p_service_request_id
      AND status = 'held';

    -- Create new hold
    v_expires_at := NOW() + INTERVAL '15 minutes';

    INSERT INTO appointment_holds (
        service_request_id, slot_config_id,
        appointment_date, appointment_time,
        entity_location_id,
        status, expires_at
    )
    VALUES (
        p_service_request_id, p_slot_config_id,
        p_appointment_date, p_appointment_time,
        p_entity_location_id,
        'held', v_expires_at
    )
    RETURNING appointment_holds.id INTO v_hold_id;

    -- Update service_request with selected location
    UPDATE service_requests
    SET entity_location_id = p_entity_location_id,
        updated_at = NOW()
    WHERE id = p_service_request_id;

    RETURN QUERY SELECT TRUE, v_hold_id, v_expires_at, NULL::TEXT;
END;
$$;
