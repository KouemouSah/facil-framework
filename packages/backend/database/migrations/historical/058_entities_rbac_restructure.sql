-- ============================================================================
-- Migration 058: Entity Restructure & Entity-Based RBAC Roles
-- ============================================================================
-- Purpose:
--   1. Clean up existing entities to match the new architecture
--   2. Create entity hierarchy with proper ministry links
--   3. Create entity-specific RBAC roles with required permissions
--
-- Entity Structure:
--   - CNEDOGE (parent entity, independent)
--     ├── CNEDOGE_PASAPORTE (department, workflows: PASAPORTE_*)
--     └── CNEDOGE_RESIDENCIA (department, workflows: RESIDENCIA_*)
--   - ONRC (independent entity, workflows: CONTRATO_*)
--   - OFIVE (independent entity, workflows: VEHICULO_*_CUVE)
--   - DGT (entity, parent ministry: INTERIOR, workflows: CONDUCIR_*)
--   - TESORO (entity, parent ministry: HACIENDA, no workflows - handles all payments)
--
-- RBAC Roles:
--   - agent_cnedoge_pasaporte: Agent for passport processing
--   - agent_cnedoge_residencia: Agent for residence permits
--   - agent_onrc: Agent for contracts
--   - agent_ofive: Agent for vehicle documents (CUVE)
--   - agent_dgt_permiso: Agent for driving permits
--   - agent_tesoro_validation: Treasury validation agent
--   - agent_tesoro_reconciliation: Treasury reconciliation agent
--   - supervisor_tesoro: Treasury supervisor
--
-- Date: 2026-01-16
-- ============================================================================

BEGIN;

-- ============================================================================
-- PART 1: VERIFY MINISTRIES EXIST
-- ============================================================================
-- Using existing ministry_codes from the database:
-- M-009 = MINISTERIO DE INTERIOR Y COOPERACIONES LOCALES (parent for DGT)
-- M-007 = MINISTERIO DE HACIENDA ECONOMIA PLANIFICACIÓN E INVERSIONES (parent for TESORO)

-- No INSERT needed - ministries already exist with codes M-007 and M-009

-- ============================================================================
-- PART 2: DISABLE VALIDATION TRIGGER TEMPORARILY
-- ============================================================================

-- Drop the workflow_codes validation trigger temporarily to allow entity restructure
DROP TRIGGER IF EXISTS tr_validate_entity_workflow_codes ON entities;

-- ============================================================================
-- PART 3: CLEAN UP ENTITIES
-- ============================================================================

-- First, remove all agent_profiles entity references to avoid FK conflicts
UPDATE agent_profiles SET entity_id = NULL;

-- Remove all entity_locations references
UPDATE entity_locations SET entity_id = NULL WHERE entity_id IS NOT NULL;

-- Delete ALL existing entities (safe as per user confirmation)
DELETE FROM entities;

-- ============================================================================
-- PART 4: CREATE NEW ENTITY STRUCTURE
-- ============================================================================

-- 4.1 Create CNEDOGE (parent entity, independent)
INSERT INTO entities (code, name, description, entity_type, ministry_id, parent_entity_id, workflow_codes, is_active)
VALUES (
    'CNEDOGE',
    'Centro Nacional de Expedición de Documentos Oficiales',
    'Centro Nacional de Expedición de Documentos Oficiales de Guinea Ecuatorial - Entidad matriz',
    'entity',
    NULL,  -- Independent (no ministry)
    NULL,  -- No parent
    '[]'::jsonb,  -- Workflows inherited by departments
    TRUE
);

-- 4.2 Create CNEDOGE_PASAPORTE (department of CNEDOGE)
INSERT INTO entities (code, name, description, entity_type, ministry_id, parent_entity_id, workflow_codes, is_active)
VALUES (
    'CNEDOGE_PASAPORTE',
    'Servicio de Pasaportes - CNEDOGE',
    'Departamento de gestión de solicitudes de pasaportes',
    'department',
    NULL,
    (SELECT id FROM entities WHERE code = 'CNEDOGE'),
    '["PASAPORTE_NUEVO", "PASAPORTE_RENOVACION", "PASAPORTE_PERDIDA", "PASAPORTE_ROBO", "PASAPORTE_DETERIORO"]'::jsonb,
    TRUE
);

