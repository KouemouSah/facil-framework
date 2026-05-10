-- ============================================================================
-- Migration 029: Appointment Holds (pre-payment) and Bata Locations
-- ============================================================================
-- Purpose:
--   1. Create appointment_holds table for temporary slot reservations (before payment)
--   2. Add CNEDOGE Bata, DGT Bata, EXTRANJERIA Bata locations
--   3. Update delay rules for new workflow (7 days after payment)
--   4. Add function to release expired holds (cron job)
--   5. Update workflow configuration for citizen-first appointment selection
--
-- New Flow:
--   DRAFT → DOCUMENTS → REVIEW → SELECT_LOCATION → SELECT_SLOT → PAYMENT → SUBMITTED → VALIDATED
--   - User selects location (Malabo or Bata) BEFORE payment
--   - User selects from 6 available slots BEFORE payment
--   - Slot is temporarily held (15 min) during payment
--   - Hold is confirmed automatically after payment success
--   - If no slots available: submit without appointment, agent assigns later
--
-- Date: 2024-12-31
-- ============================================================================

BEGIN;

-- ============================================================================
-- 1. APPOINTMENT HOLDS TABLE
-- ============================================================================
-- Temporary slot reservations before payment confirmation
-- Holds expire after 15 minutes if payment not completed

CREATE TABLE IF NOT EXISTS appointment_holds (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Link to service request
    service_request_id UUID NOT NULL REFERENCES service_requests(id) ON DELETE CASCADE,

    -- Entity and location
    entity_code VARCHAR(50) NOT NULL,
    location_name VARCHAR(255) NOT NULL,
    location_address TEXT,

    -- Appointment slot details
    appointment_date DATE NOT NULL,
    appointment_time TIME NOT NULL,

    -- Hold expiration (15 minutes to complete payment)
    expires_at TIMESTAMPTZ NOT NULL,

    -- Status
    status VARCHAR(20) NOT NULL DEFAULT 'held'
        CHECK (status IN ('held', 'confirmed', 'expired', 'released', 'fallback')),
    -- 'held'      = Temporarily reserved, waiting for payment
    -- 'confirmed' = Payment completed, slot is now permanent
    -- 'expired'   = Hold expired (payment not completed in time)
    -- 'released'  = User released the hold (selected different slot)
    -- 'fallback'  = No slots available, submitted without appointment

    -- Audit
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    confirmed_at TIMESTAMPTZ,
    expired_at TIMESTAMPTZ,
    released_at TIMESTAMPTZ,

    -- Only one active hold per service request
    CONSTRAINT unique_active_hold UNIQUE (service_request_id)
        DEFERRABLE INITIALLY DEFERRED
);

-- Indexes
CREATE INDEX idx_ah_service_request ON appointment_holds(service_request_id);
CREATE INDEX idx_ah_entity_date ON appointment_holds(entity_code, appointment_date, appointment_time);
CREATE INDEX idx_ah_expires ON appointment_holds(expires_at) WHERE status = 'held';
CREATE INDEX idx_ah_status ON appointment_holds(status);

-- Comments
COMMENT ON TABLE appointment_holds IS 'Temporary appointment slot reservations before payment (15 min expiry)';
COMMENT ON COLUMN appointment_holds.status IS 'held=waiting payment, confirmed=paid, expired=timeout, released=user cancelled, fallback=no slots';
COMMENT ON COLUMN appointment_holds.expires_at IS 'Hold expires after this time if payment not completed';

-- ============================================================================
-- 2. ADD BATA LOCATIONS
-- ============================================================================
-- Equatorial Guinea has 2 main regions:
-- - Bioko (island) = Malabo (capital)
-- - Continental = Bata (largest city)
-- Citizens should be able to choose their nearest office

-- CNEDOGE Bata (Centro Nacional de Expedición de Documentos)
INSERT INTO appointment_slot_configs
(entity_code, day_of_week, start_time, end_time, slot_duration_minutes, max_appointments_per_slot, location_name, location_address, is_active)
VALUES
('CNEDOGE', 0, '08:00', '15:00', 30, 8, 'CNEDOGE Bata', 'Bata, Litoral', TRUE),
('CNEDOGE', 1, '08:00', '15:00', 30, 8, 'CNEDOGE Bata', 'Bata, Litoral', TRUE),
('CNEDOGE', 2, '08:00', '15:00', 30, 8, 'CNEDOGE Bata', 'Bata, Litoral', TRUE),
('CNEDOGE', 3, '08:00', '15:00', 30, 8, 'CNEDOGE Bata', 'Bata, Litoral', TRUE),
('CNEDOGE', 4, '08:00', '15:00', 30, 8, 'CNEDOGE Bata', 'Bata, Litoral', TRUE)
ON CONFLICT (entity_code, day_of_week, start_time) DO NOTHING;

