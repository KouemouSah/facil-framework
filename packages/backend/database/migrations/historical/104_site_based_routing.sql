-- Migration 104: Site-Based Routing Architecture
--
-- Problem: Agents are linked to entities (CNEDOGE, DGT) not to sites
-- (CNEDOGE Malabo vs CNEDOGE Bata). No geographic routing exists.
--
-- Changes:
-- 1. Drop UNIQUE(entity_code, city) to allow multiple sites per entity+city
-- 2. Add UNIQUE(entity_code, location_name) instead
-- 3. Add entity_location_id to agent_profiles (nullable FK)
-- 4. Index for agent-location lookups
-- 5. Backfill existing agents with main office location
-- 6. Backfill existing service_requests from appointment_reservations

-- 1a. Drop blocking UNIQUE constraint (allow multiple sites per entity+city)
ALTER TABLE entity_locations DROP CONSTRAINT IF EXISTS unique_entity_city;

-- 1b. Add new UNIQUE on (entity_code, location_name) instead
-- Different sites in same city MUST have different names
-- Use DO block to avoid error if constraint already exists
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'unique_entity_location_name'
    ) THEN
        ALTER TABLE entity_locations
            ADD CONSTRAINT unique_entity_location_name UNIQUE (entity_code, location_name);
    END IF;
END $$;

-- 2. Add entity_location_id to agent_profiles
ALTER TABLE agent_profiles
    ADD COLUMN IF NOT EXISTS entity_location_id UUID REFERENCES entity_locations(id);

COMMENT ON COLUMN agent_profiles.entity_location_id IS
    'FK to entity_locations. NULL = supervisor/floating agent (sees all sites). SET = bound to specific site.';

-- 3. Index for agent-location lookups
CREATE INDEX IF NOT EXISTS idx_agent_profiles_entity_location
    ON agent_profiles(entity_location_id) WHERE entity_location_id IS NOT NULL;

-- 4. Ensure index exists for service_requests by location
-- (column was added in migration 030 but index may be missing)
CREATE INDEX IF NOT EXISTS idx_service_requests_entity_location
    ON service_requests(entity_location_id) WHERE entity_location_id IS NOT NULL;

-- 5. Backfill existing agent_profiles with main office location
-- Non-supervisor agents get assigned to the main office of their entity
UPDATE agent_profiles ap
SET entity_location_id = el.id
FROM entities e
JOIN entity_locations el ON el.entity_code = e.code AND el.is_main_office = TRUE AND el.is_active = TRUE
WHERE ap.entity_id = e.id
  AND ap.entity_location_id IS NULL
  AND ap.is_supervisor = FALSE;

-- 6. Backfill existing service_requests from appointment_reservations
-- Links service_requests to the entity_location used for their appointment
UPDATE service_requests sr
SET entity_location_id = ar.entity_location_id
FROM appointment_reservations ar
WHERE ar.service_request_id = sr.id
  AND sr.entity_location_id IS NULL;
