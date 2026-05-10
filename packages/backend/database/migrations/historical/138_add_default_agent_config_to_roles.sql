-- Migration 138: Add default_agent_config to roles table
-- Purpose: Role-based defaults for agent profile creation.
-- When admin selects a role, capabilities auto-fill from this config.
-- Follows existing pattern: menu_config, dashboard_config, ui_config

ALTER TABLE roles
ADD COLUMN IF NOT EXISTS default_agent_config JSONB DEFAULT NULL;

COMMENT ON COLUMN roles.default_agent_config IS
'Default agent profile config when creating agents with this role.
Keys: is_supervisor, can_escalate, can_assign_tasks, can_reassign,
can_approve_unlimited, max_approval_amount, working_hours_start/end, working_days.
NULL = use system defaults.';

-- Populate for existing supervisor roles
UPDATE roles SET default_agent_config = jsonb_build_object(
    'is_supervisor', true,
    'can_escalate', true,
    'can_assign_tasks', true,
    'can_reassign', true,
    'can_approve_unlimited', false
) WHERE code LIKE 'supervisor_%'
  AND default_agent_config IS NULL;

-- Populate for existing agent (non-supervisor) roles
UPDATE roles SET default_agent_config = jsonb_build_object(
    'is_supervisor', false,
    'can_escalate', true,
    'can_assign_tasks', false,
    'can_reassign', false,
    'can_approve_unlimited', false
) WHERE (code LIKE 'agent_%' AND code NOT LIKE 'supervisor_%')
  AND default_agent_config IS NULL;
