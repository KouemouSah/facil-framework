-- =============================================================================
-- Migration 316 — view_business_dashboards permission for /admin/dashboards/*
-- =============================================================================
-- Created: 2026-05-02
-- Plan reference: .claude/plans/LOOKER_STUDIO_BUSINESS_DASHBOARDS_PLAN.md §5
--                 .claude/plans/LOOKER_STUDIO_COMMUNITY_CONNECTOR_PLAN.md §5
--
-- Adds the permission needed to access the Next.js /admin/dashboards/*
-- routes (Phase 5 of the Looker rollout). The Looker connector backend
-- (B.2a) already enforces row-level security via agent_profiles.entity_id
-- — this permission gates the *frontend embed* to staff and ministry
-- supervisors only. Citizens / business / accountant roles get a 403 on
-- the route, never see the iframe.
--
-- Idempotent: re-running the migration is safe (uses ON CONFLICT DO NOTHING).
-- =============================================================================

BEGIN;

-- ---------------------------------------------------------------------------
-- 1. Insert the permission.
-- Real schema (verified against information_schema 2026-05-02):
--   columns: id (uuid), name (varchar), resource (varchar NOT NULL),
--   action (varchar NOT NULL), description (text), is_critical (bool),
--   module_name (varchar), created_at, updated_at.
-- Pattern observed on existing rows (e.g. admin.view_dashboard):
--   name='<resource>.<action>', resource='<resource>', action='<action>',
--   module_name='<resource>'. We follow this convention exactly.
-- ---------------------------------------------------------------------------
INSERT INTO permissions (name, resource, action, description, module_name, is_critical, created_at)
VALUES (
    'dashboards.view_business',
    'dashboards',
    'view_business',
    'View business dashboards (Recaudación, Agent Performance, Service Catalog) embedded from Looker Studio',
    'dashboards',
    FALSE,
    NOW()
)
ON CONFLICT (name) DO NOTHING;

-- ---------------------------------------------------------------------------
-- 2. Grant to admin/super_admin + every agent_* role that exists in this DB.
-- We intentionally do NOT grant to citizen/business/accountant — they have
-- no business reading aggregate KPIs.
-- The list below was generated from `SELECT code FROM roles WHERE code LIKE
-- 'agent_%' OR code IN ('admin','super_admin')` on 2026-05-02. Codes that
-- do not exist (e.g. 'supervisor', 'agent_aduana', 'agent_dgi',
-- 'agent_min_*' minus the ones below) have been removed to avoid silent
-- no-op INSERTs. Per-entity row-level filtering still happens at runtime
-- via agent_profiles.entity_id (B.2a RLS in dashboards_service.py).
-- ---------------------------------------------------------------------------
-- Real role_permissions schema (verified 2026-05-02):
--   role_id (uuid PK), permission_id (uuid PK), granted (bool default true),
--   created_at (timestamp default now()), created_by (uuid nullable),
--   scope (jsonb nullable). No granted_at column.
INSERT INTO role_permissions (role_id, permission_id, granted)
SELECT r.id, p.id, TRUE
FROM roles r
CROSS JOIN permissions p
WHERE p.name = 'dashboards.view_business'
  AND r.code IN (
      'admin',
      'super_admin',
      'agent_ayuntamiento',
      'agent_camara',
      'agent_cnedoge_pasaporte',
      'agent_cnedoge_residencia',
      'agent_dgt',
      'agent_extranjeria',
      'agent_itv',
      'agent_min_agricultura',
      'agent_min_comercio',
      'agent_min_electricidad',
      'agent_min_hacienda',
      'agent_min_informacion',
      'agent_min_turismo',
      'agent_minfp',
      'agent_ofive',
      'agent_oms_polyvalent',
      'agent_onrc',
      'agent_policia',
      'agent_tesoro'
  )
ON CONFLICT (role_id, permission_id) DO NOTHING;

COMMIT;

-- ---------------------------------------------------------------------------
-- VERIFICATION (run after the migration applies):
-- ---------------------------------------------------------------------------
-- 1. Permission exists:
--    SELECT name, category FROM permissions WHERE name = 'dashboards.view_business';
--
-- 2. Roles that received it (count should match the IN list above, minus any
--    role codes that don't exist in this DB):
--    SELECT r.code FROM roles r
--    JOIN role_permissions rp ON rp.role_id = r.id
--    JOIN permissions p ON p.id = rp.permission_id
--    WHERE p.name = 'dashboards.view_business'
--    ORDER BY r.code;
--
-- 3. A citizen-role user should NOT have it:
--    SELECT count(*) FROM users u
--    JOIN user_company_roles ucr ON ucr.user_id = u.id
--    WHERE u.role = 'citizen'
--      AND EXISTS (
--          SELECT 1 FROM role_permissions rp
--          JOIN permissions p ON p.id = rp.permission_id
--          WHERE rp.role_id = ucr.role_id
--            AND p.name = 'dashboards.view_business'
--      );
-- ---------------------------------------------------------------------------

-- ROLLBACK (manual):
-- BEGIN;
--   DELETE FROM role_permissions
--   WHERE permission_id = (SELECT id FROM permissions WHERE name = 'dashboards.view_business');
--   DELETE FROM permissions WHERE name = 'dashboards.view_business';
-- COMMIT;
