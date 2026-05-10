-- =============================================================================
-- Migration 029: Add City Support + Appointment Holds
-- =============================================================================
-- Combines the essential features from original 029 and 030:
-- 1. Add city column to appointment_slot_configs (for statistics)
-- 2. Create appointment_holds table (for pre-payment slot reservations)
-- 3. Update existing data with city values
-- 4. Add PostgreSQL functions for hold/confirm/release flow
-- =============================================================================

-- ============================================================================
-- PART 1: ADD CITY COLUMN TO EXISTING TABLES
-- ============================================================================

-- Add city column to appointment_slot_configs
ALTER TABLE appointment_slot_configs
ADD COLUMN IF NOT EXISTS city VARCHAR(100);

-- Add region column (for grouping: Insular vs Continental)
ALTER TABLE appointment_slot_configs
ADD COLUMN IF NOT EXISTS region VARCHAR(50);

-- Update existing Malabo locations
UPDATE appointment_slot_configs
SET city = 'Malabo', region = 'Insular'
WHERE location_name ILIKE '%malabo%'
   OR location_name ILIKE '%cnedoge%'
   OR city IS NULL;

-- Add index for city-based queries
CREATE INDEX IF NOT EXISTS idx_appointment_slot_configs_city
ON appointment_slot_configs(city);

CREATE INDEX IF NOT EXISTS idx_appointment_slot_configs_entity_city
ON appointment_slot_configs(entity_code, city);

-- ============================================================================
-- PART 2: ADD BATA LOCATIONS
-- ============================================================================

-- Insert Bata locations for main entities
INSERT INTO appointment_slot_configs (
    entity_code, day_of_week, start_time, end_time,
    slot_duration_minutes, max_appointments_per_slot,
    location_name, location_address, city, region, is_active
)
SELECT
    entity_code,
    day_of_week,
    start_time,
    end_time,
    slot_duration_minutes,
    max_appointments_per_slot,
    REPLACE(location_name, 'Malabo', 'Bata'),
    REPLACE(COALESCE(location_address, ''), 'Malabo', 'Bata'),
    'Bata',
    'Continental',
    TRUE
FROM appointment_slot_configs
WHERE city = 'Malabo'
  AND entity_code IN ('CNEDOGE', 'DGT', 'EXTRANJERIA', 'MINFP')
ON CONFLICT DO NOTHING;

-- ============================================================================
-- PART 3: CREATE APPOINTMENT HOLDS TABLE
-- ============================================================================

-- Enum for hold status
DO $$ BEGIN
    CREATE TYPE appointment_hold_status AS ENUM (
        'held',       -- Slot held, waiting for payment
        'confirmed',  -- Payment completed, appointment confirmed
        'expired',    -- 15 minutes passed without payment
        'released',   -- User manually released
        'fallback'    -- Submitted without appointment (no slots available)
    );
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- Table for temporary appointment holds
CREATE TABLE IF NOT EXISTS appointment_holds (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    service_request_id UUID NOT NULL REFERENCES service_requests(id) ON DELETE CASCADE,
    slot_config_id UUID REFERENCES appointment_slot_configs(id),

    -- Hold details
    appointment_date DATE NOT NULL,
    appointment_time TIME NOT NULL,
    location_name VARCHAR(255) NOT NULL,
    location_address TEXT,
    city VARCHAR(100),

    -- Status tracking
    status appointment_hold_status NOT NULL DEFAULT 'held',
    held_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT (NOW() + INTERVAL '15 minutes'),
    confirmed_at TIMESTAMP WITH TIME ZONE,
    released_at TIMESTAMP WITH TIME ZONE,

    -- Metadata
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),

    -- Constraints
    CONSTRAINT unique_active_hold_per_request
        UNIQUE (service_request_id)
        DEFERRABLE INITIALLY DEFERRED
);

-- Indexes for appointment_holds
CREATE INDEX IF NOT EXISTS idx_appointment_holds_status
ON appointment_holds(status) WHERE status = 'held';

