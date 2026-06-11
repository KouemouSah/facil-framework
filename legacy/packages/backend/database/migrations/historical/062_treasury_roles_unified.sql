-- ============================================================================
-- Migration 062: Treasury Roles - Unified agent_tesoro
-- ============================================================================
--
-- Purpose:
--   Create unified agent_tesoro role that combines validation + reconciliation
--   + transactions access. Keeps existing granular roles for specific cases.
--
-- Roles structure:
--   - agent_tesoro (NEW): Unified role for validation, reconciliation, transactions
--   - agent_tesoro_validation: Kept for specific use cases (validation only)
--   - agent_tesoro_reconciliation: Kept for specific use cases (reconciliation only)
--   - supervisor_tesoro: Full access to all treasury features
--
-- Date: 2026-01-18
-- ============================================================================

BEGIN;

-- ============================================================================
-- PART 1: CREATE UNIFIED AGENT_TESORO ROLE
-- ============================================================================

INSERT INTO roles (name, code, description, is_system, entity_type, created_at, updated_at)
SELECT
    'Agente Tesoro',
    'agent_tesoro',
    'Agente de tesorería unificado - validación, conciliación y transacciones. Acceso solo a sus propias operaciones.',
    FALSE,
    'agent',
    NOW(),
    NOW()
WHERE NOT EXISTS (SELECT 1 FROM roles WHERE code = 'agent_tesoro');

-- ============================================================================
-- PART 2: ENSURE ALL TREASURY PERMISSIONS EXIST
-- ============================================================================

-- Insert missing permissions if they don't exist
INSERT INTO permissions (name, resource, action, description, is_critical, module_name, created_at, updated_at)
VALUES
    -- Payment validation
    ('treasury.validate_payment', 'treasury', 'validate_payment', 'Validar pagos manuales (efectivo, cheque)', TRUE, 'treasury', NOW(), NOW()),
    ('treasury.reject_payment', 'treasury', 'reject_payment', 'Rechazar pago', TRUE, 'treasury', NOW(), NOW()),
    ('treasury.view_payment', 'treasury', 'view_payment', 'Ver detalles de pagos', FALSE, 'treasury', NOW(), NOW()),
    ('treasury.process_payment', 'treasury', 'process_payment', 'Procesar pagos pendientes', TRUE, 'treasury', NOW(), NOW()),

    -- Reconciliation
    ('treasury.reconcile', 'treasury', 'reconcile', 'Ejecutar reconciliación bancaria', TRUE, 'treasury', NOW(), NOW()),
    ('treasury.view_reconciliation', 'treasury', 'view_reconciliation', 'Ver estado de reconciliación', FALSE, 'treasury', NOW(), NOW()),

    -- Audit
    ('treasury_audit.view', 'treasury_audit', 'view', 'Ver historial de auditoría de tesorería', FALSE, 'treasury', NOW(), NOW()),
    ('treasury_audit.export', 'treasury_audit', 'export', 'Exportar registros de auditoría', FALSE, 'treasury', NOW(), NOW()),

    -- Statistics
    ('treasury_stat.view', 'treasury_stat', 'view', 'Ver estadísticas de tesorería', FALSE, 'treasury', NOW(), NOW()),
    ('treasury_stat.export', 'treasury_stat', 'export', 'Exportar estadísticas', FALSE, 'treasury', NOW(), NOW()),

    -- Anomalies
    ('treasury_anomaly.view', 'treasury_anomaly', 'view', 'Ver anomalías detectadas', FALSE, 'treasury', NOW(), NOW()),
    ('treasury_anomaly.create', 'treasury_anomaly', 'create', 'Crear reporte de anomalía manual', FALSE, 'treasury', NOW(), NOW()),
    ('treasury_anomaly.update', 'treasury_anomaly', 'update', 'Actualizar estado de anomalía', FALSE, 'treasury', NOW(), NOW()),
    ('treasury_anomaly.resolve', 'treasury_anomaly', 'resolve', 'Marcar anomalía como resuelta', TRUE, 'treasury', NOW(), NOW()),

    -- Exports
    ('treasury_export.view', 'treasury_export', 'view', 'Ver exportaciones disponibles', FALSE, 'treasury', NOW(), NOW()),
    ('treasury_export.create', 'treasury_export', 'create', 'Crear nueva exportación', FALSE, 'treasury', NOW(), NOW()),
    ('treasury_export.download', 'treasury_export', 'download', 'Descargar archivos exportados', FALSE, 'treasury', NOW(), NOW()),

    -- Settings (supervisor only)
    ('treasury.manage_settings', 'treasury', 'manage_settings', 'Gestionar configuración de tesorería (bancos, métodos de pago)', TRUE, 'treasury', NOW(), NOW())
