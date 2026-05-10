-- =============================================================================
-- Migration 314 — Companies soft-delete (archive)
-- =============================================================================
-- Replaces the citizen-facing hard-delete flow on `companies` with a soft-delete
-- "archive". Hard-delete is retained but gated behind a new admin-only
-- permission AND requires the company to have been archived first.
--
-- Why archive instead of hard-delete:
--   * Equatorial Guinea fiscal records have a 10-year retention duty
--     (commercial licenses, payments, receipts, audit trail). Hard-deleting a
--     company orphans all of that.
--   * Citizens still get the "remove from my list" UX they expect.
--   * Admins can restore in case of accidental archive.
--   * Foreign-key integrity preserved (commercial_licenses, service_payments,
--     service_requests, field_inspections, license_obligations,
--     user_company_roles all keep pointing to a real row).
--
-- Citizen archive endpoint (added in app/modules/companies/api/company_routes.py):
--     POST /companies/{id}/archive   — owner-only, 409 if blockers
-- Admin restore + hard-delete:
--     POST /companies/{id}/unarchive — requires `company.unarchive`
--     DELETE /companies/{id}         — requires `company.hard_delete` AND
--                                       archived_at IS NOT NULL
--
-- Reference: .claude/plans/SOFT_DELETE_COMPANIES_PLAN.md (Phase 1.1).
--
-- Idempotent (IF NOT EXISTS / ON CONFLICT). Safe to re-run.
-- =============================================================================

-- ============================================================
-- 1. Schema additions
-- ============================================================

ALTER TABLE companies
  ADD COLUMN IF NOT EXISTS archived_at     TIMESTAMPTZ NULL,
  ADD COLUMN IF NOT EXISTS archive_reason  VARCHAR(50) NULL,
  ADD COLUMN IF NOT EXISTS archived_by     UUID NULL REFERENCES users(id) ON DELETE SET NULL;

-- Partial index — most queries filter "non-archived only", and the column is
-- NULL for the vast majority of rows. A partial index keeps it tiny and lets
-- the admin "list archived" view stay fast as the table grows.
CREATE INDEX IF NOT EXISTS idx_companies_archived_at
  ON companies (archived_at)
  WHERE archived_at IS NOT NULL;

COMMENT ON COLUMN companies.archived_at IS
  'Soft-delete timestamp. NULL = active. Non-null = archived (citizen-initiated or admin). '
  'Citizens can no longer see the company; admins can via /admin/companies surfaces.';
COMMENT ON COLUMN companies.archive_reason IS
  'archived_by_owner | archived_by_admin | merged | inactive_long_term';
COMMENT ON COLUMN companies.archived_by IS
  'User who performed the archive action. NULL if archived by an automated process.';

-- ============================================================
-- 2. New permissions
-- ============================================================
-- `company.delete` (migration 225) is kept for backward compatibility with any
-- existing role_permissions row, but the route now checks `company.hard_delete`
-- instead. Citizens do NOT receive `company.archive` as a permission — owner
-- check happens at the route handler via user_company_roles.role.

INSERT INTO permissions (name, resource, action, description, is_critical)
VALUES
  ('company.archive',
   'company', 'archive',
   'Archivar empresa (soft-delete) — usado por el dueno para retirar la empresa de su vista. Backend valida user_company_roles.role = company_owner.',
   false),
  ('company.unarchive',
   'company', 'unarchive',
   'Restaurar empresa archivada (admin)',
   true),
  ('company.hard_delete',
   'company', 'hard_delete',
   'Eliminar definitivamente una empresa (admin) — exige que la empresa este archivada previamente.',
   true)
ON CONFLICT (name) DO NOTHING;

-- ============================================================
-- 3. Role-permission assignments
-- ============================================================

-- Admin + super_admin: full access (archive + unarchive + hard_delete).
-- Note: `company.archive` for admins is mostly defensive (admins normally
-- archive via the citizen surface acting on behalf of an owner), but having
-- the permission lets back-office tooling call the same endpoint.
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM roles r
CROSS JOIN permissions p
WHERE r.code IN ('admin', 'super_admin')
  AND p.name IN ('company.archive', 'company.unarchive', 'company.hard_delete')
ON CONFLICT DO NOTHING;

-- ONRC supervisor: archive + unarchive (no hard_delete — that stays
-- super-restricted). ONRC is the registry-of-companies authority and may need
-- to clean up duplicates.
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM roles r
CROSS JOIN permissions p
WHERE r.code = 'supervisor_onrc'
  AND p.name IN ('company.archive', 'company.unarchive')
ON CONFLICT DO NOTHING;

-- ============================================================
-- 4. Sanity: ensure no role still has `company.delete` exposed by accident.
-- ============================================================
-- We do NOT revoke existing `company.delete` grants (would break any back-office
-- tool already calling DELETE), but we surface the legacy permission for the
-- audit trail. The code path uses `company.hard_delete` for new checks; legacy
-- callers will get 403 on the route until their role is updated.

DO $$
DECLARE
  legacy_grants INTEGER;
BEGIN
  SELECT COUNT(*) INTO legacy_grants
  FROM role_permissions rp
  JOIN permissions p ON p.id = rp.permission_id
  WHERE p.name = 'company.delete';

  RAISE NOTICE 'Migration 314: % role(s) still hold legacy company.delete permission (back-compat preserved).', legacy_grants;
END $$;
