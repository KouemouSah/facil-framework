-- ============================================================================
-- Migration 030: Entity Locations - Architecture Propre (Sans Duplication)
-- ============================================================================
-- Purpose:
--   Create a normalized entity_locations table as single source of truth.
--   Remove duplicated location columns from other tables.
--   Use FK references instead of storing location data in multiple places.
--
-- Architecture:
--   entity_locations (source de verite)
--       ↓ FK
--   appointment_slot_configs, appointment_holds, appointment_reservations
--       ↓ FK (nullable)
--   service_requests
--
-- Cities:
--   - Insular: Malabo (capital)
--   - Continental: Bata, Mongomo, Evinayong, Ebebiyin
--
-- Date: 2026-01-03
-- ============================================================================

BEGIN;

-- ============================================================================
-- 1. DROP OLD OBJECTS (if exist from previous attempts)
-- ============================================================================

DROP VIEW IF EXISTS v_entity_locations CASCADE;
DROP FUNCTION IF EXISTS get_entity_locations CASCADE;
DROP FUNCTION IF EXISTS get_appointment_entity_for_workflow CASCADE;
DROP TABLE IF EXISTS appointment_entity_mapping CASCADE;

-- ============================================================================
-- 2. CREATE ENTITY_LOCATIONS TABLE (Source de Verite)
-- ============================================================================

CREATE TABLE IF NOT EXISTS entity_locations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Entity reference
    entity_code VARCHAR(50) NOT NULL,

    -- Geographic info
    city VARCHAR(100) NOT NULL,
    region VARCHAR(50) NOT NULL,

    -- Location details
    location_name VARCHAR(255) NOT NULL,
    location_address TEXT,

    -- Contact info
    phone VARCHAR(50),
    email VARCHAR(255),

    -- Attributes
    is_main_office BOOLEAN NOT NULL DEFAULT FALSE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,

    -- Operating hours (JSONB for flexibility)
    operating_hours JSONB DEFAULT '{
        "monday": {"open": "08:00", "close": "16:00"},
        "tuesday": {"open": "08:00", "close": "16:00"},
        "wednesday": {"open": "08:00", "close": "16:00"},
        "thursday": {"open": "08:00", "close": "16:00"},
        "friday": {"open": "08:00", "close": "16:00"}
    }'::jsonb,

    -- Notes
    notes TEXT,

    -- Audit
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by UUID REFERENCES users(id) ON DELETE SET NULL,
    updated_by UUID REFERENCES users(id) ON DELETE SET NULL,

    -- Constraints
    CONSTRAINT unique_entity_city UNIQUE (entity_code, city),
    CONSTRAINT valid_region CHECK (region IN ('Insular', 'Continental')),
    CONSTRAINT valid_city CHECK (city IN ('Malabo', 'Bata', 'Mongomo', 'Evinayong', 'Ebebiyin'))
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_entity_locations_entity ON entity_locations(entity_code);
CREATE INDEX IF NOT EXISTS idx_entity_locations_city ON entity_locations(city);
CREATE INDEX IF NOT EXISTS idx_entity_locations_region ON entity_locations(region);
CREATE INDEX IF NOT EXISTS idx_entity_locations_active ON entity_locations(is_active) WHERE is_active = TRUE;
CREATE INDEX IF NOT EXISTS idx_entity_locations_entity_active ON entity_locations(entity_code, is_active) WHERE is_active = TRUE;

-- Comments
COMMENT ON TABLE entity_locations IS 'Master table of physical locations for each government entity. Single source of truth for location data.';
COMMENT ON COLUMN entity_locations.entity_code IS 'Entity code (CNEDOGE, DGT, EXTRANJERIA, MINFP, ONRC, MINHV)';
COMMENT ON COLUMN entity_locations.city IS 'City: Malabo (Insular) or Bata/Mongomo/Evinayong/Ebebiyin (Continental)';
COMMENT ON COLUMN entity_locations.region IS 'Region: Insular (Bioko island) or Continental (mainland)';
COMMENT ON COLUMN entity_locations.is_main_office IS 'True for main office (typically in Malabo, the capital)';
COMMENT ON COLUMN entity_locations.operating_hours IS 'Operating hours per day as JSONB: {"monday": {"open": "08:00", "close": "16:00"}, ...}';

-- ============================================================================
-- 3. SEED DATA - INITIAL LOCATIONS
-- ============================================================================