ON CONFLICT (name) DO NOTHING;

-- ============================================================================
-- PART 3: ASSIGN PERMISSIONS TO AGENT_TESORO (UNIFIED)
-- ============================================================================
-- Menus: Validation, Reconciliation, Transactions
-- Scope: Only their own operations

INSERT INTO role_permissions (role_id, permission_id, created_at)
SELECT r.id, p.id, NOW()
FROM roles r
CROSS JOIN permissions p
WHERE r.code = 'agent_tesoro'
  AND p.name IN (
    -- Payment operations (Validation menu)
    'treasury.view_payment',
    'treasury.validate_payment',
    'treasury.reject_payment',
    'treasury.process_payment',

    -- Reconciliation operations (Reconciliation menu)
    'treasury.reconcile',
    'treasury.view_reconciliation',

    -- Transactions menu (view history - same as view_payment)
    -- treasury.view_payment already included above

    -- Basic agent permissions
    'assignments.view_own',
    'workloads.view_own',
    'agents.view_own_profile',
    'agents.update_availability',
    'notifications.log.read'
  )
ON CONFLICT (role_id, permission_id) DO NOTHING;

-- ============================================================================
-- PART 4: UPDATE SUPERVISOR_TESORO PERMISSIONS (FULL ACCESS)
-- ============================================================================
-- Menus: ALL
-- Scope: All team operations + Settings

INSERT INTO role_permissions (role_id, permission_id, created_at)
SELECT r.id, p.id, NOW()
FROM roles r
CROSS JOIN permissions p
WHERE r.code = 'supervisor_tesoro'
  AND p.name IN (
    -- ALL Payment operations
    'treasury.view_payment',
    'treasury.validate_payment',
    'treasury.reject_payment',
    'treasury.process_payment',

    -- ALL Reconciliation operations
    'treasury.reconcile',
    'treasury.view_reconciliation',

    -- ALL Audit operations
    'treasury_audit.view',
    'treasury_audit.export',

    -- ALL Statistics operations
    'treasury_stat.view',
    'treasury_stat.export',

    -- ALL Anomaly operations
    'treasury_anomaly.view',
    'treasury_anomaly.create',
    'treasury_anomaly.update',
    'treasury_anomaly.resolve',

    -- ALL Export operations
    'treasury_export.view',
    'treasury_export.create',
    'treasury_export.download',

    -- Settings management (SUPERVISOR ONLY)
    'treasury.manage_settings',

    -- Team management permissions
    'assignments.view_own',
    'assignments.view_team',
    'assignments.reassign',
    'workloads.view_own',
    'workloads.view_team',
    'workloads.manage',
    'agents.view_own_profile',
    'agents.update_availability',
    'notifications.log.read'
  )
ON CONFLICT (role_id, permission_id) DO NOTHING;

-- ============================================================================
-- PART 5: UPDATE DEFAULT ROLE ASSIGNMENT FOR TESORO ENTITY
-- ============================================================================
-- When an agent is assigned to TESORO entity, default role is now agent_tesoro

-- Note: This is informational - actual role assignment happens at agent creation time
-- The application code should use 'agent_tesoro' as default for new TESORO agents

COMMENT ON TABLE roles IS 'Roles table. Default role for TESORO entity agents: agent_tesoro (unified). Supervisor role: supervisor_tesoro.';

COMMIT;

-- ============================================================================
-- SUMMARY
-- ============================================================================
--
-- Roles disponibles pour TESORO:
--
-- | Rôle                        | Menus                              | Scope           |
-- |-----------------------------|------------------------------------|-----------------|
-- | agent_tesoro                | Validation, Réconciliation, Trans. | Propres ops     |
-- | agent_tesoro_validation     | Validation uniquement              | Propres ops     |
-- | agent_tesoro_reconciliation | Réconciliation uniquement          | Propres ops     |
-- | supervisor_tesoro           | TOUS                               | Équipe + Config |
--
-- ============================================================================
