-- ============================================================================
-- Migration 055: Agent RBAC Roles - Predefined Roles for Agent Types
-- ============================================================================
-- Creates predefined RBAC roles to be assigned to agents during creation.
-- This approach separates "what the agent does" (agent_role metadata) from
-- "what the agent can access" (RBAC permissions).
--
-- Roles created:
-- - dgi_validator: Basic validation for DGI agents
-- - dgi_approver: Senior DGI agent with approval rights
-- - ministry_validator: Basic validation for ministry agents
-- - ministry_approver: Senior ministry agent with approval rights
-- - auditor: Read-only audit access
-- - supervisor_agent: Full access for supervisors
-- ============================================================================

-- ============================================================================
-- 1. CREATE AGENT RBAC ROLES
-- ============================================================================

-- DGI Validator: Can view and validate declarations, service requests
INSERT INTO roles (name, code, description, is_system, entity_type, created_at, updated_at)
SELECT
    'DGI Validador',
    'dgi_validator',
    'Agente DGI con permisos de validacion basica de declaraciones y solicitudes',
    TRUE,
    'agent',
    NOW(),
    NOW()
WHERE NOT EXISTS (SELECT 1 FROM roles WHERE code = 'dgi_validator');

-- DGI Approver: Can approve declarations and payments (senior)
INSERT INTO roles (name, code, description, is_system, entity_type, created_at, updated_at)
SELECT
    'DGI Aprobador',
    'dgi_approver',
    'Agente DGI senior con permisos de aprobacion de declaraciones y pagos',
    TRUE,
    'agent',
    NOW(),
    NOW()
WHERE NOT EXISTS (SELECT 1 FROM roles WHERE code = 'dgi_approver');

-- Ministry Validator: Can view and validate service requests for ministry
INSERT INTO roles (name, code, description, is_system, entity_type, created_at, updated_at)
SELECT
    'Validador Ministerial',
    'ministry_validator',
    'Agente ministerial con permisos de validacion de solicitudes',
    TRUE,
    'agent',
    NOW(),
    NOW()
WHERE NOT EXISTS (SELECT 1 FROM roles WHERE code = 'ministry_validator');

-- Ministry Approver: Can approve service requests and escalate
INSERT INTO roles (name, code, description, is_system, entity_type, created_at, updated_at)
SELECT
    'Aprobador Ministerial',
    'ministry_approver',
    'Agente ministerial senior con permisos de aprobacion',
    TRUE,
    'agent',
    NOW(),
    NOW()
WHERE NOT EXISTS (SELECT 1 FROM roles WHERE code = 'ministry_approver');

-- Auditor: Read-only audit access across modules
INSERT INTO roles (name, code, description, is_system, entity_type, created_at, updated_at)
SELECT
    'Auditor',
    'auditor',
    'Acceso de solo lectura para auditoria',
    TRUE,
    'agent',
    NOW(),
    NOW()
WHERE NOT EXISTS (SELECT 1 FROM roles WHERE code = 'auditor');

-- Supervisor Agent: Full access for supervisors
INSERT INTO roles (name, code, description, is_system, entity_type, created_at, updated_at)
SELECT
    'Supervisor de Agentes',
    'supervisor_agent',
    'Supervisor con acceso completo a gestion de agentes y asignaciones',
    TRUE,
    'agent',
    NOW(),
    NOW()
WHERE NOT EXISTS (SELECT 1 FROM roles WHERE code = 'supervisor_agent');

-- ============================================================================
-- 2. ADD MISSING AGENT-SPECIFIC PERMISSIONS
-- ============================================================================

INSERT INTO permissions (name, resource, action, description, is_critical, module_name)
VALUES
    -- Declarations permissions for agents
    ('declarations.view_assigned', 'declarations', 'view_assigned', 'Ver declaraciones asignadas al agente', FALSE, 'declarations'),
    ('declarations.view_ministry', 'declarations', 'view_ministry', 'Ver declaraciones del ministerio asignado', FALSE, 'declarations'),
    ('declarations.validate', 'declarations', 'validate', 'Validar declaraciones', FALSE, 'declarations'),
    ('declarations.approve', 'declarations', 'approve', 'Aprobar declaraciones', FALSE, 'declarations'),
    ('declarations.reject', 'declarations', 'reject', 'Rechazar declaraciones', FALSE, 'declarations'),
    ('declarations.escalate', 'declarations', 'escalate', 'Escalar declaraciones a supervisor', FALSE, 'declarations'),
    ('declarations.request_documents', 'declarations', 'request_documents', 'Solicitar documentos adicionales', FALSE, 'declarations'),

    -- Assignments permissions
    ('assignments.view_own', 'assignments', 'view_own', 'Ver asignaciones propias', FALSE, 'assignments'),
    ('assignments.view_team', 'assignments', 'view_team', 'Ver asignaciones del equipo', FALSE, 'assignments'),
    ('assignments.reassign', 'assignments', 'reassign', 'Reasignar tareas a otros agentes', FALSE, 'assignments'),

    -- Agent workload permissions
    ('workloads.view_own', 'workloads', 'view_own', 'Ver carga de trabajo propia', FALSE, 'agents'),
    ('workloads.view_team', 'workloads', 'view_team', 'Ver carga de trabajo del equipo', FALSE, 'agents'),
    ('workloads.manage', 'workloads', 'manage', 'Gestionar carga de trabajo (supervisor)', FALSE, 'agents'),

    -- Agent profile permissions
    ('agents.view_own_profile', 'agents', 'view_own', 'Ver perfil de agente propio', FALSE, 'agents'),
    ('agents.update_availability', 'agents', 'update_availability', 'Actualizar disponibilidad propia', FALSE, 'agents')
