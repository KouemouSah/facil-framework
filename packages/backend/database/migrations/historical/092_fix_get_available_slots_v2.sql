-- ============================================================================
-- Migration 092: Fix get_available_slots_v2 for post-030 schema
-- ============================================================================
-- Purpose:
--   The original function (migration 029) used columns that were moved to
--   entity_locations table in migration 030:
--   - appointment_slot_configs.location_name → entity_locations.location_name
--   - appointment_slot_configs.location_address → entity_locations.location_address
--   - appointment_reservations.entity_code → entity_location_id FK
--   - appointment_holds.entity_code → entity_location_id FK
--
--   This recreates the function with proper JOINs via entity_location_id.
--
-- Date: 2026-02-10
-- ============================================================================

CREATE OR REPLACE FUNCTION get_available_slots_v2(
    p_entity_code VARCHAR(50),
    p_location_name VARCHAR(255),
    p_from_date DATE,
    p_limit INTEGER DEFAULT 6
) RETURNS TABLE (
    slot_date DATE,
    slot_time TIME,
    location_name VARCHAR(255),
    location_address TEXT,
    slots_remaining INTEGER
) AS $func$
DECLARE
    v_current_date DATE := p_from_date;
    v_max_search_days INTEGER := 60;
    v_day_count INTEGER := 0;
    v_slots_found INTEGER := 0;
    v_slot RECORD;
    v_location_ids UUID[];
BEGIN
    -- Pre-fetch entity_location IDs for this entity+location combo
    SELECT array_agg(el.id) INTO v_location_ids
    FROM entity_locations el
    WHERE el.entity_code = p_entity_code
    AND el.location_name = p_location_name
    AND el.is_active = TRUE;

    IF v_location_ids IS NULL THEN
        RETURN;
    END IF;

    WHILE v_day_count < v_max_search_days AND v_slots_found < p_limit LOOP
        -- Skip weekends (PostgreSQL DOW: 0=Sunday, 6=Saturday)
        IF EXTRACT(DOW FROM v_current_date)::INTEGER IN (0, 6) THEN
            v_current_date := v_current_date + INTERVAL '1 day';
            v_day_count := v_day_count + 1;
            CONTINUE;
        END IF;

        -- Skip blocked dates
        IF is_appointment_date_blocked(p_entity_code, v_current_date) THEN
            v_current_date := v_current_date + INTERVAL '1 day';
            v_day_count := v_day_count + 1;
            CONTINUE;
        END IF;

        -- Get available slots for this day
        -- JOINs use entity_location_id (post-migration 030 schema)
        FOR v_slot IN (
            SELECT
                v_current_date as slot_date,
                sc.start_time as slot_time,
                el.location_name,
                el.location_address,
                sc.max_appointments_per_slot - COALESCE(res.cnt, 0) - COALESCE(holds.cnt, 0) as slots_remaining
            FROM appointment_slot_configs sc
            INNER JOIN entity_locations el ON el.id = sc.entity_location_id
            -- Count confirmed reservations for these locations
            LEFT JOIN (
                SELECT ar.appointment_time, COUNT(*) as cnt
                FROM appointment_reservations ar
                WHERE ar.entity_location_id = ANY(v_location_ids)
                AND ar.appointment_date = v_current_date
                AND ar.status IN ('scheduled', 'confirmed')
                GROUP BY ar.appointment_time
            ) res ON sc.start_time = res.appointment_time
            -- Count active holds (not expired) for these locations
            LEFT JOIN (
                SELECT ah.appointment_time, COUNT(*) as cnt
                FROM appointment_holds ah
                WHERE ah.entity_location_id = ANY(v_location_ids)
                AND ah.appointment_date = v_current_date
                AND ah.status = 'held'
                AND ah.expires_at > NOW()
                GROUP BY ah.appointment_time
            ) holds ON sc.start_time = holds.appointment_time
            WHERE sc.entity_location_id = ANY(v_location_ids)
            AND sc.is_active = TRUE
            AND sc.day_of_week = (EXTRACT(DOW FROM v_current_date)::INTEGER + 6) % 7  -- Convert to 0=Monday
            AND (sc.max_appointments_per_slot - COALESCE(res.cnt, 0) - COALESCE(holds.cnt, 0)) > 0
            ORDER BY sc.start_time
        )
        LOOP
            IF v_slots_found < p_limit THEN
                slot_date := v_slot.slot_date;
                slot_time := v_slot.slot_time;
                location_name := v_slot.location_name;
                location_address := v_slot.location_address;
                slots_remaining := v_slot.slots_remaining;
                v_slots_found := v_slots_found + 1;
                RETURN NEXT;
            END IF;
        END LOOP;

        v_current_date := v_current_date + INTERVAL '1 day';
        v_day_count := v_day_count + 1;
    END LOOP;

    RETURN;
END;
$func$ LANGUAGE plpgsql;

COMMENT ON FUNCTION get_available_slots_v2 IS 'Returns available appointment slots considering reservations and active holds. Uses entity_location_id joins (post-migration 030).';