-- 4.3 Create CNEDOGE_RESIDENCIA (department of CNEDOGE)
INSERT INTO entities (code, name, description, entity_type, ministry_id, parent_entity_id, workflow_codes, is_active)
VALUES (
    'CNEDOGE_RESIDENCIA',
    'Servicio de Residencias - CNEDOGE',
    'Departamento de gestión de permisos de residencia',
    'department',
    NULL,
    (SELECT id FROM entities WHERE code = 'CNEDOGE'),
    '["RESIDENCIA_PRIMERA_VEZ", "RESIDENCIA_RENOVACION", "RESIDENCIA_DUPLICADO", "RESIDENCIA_CAMBIO_DATOS", "RESIDENCIA_REAGRUPACION"]'::jsonb,
    TRUE
);

-- 4.4 Create ONRC (independent entity for contracts)
INSERT INTO entities (code, name, description, entity_type, ministry_id, parent_entity_id, workflow_codes, is_active)
VALUES (
    'ONRC',
    'Oficina Nacional de Registro de Contratos',
    'Oficina Nacional de Registro y Gestión de Contratos',
    'entity',
    NULL,  -- Independent
    NULL,
    '["CONTRATO_OBRA", "CONTRATO_SERVICIO", "CONTRATO_SUMINISTRO", "CONTRATO_CONCESION", "CONTRATO_JOINT_VENTURE", "CONTRATO_ARRENDAMIENTO", "CONTRATO_OTRO"]'::jsonb,
    TRUE
);

-- 4.5 Create OFIVE (independent entity for vehicle documents - CUVE)
INSERT INTO entities (code, name, description, entity_type, ministry_id, parent_entity_id, workflow_codes, is_active)
VALUES (
    'OFIVE',
    'Oficina de Vehículos - CUVE',
    'Oficina de gestión de documentos de vehículos (CUVE)',
    'entity',
    NULL,  -- Independent
    NULL,
    '["VEHICULO_PRIMERA_MATRICULACION", "VEHICULO_TRANSFERENCIA", "VEHICULO_RENOVACION_CUVE", "VEHICULO_DUPLICADO_PERMISO", "VEHICULO_DUPLICADO_CUVE", "VEHICULO_CAMBIO_CARACTERISTICAS"]'::jsonb,
    TRUE
);

-- 4.6 Create DGT (entity linked to M-009 MINISTERIO DE INTERIOR - for driving permits)
INSERT INTO entities (code, name, description, entity_type, ministry_id, parent_entity_id, workflow_codes, is_active)
VALUES (
    'DGT',
    'Dirección General de Tráfico',
    'Dirección General de Tráfico y Seguridad Vial - Permisos de conducir',
    'entity',
    (SELECT id FROM ministries WHERE ministry_code = 'M-009'),
    NULL,
    '["CONDUCIR_NUEVO", "CONDUCIR_CANJE", "CONDUCIR_RENOVACION", "CONDUCIR_DUPLICADO", "CONDUCIR_EXTENSION"]'::jsonb,
    TRUE
);

-- 4.7 Create TESORO (entity linked to M-007 MINISTERIO DE HACIENDA - for payments)
INSERT INTO entities (code, name, description, entity_type, ministry_id, parent_entity_id, workflow_codes, is_active)
VALUES (
    'TESORO',
    'Tesoro Público',
    'Dirección General del Tesoro Público - Gestión de pagos y validaciones',
    'entity',
    (SELECT id FROM ministries WHERE ministry_code = 'M-007'),
    NULL,
    '[]'::jsonb,  -- No workflows - handles all payments transversally
    TRUE
);

-- ============================================================================
-- PART 5: ADD MISSING PERMISSIONS
-- ============================================================================

-- Add service_requests permissions if not exists
INSERT INTO permissions (name, resource, action, description, is_critical, module_name)
VALUES
    ('service_requests.escalate', 'service_requests', 'escalate', 'Escalar solicitud a supervisor', FALSE, 'service_request'),
    ('service_requests.request_documents', 'service_requests', 'request_documents', 'Solicitar documentos adicionales', FALSE, 'service_request')
ON CONFLICT (name) DO NOTHING;