ON CONFLICT (name) DO NOTHING;

-- ============================================================================
-- 3. ASSIGN PERMISSIONS TO DGI VALIDATOR ROLE
-- ============================================================================

INSERT INTO role_permissions (role_id, permission_id, created_at)
SELECT r.id, p.id, NOW()
FROM roles r
CROSS JOIN permissions p
WHERE r.code = 'dgi_validator'
  AND p.name IN (
    -- Service requests
    'service_requests.read',
    'service_requests.validate',

    -- Declarations (view and validate)
    'declarations.view_assigned',
    'declarations.validate',
    'declarations.request_documents',

    -- Assignments
    'assignments.view_own',

    -- Workload
    'workloads.view_own',

    -- Profile
    'agents.view_own_profile',
    'agents.update_availability',

    -- Notifications
    'notifications.log.read'
  )
ON CONFLICT (role_id, permission_id) DO NOTHING;

-- ============================================================================
-- 4. ASSIGN PERMISSIONS TO DGI APPROVER ROLE
-- ============================================================================

INSERT INTO role_permissions (role_id, permission_id, created_at)
SELECT r.id, p.id, NOW()
FROM roles r
CROSS JOIN permissions p
WHERE r.code = 'dgi_approver'
  AND p.name IN (
    -- All validator permissions
    'service_requests.read',
    'service_requests.validate',
    'declarations.view_assigned',
    'declarations.validate',
    'declarations.request_documents',
    'assignments.view_own',
    'workloads.view_own',
    'agents.view_own_profile',
    'agents.update_availability',
    'notifications.log.read',

    -- Additional approver permissions
    'service_requests.reject',
    'declarations.view_ministry',
    'declarations.approve',
    'declarations.reject',
    'declarations.escalate',
    'assignments.view_team',
    'assignments.reassign',
    'workloads.view_team',

    -- Treasury permissions (for payment approval)
    'treasury.payments.view',
    'treasury.payments.lock',
    'treasury.payments.validate',
    'treasury.payments.reject'
  )
ON CONFLICT (role_id, permission_id) DO NOTHING;

-- ============================================================================
-- 5. ASSIGN PERMISSIONS TO MINISTRY VALIDATOR ROLE
-- ============================================================================

INSERT INTO role_permissions (role_id, permission_id, created_at)
SELECT r.id, p.id, NOW()
FROM roles r
CROSS JOIN permissions p
WHERE r.code = 'ministry_validator'
  AND p.name IN (
    -- Service requests
    'service_requests.read',
    'service_requests.validate',

    -- Assignments
    'assignments.view_own',

    -- Workload
    'workloads.view_own',

    -- Profile
    'agents.view_own_profile',
    'agents.update_availability',

    -- Notifications
    'notifications.log.read',

    -- Workflow documents
    'workflow_documents.read',

    -- Funcionario verification (view pending)
    'funcionario.verificacion.read_all'
  )
ON CONFLICT (role_id, permission_id) DO NOTHING;

-- ============================================================================
-- 6. ASSIGN PERMISSIONS TO MINISTRY APPROVER ROLE
-- ============================================================================

INSERT INTO role_permissions (role_id, permission_id, created_at)
SELECT r.id, p.id, NOW()
FROM roles r
CROSS JOIN permissions p
WHERE r.code = 'ministry_approver'
  AND p.name IN (
    -- All ministry validator permissions
    'service_requests.read',
    'service_requests.validate',
    'assignments.view_own',
    'workloads.view_own',
    'agents.view_own_profile',
    'agents.update_availability',
    'notifications.log.read',
    'workflow_documents.read',
    'funcionario.verificacion.read_all',

    -- Additional approver permissions
    'service_requests.reject',
    'service_requests.assign',
    'assignments.view_team',
    'assignments.reassign',
    'workloads.view_team',

    -- Funcionario verification (process)
    'funcionario.verificacion.process',

    -- Requests verification
    'requests.verify',
    'requests.reverify'
  )
