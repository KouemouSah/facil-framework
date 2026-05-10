-- ============================================================================
-- MIGRATION 333: Denormalize entity_code on treasury_exports
-- Date: 2026-05-06
-- Context: P8 hardening of Bug 1 (Phase 7 follow-up)
--
-- Problem: _authorize_export_action() relied on the JOIN
--   treasury_exports.requested_by → agent_profiles → entities.code
-- with `agent_profiles.is_active = true`. If the requester's profile is
-- later deactivated (rotation, decommission), the JOIN returns NULL and
-- a scoped supervisor cannot read the historical export anymore (403).
-- This migration denormalizes entity_code into treasury_exports so the
-- scope check is independent of the requester's current profile state.
--
-- Strategy:
--   1. Add column requested_by_entity_code VARCHAR(50) (nullable)
--   2. Backfill from agent_profiles + entities at the time of the request
--      (joins on requested_by user_id; uses any active or inactive profile)
--   3. Create an index for the lookup pattern
--   4. The application updates will set this column on every new export
--      (in a follow-up code change to /treasury/exports/generate)
--
-- Idempotent: ADD COLUMN IF NOT EXISTS, COALESCE-guarded UPDATE,
--             CREATE INDEX IF NOT EXISTS.
-- ============================================================================

BEGIN;

-- 1. Add column (nullable: legacy rows + global-admin generated rows can have NULL)
ALTER TABLE treasury_exports
    ADD COLUMN IF NOT EXISTS requested_by_entity_code VARCHAR(50);

COMMENT ON COLUMN treasury_exports.requested_by_entity_code IS
    'Denormalized entity code of the agent who requested this export, '
    'captured at request time. Used by _authorize_export_action() to '
    'enforce per-entity scope without depending on agent_profile state.';

-- 2. Backfill from current agent_profiles (one-shot snapshot at migration time).
-- We pick the most recent active profile, falling back to the most recent
-- inactive one. Multiple profiles per user are rare but historically possible.
UPDATE treasury_exports te
SET requested_by_entity_code = sub.entity_code
FROM (
    SELECT DISTINCT ON (ap.user_id)
        ap.user_id,
        e.code AS entity_code
    FROM agent_profiles ap
    JOIN entities e ON e.id = ap.entity_id
    ORDER BY ap.user_id, ap.is_active DESC, ap.created_at DESC
) sub
WHERE te.requested_by = sub.user_id
  AND te.requested_by_entity_code IS NULL;

-- 3. Index for the scope-check lookup
CREATE INDEX IF NOT EXISTS idx_treasury_exports_entity_code
    ON treasury_exports (requested_by_entity_code)
    WHERE requested_by_entity_code IS NOT NULL;

-- Verification: count populated rows
DO $$
DECLARE
    v_total INTEGER;
    v_with_entity INTEGER;
BEGIN
    SELECT COUNT(*) INTO v_total FROM treasury_exports;
    SELECT COUNT(*) INTO v_with_entity
        FROM treasury_exports
        WHERE requested_by_entity_code IS NOT NULL;
    RAISE NOTICE 'Migration 333: % / % treasury_exports rows backfilled with entity_code',
        v_with_entity, v_total;
END $$;

COMMIT;
