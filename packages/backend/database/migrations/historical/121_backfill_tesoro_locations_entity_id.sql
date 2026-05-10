-- Migration 121: Backfill entity_id NULL on entity_locations
-- Problem: Some entity_locations (e.g., TGE BATA, TGE OYALA) have entity_id = NULL
-- because they were created manually without linking to the parent entity.
-- Fix: Set entity_id from the matching entities record via entity_code.

UPDATE entity_locations el
SET entity_id = e.id
FROM entities e
WHERE e.code = el.entity_code
  AND e.is_active = true
  AND el.entity_id IS NULL;

-- Verify
DO $$
DECLARE
    orphan_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO orphan_count
    FROM entity_locations
    WHERE entity_id IS NULL
      AND is_active = true;

    IF orphan_count = 0 THEN
        RAISE NOTICE 'All active entity_locations have entity_id set';
    ELSE
        RAISE WARNING '% active entity_locations still have NULL entity_id', orphan_count;
    END IF;
END $$;