-- Add agent-related permissions
INSERT INTO permissions (name, resource, action, description, is_critical, module_name)
VALUES
    ('assignments.view_own', 'assignments', 'view_own', 'Ver asignaciones propias', FALSE, 'agent'),
    ('assignments.view_team', 'assignments', 'view_team', 'Ver asignaciones del equipo', FALSE, 'agent'),
    ('assignments.reassign', 'assignments', 'reassign', 'Reasignar solicitudes a otro agente', FALSE, 'agent'),
    ('workloads.view_own', 'workloads', 'view_own', 'Ver carga de trabajo propia', FALSE, 'agent'),
    ('workloads.view_team', 'workloads', 'view_team', 'Ver carga de trabajo del equipo', FALSE, 'agent'),
    ('workloads.manage', 'workloads', 'manage', 'Gestionar cargas de trabajo', FALSE, 'agent'),
    ('agents.view_own_profile', 'agents', 'view_own_profile', 'Ver perfil de agente propio', FALSE, 'agent'),
    ('agents.update_availability', 'agents', 'update_availability', 'Actualizar disponibilidad', FALSE, 'agent'),
    ('workflow_documents.read', 'workflow_documents', 'read', 'Consultar documentos de workflow', FALSE, 'service_request')
ON CONFLICT (name) DO NOTHING;

-- ============================================================================
-- PART 6: CREATE ENTITY-BASED RBAC ROLES
-- ============================================================================

-- 6.1 Agent CNEDOGE Pasaporte
INSERT INTO roles (name, code, description, is_system, entity_type, created_at, updated_at)
SELECT
    'Agente CNEDOGE Pasaporte',
    'agent_cnedoge_pasaporte',
    'Agente de gestión de pasaportes - Entidad CNEDOGE_PASAPORTE',
    FALSE,  -- NOT system role - can be modified/deleted
    'agent',
    NOW(),
    NOW()
WHERE NOT EXISTS (SELECT 1 FROM roles WHERE code = 'agent_cnedoge_pasaporte');

-- 6.2 Agent CNEDOGE Residencia
INSERT INTO roles (name, code, description, is_system, entity_type, created_at, updated_at)
SELECT
    'Agente CNEDOGE Residencia',
    'agent_cnedoge_residencia',
    'Agente de gestión de permisos de residencia - Entidad CNEDOGE_RESIDENCIA',
    FALSE,
    'agent',
    NOW(),
    NOW()
WHERE NOT EXISTS (SELECT 1 FROM roles WHERE code = 'agent_cnedoge_residencia');

-- 6.3 Agent ONRC (Contratos)
INSERT INTO roles (name, code, description, is_system, entity_type, created_at, updated_at)
SELECT
    'Agente ONRC',
    'agent_onrc',
    'Agente de gestión de contratos - Entidad ONRC',
    FALSE,
    'agent',
    NOW(),
    NOW()
WHERE NOT EXISTS (SELECT 1 FROM roles WHERE code = 'agent_onrc');

-- 6.4 Agent OFIVE (CUVE - Vehicles)
INSERT INTO roles (name, code, description, is_system, entity_type, created_at, updated_at)
SELECT
    'Agente OFIVE (CUVE)',
    'agent_ofive',
    'Agente de gestión de documentos de vehículos (CUVE) - Entidad OFIVE',
    FALSE,
    'agent',
    NOW(),
    NOW()
WHERE NOT EXISTS (SELECT 1 FROM roles WHERE code = 'agent_ofive');

-- 6.5 Agent DGT Permiso (Driving permits)
INSERT INTO roles (name, code, description, is_system, entity_type, created_at, updated_at)
SELECT
    'Agente DGT Permiso',
    'agent_dgt_permiso',
    'Agente de permisos de conducir - Entidad DGT (Ministerio Interior)',
    FALSE,
    'agent',
    NOW(),
    NOW()
WHERE NOT EXISTS (SELECT 1 FROM roles WHERE code = 'agent_dgt_permiso');

-- 6.6 Agent Tesoro Validation
INSERT INTO roles (name, code, description, is_system, entity_type, created_at, updated_at)
SELECT
    'Agente Tesoro Validación',
    'agent_tesoro_validation',
    'Agente de validación de pagos - Entidad TESORO (Ministerio Hacienda)',
    FALSE,
    'agent',
    NOW(),
    NOW()