CREATE INDEX IF NOT EXISTS idx_appointment_holds_expires
ON appointment_holds(expires_at) WHERE status = 'held';

CREATE INDEX IF NOT EXISTS idx_appointment_holds_city
ON appointment_holds(city);

CREATE INDEX IF NOT EXISTS idx_appointment_holds_date_city
ON appointment_holds(appointment_date, city);

-- ============================================================================
-- PART 4: ADD COLUMNS TO SERVICE_REQUESTS
-- ============================================================================

-- Add selected_location column to service_requests
ALTER TABLE service_requests
ADD COLUMN IF NOT EXISTS selected_location VARCHAR(255);

ALTER TABLE service_requests
ADD COLUMN IF NOT EXISTS selected_city VARCHAR(100);

-- Index for city-based statistics on service_requests
CREATE INDEX IF NOT EXISTS idx_service_requests_city
ON service_requests(selected_city) WHERE selected_city IS NOT NULL;

-- ============================================================================
-- PART 5: FUNCTIONS FOR APPOINTMENT HOLD FLOW
-- ============================================================================

-- Function to hold a slot (called before payment)
CREATE OR REPLACE FUNCTION hold_appointment_slot(
    p_service_request_id UUID,
    p_slot_config_id UUID,
    p_appointment_date DATE,
    p_appointment_time TIME,
    p_location_name VARCHAR(255),
    p_location_address TEXT DEFAULT NULL,
    p_city VARCHAR(100) DEFAULT NULL
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
    SELECT COUNT(*) INTO v_current_holds
    FROM appointment_holds
    WHERE slot_config_id = p_slot_config_id
      AND appointment_date = p_appointment_date
      AND appointment_time = p_appointment_time
      AND status IN ('held', 'confirmed')
      AND (status = 'confirmed' OR expires_at > NOW());

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
        location_name, location_address, city,
        status, expires_at
    )
    VALUES (
        p_service_request_id, p_slot_config_id,
        p_appointment_date, p_appointment_time,
        p_location_name, p_location_address, COALESCE(p_city, v_slot_config.city),
        'held', v_expires_at
    )
    RETURNING id INTO v_hold_id;

    RETURN QUERY SELECT TRUE, v_hold_id, v_expires_at, NULL::TEXT;
END;
$$;

