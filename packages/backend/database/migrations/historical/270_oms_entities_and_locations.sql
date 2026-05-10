-- Migration 221: OMS Entities and Locations
--
-- Creates 8 entities for the commercial license workflow:
--   - 2 payment validators: AYUNTAMIENTO (municipal), CAMARA_COMERCIO (chamber)
--   - 6 ministry processing entities (Mode A post-TESORO routing)
--
-- TESORO already exists (validates tesoro fee_type payments).
-- Each entity gets 2 locations: Malabo (Insular) + Bata (Continental).

BEGIN;

-- ============================================================
-- 1. Payment Validator Entities
-- ============================================================

INSERT INTO entities (code, name, entity_type, ministry_id, workflow_codes)
VALUES
    ('AYUNTAMIENTO', 'Ayuntamiento', 'entity', 107, '[]'::jsonb),
    ('CAMARA_COMERCIO', 'Cámara de Comercio', 'entity', 108, '[]'::jsonb)
ON CONFLICT (code) DO NOTHING;

-- ============================================================
-- 2. Ministry Processing Entities (Mode A post-TESORO)
-- ============================================================

INSERT INTO entities (code, name, entity_type, ministry_id, workflow_codes)
VALUES
    ('MIN_HACIENDA', 'Ministerio de Hacienda', 'entity', 91, '[]'::jsonb),
    ('MIN_COMERCIO', 'Ministerio de Comercio', 'entity', 87, '[]'::jsonb),
    ('MIN_INFORMACION', 'Ministerio de Información', 'entity', 92, '[]'::jsonb),
    ('MIN_TURISMO', 'Ministerio de Turismo', 'entity', 103, '[]'::jsonb),
    ('MIN_AGRICULTURA', 'Ministerio de Agricultura', 'entity', 104, '[]'::jsonb),
    ('MIN_ELECTRICIDAD', 'Ministerio de Electricidad', 'entity', 105, '[]'::jsonb)
ON CONFLICT (code) DO NOTHING;

-- ============================================================
-- 3. Entity Locations (2 per entity = 16 total)
-- ============================================================

DO $$
DECLARE
    v_malabo_id UUID := (SELECT id FROM cities WHERE name = 'Malabo');
    v_bata_id UUID := (SELECT id FROM cities WHERE name = 'Bata');
    v_entity_codes TEXT[] := ARRAY[
        'AYUNTAMIENTO', 'CAMARA_COMERCIO',
        'MIN_HACIENDA', 'MIN_COMERCIO', 'MIN_INFORMACION',
        'MIN_TURISMO', 'MIN_AGRICULTURA', 'MIN_ELECTRICIDAD'
    ];
    v_code TEXT;
    v_entity_id UUID;
BEGIN
    FOREACH v_code IN ARRAY v_entity_codes LOOP
        SELECT id INTO v_entity_id FROM entities WHERE code = v_code;
        IF v_entity_id IS NULL THEN
            RAISE NOTICE 'Entity % not found, skipping', v_code;
            CONTINUE;
        END IF;

        -- Malabo (Insular) — main office
        INSERT INTO entity_locations (
            entity_code, entity_id, city, city_id, region,
            location_name, is_main_office, is_active
        ) VALUES (
            v_code, v_entity_id, 'Malabo', v_malabo_id, 'Insular',
            v_code || ' Malabo', true, true
        ) ON CONFLICT (entity_code, location_name) DO NOTHING;

        -- Bata (Continental)
        INSERT INTO entity_locations (
            entity_code, entity_id, city, city_id, region,
            location_name, is_main_office, is_active
        ) VALUES (
            v_code, v_entity_id, 'Bata', v_bata_id, 'Continental',
            v_code || ' Bata', false, true
        ) ON CONFLICT (entity_code, location_name) DO NOTHING;
    END LOOP;
END $$;

-- ============================================================
-- 4. Routing View (2-step OMS routing)
-- ============================================================
-- NOTE: Original view had a design flaw (conflated payment validators
-- with post-payment processors). Fixed in migration 222.
-- This file shows the CORRECTED version for reference.

CREATE OR REPLACE VIEW v_obligation_routing AS
SELECT
    e.id AS entity_id,
    e.code AS entity_code,
    e.name AS entity_name,
    e.ministry_id,
    el.id AS entity_location_id,
    el.city,
    el.city_id,
    el.region,
    CASE
        WHEN e.code IN ('TESORO', 'AYUNTAMIENTO', 'CAMARA_COMERCIO')
            THEN 'payment_validator'
        ELSE 'post_payment_processor'
    END AS routing_role,
    CASE
        WHEN e.code = 'AYUNTAMIENTO' THEN 'municipal'
        WHEN e.code = 'CAMARA_COMERCIO' THEN 'chamber'
        ELSE 'tesoro'
    END AS validates_fee_type
FROM entities e
JOIN entity_locations el ON el.entity_id = e.id AND el.is_active = true
WHERE e.code IN (
    'TESORO', 'AYUNTAMIENTO', 'CAMARA_COMERCIO',
    'MIN_HACIENDA', 'MIN_COMERCIO', 'MIN_INFORMACION',
    'MIN_TURISMO', 'MIN_AGRICULTURA', 'MIN_ELECTRICIDAD'
);

COMMENT ON VIEW v_obligation_routing IS
    'OMS 2-step routing: Step 1 = payment_validator (fee_type → TESORO/AYUNT/CAMARA), '
    'Step 2 = post_payment_processor (ministry_id → MIN_* for Mode A).';

COMMIT;
