-- Migration 177: Add 'treasury' value to entity_type_enum
--
-- The agent resolution logic needs to distinguish the treasury entity from
-- other entities with empty workflow_codes (e.g., COMISARIA).
-- Instead of checking permissions as a proxy, we use the semantic entity_type.
--
-- This is DB-driven: if the entity code or name changes, the resolution
-- still works because it checks entity_type, not a hardcoded code.

-- Step 1: Add 'treasury' to the enum (idempotent — DO NOTHING if exists)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_enum
        JOIN pg_type ON pg_type.oid = pg_enum.enumtypid
        WHERE pg_type.typname = 'entity_type_enum'
          AND pg_enum.enumlabel = 'treasury'
    ) THEN
        ALTER TYPE entity_type_enum ADD VALUE 'treasury';
        RAISE NOTICE 'Added treasury to entity_type_enum';
    ELSE
        RAISE NOTICE 'treasury already exists in entity_type_enum — skipping';
    END IF;
END $$;

-- Step 2: Mark TESORO as treasury (the entity that validates payments)
-- Uses workflow_codes=[] + role pattern as identification, NOT hardcoded code.
-- If tomorrow TESORO is renamed, this migration already ran.
UPDATE entities
SET entity_type = 'treasury'
WHERE workflow_codes = '[]'::jsonb
  AND code IN (
      SELECT DISTINCT e.code
      FROM entities e
      JOIN agent_profiles ap ON ap.entity_id = e.id
      JOIN users u ON u.id = ap.user_id
      JOIN role_permissions rp ON rp.role_id = u.role_id
      JOIN permissions p ON p.id = rp.permission_id
      WHERE p.name = 'treasury_stat.view'
        AND e.is_active = true
  );