-- DGT Bata (Dirección General de Tráfico)
INSERT INTO appointment_slot_configs
(entity_code, day_of_week, start_time, end_time, slot_duration_minutes, max_appointments_per_slot, location_name, location_address, is_active)
VALUES
('DGT', 0, '08:00', '14:00', 30, 6, 'DGT Bata', 'Bata, Litoral', TRUE),
('DGT', 1, '08:00', '14:00', 30, 6, 'DGT Bata', 'Bata, Litoral', TRUE),
('DGT', 2, '08:00', '14:00', 30, 6, 'DGT Bata', 'Bata, Litoral', TRUE),
('DGT', 3, '08:00', '14:00', 30, 6, 'DGT Bata', 'Bata, Litoral', TRUE),
('DGT', 4, '08:00', '14:00', 30, 6, 'DGT Bata', 'Bata, Litoral', TRUE)
ON CONFLICT (entity_code, day_of_week, start_time) DO NOTHING;

-- EXTRANJERIA Bata
INSERT INTO appointment_slot_configs
(entity_code, day_of_week, start_time, end_time, slot_duration_minutes, max_appointments_per_slot, location_name, location_address, is_active)
VALUES
('EXTRANJERIA', 0, '09:00', '14:00', 30, 5, 'Extranjería Bata', 'Bata, Litoral', TRUE),
('EXTRANJERIA', 1, '09:00', '14:00', 30, 5, 'Extranjería Bata', 'Bata, Litoral', TRUE),
('EXTRANJERIA', 2, '09:00', '14:00', 30, 5, 'Extranjería Bata', 'Bata, Litoral', TRUE),
('EXTRANJERIA', 3, '09:00', '14:00', 30, 5, 'Extranjería Bata', 'Bata, Litoral', TRUE),
('EXTRANJERIA', 4, '09:00', '14:00', 30, 5, 'Extranjería Bata', 'Bata, Litoral', TRUE)
ON CONFLICT (entity_code, day_of_week, start_time) DO NOTHING;

-- MINFP Bata (Ministerio de Función Pública)
INSERT INTO appointment_slot_configs
(entity_code, day_of_week, start_time, end_time, slot_duration_minutes, max_appointments_per_slot, location_name, location_address, is_active)
VALUES
('MINFP', 0, '08:00', '14:00', 30, 5, 'MINFP Bata', 'Bata, Litoral', TRUE),
('MINFP', 1, '08:00', '14:00', 30, 5, 'MINFP Bata', 'Bata, Litoral', TRUE),
('MINFP', 2, '08:00', '14:00', 30, 5, 'MINFP Bata', 'Bata, Litoral', TRUE),
('MINFP', 3, '08:00', '14:00', 30, 5, 'MINFP Bata', 'Bata, Litoral', TRUE),
('MINFP', 4, '08:00', '14:00', 30, 5, 'MINFP Bata', 'Bata, Litoral', TRUE)
ON CONFLICT (entity_code, day_of_week, start_time) DO NOTHING;

-- MINFP Malabo (was missing in 028)
INSERT INTO appointment_slot_configs
(entity_code, day_of_week, start_time, end_time, slot_duration_minutes, max_appointments_per_slot, location_name, location_address, is_active)
VALUES
('MINFP', 0, '08:00', '14:00', 30, 6, 'MINFP Malabo', 'Malabo, Bioko Norte', TRUE),
('MINFP', 1, '08:00', '14:00', 30, 6, 'MINFP Malabo', 'Malabo, Bioko Norte', TRUE),
('MINFP', 2, '08:00', '14:00', 30, 6, 'MINFP Malabo', 'Malabo, Bioko Norte', TRUE),
('MINFP', 3, '08:00', '14:00', 30, 6, 'MINFP Malabo', 'Malabo, Bioko Norte', TRUE),
('MINFP', 4, '08:00', '14:00', 30, 6, 'MINFP Malabo', 'Malabo, Bioko Norte', TRUE)
ON CONFLICT (entity_code, day_of_week, start_time) DO NOTHING;

