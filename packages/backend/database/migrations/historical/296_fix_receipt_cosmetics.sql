-- 296_fix_receipt_cosmetics.sql
-- P8.2 X8 cosmetic fix: clean up receipt display data.
--
-- 1. fiscal_services id=1146: raw unicode escape '\u00ed' → actual 'í'
-- 2. entity_locations: raw CAMARA_COMERCIO/AYUNTAMIENTO codes → human names
--
-- Both idempotent via WHERE matching old values only.

BEGIN;

-- Fix 1: decode raw unicode escape in fiscal_services
UPDATE fiscal_services
SET name_es = 'Autorización de venta Pescados abacerías',
    updated_at = NOW()
WHERE id = 1146
  AND name_es LIKE '%abacer%u00ed%';

-- Fix 2: entity_locations human-readable names
UPDATE entity_locations SET location_name = 'Ayuntamiento de Malabo'
WHERE location_name = 'AYUNTAMIENTO Malabo';
UPDATE entity_locations SET location_name = 'Ayuntamiento de Bata'
WHERE location_name = 'AYUNTAMIENTO Bata';
UPDATE entity_locations SET location_name = 'Cámara de Comercio de Malabo'
WHERE location_name = 'CAMARA_COMERCIO Malabo';
UPDATE entity_locations SET location_name = 'Cámara de Comercio de Bata'
WHERE location_name = 'CAMARA_COMERCIO Bata';

COMMIT;
