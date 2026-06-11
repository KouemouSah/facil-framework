-- Migration 195: Agent Trade Presets
-- Phase 7 of GESTION_ACCES_PROFESSIONAL_REDESIGN
-- Creates missing agent/supervisor roles for ITV, MINFP, EXTRANJERIA, POLICIA

BEGIN;

-- ============================================================================
-- 1. Create missing roles
-- ============================================================================

INSERT INTO roles (code, name, description, is_system, entity_type)
VALUES
  -- ITV
  ('agent_itv', 'Agent ITV', 'Agent inspection technique véhicules', false, 'agent'),
  ('supervisor_itv', 'Supervisor ITV', 'Supervisor inspection technique véhicules', false, 'entity_agent'),
  -- MINFP
  ('agent_minfp', 'Agent MINFP', 'Agent Ministerio de Función Pública', false, 'agent'),
  ('supervisor_minfp', 'Supervisor MINFP', 'Supervisor Ministerio de Función Pública', false, 'entity_agent'),
  -- Missing supervisors
  ('supervisor_extranjeria', 'Supervisor Extranjería', 'Supervisor Comisaría Dept Extranjería', false, 'entity_agent'),
  ('supervisor_policia', 'Supervisor Policía', 'Supervisor Comisaría Dept Visado', false, 'entity_agent')
ON CONFLICT (code) DO UPDATE SET
  name = EXCLUDED.name,
  description = EXCLUDED.description;

-- ============================================================================
-- 2. Grant agent base permissions (same 24 as existing agents)
-- Copy from agent_cnedoge_pasaporte as reference
-- ============================================================================

-- agent_itv
INSERT INTO role_permissions (role_id, permission_id)
SELECT r_new.id, rp.permission_id
FROM roles r_new
CROSS JOIN (
  SELECT rp2.permission_id
  FROM role_permissions rp2
  JOIN roles r_ref ON r_ref.id = rp2.role_id
  WHERE r_ref.code = 'agent_cnedoge_pasaporte'
) rp
WHERE r_new.code = 'agent_itv'
ON CONFLICT (role_id, permission_id) DO NOTHING;

-- agent_minfp
INSERT INTO role_permissions (role_id, permission_id)
SELECT r_new.id, rp.permission_id
FROM roles r_new
CROSS JOIN (
  SELECT rp2.permission_id
  FROM role_permissions rp2
  JOIN roles r_ref ON r_ref.id = rp2.role_id
  WHERE r_ref.code = 'agent_cnedoge_pasaporte'
) rp
WHERE r_new.code = 'agent_minfp'
ON CONFLICT (role_id, permission_id) DO NOTHING;

-- ============================================================================
-- 3. Grant supervisor base permissions (same 21 as existing supervisors)
-- Copy from supervisor_cnedoge_pasaporte as reference
-- ============================================================================

-- supervisor_itv
INSERT INTO role_permissions (role_id, permission_id)
SELECT r_new.id, rp.permission_id
FROM roles r_new
CROSS JOIN (
  SELECT rp2.permission_id
  FROM role_permissions rp2
  JOIN roles r_ref ON r_ref.id = rp2.role_id
  WHERE r_ref.code = 'supervisor_cnedoge_pasaporte'
) rp
WHERE r_new.code = 'supervisor_itv'
ON CONFLICT (role_id, permission_id) DO NOTHING;

-- supervisor_minfp
INSERT INTO role_permissions (role_id, permission_id)
SELECT r_new.id, rp.permission_id
FROM roles r_new
CROSS JOIN (
  SELECT rp2.permission_id
  FROM role_permissions rp2
  JOIN roles r_ref ON r_ref.id = rp2.role_id
  WHERE r_ref.code = 'supervisor_cnedoge_pasaporte'
) rp
WHERE r_new.code = 'supervisor_minfp'
ON CONFLICT (role_id, permission_id) DO NOTHING;

-- supervisor_extranjeria
INSERT INTO role_permissions (role_id, permission_id)
SELECT r_new.id, rp.permission_id
FROM roles r_new
CROSS JOIN (
  SELECT rp2.permission_id
  FROM role_permissions rp2
  JOIN roles r_ref ON r_ref.id = rp2.role_id
  WHERE r_ref.code = 'supervisor_cnedoge_pasaporte'
) rp
WHERE r_new.code = 'supervisor_extranjeria'
ON CONFLICT (role_id, permission_id) DO NOTHING;

-- supervisor_policia
INSERT INTO role_permissions (role_id, permission_id)
SELECT r_new.id, rp.permission_id
FROM roles r_new
CROSS JOIN (
  SELECT rp2.permission_id
  FROM role_permissions rp2
  JOIN roles r_ref ON r_ref.id = rp2.role_id
  WHERE r_ref.code = 'supervisor_cnedoge_pasaporte'
) rp
WHERE r_new.code = 'supervisor_policia'
ON CONFLICT (role_id, permission_id) DO NOTHING;

-- ============================================================================
-- 4. Remove appointment-related perms from agents that DON'T handle appointments
-- ITV, MINFP (except carnet_funcionario), ONRC don't use appointments
-- ============================================================================

-- Remove appointment perms from agent_itv (ITV = inspection only, no appointments)
DELETE FROM role_permissions
WHERE role_id = (SELECT id FROM roles WHERE code = 'agent_itv')
  AND permission_id IN (
    SELECT id FROM permissions WHERE name IN (
      'service_request.schedule_appointment',
      'service_request.cancel_appointment',
      'service_request.reschedule_appointment',
      'service_request.view_appointments',
      'service_request.view_available_slots'
    )
  );

-- Remove appointment perms from agent_onrc (contracts don't need appointments)
DELETE FROM role_permissions
WHERE role_id = (SELECT id FROM roles WHERE code = 'agent_onrc')
  AND permission_id IN (
    SELECT id FROM permissions WHERE name IN (
      'service_request.schedule_appointment',
      'service_request.cancel_appointment',
      'service_request.reschedule_appointment',
      'service_request.view_appointments',
      'service_request.view_available_slots'
    )
  );

COMMIT;
