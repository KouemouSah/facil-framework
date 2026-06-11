-- Migration 075: Assign agent.view_performance permission to agent roles
-- Purpose: Allow agents to view their personal statistics on /dashboard/agent/stats
-- Date: 2026-01-25

-- This migration completes Phase 3c of Dynamic Menu Dashboard Implementation:
-- Agent Stats page requires the agent.view_performance permission

BEGIN;

-- Assign permission to all agent roles
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM roles r
CROSS JOIN permissions p
WHERE r.code IN (
    'agent_cnedoge_pasaporte',
    'agent_cnedoge_residencia',
    'agent_dgt',
    'agent_ofive',
    'agent_onrc',
    'agent_tesoro'
)
AND p.name = 'agent.view_performance'
ON CONFLICT (role_id, permission_id) DO NOTHING;

-- Also assign to admin role for supervision
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM roles r
CROSS JOIN permissions p
WHERE r.code = 'admin'
AND p.name = 'agent.view_performance'
ON CONFLICT (role_id, permission_id) DO NOTHING;

COMMIT;
