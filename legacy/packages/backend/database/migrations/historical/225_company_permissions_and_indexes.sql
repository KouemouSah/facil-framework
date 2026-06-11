-- Migration 225: Company permissions and search indexes
-- Phase 2 of Companies Module Refactoring
--
-- Creates:
-- 1. company.* permissions (8 total)
-- 2. Role-permission assignments for admin + relevant agent/supervisor roles
-- 3. GIN trigram indexes for fast ILIKE search on legal_name and nif
-- 4. Composite index on (is_active, is_verified) for admin filters

-- ============================================================
-- 1. Permissions
-- ============================================================
INSERT INTO permissions (name, resource, action, description, is_critical)
VALUES
  ('company.view',           'company', 'view',           'Ver detalles de empresa',           false),
  ('company.create',         'company', 'create',         'Crear nuevas empresas',             true),
  ('company.update',         'company', 'update',         'Modificar datos de empresa',        true),
  ('company.delete',         'company', 'delete',         'Eliminar empresa',                  true),
  ('company.verify',         'company', 'verify',         'Verificar/aprobar empresa',         true),
  ('company.view_all',       'company', 'view_all',       'Ver todas las empresas (admin)',     false),
  ('company.view_stats',     'company', 'view_stats',     'Ver estadisticas de empresas',      false),
  ('company.manage_members', 'company', 'manage_members', 'Gestionar miembros de empresa',     true)
ON CONFLICT (name) DO NOTHING;

-- ============================================================
-- 2. Role-permission assignments
-- ============================================================

-- Admin: all company permissions
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM roles r
CROSS JOIN permissions p
WHERE r.code = 'admin'
  AND p.name LIKE 'company.%'
ON CONFLICT DO NOTHING;

-- Super admin: all company permissions
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM roles r
CROSS JOIN permissions p
WHERE r.code = 'super_admin'
  AND p.name LIKE 'company.%'
ON CONFLICT DO NOTHING;

-- Supervisor tesoro: view, view_all, view_stats
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM roles r
CROSS JOIN permissions p
WHERE r.code = 'supervisor_tesoro'
  AND p.name IN ('company.view', 'company.view_all', 'company.view_stats')
ON CONFLICT DO NOTHING;

-- Agent OMS polyvalent: view, view_all
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM roles r
CROSS JOIN permissions p
WHERE r.code = 'agent_oms_polyvalent'
  AND p.name IN ('company.view', 'company.view_all')
ON CONFLICT DO NOTHING;

-- ONRC agent: view, view_all, create, update, verify
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM roles r
CROSS JOIN permissions p
WHERE r.code = 'agent_onrc'
  AND p.name IN ('company.view', 'company.view_all', 'company.create', 'company.update', 'company.verify')
ON CONFLICT DO NOTHING;

-- ONRC supervisor: all except delete
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM roles r
CROSS JOIN permissions p
WHERE r.code = 'supervisor_onrc'
  AND p.name IN ('company.view', 'company.view_all', 'company.view_stats', 'company.create', 'company.update', 'company.verify', 'company.manage_members')
ON CONFLICT DO NOTHING;

-- Commerce ministry agent: view, view_all
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM roles r
CROSS JOIN permissions p
WHERE r.code = 'agent_min_comercio'
  AND p.name IN ('company.view', 'company.view_all')
ON CONFLICT DO NOTHING;

-- Commerce ministry supervisor: view, view_all, view_stats
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM roles r
CROSS JOIN permissions p
WHERE r.code = 'supervisor_min_comercio'
  AND p.name IN ('company.view', 'company.view_all', 'company.view_stats')
ON CONFLICT DO NOTHING;

-- ============================================================
-- 3. Search indexes (pg_trgm available)
-- ============================================================
CREATE INDEX IF NOT EXISTS idx_companies_legal_name_trgm
  ON companies USING gin (legal_name gin_trgm_ops);

CREATE INDEX IF NOT EXISTS idx_companies_nif_trgm
  ON companies USING gin (nif gin_trgm_ops) WHERE nif IS NOT NULL;

-- ============================================================
-- 4. Filter indexes
-- ============================================================
CREATE INDEX IF NOT EXISTS idx_companies_active_verified
  ON companies (is_active, is_verified);

CREATE INDEX IF NOT EXISTS idx_companies_city_id
  ON companies (city_id) WHERE city_id IS NOT NULL;