-- ============================================================================
-- 3. UPDATE DELAY RULES FOR NEW WORKFLOW
-- ============================================================================
-- New flow: 7 business days AFTER PAYMENT (not after validation)
-- Update default rules to 7 days

UPDATE appointment_delay_rules
SET delay_business_days = 7
WHERE workflow_code IS NULL;

-- Add specific rule for PASAPORTE workflows (7 days)
INSERT INTO appointment_delay_rules (workflow_code, priority, delay_business_days, is_active) VALUES
('PASAPORTE_NUEVO', 'NORMAL', 7, TRUE),
('PASAPORTE_RENOVACION', 'NORMAL', 7, TRUE),
('PASAPORTE_PERDIDA', 'NORMAL', 7, TRUE),
('PASAPORTE_ROBO', 'NORMAL', 7, TRUE),
('PASAPORTE_DETERIORO', 'NORMAL', 7, TRUE)
ON CONFLICT (workflow_code, priority) DO UPDATE SET delay_business_days = 7;

-- ============================================================================
-- 4. ADD COLUMNS TO SERVICE_REQUESTS FOR LOCATION SELECTION
-- ============================================================================
-- Track user's selected location before appointment is confirmed

ALTER TABLE service_requests
ADD COLUMN IF NOT EXISTS selected_location VARCHAR(255);

COMMENT ON COLUMN service_requests.selected_location IS 'User-selected appointment location (e.g., CNEDOGE Malabo, CNEDOGE Bata)';

-- ============================================================================
-- 5. FUNCTION: Release Expired Holds
-- ============================================================================
-- Should be called by a cron job every minute

CREATE OR REPLACE FUNCTION release_expired_appointment_holds()
RETURNS TABLE (
    released_count INTEGER,
    service_request_ids UUID[]
) AS $$
DECLARE
    v_released_count INTEGER;
    v_request_ids UUID[];
BEGIN
    -- Get IDs of holds to expire
    SELECT ARRAY_AGG(service_request_id)
    INTO v_request_ids
    FROM appointment_holds
    WHERE status = 'held' AND expires_at < NOW();

    -- Update holds to expired
    UPDATE appointment_holds
    SET status = 'expired',
        expired_at = NOW()
    WHERE status = 'held' AND expires_at < NOW();

    GET DIAGNOSTICS v_released_count = ROW_COUNT;

    RETURN QUERY SELECT v_released_count, COALESCE(v_request_ids, ARRAY[]::UUID[]);
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION release_expired_appointment_holds IS 'Releases appointment holds that have expired (15 min timeout). Call via cron.';

-- ============================================================================
-- 6. FUNCTION: Hold Appointment Slot
-- ============================================================================
-- Called when user selects a slot (before payment)

CREATE OR REPLACE FUNCTION hold_appointment_slot(
    p_service_request_id UUID,
    p_entity_code VARCHAR(50),
    p_location_name VARCHAR(255),
    p_location_address TEXT,
    p_appointment_date DATE,
    p_appointment_time TIME,
    p_hold_minutes INTEGER DEFAULT 15
) RETURNS appointment_holds AS $$
DECLARE
    v_hold appointment_holds;
    v_expires_at TIMESTAMPTZ;
BEGIN
    -- Calculate expiration time
    v_expires_at := NOW() + (p_hold_minutes || ' minutes')::INTERVAL;

    -- Release any existing hold for this request
    UPDATE appointment_holds
    SET status = 'released',
        released_at = NOW()
    WHERE service_request_id = p_service_request_id
    AND status = 'held';

    -- Create new hold
    INSERT INTO appointment_holds (
        service_request_id,
        entity_code,
        location_name,
        location_address,
        appointment_date,
        appointment_time,
        expires_at,
        status
    ) VALUES (
        p_service_request_id,
        p_entity_code,
        p_location_name,
        p_location_address,
        p_appointment_date,
        p_appointment_time,
        v_expires_at,
        'held'
    )
    ON CONFLICT (service_request_id)
    DO UPDATE SET
        entity_code = EXCLUDED.entity_code,
        location_name = EXCLUDED.location_name,
        location_address = EXCLUDED.location_address,
        appointment_date = EXCLUDED.appointment_date,
        appointment_time = EXCLUDED.appointment_time,
        expires_at = EXCLUDED.expires_at,
        status = 'held',
        released_at = NULL,
        expired_at = NULL,
        confirmed_at = NULL,
        created_at = NOW()
    RETURNING * INTO v_hold;

    -- Update service_request with selected location
    UPDATE service_requests
    SET selected_location = p_location_name,
        updated_at = NOW()
    WHERE id = p_service_request_id;

    RETURN v_hold;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION hold_appointment_slot IS 'Creates a temporary hold on an appointment slot (15 min default). Releases any previous hold.';

