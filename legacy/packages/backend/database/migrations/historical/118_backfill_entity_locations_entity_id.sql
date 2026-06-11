-- Migration 118: Backfill entity_locations.entity_id
--
-- Problem: All 16 entity_locations rows have entity_id = NULL since migration 058.
-- This breaks FK-based joins and site-based routing across ALL entities.
--
-- Fix: Populate entity_id by matching entity_code to entities.code.

UPDATE entity_locations el
SET entity_id = e.id
FROM entities e
WHERE e.code = el.entity_code
  AND e.is_active = true
  AND el.entity_id IS NULL;

-- Verify: all rows should now have entity_id populated
DO $$
DECLARE orphan_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO orphan_count FROM entity_locations WHERE entity_id IS NULL;
    IF orphan_count > 0 THEN
        RAISE WARNING '% entity_locations still have NULL entity_id — check entities.code matches', orphan_count;
    ELSE
        RAISE NOTICE 'All entity_locations.entity_id populated OK (16/16)';
    END IF;
END $$;