INSERT INTO entity_locations (entity_code, city, region, location_name, location_address, phone, is_main_office) VALUES
-- CNEDOGE
('CNEDOGE', 'Malabo', 'Insular', 'CNEDOGE Malabo', 'Monstoles', '+240 222 251 000', TRUE),
('CNEDOGE', 'Bata', 'Continental', 'CNEDOGE Bata', 'Paseo Maritimo', '+240 333 082 000', FALSE),
-- DGT
('DGT', 'Malabo', 'Insular', 'DG de Trafico', 'Malabo II - Ministerio del Interior', '+240 222 252 000', TRUE),
('DGT', 'Bata', 'Continental', 'DG de Trafico', 'Oficina Regional de Trafico', '+240 333 083 000', FALSE),
-- EXTRANJERIA
('EXTRANJERIA', 'Malabo', 'Insular', 'Extranjeria Malabo', 'Comisaria Central - Guantanamo', '+240 222 253 000', TRUE),
('EXTRANJERIA', 'Bata', 'Continental', 'Extranjeria Bata', 'Comisaria de Bata', '+240 333 084 000', FALSE),
-- MINFP (solo Malabo)
('MINFP', 'Malabo', 'Insular', 'Ministerio de la Funcion Publica', 'Malabo II', '+240 222 254 000', TRUE),
-- ONRC
('ONRC', 'Malabo', 'Insular', 'Palacio de Justicia', 'Avenida Hassan II', '+240 222 255 000', TRUE),
('ONRC', 'Bata', 'Continental', 'Palacio de Justicia', 'Juzgados de Bata', '+240 333 085 000', FALSE),
-- MINHV (solo Malabo)
('MINHV', 'Malabo', 'Insular', 'Ministerio de Hacienda', 'Malabo 2', '+240 222 256 000', TRUE)
ON CONFLICT (entity_code, city) DO UPDATE SET
    location_name = EXCLUDED.location_name,
    location_address = EXCLUDED.location_address,
    phone = EXCLUDED.phone,
    is_main_office = EXCLUDED.is_main_office,
    updated_at = NOW();

-- ============================================================================
-- 4. MODIFY APPOINTMENT_SLOT_CONFIGS
-- ============================================================================
-- Remove duplicated columns, add FK to entity_locations

-- Step 4.0: Drop dependent views FIRST (they will be recreated in section 11)
DROP VIEW IF EXISTS v_available_appointment_slots CASCADE;
DROP VIEW IF EXISTS v_slot_availability_by_city CASCADE;
DROP VIEW IF EXISTS v_appointments_by_city CASCADE;
DROP VIEW IF EXISTS v_service_requests_by_city CASCADE;

-- Step 4.1: Add entity_location_id column
ALTER TABLE appointment_slot_configs
ADD COLUMN IF NOT EXISTS entity_location_id UUID;

-- Step 4.2: Populate entity_location_id from existing data
UPDATE appointment_slot_configs asc_table
SET entity_location_id = el.id
FROM entity_locations el
WHERE asc_table.entity_code = el.entity_code
  AND asc_table.city = el.city
  AND asc_table.entity_location_id IS NULL;

-- Step 4.3: For slots without city, default to Malabo
UPDATE appointment_slot_configs asc_table
SET entity_location_id = el.id
FROM entity_locations el
WHERE asc_table.entity_code = el.entity_code
  AND el.city = 'Malabo'
  AND asc_table.entity_location_id IS NULL;

-- Step 4.4: Add FK constraint
ALTER TABLE appointment_slot_configs
ADD CONSTRAINT fk_slot_entity_location
FOREIGN KEY (entity_location_id) REFERENCES entity_locations(id);

-- Step 4.5: Drop old columns (architecture propre - pas de retrocompatibilite)
ALTER TABLE appointment_slot_configs
DROP COLUMN IF EXISTS location_name,
DROP COLUMN IF EXISTS location_address,
DROP COLUMN IF EXISTS city,
DROP COLUMN IF EXISTS region;

-- Step 4.6: Drop old unique constraint and create new one
-- Must drop constraint (not index) because unique_slot is a named constraint
ALTER TABLE appointment_slot_configs DROP CONSTRAINT IF EXISTS unique_slot;
ALTER TABLE appointment_slot_configs DROP CONSTRAINT IF EXISTS unique_slot_v2;
DROP INDEX IF EXISTS unique_slot;
DROP INDEX IF EXISTS unique_slot_v2;
CREATE UNIQUE INDEX unique_slot_v2 ON appointment_slot_configs(entity_location_id, day_of_week, start_time);

