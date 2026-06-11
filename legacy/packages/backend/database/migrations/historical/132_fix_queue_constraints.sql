-- Migration 132: Fix agent_work_queue constraints for service_request routing
--
-- Fixes discovered during implementation audit:
-- 1. ministry_id is NOT NULL → must be nullable (entity_code replaces it for routing)
-- 2. item_type CHECK only allows 'payment','declaration' → must include 'service_request'
--
-- Table has 0 rows → safe to alter constraints.
-- priority_score stays INTEGER (Python code converts Decimal→int before INSERT).

-- 1. Make ministry_id nullable (entity_code is now the primary routing column)
ALTER TABLE agent_work_queue ALTER COLUMN ministry_id DROP NOT NULL;

COMMENT ON COLUMN agent_work_queue.ministry_id IS
    'Deprecated for service_request routing. Use entity_code instead. '
    'Kept nullable for legacy declaration routing.';

-- 2. Drop old CHECK constraint on item_type and add new one including 'service_request'
DO $$
DECLARE
    constraint_name TEXT;
BEGIN
    SELECT conname INTO constraint_name
    FROM pg_constraint
    WHERE conrelid = 'agent_work_queue'::regclass
      AND contype = 'c'
      AND pg_get_constraintdef(oid) LIKE '%item_type%';

    IF constraint_name IS NOT NULL THEN
        EXECUTE 'ALTER TABLE agent_work_queue DROP CONSTRAINT ' || constraint_name;
        RAISE NOTICE 'Dropped constraint: %', constraint_name;
    END IF;
END $$;

ALTER TABLE agent_work_queue
    ADD CONSTRAINT agent_work_queue_item_type_check
    CHECK (item_type IN ('payment', 'declaration', 'service_request'));
