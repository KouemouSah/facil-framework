-- =============================================================================
-- Migration 317 — dashboard_registrations table + dashboards.manage permission
-- =============================================================================
-- Created: 2026-05-04
-- Plan reference: .claude/plans/LOOKER_E1_AUTOMATION_MASTER_PLAN.md
--                 .claude/plans/LOOKER_E1_PHASE1_DETAIL.md
--
-- Replaces the env-vars-on-Cloud-Run flow for Looker Studio report_id mapping
-- by an editable BD table. Admin can change report_id without redeploy.
--
-- Backwards-compat: GET /api/v1/dashboards/reports-config keeps env-var
-- fallback when the table row is missing or the table is empty (Phase 2 of E1).
--
-- Idempotent: re-running the migration is safe (uses CREATE TABLE IF NOT
-- EXISTS, ON CONFLICT DO NOTHING, IF NOT EXISTS on indexes/constraints).
--
-- BD verified 2026-05-04 BEFORE writing this migration:
--   - dashboard_registrations does NOT exist
--   - dashboards.manage permission does NOT exist
--   - permissions schema: id, name, resource, action, description,
--     is_critical, module_name, created_at, updated_at (no `category`)
--   - role_permissions schema: role_id, permission_id, granted, created_at,
--     created_by, scope (no `granted_at`)
--   - audit_role_permissions_change trigger active on INSERT/DELETE -
--     requires app.current_user_id to be set before grants
-- =============================================================================

BEGIN;

-- ---------------------------------------------------------------------------
-- 1. Table dashboard_registrations
-- One row per dashboard in dashboards_service.py registry. Editable via
-- /admin/dashboards/config (Next.js admin panel).
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS dashboard_registrations (
    dashboard_id     text PRIMARY KEY,
    looker_report_id text NOT NULL,
    looker_page_id   text,
    is_active        boolean NOT NULL DEFAULT true,
    updated_by       uuid REFERENCES users(id) ON DELETE SET NULL,
    updated_at       timestamptz NOT NULL DEFAULT now(),
    created_at       timestamptz NOT NULL DEFAULT now(),
    -- Looker Studio report IDs are alphanumeric tokens with dashes/underscores.
    -- Real samples observed: 8-64 chars typical. Strict regex = first defense.
    CONSTRAINT chk_looker_report_id_format
        CHECK (looker_report_id ~ '^[a-zA-Z0-9_-]{8,64}$'),
    -- page_id is optional. Looker uses the format p_<digits>, but custom IDs
    -- with letters and underscores also exist. NULL = use first page.
    CONSTRAINT chk_looker_page_id_format
        CHECK (looker_page_id IS NULL OR looker_page_id ~ '^[a-zA-Z0-9_]{1,32}$')
);

-- Partial index for the hot read path: GET /reports-config filters on
-- is_active = true. Reduces scan cost on a tiny table — defensive given
-- this endpoint is hit on every admin page load (1M+ scenario).
CREATE INDEX IF NOT EXISTS idx_dashboard_registrations_active
    ON dashboard_registrations(is_active) WHERE is_active = true;

COMMENT ON TABLE dashboard_registrations IS
    'Looker Studio report_id mapping per dashboard. Editable via /admin/dashboards/config (E1 plan).';
COMMENT ON COLUMN dashboard_registrations.dashboard_id IS
    'Matches dashboards_service.py registry keys: recaudacion, agentes, services.';
COMMENT ON COLUMN dashboard_registrations.looker_report_id IS
    'Looker Studio report ID extracted from /reporting/<id>/page/... URL.';
COMMENT ON COLUMN dashboard_registrations.looker_page_id IS
    'Optional Looker Studio page ID (p_xxx). NULL = first page (Looker default).';
COMMENT ON COLUMN dashboard_registrations.is_active IS
    'False to hide a dashboard from /reports-config without deleting the row (preserves audit trail).';

