-- =============================================================================
-- Migration 319 — extend dashboard_registrations for dual provider support
-- =============================================================================
-- Created: 2026-05-04
-- Plan reference: .claude/plans/GRAFANA_E1_MASTER_PLAN.md §3, §5.3
--
-- Adds Grafana support alongside Looker Studio so /admin/dashboards/config can
-- toggle the provider per dashboard for the comparative evaluation.
--
-- Design choices
-- --------------
-- 1. ENUM `dashboard_provider_enum` for type safety. Values: 'looker_studio',
--    'grafana'. Future-proof: ALTER TYPE ADD VALUE works for new providers.
-- 2. New columns added with defaults so existing rows (created by mig 317
--    + the page admin /config since 2026-05-04) auto-populate to 'looker_studio'
--    — backwards-compatible.
-- 3. Both column groups (looker_*, grafana_*) coexist on the same row. The
--    `provider` column tells the backend which to use; the other group can
--    stay populated as a fallback or for future side-by-side rendering.
-- 4. CHECK constraint: if provider='grafana', grafana_dashboard_uid MUST NOT
--    be NULL (else /admin would render a broken iframe). Symmetric on Looker
--    relaxed because legacy rows may have been seeded with NULL report_id
--    (env_fallback path).
--
-- BD verified 2026-05-04 BEFORE writing this migration:
--   - dashboard_registrations exists (mig 317)
--   - 1 row already present (recaudacion test), to be auto-defaulted to 'looker_studio'
--   - dashboard_provider_enum does NOT yet exist (no naming collision)
--
-- Idempotent: CREATE TYPE IF NOT EXISTS not supported pre-PG14 → use DO block.
-- ADD COLUMN IF NOT EXISTS works on Postgres 9.6+.
-- =============================================================================

BEGIN;

-- ---------------------------------------------------------------------------
-- 1. ENUM type for provider
-- ---------------------------------------------------------------------------
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'dashboard_provider_enum') THEN
        CREATE TYPE dashboard_provider_enum AS ENUM ('looker_studio', 'grafana');
    END IF;
END $$;

-- ---------------------------------------------------------------------------
-- 2. Add new columns to dashboard_registrations
-- ---------------------------------------------------------------------------
ALTER TABLE dashboard_registrations
    ADD COLUMN IF NOT EXISTS provider dashboard_provider_enum NOT NULL DEFAULT 'looker_studio';

ALTER TABLE dashboard_registrations
    ADD COLUMN IF NOT EXISTS grafana_dashboard_uid text;

ALTER TABLE dashboard_registrations
    ADD COLUMN IF NOT EXISTS grafana_org_id integer DEFAULT 1;

-- ---------------------------------------------------------------------------
-- 3. CHECK: grafana provider requires uid populated
-- We drop-and-recreate to make the migration idempotent.
-- ---------------------------------------------------------------------------
ALTER TABLE dashboard_registrations
    DROP CONSTRAINT IF EXISTS chk_grafana_uid_required_when_grafana;
ALTER TABLE dashboard_registrations
    ADD CONSTRAINT chk_grafana_uid_required_when_grafana
    CHECK (
        provider <> 'grafana'
        OR (grafana_dashboard_uid IS NOT NULL AND length(grafana_dashboard_uid) >= 4)
    );

-- ---------------------------------------------------------------------------
-- 4. CHECK: grafana_dashboard_uid format (Grafana UIDs are alphanum + underscore + dash, ≤40 chars)
-- ---------------------------------------------------------------------------
ALTER TABLE dashboard_registrations
    DROP CONSTRAINT IF EXISTS chk_grafana_dashboard_uid_format;
ALTER TABLE dashboard_registrations
    ADD CONSTRAINT chk_grafana_dashboard_uid_format
    CHECK (
        grafana_dashboard_uid IS NULL
        OR grafana_dashboard_uid ~ '^[a-zA-Z0-9_-]{4,40}$'
    );

-- ---------------------------------------------------------------------------
-- 5. Comments
-- ---------------------------------------------------------------------------
COMMENT ON COLUMN dashboard_registrations.provider IS
    'Which embed source to use: looker_studio (default, mig 317) or grafana (mig 319).';
COMMENT ON COLUMN dashboard_registrations.grafana_dashboard_uid IS
    'Grafana dashboard UID (the stable identifier in Grafana, e.g. ''facil-recaudacion''). NULL when provider=looker_studio.';
COMMENT ON COLUMN dashboard_registrations.grafana_org_id IS
    'Grafana organization ID. Default 1 (single-org Grafana Cloud). Used in embed URL ?orgId=N.';

COMMIT;

-- ---------------------------------------------------------------------------
-- VERIFICATION (run after applying):
-- ---------------------------------------------------------------------------
-- 1. ENUM created:
--    SELECT typname, enumlabel FROM pg_type t JOIN pg_enum e ON e.enumtypid=t.oid
--    WHERE typname = 'dashboard_provider_enum' ORDER BY enumsortorder;
--    -- expected: looker_studio, grafana
--
-- 2. New columns present:
--    SELECT column_name, data_type, column_default, is_nullable
--    FROM information_schema.columns
--    WHERE table_name = 'dashboard_registrations' ORDER BY ordinal_position;
--
-- 3. CHECK constraints active:
--    SELECT conname, pg_get_constraintdef(oid) FROM pg_constraint
--    WHERE conrelid = 'dashboard_registrations'::regclass AND contype = 'c';
--    -- expected: chk_looker_report_id_format, chk_looker_page_id_format,
--    --           chk_grafana_uid_required_when_grafana, chk_grafana_dashboard_uid_format
--
-- 4. Existing rows auto-defaulted:
--    SELECT dashboard_id, provider, looker_report_id, grafana_dashboard_uid
--    FROM dashboard_registrations;
--    -- expected: provider = 'looker_studio' for all existing rows
--
-- 5. CHECK reject path:
--    INSERT INTO dashboard_registrations (dashboard_id, provider, looker_report_id)
--    VALUES ('test_g_bad', 'grafana', 'fake-report-id');
--    -- expected: ERROR violates chk_grafana_uid_required_when_grafana
--
-- 6. CHECK valid path:
--    INSERT INTO dashboard_registrations
--      (dashboard_id, provider, grafana_dashboard_uid, grafana_org_id, looker_report_id)
--    VALUES ('test_g_ok', 'grafana', 'facil-test-recaudacion', 1, 'placeholder');
--    -- expected: success (looker_report_id placeholder ignored when provider=grafana)
--    DELETE FROM dashboard_registrations WHERE dashboard_id = 'test_g_ok';
-- ---------------------------------------------------------------------------

-- ROLLBACK (manual, if absolutely needed):
-- BEGIN;
--   ALTER TABLE dashboard_registrations DROP CONSTRAINT IF EXISTS chk_grafana_uid_required_when_grafana;
--   ALTER TABLE dashboard_registrations DROP CONSTRAINT IF EXISTS chk_grafana_dashboard_uid_format;
--   ALTER TABLE dashboard_registrations DROP COLUMN IF EXISTS grafana_org_id;
--   ALTER TABLE dashboard_registrations DROP COLUMN IF EXISTS grafana_dashboard_uid;
--   ALTER TABLE dashboard_registrations DROP COLUMN IF EXISTS provider;
--   DROP TYPE IF EXISTS dashboard_provider_enum;
-- COMMIT;