-- Step 4.7: Make entity_location_id NOT NULL (after data migration)
-- Note: Only if all slots have been assigned a location
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM appointment_slot_configs WHERE entity_location_id IS NULL
    ) THEN
        ALTER TABLE appointment_slot_configs
        ALTER COLUMN entity_location_id SET NOT NULL;
    END IF;
END $$;

-- Step 4.8: Update index for entity-based queries
DROP INDEX IF EXISTS idx_asc_entity;
CREATE INDEX idx_slot_entity_location ON appointment_slot_configs(entity_location_id);

COMMENT ON COLUMN appointment_slot_configs.entity_location_id IS 'FK to entity_locations - the physical location for this slot';

-- ============================================================================
-- 5. MODIFY APPOINTMENT_HOLDS
-- ============================================================================
-- Remove duplicated columns, add FK to entity_locations

-- Step 5.1: Add entity_location_id column
ALTER TABLE appointment_holds
ADD COLUMN IF NOT EXISTS entity_location_id UUID;

-- Step 5.2: Populate from existing data
UPDATE appointment_holds ah
SET entity_location_id = el.id
FROM entity_locations el
WHERE ah.city = el.city
  AND ah.entity_location_id IS NULL;

-- Step 5.3: Default to Malabo for holds without city
UPDATE appointment_holds ah
SET entity_location_id = el.id
FROM entity_locations el
WHERE el.city = 'Malabo'
  AND el.entity_code = 'CNEDOGE'  -- Default entity
  AND ah.entity_location_id IS NULL;

-- Step 5.4: Add FK constraint
ALTER TABLE appointment_holds
ADD CONSTRAINT fk_hold_entity_location
FOREIGN KEY (entity_location_id) REFERENCES entity_locations(id);

-- Step 5.5: Drop old columns
ALTER TABLE appointment_holds
DROP COLUMN IF EXISTS location_name,
DROP COLUMN IF EXISTS location_address,
DROP COLUMN IF EXISTS city;

COMMENT ON COLUMN appointment_holds.entity_location_id IS 'FK to entity_locations - the location for this appointment hold';

-- ============================================================================
-- 6. MODIFY APPOINTMENT_RESERVATIONS
-- ============================================================================
-- Remove duplicated columns, add FK to entity_locations

-- Step 6.1: Add entity_location_id column
ALTER TABLE appointment_reservations
ADD COLUMN IF NOT EXISTS entity_location_id UUID;

-- Step 6.2: Populate from existing data
UPDATE appointment_reservations ar
SET entity_location_id = el.id
FROM entity_locations el
WHERE ar.entity_code = el.entity_code
  AND ar.entity_location_id IS NULL;

-- Step 6.3: Add FK constraint
ALTER TABLE appointment_reservations
ADD CONSTRAINT fk_reservation_entity_location
FOREIGN KEY (entity_location_id) REFERENCES entity_locations(id);

-- Step 6.4: Drop old columns
ALTER TABLE appointment_reservations
DROP COLUMN IF EXISTS location_name,
DROP COLUMN IF EXISTS location_address,
DROP COLUMN IF EXISTS entity_code;

COMMENT ON COLUMN appointment_reservations.entity_location_id IS 'FK to entity_locations - the location for this reservation';

-- ============================================================================
-- 7. MODIFY SERVICE_REQUESTS
-- ============================================================================
-- Remove duplicated columns, add FK to entity_locations (nullable)

-- Step 7.1: Add entity_location_id column
ALTER TABLE service_requests
ADD COLUMN IF NOT EXISTS entity_location_id UUID;

-- Step 7.2: Populate from existing data (if possible)
UPDATE service_requests sr
SET entity_location_id = el.id
FROM entity_locations el
WHERE sr.selected_city = el.city
  AND sr.entity_code = el.entity_code
  AND sr.entity_location_id IS NULL;

-- Step 7.3: Add FK constraint (nullable - not all requests have appointments)
ALTER TABLE service_requests
ADD CONSTRAINT fk_request_entity_location
FOREIGN KEY (entity_location_id) REFERENCES entity_locations(id);

