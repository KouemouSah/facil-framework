-- ============================================================================
-- MIGRATION 336: Create schema_migrations tracking table
-- Date: 2026-05-09
-- Context: Phase A of MIGRATIONS_BASELINE_REFACTOR_PLAN
--
-- Problem: Current deploy workflow re-applies all 321 migrations on every
-- deploy in idempotent-skip mode (try/except 'already exists'). No tracking,
-- no checksum, no advisory lock. Slow + fragile + not auditable.
--
-- Strategy:
--   1. Create schema_migrations table (PRIMARY KEY = version)
--   2. Track filename, checksum, applied_at, applied_by, execution time, type
--   3. Indexed on applied_at DESC (audit) and filetype (filter migrations
--      vs baselines vs seeds)
--
-- This migration alone has ZERO functional impact: the table is created but
-- not yet used by any code. The script `scripts/deploy/init_database.py`
-- (next commit, Phase A step 2) will use it. Until then, the deploy
-- workflow continues to use the legacy "replay all" pattern.
--
-- Idempotent: CREATE TABLE IF NOT EXISTS, CREATE INDEX IF NOT EXISTS.
-- Reversible: DROP TABLE schema_migrations (data loss = re-bootstrap needed).
-- ============================================================================

BEGIN;

-- 1. Create the tracking table
CREATE TABLE IF NOT EXISTS schema_migrations (
    -- Version derived from filename prefix (e.g. "336" from "336_create_*.sql"
    -- or full filename for seeds). Primary key prevents duplicate application.
    version VARCHAR(64) PRIMARY KEY,

    -- SHA-256 hex digest of the file content at apply time. Used to detect
    -- accidental edits to already-applied migrations (warn but do not fail).
    checksum VARCHAR(64) NOT NULL,

    -- Timestamp the migration was applied successfully.
    applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Identifier of the actor that applied it (github-actions, manual, bootstrap, etc.).
    applied_by VARCHAR(128) NOT NULL DEFAULT 'github-actions',

    -- Execution time in milliseconds (NULL if not measured).
    execution_time_ms INTEGER,

    -- Source filename (full, with extension). Useful for audit + debugging.
    filename TEXT NOT NULL,

    -- Type of file applied. Allows separate filtering of structural vs
    -- baseline vs seed migrations in audits.
    --   'migration' : incremental DDL (default)
    --   'baseline'  : consolidated schema dump (Phase D, future)
    --   'seed'      : idempotent DML (Phase C, future)
    filetype VARCHAR(16) NOT NULL DEFAULT 'migration'
        CHECK (filetype IN ('migration', 'baseline', 'seed'))
);

-- 2. Indexes for audit queries
CREATE INDEX IF NOT EXISTS idx_schema_migrations_applied_at
    ON schema_migrations(applied_at DESC);

CREATE INDEX IF NOT EXISTS idx_schema_migrations_filetype
    ON schema_migrations(filetype);

-- 3. Comment for documentation visibility (psql \dt+)
COMMENT ON TABLE schema_migrations IS
    'Tracks DDL migrations, baselines and seeds applied to this database. '
    'Managed by scripts/deploy/init_database.py. '
    'See .claude/plans/MIGRATIONS_BASELINE_REFACTOR_PLAN.md for context.';

COMMIT;
