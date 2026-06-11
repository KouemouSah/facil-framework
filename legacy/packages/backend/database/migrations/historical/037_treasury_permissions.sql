-- ============================================================================
-- Migration 037: Add Treasury Phase 1A + 1B Permissions
-- ============================================================================
-- Adds permissions for:
-- - Treasury Audit (Phase 1A)
-- - Treasury SLA Stats (Phase 1B)
-- ============================================================================

-- ============================================================================
-- 1. ADD TREASURY PERMISSIONS
-- ============================================================================

INSERT INTO permissions (name, resource, action, description, is_critical, module_name)
VALUES
    -- Treasury Audit (Phase 1A)
    ('treasury.audit.view', 'treasury_audit', 'read', 'Ver historial de auditoria de pagos Treasury', FALSE, 'treasury'),

    -- Treasury Stats (Phase 1B)
    ('treasury.stats.view', 'treasury_stats', 'read', 'Ver estadisticas SLA de Treasury', FALSE, 'treasury'),

    -- Treasury Payments (existing but ensuring)
    ('treasury.payments.view', 'treasury_payments', 'read', 'Ver pagos pendientes de validacion', FALSE, 'treasury'),
    ('treasury.payments.lock', 'treasury_payments', 'lock', 'Bloquear pagos para revision', FALSE, 'treasury'),
    ('treasury.payments.validate', 'treasury_payments', 'validate', 'Validar pagos', FALSE, 'treasury'),
    ('treasury.payments.reject', 'treasury_payments', 'reject', 'Rechazar pagos', FALSE, 'treasury'),

    -- Treasury Bank Config
    ('treasury.banks.view', 'treasury_banks', 'read', 'Ver configuracion de bancos', FALSE, 'treasury'),
    ('treasury.banks.manage', 'treasury_banks', 'write', 'Administrar configuracion de bancos', TRUE, 'treasury'),

    -- Treasury Payment Methods Config
    ('treasury.payment_methods.view', 'treasury_payment_methods', 'read', 'Ver metodos de pago', FALSE, 'treasury'),
    ('treasury.payment_methods.manage', 'treasury_payment_methods', 'write', 'Administrar metodos de pago', TRUE, 'treasury'),

    -- Treasury Anomalies (Phase 2A)
    ('treasury.anomalies.view', 'treasury_anomalies', 'read', 'Ver anomalias de pagos', FALSE, 'treasury'),
    ('treasury.anomalies.create', 'treasury_anomalies', 'create', 'Crear anomalias manuales', FALSE, 'treasury'),
    ('treasury.anomalies.update', 'treasury_anomalies', 'update', 'Actualizar estado de anomalias', FALSE, 'treasury'),

    -- Treasury Exports (Phase 2B)
    ('treasury.exports.view', 'treasury_exports', 'read', 'Ver historial de exports', FALSE, 'treasury'),
    ('treasury.exports.create', 'treasury_exports', 'create', 'Generar nuevos exports', FALSE, 'treasury'),
    ('treasury.exports.download', 'treasury_exports', 'download', 'Descargar archivos de export', FALSE, 'treasury')
ON CONFLICT (name) DO NOTHING;

-- ============================================================================
-- 2. ASSIGN PERMISSIONS TO TREASURY AGENT ROLE (if exists)
-- ============================================================================

-- First check if treasury_agent role exists, if not create it
-- roles table schema: id, name, code, entity_type, description, is_system, created_at, updated_at, created_by
INSERT INTO roles (name, code, description, is_system, created_at, updated_at)
SELECT 'Treasury Agent', 'treasury_agent', 'Agente de Tesoreria - Gestiona validaciones de pago', TRUE, NOW(), NOW()
WHERE NOT EXISTS (SELECT 1 FROM roles WHERE code = 'treasury_agent');

-- Assign permissions to treasury_agent role
INSERT INTO role_permissions (role_id, permission_id, created_at)
SELECT r.id, p.id, NOW()
FROM roles r
CROSS JOIN permissions p
WHERE r.code = 'treasury_agent'
  AND p.name IN (
    'treasury.audit.view',
    'treasury.stats.view',
    'treasury.payments.view',
    'treasury.payments.lock',
    'treasury.payments.validate',
    'treasury.payments.reject',
    'treasury.banks.view',
    'treasury.payment_methods.view',
    'treasury.anomalies.view',
    'treasury.anomalies.create',
    'treasury.anomalies.update',
    'treasury.exports.view',
    'treasury.exports.create',
    'treasury.exports.download'
  )
ON CONFLICT (role_id, permission_id) DO NOTHING;

-- ============================================================================
-- 3. ASSIGN PERMISSIONS TO ADMIN ROLE
-- ============================================================================

INSERT INTO role_permissions (role_id, permission_id, created_at)
SELECT r.id, p.id, NOW()
FROM roles r
CROSS JOIN permissions p
WHERE r.code = 'admin'
  AND p.name LIKE 'treasury.%'
ON CONFLICT (role_id, permission_id) DO NOTHING;

-- ============================================================================
-- 4. ASSIGN PERMISSIONS TO SUPERVISOR ROLE
-- ============================================================================

INSERT INTO role_permissions (role_id, permission_id, created_at)
SELECT r.id, p.id, NOW()
FROM roles r
CROSS JOIN permissions p
WHERE r.code = 'supervisor'
  AND p.name IN (
    'treasury.audit.view',
    'treasury.stats.view',
    'treasury.payments.view',
    'treasury.banks.view',
    'treasury.payment_methods.view',
    'treasury.anomalies.view',
    'treasury.exports.view',
    'treasury.exports.download'
  )
ON CONFLICT (role_id, permission_id) DO NOTHING;

-- ============================================================================
-- VERIFICATION
-- ============================================================================

SELECT
    'Treasury permissions added' AS status,
    COUNT(*) AS permission_count
FROM permissions
WHERE name LIKE 'treasury.%';