WHERE NOT EXISTS (SELECT 1 FROM roles WHERE code = 'agent_tesoro_validation');

-- 6.7 Agent Tesoro Reconciliation
INSERT INTO roles (name, code, description, is_system, entity_type, created_at, updated_at)
SELECT
    'Agente Tesoro Conciliación',
    'agent_tesoro_reconciliation',
    'Agente de conciliación de pagos - Entidad TESORO (Ministerio Hacienda)',
    FALSE,
    'agent',
    NOW(),
    NOW()
WHERE NOT EXISTS (SELECT 1 FROM roles WHERE code = 'agent_tesoro_reconciliation');

-- 6.8 Supervisor Tesoro
INSERT INTO roles (name, code, description, is_system, entity_type, created_at, updated_at)
SELECT
    'Supervisor Tesoro',
    'supervisor_tesoro',
    'Supervisor de tesorería con acceso completo a pagos - Entidad TESORO',
    FALSE,
    'agent',
    NOW(),
    NOW()
WHERE NOT EXISTS (SELECT 1 FROM roles WHERE code = 'supervisor_tesoro');

-- ============================================================================
-- PART 7: ASSIGN PERMISSIONS TO ENTITY-BASED ROLES
-- ============================================================================

-- Common permissions for all entity agents (CNEDOGE_PASAPORTE, CNEDOGE_RESIDENCIA, ONRC, OFIVE, DGT)
-- Permissions: view, validate, reject, request_documents, escalate

-- 7.1 Agent CNEDOGE Pasaporte permissions
INSERT INTO role_permissions (role_id, permission_id, created_at)
SELECT r.id, p.id, NOW()
FROM roles r
CROSS JOIN permissions p
WHERE r.code = 'agent_cnedoge_pasaporte'
  AND p.name IN (
    'service_requests.read',
    'service_requests.validate',
    'service_requests.reject',
    'service_requests.request_documents',
    'service_requests.escalate',
    'assignments.view_own',
    'workloads.view_own',
    'agents.view_own_profile',
    'agents.update_availability',
    'notifications.log.read',
    'workflow_documents.read'
  )
ON CONFLICT (role_id, permission_id) DO NOTHING;

-- 7.2 Agent CNEDOGE Residencia permissions
INSERT INTO role_permissions (role_id, permission_id, created_at)
SELECT r.id, p.id, NOW()
FROM roles r
CROSS JOIN permissions p
WHERE r.code = 'agent_cnedoge_residencia'
  AND p.name IN (
    'service_requests.read',
    'service_requests.validate',
    'service_requests.reject',
    'service_requests.request_documents',
    'service_requests.escalate',
    'assignments.view_own',
    'workloads.view_own',
    'agents.view_own_profile',
    'agents.update_availability',
    'notifications.log.read',
    'workflow_documents.read'
  )
ON CONFLICT (role_id, permission_id) DO NOTHING;

-- 7.3 Agent ONRC permissions
INSERT INTO role_permissions (role_id, permission_id, created_at)
SELECT r.id, p.id, NOW()
FROM roles r
CROSS JOIN permissions p
WHERE r.code = 'agent_onrc'
  AND p.name IN (
    'service_requests.read',
    'service_requests.validate',
    'service_requests.reject',
    'service_requests.request_documents',
    'service_requests.escalate',
    'assignments.view_own',
    'workloads.view_own',
    'agents.view_own_profile',
    'agents.update_availability',
    'notifications.log.read',
    'workflow_documents.read'
  )
ON CONFLICT (role_id, permission_id) DO NOTHING;

-- 7.4 Agent OFIVE permissions
INSERT INTO role_permissions (role_id, permission_id, created_at)
SELECT r.id, p.id, NOW()
FROM roles r
CROSS JOIN permissions p
WHERE r.code = 'agent_ofive'
  AND p.name IN (
    'service_requests.read',
    'service_requests.validate',
    'service_requests.reject',
    'service_requests.request_documents',
    'service_requests.escalate',
    'assignments.view_own',
    'workloads.view_own',
    'agents.view_own_profile',
    'agents.update_availability',
    'notifications.log.read',
    'workflow_documents.read'
  )