-- ============================================================================
-- 7. FUNCTION: Confirm Appointment Hold (after payment)
-- ============================================================================
-- Called by payment webhook after successful payment

CREATE OR REPLACE FUNCTION confirm_appointment_hold(
    p_service_request_id UUID
) RETURNS BOOLEAN AS $$
DECLARE
    v_hold appointment_holds;
BEGIN
    -- Get the current hold
    SELECT * INTO v_hold
    FROM appointment_holds
    WHERE service_request_id = p_service_request_id
    AND status = 'held';

    -- No hold found or already expired
    IF v_hold.id IS NULL THEN
        RETURN FALSE;
    END IF;

    -- Check if hold has expired
    IF v_hold.expires_at < NOW() THEN
        UPDATE appointment_holds
        SET status = 'expired',
            expired_at = NOW()
        WHERE id = v_hold.id;
        RETURN FALSE;
    END IF;

    -- Confirm the hold
    UPDATE appointment_holds
    SET status = 'confirmed',
        confirmed_at = NOW()
    WHERE id = v_hold.id;

    -- Create permanent reservation
    INSERT INTO appointment_reservations (
        service_request_id,
        entity_code,
        appointment_date,
        appointment_time,
        location_name,
        location_address,
        status
    ) VALUES (
        p_service_request_id,
        v_hold.entity_code,
        v_hold.appointment_date,
        v_hold.appointment_time,
        v_hold.location_name,
        v_hold.location_address,
        'scheduled'
    );

    -- Update service_request with confirmed appointment
    UPDATE service_requests
    SET cita_date = v_hold.appointment_date,
        cita_time = v_hold.appointment_time,
        cita_location = v_hold.location_name,
        status = 'submitted',
        submitted_at = NOW(),
        updated_at = NOW()
    WHERE id = p_service_request_id;

    RETURN TRUE;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION confirm_appointment_hold IS 'Confirms a held appointment after payment. Creates permanent reservation and updates service_request.';

-- ============================================================================
-- 8. FUNCTION: Submit Without Appointment (fallback)
-- ============================================================================
-- When no slots are available, submit anyway and let agent assign later

CREATE OR REPLACE FUNCTION submit_without_appointment(
    p_service_request_id UUID,
    p_location_name VARCHAR(255)
) RETURNS BOOLEAN AS $$
BEGIN
    -- Create a fallback hold record for tracking
    INSERT INTO appointment_holds (
        service_request_id,
        entity_code,
        location_name,
        appointment_date,
        appointment_time,
        expires_at,
        status
    ) VALUES (
        p_service_request_id,
        CASE
            WHEN p_location_name LIKE '%CNEDOGE%' THEN 'CNEDOGE'
            WHEN p_location_name LIKE '%DGT%' THEN 'DGT'
            WHEN p_location_name LIKE '%EXTRANJERIA%' THEN 'EXTRANJERIA'
            WHEN p_location_name LIKE '%MINFP%' THEN 'MINFP'
            ELSE 'CNEDOGE'
        END,
        p_location_name,
        NULL,  -- No appointment date yet
        NULL,  -- No appointment time yet
        NOW(), -- Expires immediately (not a real hold)
        'fallback'
    )
    ON CONFLICT (service_request_id)
    DO UPDATE SET
        status = 'fallback',
        location_name = EXCLUDED.location_name,
        appointment_date = NULL,
        appointment_time = NULL;

    -- Update service_request
    UPDATE service_requests
    SET selected_location = p_location_name,
        cita_location = p_location_name,
        cita_date = NULL,
        cita_time = NULL,
        notes = COALESCE(notes, '') || E'\n[SISTEMA] Sin disponibilidad de citas. Un agente asignará la cita.',
        status = 'submitted',
        submitted_at = NOW(),
        updated_at = NOW()
    WHERE id = p_service_request_id;

    RETURN TRUE;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION submit_without_appointment IS 'Submits a request without appointment when no slots available. Agent will assign later.';

