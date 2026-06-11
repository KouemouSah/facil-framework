-- =============================================================================
-- Migration 031: Cities Table
-- =============================================================================
-- Creates a cities table for dynamic city management
-- Cities are linked to regions (Insular/Continental)
-- Entity locations reference this table for city selection
-- =============================================================================

-- ============================================================================
-- PART 1: CREATE CITIES TABLE
-- ============================================================================

CREATE TABLE IF NOT EXISTS cities (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- City information
    name VARCHAR(100) NOT NULL UNIQUE,
    region VARCHAR(50) NOT NULL,
    description TEXT,
    is_capital BOOLEAN DEFAULT FALSE,

    -- Status
    is_active BOOLEAN DEFAULT TRUE,

    -- Audit fields
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_by UUID REFERENCES users(id),
    updated_by UUID REFERENCES users(id),

    -- Constraints
    CONSTRAINT valid_region CHECK (region IN ('Insular', 'Continental'))
);

-- Index for active cities lookup
CREATE INDEX IF NOT EXISTS idx_cities_active ON cities(is_active) WHERE is_active = TRUE;
CREATE INDEX IF NOT EXISTS idx_cities_region ON cities(region);
CREATE INDEX IF NOT EXISTS idx_cities_name ON cities(name);

-- ============================================================================
-- PART 2: SEED DEFAULT CITIES
-- ============================================================================

INSERT INTO cities (name, region, description, is_capital, is_active)
VALUES
    ('Malabo', 'Insular', 'Capital en la Isla de Bioko', TRUE, TRUE),
    ('Bata', 'Continental', 'Ciudad más grande del continente', FALSE, TRUE),
    ('Mongomo', 'Continental', 'Provincia de Wele-Nzas', FALSE, TRUE),
    ('Evinayong', 'Continental', 'Provincia de Centro Sur', FALSE, TRUE),
    ('Ebebiyin', 'Continental', 'Provincia de Kie-Ntem', FALSE, TRUE)
ON CONFLICT (name) DO NOTHING;

-- ============================================================================
-- PART 3: CREATE ENTITIES TABLE (for dynamic entity codes)
-- ============================================================================

CREATE TABLE IF NOT EXISTS entities (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Entity information
    code VARCHAR(50) NOT NULL UNIQUE,
    name VARCHAR(255) NOT NULL,
    description TEXT,

    -- Status
    is_active BOOLEAN DEFAULT TRUE,

    -- Audit fields
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_by UUID REFERENCES users(id),
    updated_by UUID REFERENCES users(id)
);

-- Index for active entities lookup
CREATE INDEX IF NOT EXISTS idx_entities_active ON entities(is_active) WHERE is_active = TRUE;
CREATE INDEX IF NOT EXISTS idx_entities_code ON entities(code);

-- ============================================================================
-- PART 4: SEED DEFAULT ENTITIES
-- ============================================================================

INSERT INTO entities (code, name, description, is_active)
VALUES
    ('CNEDOGE', 'Centro Nacional de Expedición de Documentos Oficiales', 'Centro Nacional de Expedición de Documentos Oficiales de Guinea Ecuatorial', TRUE),
    ('DGT', 'Dirección General de Tráfico', 'Dirección General de Tráfico', TRUE),
    ('EXTRANJERIA', 'Oficina de Extranjería', 'Oficina de Extranjería e Inmigración', TRUE),
    ('MINFP', 'Ministerio de la Función Pública', 'Ministerio de la Función Pública', TRUE),
    ('ONRC', 'Oficina Nacional del Registro Civil', 'Oficina Nacional del Registro Civil', TRUE),
    ('MINHV', 'Ministerio de Hacienda y Vivienda', 'Ministerio de Hacienda y Vivienda', TRUE)
ON CONFLICT (code) DO NOTHING;

-- ============================================================================
-- PART 5: UPDATE ENTITY_LOCATIONS TABLE (add foreign key references)
-- ============================================================================

-- Add city_id column to entity_locations if it doesn't exist
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'entity_locations' AND column_name = 'city_id'
    ) THEN
        ALTER TABLE entity_locations ADD COLUMN city_id UUID REFERENCES cities(id);
    END IF;
END $$;

-- Add entity_id column to entity_locations if it doesn't exist
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'entity_locations' AND column_name = 'entity_id'
    ) THEN
        ALTER TABLE entity_locations ADD COLUMN entity_id UUID REFERENCES entities(id);
    END IF;
END $$;

-- Update existing records with city_id based on city name
UPDATE entity_locations el
SET city_id = c.id
FROM cities c
WHERE el.city = c.name AND el.city_id IS NULL;

-- Update existing records with entity_id based on entity_code
UPDATE entity_locations el
SET entity_id = e.id
FROM entities e
WHERE el.entity_code = e.code AND el.entity_id IS NULL;

-- Create indexes for the foreign keys
CREATE INDEX IF NOT EXISTS idx_entity_locations_city_id ON entity_locations(city_id);
CREATE INDEX IF NOT EXISTS idx_entity_locations_entity_id ON entity_locations(entity_id);

-- ============================================================================
-- PART 6: GRANT PERMISSIONS
-- ============================================================================

GRANT SELECT ON cities TO authenticated;
GRANT SELECT ON entities TO authenticated;

-- Admin can manage cities and entities
GRANT INSERT, UPDATE, DELETE ON cities TO authenticated;
GRANT INSERT, UPDATE, DELETE ON entities TO authenticated;

-- ============================================================================
-- MIGRATION COMPLETE
-- ============================================================================