ON CONFLICT (role_id, permission_id) DO NOTHING;

-- 7.5 Agent DGT Permiso permissions
INSERT INTO role_permissions (role_id, permission_id, created_at)
SELECT r.id, p.id, NOW()
FROM roles r
CROSS JOIN permissions p
WHERE r.code = 'agent_dgt_permiso'
  AND p.name IN (
    'service_requests.read',
    'service_requests.validate',
    'service_requests.reject',
    'service_requests.request_documents',
    'service_requests.escalate',
    'assignments.view_own',
    'workloads.view_own',
    'agents.view_own_profile',
    'agents.update_availability',
    'notifications.log.read',
    'workflow_documents.read'
  )
ON CONFLICT (role_id, permission_id) DO NOTHING;

-- 7.6 Agent Tesoro Validation permissions
INSERT INTO role_permissions (role_id, permission_id, created_at)
SELECT r.id, p.id, NOW()
FROM roles r
CROSS JOIN permissions p
WHERE r.code = 'agent_tesoro_validation'
  AND p.name IN (
    -- Treasury validation permissions
    'treasury.payments.view',
    'treasury.payments.lock',
    'treasury.payments.validate',
    'treasury.payments.reject',
    -- Basic permissions
    'assignments.view_own',
    'workloads.view_own',
    'agents.view_own_profile',
    'agents.update_availability',
    'notifications.log.read',
    -- Audit access (read-only)
    'treasury.audit.view',
    'treasury.anomalies.view'
  )
ON CONFLICT (role_id, permission_id) DO NOTHING;

-- 7.7 Agent Tesoro Reconciliation permissions
INSERT INTO role_permissions (role_id, permission_id, created_at)
SELECT r.id, p.id, NOW()
FROM roles r
CROSS JOIN permissions p
WHERE r.code = 'agent_tesoro_reconciliation'
  AND p.name IN (
    -- Treasury reconciliation permissions
    'treasury.payments.view',
    'treasury.anomalies.view',
    'treasury.anomalies.create',
    'treasury.anomalies.update',
    'treasury.exports.view',
    'treasury.exports.create',
    'treasury.exports.download',
    -- Basic permissions
    'assignments.view_own',
    'workloads.view_own',
    'agents.view_own_profile',
    'agents.update_availability',
    'notifications.log.read',
    -- Audit access
    'treasury.audit.view',
    'treasury.stats.view'
  )
ON CONFLICT (role_id, permission_id) DO NOTHING;

-- 7.8 Supervisor Tesoro permissions (full treasury access)
INSERT INTO role_permissions (role_id, permission_id, created_at)
SELECT r.id, p.id, NOW()
FROM roles r
CROSS JOIN permissions p
WHERE r.code = 'supervisor_tesoro'
  AND p.name IN (
    -- All treasury permissions
    'treasury.payments.view',
    'treasury.payments.lock',
    'treasury.payments.validate',
    'treasury.payments.reject',
    'treasury.banks.view',
    'treasury.banks.manage',
    'treasury.payment_methods.view',
    'treasury.payment_methods.manage',
    'treasury.anomalies.view',
    'treasury.anomalies.create',
    'treasury.anomalies.update',
    'treasury.exports.view',
    'treasury.exports.create',
    'treasury.exports.download',
    'treasury.audit.view',
    'treasury.stats.view',
    -- Team management
    'assignments.view_own',
    'assignments.view_team',
    'assignments.reassign',
    'workloads.view_own',
    'workloads.view_team',
    'workloads.manage',
    -- Profile
    'agents.view_own_profile',
    'agents.update_availability',
    'notifications.log.read',
    'notifications.log.export'
  )
ON CONFLICT (role_id, permission_id) DO NOTHING;

-- ============================================================================
-- PART 8: RE-ENABLE VALIDATION TRIGGER
-- ============================================================================

-- Recreate the trigger (if the function exists)
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_proc WHERE proname = 'validate_entity_workflow_codes') THEN
        CREATE TRIGGER tr_validate_entity_workflow_codes
            BEFORE INSERT OR UPDATE OF workflow_codes ON entities
            FOR EACH ROW
            EXECUTE FUNCTION validate_entity_workflow_codes();
    END IF;
END $$;