ON CONFLICT (role_id, permission_id) DO NOTHING;

-- ============================================================================
-- 7. ASSIGN PERMISSIONS TO AUDITOR ROLE
-- ============================================================================

INSERT INTO role_permissions (role_id, permission_id, created_at)
SELECT r.id, p.id, NOW()
FROM roles r
CROSS JOIN permissions p
WHERE r.code = 'auditor'
  AND p.name IN (
    -- Read-only service requests
    'service_requests.read',
    'service_requests.all',

    -- Read-only declarations
    'declarations.view_assigned',
    'declarations.view_ministry',

    -- Audit permissions
    'treasury.audit.view',
    'treasury.stats.view',
    'notifications.log.read',
    'notifications.log.export',
    'notifications.stats.read',

    -- Treasury view (no modify)
    'treasury.payments.view',
    'treasury.banks.view',
    'treasury.payment_methods.view',
    'treasury.anomalies.view',
    'treasury.exports.view',
    'treasury.exports.download',

    -- Verified identifiers (audit)
    'verified_identifiers.read',
    'verified_identifiers.audit',
    'verified_identifiers.stats',

    -- Basic profile access
    'agents.view_own_profile'
  )
ON CONFLICT (role_id, permission_id) DO NOTHING;

-- ============================================================================
-- 8. ASSIGN PERMISSIONS TO SUPERVISOR AGENT ROLE
-- ============================================================================

INSERT INTO role_permissions (role_id, permission_id, created_at)
SELECT r.id, p.id, NOW()
FROM roles r
CROSS JOIN permissions p
WHERE r.code = 'supervisor_agent'
  AND p.name IN (
    -- All service request permissions
    'service_requests.read',
    'service_requests.update',
    'service_requests.assign',
    'service_requests.validate',
    'service_requests.reject',
    'service_requests.all',

    -- All declaration permissions
    'declarations.view_assigned',
    'declarations.view_ministry',
    'declarations.validate',
    'declarations.approve',
    'declarations.reject',
    'declarations.escalate',
    'declarations.request_documents',

    -- Full assignment permissions
    'assignments.view_own',
    'assignments.view_team',
    'assignments.reassign',

    -- Full workload permissions
    'workloads.view_own',
    'workloads.view_team',
    'workloads.manage',

    -- Profile management
    'agents.view_own_profile',
    'agents.update_availability',

    -- Notifications
    'notifications.log.read',
    'notifications.log.export',
    'notifications.stats.read',

    -- Treasury
    'treasury.payments.view',
    'treasury.payments.lock',
    'treasury.payments.validate',
    'treasury.payments.reject',
    'treasury.audit.view',
    'treasury.stats.view',
    'treasury.anomalies.view',

    -- Workflow
    'workflow_documents.read',

    -- Funcionario
    'funcionario.verificacion.read_all',
    'funcionario.verificacion.process',

    -- Verification
    'requests.verify',
    'requests.reverify',
    'verified_identifiers.read',
    'verified_identifiers.search'
  )
ON CONFLICT (role_id, permission_id) DO NOTHING;

-- ============================================================================
-- 9. CREATE VIEW FOR AGENT RBAC ROLE SELECTION
-- ============================================================================

CREATE OR REPLACE VIEW vw_agent_rbac_roles AS
SELECT
    r.id,
    r.code,
    r.name,
    r.description,
    r.entity_type,
    COUNT(rp.permission_id) as permission_count,
    ARRAY_AGG(p.name ORDER BY p.name) FILTER (WHERE p.name IS NOT NULL) as permissions
FROM roles r
LEFT JOIN role_permissions rp ON r.id = rp.role_id
LEFT JOIN permissions p ON rp.permission_id = p.id
WHERE r.entity_type = 'agent'
  AND r.is_system = TRUE
GROUP BY r.id, r.code, r.name, r.description, r.entity_type
ORDER BY r.name;

COMMENT ON VIEW vw_agent_rbac_roles IS 'View of predefined RBAC roles available for agent assignment';

-- ============================================================================
-- 10. VERIFICATION
-- ============================================================================

SELECT
    'Agent RBAC roles created' AS status,
    COUNT(*) AS role_count
FROM roles
WHERE entity_type = 'agent' AND is_system = TRUE;

SELECT
    r.code,
    r.name,
    COUNT(rp.permission_id) as permission_count
FROM roles r
LEFT JOIN role_permissions rp ON r.id = rp.role_id
WHERE r.entity_type = 'agent'
GROUP BY r.code, r.name
ORDER BY r.name;

-- ============================================================================
-- END OF MIGRATION 055
-- ============================================================================
