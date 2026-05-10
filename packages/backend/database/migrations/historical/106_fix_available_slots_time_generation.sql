-- ============================================================================
-- Migration 106: Fix get_available_slots_v3 to generate all time slots
-- ============================================================================
-- Problem:
--   v3 returned only sc.start_time (08:00) per day instead of generating
--   all intermediate slots (08:00, 08:30, 09:00, ..., 14:30) from the
--   config's start_time/end_time/slot_duration_minutes.
--
-- Fix:
--   Use generate_series to produce individual time slots between
--   start_time and end_time at slot_duration_minutes intervals.
--   Each generated slot is checked against reservations and holds
--   for capacity (max_appointments_per_slot).
--
-- Date: 2026-02-17
-- ============================================================================

CREATE OR REPLACE FUNCTION get_available_slots_v3(
    p_entity_location_id UUID,
    p_from_date DATE,
    p_limit INTEGER DEFAULT 20
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
    ),
    -- Generate individual time slots from each config's range
    time_slots AS (
        SELECT
            dr.dt,
            (sc.start_time + (gs.n * sc.slot_duration_minutes) * INTERVAL '1 minute')::TIME AS t_slot,
            sc.id AS config_id,
            sc.max_appointments_per_slot,
            el.location_name AS loc_name,
            el.location_address AS loc_address,
            el.city AS loc_city
        FROM date_range dr
        CROSS JOIN appointment_slot_configs sc
        INNER JOIN entity_locations el ON el.id = sc.entity_location_id
        CROSS JOIN LATERAL generate_series(
            0,
            GREATEST(0, (EXTRACT(EPOCH FROM (sc.end_time - sc.start_time))::INTEGER / (sc.slot_duration_minutes * 60)) - 1)
        ) AS gs(n)
        WHERE sc.entity_location_id = p_entity_location_id
        AND sc.is_active = TRUE
        AND sc.day_of_week = (EXTRACT(DOW FROM dr.dt)::INTEGER + 6) % 7
        AND NOT is_appointment_date_blocked(v_entity_code, dr.dt)
    )
    SELECT
        ts.dt AS slot_date,
        ts.t_slot AS slot_time,
        ts.loc_name AS location_name,
        ts.loc_address AS location_address,
        ts.loc_city AS city,
        (ts.max_appointments_per_slot - COALESCE(res.cnt, 0) - COALESCE(holds.cnt, 0))::INTEGER AS slots_remaining
    FROM time_slots ts
    -- Count confirmed reservations per (date, time)
    LEFT JOIN LATERAL (
        SELECT COUNT(*)::INTEGER AS cnt
        FROM appointment_reservations ar
        WHERE ar.entity_location_id = p_entity_location_id
        AND ar.appointment_date = ts.dt
        AND ar.appointment_time = ts.t_slot
        AND ar.status IN ('scheduled', 'confirmed')
    ) res ON TRUE
    -- Count active holds per (date, time)
    LEFT JOIN LATERAL (
        SELECT COUNT(*)::INTEGER AS cnt
        FROM appointment_holds ah
        WHERE ah.entity_location_id = p_entity_location_id
        AND ah.appointment_date = ts.dt
        AND ah.appointment_time = ts.t_slot
        AND ah.status = 'held'
        AND ah.expires_at > NOW()
    ) holds ON TRUE
    WHERE (ts.max_appointments_per_slot - COALESCE(res.cnt, 0) - COALESCE(holds.cnt, 0)) > 0
    ORDER BY ts.dt, ts.t_slot
    LIMIT p_limit;
END;
$func$ LANGUAGE plpgsql;

COMMENT ON FUNCTION get_available_slots_v3 IS 'Set-based slot availability query. Generates all time slots from config ranges (start_time to end_time by slot_duration_minutes). Accepts entity_location_id UUID.';