-- ============================================================================
-- PART 9: CREATE MAPPING VIEW FOR ENTITY -> ROLE
-- ============================================================================

CREATE OR REPLACE VIEW v_entity_default_roles AS
SELECT
    e.id as entity_id,
    e.code as entity_code,
    e.name as entity_name,
    e.entity_type,
    m.ministry_code,
    m.name_es as ministry_name,
    CASE e.code
        WHEN 'CNEDOGE_PASAPORTE' THEN 'agent_cnedoge_pasaporte'
        WHEN 'CNEDOGE_RESIDENCIA' THEN 'agent_cnedoge_residencia'
        WHEN 'ONRC' THEN 'agent_onrc'
        WHEN 'OFIVE' THEN 'agent_ofive'
        WHEN 'DGT' THEN 'agent_dgt_permiso'
        WHEN 'TESORO' THEN 'agent_tesoro_validation'  -- Default treasury role
        ELSE NULL
    END as default_role_code,
    r.id as default_role_id,
    r.name as default_role_name
FROM entities e
LEFT JOIN ministries m ON e.ministry_id = m.id
LEFT JOIN roles r ON r.code = CASE e.code
    WHEN 'CNEDOGE_PASAPORTE' THEN 'agent_cnedoge_pasaporte'
    WHEN 'CNEDOGE_RESIDENCIA' THEN 'agent_cnedoge_residencia'
    WHEN 'ONRC' THEN 'agent_onrc'
    WHEN 'OFIVE' THEN 'agent_ofive'
    WHEN 'DGT' THEN 'agent_dgt_permiso'
    WHEN 'TESORO' THEN 'agent_tesoro_validation'
    ELSE NULL
END
WHERE e.is_active = true
ORDER BY e.entity_type, e.code;

COMMENT ON VIEW v_entity_default_roles IS 'Maps entities to their default RBAC roles for agent creation';

-- ============================================================================
-- PART 10: VERIFICATION
-- ============================================================================

-- Verify entities created
SELECT 'Entities created:' as status;
SELECT e.code, e.name, e.entity_type,
       COALESCE(m.ministry_code, 'Independent') as ministry,
       COALESCE(pe.code, 'None') as parent_entity
FROM entities e
LEFT JOIN ministries m ON e.ministry_id = m.id
LEFT JOIN entities pe ON e.parent_entity_id = pe.id
ORDER BY e.entity_type, e.code;

-- Verify roles created
SELECT 'Entity RBAC roles created:' as status;
SELECT r.code, r.name, r.is_system FROM roles r
WHERE r.code LIKE 'agent_%' OR r.code LIKE 'supervisor_tesoro'
ORDER BY r.code;

-- Verify permissions per role
SELECT 'Permissions per role:' as status;
SELECT r.code, r.name, COUNT(rp.permission_id) as permission_count
FROM roles r
LEFT JOIN role_permissions rp ON r.id = rp.role_id
WHERE r.code IN (
    'agent_cnedoge_pasaporte', 'agent_cnedoge_residencia', 'agent_onrc',
    'agent_ofive', 'agent_dgt_permiso', 'agent_tesoro_validation',
    'agent_tesoro_reconciliation', 'supervisor_tesoro'
)
GROUP BY r.code, r.name
ORDER BY r.code;

COMMIT;

-- ============================================================================
-- ROLLBACK SCRIPT (run separately if needed)
-- ============================================================================
-- BEGIN;
-- DELETE FROM role_permissions WHERE role_id IN (
--     SELECT id FROM roles WHERE code IN (
--         'agent_cnedoge_pasaporte', 'agent_cnedoge_residencia', 'agent_onrc',
--         'agent_ofive', 'agent_dgt_permiso', 'agent_tesoro_validation',
--         'agent_tesoro_reconciliation', 'supervisor_tesoro'
--     )
-- );
-- DELETE FROM roles WHERE code IN (
--     'agent_cnedoge_pasaporte', 'agent_cnedoge_residencia', 'agent_onrc',
--     'agent_ofive', 'agent_dgt_permiso', 'agent_tesoro_validation',
--     'agent_tesoro_reconciliation', 'supervisor_tesoro'
-- );
-- -- Note: Entity rollback would require restoring from backup
-- COMMIT;