-- ---------------------------------------------------------------------------
-- 2. Permission dashboards.manage
-- Real schema verified 2026-05-04: name, resource, action, description,
-- module_name, is_critical, created_at. NO `category` column (it does not
-- exist; migration 316 was patched to remove the wrong reference).
--
-- is_critical = TRUE because changing report_id changes what every admin
-- sees. Future MFA/double-validation logic can hook on this flag.
-- ---------------------------------------------------------------------------
INSERT INTO permissions (name, resource, action, description, module_name, is_critical, created_at)
VALUES (
    'dashboards.manage',
    'dashboards',
    'manage',
    'Manage Looker Studio dashboard configurations (report_id, page_id, active state)',
    'dashboards',
    TRUE,
    NOW()
)
ON CONFLICT (name) DO NOTHING;

-- ---------------------------------------------------------------------------
-- 3. Grant to admin + super_admin ONLY.
-- This permission writes to a config that ALL admins read. Strict
-- separation of privileges: dashboards.view_business (migration 316) is
-- broad (21 roles, read), dashboards.manage (this migration) is narrow
-- (2 roles, write). No grant to supervisors/agents.
--
-- Real role_permissions schema verified 2026-05-04: role_id, permission_id,
-- granted (bool), created_at, created_by, scope. NO `granted_at` column.
--
-- Role codes verified live 2026-05-04 (admin id=3674d2c7-..., super_admin
-- id=2d61119a-...). Both exist; no invented codes.
-- ---------------------------------------------------------------------------
INSERT INTO role_permissions (role_id, permission_id, granted)
SELECT r.id, p.id, TRUE
FROM roles r
CROSS JOIN permissions p
WHERE p.name = 'dashboards.manage'
  AND r.code IN ('admin', 'super_admin')
ON CONFLICT (role_id, permission_id) DO NOTHING;

COMMIT;

-- ---------------------------------------------------------------------------
-- VERIFICATION (run after applying):
-- ---------------------------------------------------------------------------
-- 1. Table created with correct columns:
--    \d dashboard_registrations
--
-- 2. CHECK constraints active:
--    SELECT conname, pg_get_constraintdef(oid) FROM pg_constraint
--    WHERE conrelid = 'dashboard_registrations'::regclass AND contype = 'c';
--    -- expected: chk_looker_report_id_format, chk_looker_page_id_format
--
-- 3. Partial index created:
--    SELECT indexname, indexdef FROM pg_indexes
--    WHERE tablename = 'dashboard_registrations';
--    -- expected: dashboard_registrations_pkey, idx_dashboard_registrations_active
--
-- 4. Permission registered:
--    SELECT id, name, is_critical, module_name FROM permissions
--    WHERE name = 'dashboards.manage';
--    -- expected: 1 row, is_critical=TRUE
--
-- 5. Grants count exactly 2:
--    SELECT r.code FROM roles r
--    JOIN role_permissions rp ON rp.role_id = r.id
--    JOIN permissions p ON p.id = rp.permission_id
--    WHERE p.name = 'dashboards.manage'
--    ORDER BY r.code;
--    -- expected: admin, super_admin
--
-- 6. Idempotence: re-run the migration in psql, expect zero new rows on
--    permissions, role_permissions, and dashboard_registrations.
--
-- 7. CHECK valid path:
--    INSERT INTO dashboard_registrations (dashboard_id, looker_report_id, looker_page_id)
--    VALUES ('test_dummy', 'abc123-def456-ghi789', 'p_12345');
--    -- expected: success
--    DELETE FROM dashboard_registrations WHERE dashboard_id = 'test_dummy';
--
-- 8. CHECK reject path (regex fail, 7 chars too short):
--    INSERT INTO dashboard_registrations (dashboard_id, looker_report_id)
--    VALUES ('test_bad', 'tooshrt');
--    -- expected: ERROR violates chk_looker_report_id_format
-- ---------------------------------------------------------------------------

-- ROLLBACK (manual, if absolutely needed):
-- BEGIN;
--   DELETE FROM role_permissions
--   WHERE permission_id = (SELECT id FROM permissions WHERE name = 'dashboards.manage');
--   DELETE FROM permissions WHERE name = 'dashboards.manage';
--   DROP TABLE IF EXISTS dashboard_registrations;
-- COMMIT;