-- Function to confirm a hold (called after payment)
CREATE OR REPLACE FUNCTION confirm_appointment_hold(
    p_service_request_id UUID
)
RETURNS TABLE (
    success BOOLEAN,
    appointment_date DATE,
    appointment_time TIME,
    location_name VARCHAR(255),
    city VARCHAR(100),
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
        RETURN QUERY SELECT FALSE, NULL::DATE, NULL::TIME, NULL::VARCHAR(255),
            NULL::VARCHAR(100), 'No active hold found or hold expired'::TEXT;
        RETURN;
    END IF;

    -- Confirm the hold
    UPDATE appointment_holds
    SET status = 'confirmed', confirmed_at = NOW(), updated_at = NOW()
    WHERE id = v_hold.id;

    -- Update service_request with appointment details
    UPDATE service_requests
    SET
        appointment_date = v_hold.appointment_date,
        appointment_time = v_hold.appointment_time,
        selected_location = v_hold.location_name,
        selected_city = v_hold.city,
        updated_at = NOW()
    WHERE id = p_service_request_id;

    RETURN QUERY SELECT TRUE, v_hold.appointment_date, v_hold.appointment_time,
        v_hold.location_name, v_hold.city, NULL::TEXT;
END;
$$;

-- Function to release expired holds (run by cron job)
CREATE OR REPLACE FUNCTION release_expired_appointment_holds()
RETURNS INTEGER
LANGUAGE plpgsql
AS $$
DECLARE
    v_count INTEGER;
BEGIN
    UPDATE appointment_holds
    SET status = 'expired', released_at = NOW(), updated_at = NOW()
    WHERE status = 'held'
      AND expires_at <= NOW();

    GET DIAGNOSTICS v_count = ROW_COUNT;
    RETURN v_count;
END;
$$;

-- Function to submit without appointment (fallback when no slots)
CREATE OR REPLACE FUNCTION submit_without_appointment(
    p_service_request_id UUID,
    p_preferred_location VARCHAR(255),
    p_preferred_city VARCHAR(100) DEFAULT NULL
)
RETURNS TABLE (
    success BOOLEAN,
    location_name VARCHAR(255),
    city VARCHAR(100),
    error_message TEXT
)
LANGUAGE plpgsql
AS $$
BEGIN
    -- Release any existing hold
    UPDATE appointment_holds
    SET status = 'released', released_at = NOW(), updated_at = NOW()
    WHERE service_request_id = p_service_request_id
      AND status = 'held';

    -- Create fallback record
    INSERT INTO appointment_holds (
        service_request_id, appointment_date, appointment_time,
        location_name, city, status
    )
    VALUES (
        p_service_request_id, CURRENT_DATE, '00:00:00',
        p_preferred_location, p_preferred_city, 'fallback'
    );

    -- Update service_request
    UPDATE service_requests
    SET
        selected_location = p_preferred_location,
        selected_city = p_preferred_city,
        updated_at = NOW()
    WHERE id = p_service_request_id;

    RETURN QUERY SELECT TRUE, p_preferred_location, p_preferred_city, NULL::TEXT;
END;
$$;

-- ============================================================================
-- PART 6: STATISTICS VIEWS
-- ============================================================================

-- View: Appointments by city
CREATE OR REPLACE VIEW v_appointments_by_city AS
SELECT
    COALESCE(city, 'Non spécifié') as city,
    COUNT(*) as total_appointments,
    COUNT(*) FILTER (WHERE status = 'confirmed') as confirmed,
    COUNT(*) FILTER (WHERE status = 'held') as pending,
    COUNT(*) FILTER (WHERE status = 'expired') as expired,
    COUNT(*) FILTER (WHERE status = 'fallback') as without_appointment
FROM appointment_holds
GROUP BY city;

-- View: Service requests by city
-- Note: Uses UPPERCASE enum values as defined in service_request_status_enum
CREATE OR REPLACE VIEW v_service_requests_by_city AS
SELECT
    COALESCE(selected_city, 'Non spécifié') as city,
    COUNT(*) as total_requests,
    COUNT(*) FILTER (WHERE status = 'DRAFT') as draft,
    COUNT(*) FILTER (WHERE status = 'SUBMITTED') as submitted,
    COUNT(*) FILTER (WHERE status = 'UNDER_REVIEW') as under_review,
    COUNT(*) FILTER (WHERE status = 'DOSSIER_VALIDE') as approved,
    COUNT(*) FILTER (WHERE status = 'COMPLETED') as completed
FROM service_requests
GROUP BY selected_city;

-- View: Slot availability by city
-- Note: Using 'sc' alias instead of 'asc' because ASC is a SQL reserved keyword
CREATE OR REPLACE VIEW v_slot_availability_by_city AS
SELECT
    sc.city,
    sc.entity_code,
    sc.location_name,
    COUNT(DISTINCT sc.id) as slot_configs,
    SUM(sc.max_appointments_per_slot) as daily_capacity,
    COUNT(ah.id) FILTER (WHERE ah.status = 'confirmed' AND ah.appointment_date >= CURRENT_DATE) as upcoming_confirmed
FROM appointment_slot_configs sc
LEFT JOIN appointment_holds ah ON sc.id = ah.slot_config_id
WHERE sc.is_active = TRUE
GROUP BY sc.city, sc.entity_code, sc.location_name;

-- ============================================================================
-- PART 7: GRANT PERMISSIONS
-- ============================================================================

-- Grant permissions on new table
GRANT SELECT, INSERT, UPDATE ON appointment_holds TO authenticated;
GRANT SELECT ON v_appointments_by_city TO authenticated;
GRANT SELECT ON v_service_requests_by_city TO authenticated;
GRANT SELECT ON v_slot_availability_by_city TO authenticated;

-- ============================================================================
-- MIGRATION COMPLETE
-- ============================================================================