-- Step 7.4: Drop old columns
ALTER TABLE service_requests
DROP COLUMN IF EXISTS selected_location,
DROP COLUMN IF EXISTS selected_city;

-- Step 7.5: Create index
CREATE INDEX IF NOT EXISTS idx_sr_entity_location ON service_requests(entity_location_id) WHERE entity_location_id IS NOT NULL;

COMMENT ON COLUMN service_requests.entity_location_id IS 'FK to entity_locations - user selected location for appointment (nullable)';

-- ============================================================================
-- 8. CREATE VIEW FOR ACTIVE LOCATIONS
-- ============================================================================

CREATE OR REPLACE VIEW v_entity_locations AS
SELECT
    id,
    entity_code,
    city,
    region,
    location_name,
    location_address,
    phone,
    email,
    is_main_office,
    is_active,
    operating_hours
FROM entity_locations
WHERE is_active = TRUE
ORDER BY entity_code, is_main_office DESC, city;

COMMENT ON VIEW v_entity_locations IS 'Active locations per entity for appointment selection';

-- ============================================================================
-- 9. CREATE HELPER FUNCTION
-- ============================================================================

CREATE OR REPLACE FUNCTION get_entity_locations(
    p_entity_code VARCHAR(50)
)
RETURNS TABLE (
    id UUID,
    city VARCHAR(100),
    region VARCHAR(50),
    location_name VARCHAR(255),
    location_address TEXT,
    phone VARCHAR(50),
    is_main_office BOOLEAN
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        el.id,
        el.city,
        el.region,
        el.location_name,
        el.location_address,
        el.phone,
        el.is_main_office
    FROM entity_locations el
    WHERE el.entity_code = p_entity_code
      AND el.is_active = TRUE
    ORDER BY el.is_main_office DESC, el.city;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION get_entity_locations IS 'Returns all active locations for an entity (main office first)';

-- ============================================================================
-- 10. UPDATE HOLD FUNCTIONS TO USE entity_location_id
-- ============================================================================

-- Drop and recreate hold_appointment_slot
DROP FUNCTION IF EXISTS hold_appointment_slot CASCADE;

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

COMMENT ON FUNCTION hold_appointment_slot IS 'Creates a temporary 15-minute hold on an appointment slot. Uses entity_location_id FK.';

-- Update confirm function
DROP FUNCTION IF EXISTS confirm_appointment_hold CASCADE;

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

COMMENT ON FUNCTION confirm_appointment_hold IS 'Confirms an appointment hold after payment. Updates service_request with appointment details.';

-- Update submit without appointment function
DROP FUNCTION IF EXISTS submit_without_appointment CASCADE;

CREATE OR REPLACE FUNCTION submit_without_appointment(
    p_service_request_id UUID,
    p_entity_location_id UUID
)
RETURNS TABLE (
    success BOOLEAN,
    location_id UUID,
    error_message TEXT
)
LANGUAGE plpgsql
AS $$
BEGIN
    -- Verify location exists
    IF NOT EXISTS (SELECT 1 FROM entity_locations WHERE id = p_entity_location_id AND is_active = TRUE) THEN
        RETURN QUERY SELECT FALSE, NULL::UUID, 'Location not found or inactive'::TEXT;
        RETURN;
    END IF;

    -- Release any existing hold
    UPDATE appointment_holds
    SET status = 'released', released_at = NOW(), updated_at = NOW()
    WHERE service_request_id = p_service_request_id
      AND status = 'held';

    -- Create fallback record
    INSERT INTO appointment_holds (
        service_request_id, appointment_date, appointment_time,
        entity_location_id, status
    )
    VALUES (
        p_service_request_id, CURRENT_DATE, '00:00:00',
        p_entity_location_id, 'fallback'
    );

    -- Update service_request
    UPDATE service_requests
    SET
        entity_location_id = p_entity_location_id,
        updated_at = NOW()
    WHERE id = p_service_request_id;

    RETURN QUERY SELECT TRUE, p_entity_location_id, NULL::TEXT;
END;
$$;

COMMENT ON FUNCTION submit_without_appointment IS 'Submits request without appointment (fallback). Agent will schedule later.';

-- ============================================================================
-- 11. UPDATE STATISTICS VIEWS
-- ============================================================================

-- View: Appointments by city (using entity_locations)
DROP VIEW IF EXISTS v_appointments_by_city CASCADE;

CREATE OR REPLACE VIEW v_appointments_by_city AS
SELECT
    COALESCE(el.city, 'Non specifie') as city,
    COALESCE(el.region, 'Non specifie') as region,
    COUNT(*) as total_appointments,
    COUNT(*) FILTER (WHERE ah.status = 'confirmed') as confirmed,
    COUNT(*) FILTER (WHERE ah.status = 'held') as pending,
    COUNT(*) FILTER (WHERE ah.status = 'expired') as expired,
    COUNT(*) FILTER (WHERE ah.status = 'fallback') as without_appointment
FROM appointment_holds ah
LEFT JOIN entity_locations el ON ah.entity_location_id = el.id
GROUP BY el.city, el.region;

-- View: Service requests by city (using entity_locations)
DROP VIEW IF EXISTS v_service_requests_by_city CASCADE;

CREATE OR REPLACE VIEW v_service_requests_by_city AS
SELECT
    COALESCE(el.city, 'Non specifie') as city,
    COALESCE(el.region, 'Non specifie') as region,
    COUNT(*) as total_requests,
    COUNT(*) FILTER (WHERE sr.status = 'DRAFT') as draft,
    COUNT(*) FILTER (WHERE sr.status = 'SUBMITTED') as submitted,
    COUNT(*) FILTER (WHERE sr.status = 'UNDER_REVIEW') as under_review,
    COUNT(*) FILTER (WHERE sr.status = 'DOSSIER_VALIDE') as approved,
    COUNT(*) FILTER (WHERE sr.status = 'COMPLETED') as completed
FROM service_requests sr
LEFT JOIN entity_locations el ON sr.entity_location_id = el.id
GROUP BY el.city, el.region;

-- View: Slot availability by location
DROP VIEW IF EXISTS v_slot_availability_by_city CASCADE;

CREATE OR REPLACE VIEW v_slot_availability_by_location AS
SELECT
    el.id as location_id,
    el.entity_code,
    el.city,
    el.region,
    el.location_name,
    COUNT(DISTINCT sc.id) as slot_configs,
    COALESCE(SUM(sc.max_appointments_per_slot), 0) as daily_capacity,
    COUNT(ah.id) FILTER (WHERE ah.status = 'confirmed' AND ah.appointment_date >= CURRENT_DATE) as upcoming_confirmed
FROM entity_locations el
LEFT JOIN appointment_slot_configs sc ON el.id = sc.entity_location_id AND sc.is_active = TRUE
LEFT JOIN appointment_holds ah ON sc.id = ah.slot_config_id
WHERE el.is_active = TRUE
GROUP BY el.id, el.entity_code, el.city, el.region, el.location_name
ORDER BY el.entity_code, el.is_main_office DESC, el.city;

-- ============================================================================
-- 12. TRIGGER FOR updated_at
-- ============================================================================

CREATE OR REPLACE FUNCTION update_entity_location_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_entity_location_updated_at ON entity_locations;
CREATE TRIGGER trigger_entity_location_updated_at
    BEFORE UPDATE ON entity_locations
    FOR EACH ROW
    EXECUTE FUNCTION update_entity_location_timestamp();

-- ============================================================================
-- 13. GRANT PERMISSIONS
-- ============================================================================

GRANT SELECT ON entity_locations TO authenticated;
GRANT SELECT ON v_entity_locations TO authenticated;
GRANT SELECT ON v_appointments_by_city TO authenticated;
GRANT SELECT ON v_service_requests_by_city TO authenticated;
GRANT SELECT ON v_slot_availability_by_location TO authenticated;

COMMIT;

-- ============================================================================
-- ROLLBACK SCRIPT (run separately if needed)
-- ============================================================================
-- BEGIN;
-- -- Restore old columns (would need to repopulate data)
-- ALTER TABLE appointment_slot_configs ADD COLUMN location_name VARCHAR(255);
-- ALTER TABLE appointment_slot_configs ADD COLUMN location_address TEXT;
-- ALTER TABLE appointment_slot_configs ADD COLUMN city VARCHAR(100);
-- ALTER TABLE appointment_slot_configs ADD COLUMN region VARCHAR(50);
-- -- ... etc
-- DROP TABLE IF EXISTS entity_locations CASCADE;
-- COMMIT;
