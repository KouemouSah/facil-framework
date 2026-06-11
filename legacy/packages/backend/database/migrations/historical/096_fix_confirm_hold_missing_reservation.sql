-- ============================================================================
-- Migration 096: Fix confirm_appointment_hold - Insert into appointment_reservations
-- ============================================================================
-- Bug: Migration 030 rewrote confirm_appointment_hold() but DROPPED the
--   INSERT INTO appointment_reservations that existed in migration 029.
--
-- Impact:
--   - appointment_reservations table is EMPTY despite confirmed appointments
--   - get_available_slots_v3() counts reservations (0) + active holds (0 after confirm)
--   - Confirmed slots appear as available → double-booking possible
--
-- Fix:
--   1. Recreate confirm_appointment_hold() WITH the INSERT INTO appointment_reservations
--   2. Backfill existing confirmed holds into appointment_reservations
--   3. Add safety net: get_available_slots_v3() also counts confirmed holds
--
-- Date: 2026-02-11
-- ============================================================================

-- ============================================================================
-- 1. FIX: Recreate confirm_appointment_hold with reservation INSERT
-- ============================================================================

CREATE OR REPLACE FUNCTION confirm_appointment_hold(
    p_service_request_id UUID
)
RETURNS TABLE (
    success BOOLEAN,
    appointment_date DATE,
    appointment_time TIME,
    location_id UUID,
    error_message TEXT
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_hold RECORD;
BEGIN
    -- Find active hold
    SELECT * INTO v_hold
    FROM appointment_holds
    WHERE service_request_id = p_service_request_id
      AND status = 'held'
      AND expires_at > NOW()
    FOR UPDATE;

    IF NOT FOUND THEN
        RETURN QUERY SELECT FALSE, NULL::DATE, NULL::TIME, NULL::UUID,
            'No active hold found or hold expired'::TEXT;
        RETURN;
    END IF;

    -- Confirm the hold
    UPDATE appointment_holds
    SET status = 'confirmed', confirmed_at = NOW(), updated_at = NOW()
    WHERE id = v_hold.id;

    -- Create permanent reservation (WAS MISSING since migration 030)
    INSERT INTO appointment_reservations (
        service_request_id,
        entity_location_id,
        appointment_date,
        appointment_time,
        status
    ) VALUES (
        p_service_request_id,
        v_hold.entity_location_id,
        v_hold.appointment_date,
        v_hold.appointment_time,
        'scheduled'
    );

    -- Update service_request with appointment details
    UPDATE service_requests
    SET
        cita_date = v_hold.appointment_date,
        cita_time = v_hold.appointment_time,
        entity_location_id = v_hold.entity_location_id,
        updated_at = NOW()
    WHERE id = p_service_request_id;

    RETURN QUERY SELECT TRUE, v_hold.appointment_date, v_hold.appointment_time,
        v_hold.entity_location_id, NULL::TEXT;
END;
$$;

COMMENT ON FUNCTION confirm_appointment_hold IS 'Confirms an appointment hold after payment. Creates permanent reservation in appointment_reservations and updates service_request.';

-- ============================================================================
-- 2. BACKFILL: Create reservations for existing confirmed holds
-- ============================================================================

INSERT INTO appointment_reservations (
    service_request_id,
    entity_location_id,
    appointment_date,
    appointment_time,
    status,
    created_at
)
SELECT
    ah.service_request_id,
    ah.entity_location_id,
    ah.appointment_date,
    ah.appointment_time,
    'scheduled',
    ah.confirmed_at  -- Use confirm timestamp as creation date
FROM appointment_holds ah
WHERE ah.status = 'confirmed'
  AND ah.service_request_id IS NOT NULL
  AND ah.entity_location_id IS NOT NULL
  -- Avoid duplicates if migration is re-run
  AND NOT EXISTS (
      SELECT 1 FROM appointment_reservations ar
      WHERE ar.service_request_id = ah.service_request_id
        AND ar.appointment_date = ah.appointment_date
        AND ar.appointment_time = ah.appointment_time
        AND ar.status IN ('scheduled', 'confirmed')
  );

-- ============================================================================
-- 3. SAFETY NET: Update get_available_slots_v3 to also count confirmed holds
-- ============================================================================
-- This is a belt-and-suspenders approach: even if somehow a reservation
-- is not created, confirmed holds will still block the slot.

CREATE OR REPLACE FUNCTION get_available_slots_v3(
    p_entity_location_id UUID,
    p_from_date DATE,
    p_limit INTEGER DEFAULT 6
) RETURNS TABLE (
    slot_date DATE,
    slot_time TIME,
    location_name VARCHAR(255),
    location_address TEXT,
    city VARCHAR(100),
    slots_remaining INTEGER
) AS $func$
DECLARE
    v_entity_code VARCHAR(50);
BEGIN
    -- Resolve entity_code once (needed for blocked dates check)
    SELECT el.entity_code INTO v_entity_code
    FROM entity_locations el
    WHERE el.id = p_entity_location_id AND el.is_active = TRUE;

    IF v_entity_code IS NULL THEN
        RETURN;
    END IF;

    RETURN QUERY
    WITH date_range AS (
        SELECT d::date AS dt
        FROM generate_series(
            p_from_date,
            p_from_date + INTERVAL '59 days',
            INTERVAL '1 day'
        ) AS d
        WHERE EXTRACT(DOW FROM d)::INTEGER NOT IN (0, 6)  -- skip weekends
    )
    SELECT
        dr.dt AS slot_date,
        sc.start_time AS slot_time,
        el.location_name,
        el.location_address,
        el.city,
        (sc.max_appointments_per_slot - COALESCE(res.cnt, 0) - COALESCE(holds.cnt, 0))::INTEGER AS slots_remaining
    FROM date_range dr
    CROSS JOIN appointment_slot_configs sc
    INNER JOIN entity_locations el ON el.id = sc.entity_location_id
    -- Count confirmed reservations per (date, time) via LATERAL
    LEFT JOIN LATERAL (
        SELECT COUNT(*)::INTEGER AS cnt
        FROM appointment_reservations ar
        WHERE ar.entity_location_id = p_entity_location_id
        AND ar.appointment_date = dr.dt
        AND ar.appointment_time = sc.start_time
        AND ar.status IN ('scheduled', 'confirmed')
    ) res ON TRUE
    -- Count active holds per (date, time) via LATERAL
    -- FIXED: Also count 'confirmed' holds as safety net (in case reservation insert failed)
    LEFT JOIN LATERAL (
        SELECT COUNT(*)::INTEGER AS cnt
        FROM appointment_holds ah
        WHERE ah.entity_location_id = p_entity_location_id
        AND ah.appointment_date = dr.dt
        AND ah.appointment_time = sc.start_time
        AND (
            (ah.status = 'held' AND ah.expires_at > NOW())
            OR (ah.status = 'confirmed' AND NOT EXISTS (
                -- Only count confirmed hold if no matching reservation exists
                SELECT 1 FROM appointment_reservations ar2
                WHERE ar2.service_request_id = ah.service_request_id
                  AND ar2.appointment_date = ah.appointment_date
                  AND ar2.appointment_time = ah.appointment_time
                  AND ar2.status IN ('scheduled', 'confirmed')
            ))
        )
    ) holds ON TRUE
    WHERE sc.entity_location_id = p_entity_location_id
    AND sc.is_active = TRUE
    AND sc.day_of_week = (EXTRACT(DOW FROM dr.dt)::INTEGER + 6) % 7  -- Convert to 0=Monday
    AND NOT is_appointment_date_blocked(v_entity_code, dr.dt)
    AND (sc.max_appointments_per_slot - COALESCE(res.cnt, 0) - COALESCE(holds.cnt, 0)) > 0
    ORDER BY dr.dt, sc.start_time
    LIMIT p_limit;
END;
$func$ LANGUAGE plpgsql;

COMMENT ON FUNCTION get_available_slots_v3 IS 'Set-based slot availability query. Counts reservations + active/confirmed holds. Accepts entity_location_id UUID. Fixed in migration 096 to prevent ghost availability.';
