-- ============================================================================
-- Migration 093: Optimized get_available_slots_v3 (set-based, UUID pivot)
-- ============================================================================
-- Purpose:
--   Replace procedural PL/pgSQL loop (v2) with set-based query using
--   generate_series + LATERAL JOINs. Accepts entity_location_id UUID
--   directly instead of (entity_code, location_name) strings.
--
-- Performance:
--   v2: PL/pgSQL WHILE loop, up to 60 iterations with 1 query each
--   v3: Single query with generate_series + LATERAL (1 round-trip)
--
-- Date: 2026-02-10
-- ============================================================================

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
    LEFT JOIN LATERAL (
        SELECT COUNT(*)::INTEGER AS cnt
        FROM appointment_holds ah
        WHERE ah.entity_location_id = p_entity_location_id
        AND ah.appointment_date = dr.dt
        AND ah.appointment_time = sc.start_time
        AND ah.status = 'held'
        AND ah.expires_at > NOW()
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

COMMENT ON FUNCTION get_available_slots_v3 IS 'Set-based slot availability query. Accepts entity_location_id UUID directly. Replaces procedural v2 loop.';
