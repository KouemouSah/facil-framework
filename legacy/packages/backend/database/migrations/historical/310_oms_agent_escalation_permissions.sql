-- Migration 310: Grant escalation permissions to OMS agents
--
-- OMS agents need service_request.escalate to escalate bundle SRs
-- and agent.view_escalations to see their own escalations.
-- Without these, the "Escalader" button would 403.

BEGIN;

INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM roles r
CROSS JOIN permissions p
WHERE r.code IN (
    'agent_ayuntamiento', 'agent_camara',
    'agent_min_comercio', 'agent_min_hacienda', 'agent_min_informacion',
    'agent_min_turismo', 'agent_min_agricultura', 'agent_min_electricidad',
    'agent_oms_polyvalent'
)
AND p.name IN ('service_request.escalate', 'agent.view_escalations')
ON CONFLICT DO NOTHING;

-- Supervisors need queue.escalate (handle escalations in their queue)
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM roles r
CROSS JOIN permissions p
WHERE r.code IN (
    'supervisor_ayuntamiento', 'supervisor_camara',
    'supervisor_min_comercio', 'supervisor_min_hacienda', 'supervisor_min_informacion',
    'supervisor_min_turismo', 'supervisor_min_agricultura', 'supervisor_min_electricidad'
)
AND p.name IN ('queue.escalate', 'agent.view_escalations', 'service_request.escalate')
ON CONFLICT DO NOTHING;

COMMIT;