-- ============================================================================
-- 9. FUNCTION: Get Available Slots with Hold Count
-- ============================================================================
-- Returns available slots considering both reservations AND active holds

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
) AS $$
DECLARE
    v_current_date DATE := p_from_date;
    v_max_search_days INTEGER := 60;
    v_day_count INTEGER := 0;
    v_slots_found INTEGER := 0;
    v_slot RECORD;
BEGIN
    WHILE v_day_count < v_max_search_days AND v_slots_found < p_limit LOOP
        -- Skip weekends (0=Monday in our system, Saturday=5, Sunday=6)
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
        FOR v_slot IN (
            SELECT
                v_current_date as slot_date,
                asc.start_time as slot_time,
                asc.location_name,
                asc.location_address,
                asc.max_appointments_per_slot - COALESCE(res.cnt, 0) - COALESCE(holds.cnt, 0) as slots_remaining
            FROM appointment_slot_configs asc
            -- Count confirmed reservations
            LEFT JOIN (
                SELECT appointment_time, COUNT(*) as cnt
                FROM appointment_reservations
                WHERE entity_code = p_entity_code
                AND appointment_date = v_current_date
                AND status IN ('scheduled', 'confirmed')
                GROUP BY appointment_time
            ) res ON asc.start_time = res.appointment_time
            -- Count active holds (not expired)
            LEFT JOIN (
                SELECT appointment_time, COUNT(*) as cnt
                FROM appointment_holds
                WHERE entity_code = p_entity_code
                AND appointment_date = v_current_date
                AND status = 'held'
                AND expires_at > NOW()
                GROUP BY appointment_time
            ) holds ON asc.start_time = holds.appointment_time
            WHERE asc.entity_code = p_entity_code
            AND asc.location_name = p_location_name
            AND asc.is_active = TRUE
            AND asc.day_of_week = (EXTRACT(DOW FROM v_current_date)::INTEGER + 6) % 7  -- Convert to 0=Monday
            AND (asc.max_appointments_per_slot - COALESCE(res.cnt, 0) - COALESCE(holds.cnt, 0)) > 0
            ORDER BY asc.start_time
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
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION get_available_slots_v2 IS 'Returns available appointment slots considering both reservations and active holds.';

-- ============================================================================
-- 10. VIEW: Entity Locations
-- ============================================================================
-- Easy lookup of available locations per entity

CREATE OR REPLACE VIEW v_entity_locations AS
SELECT DISTINCT
    entity_code,
    location_name,
    location_address
FROM appointment_slot_configs
WHERE is_active = TRUE
ORDER BY entity_code, location_name;

COMMENT ON VIEW v_entity_locations IS 'Distinct locations available for each entity (Malabo, Bata, etc.)';

-- ============================================================================
-- 11. INDEX FOR FASTER SLOT LOOKUP
-- ============================================================================

CREATE INDEX IF NOT EXISTS idx_asc_location_lookup
ON appointment_slot_configs(entity_code, location_name, day_of_week, is_active)
WHERE is_active = TRUE;

CREATE INDEX IF NOT EXISTS idx_ah_slot_lookup
ON appointment_holds(entity_code, appointment_date, appointment_time, status)
WHERE status = 'held';

COMMIT;

-- ============================================================================
-- ROLLBACK SCRIPT (run separately if needed)
-- ============================================================================
-- BEGIN;
-- DROP FUNCTION IF EXISTS get_available_slots_v2;
-- DROP FUNCTION IF EXISTS submit_without_appointment;
-- DROP FUNCTION IF EXISTS confirm_appointment_hold;
-- DROP FUNCTION IF EXISTS hold_appointment_slot;
-- DROP FUNCTION IF EXISTS release_expired_appointment_holds;
-- DROP VIEW IF EXISTS v_entity_locations;
-- ALTER TABLE service_requests DROP COLUMN IF EXISTS selected_location;
-- DELETE FROM appointment_slot_configs WHERE location_name LIKE '%Bata%';
-- DELETE FROM appointment_delay_rules WHERE workflow_code LIKE 'PASAPORTE%';
-- DROP TABLE IF EXISTS appointment_holds;
-- COMMIT;
