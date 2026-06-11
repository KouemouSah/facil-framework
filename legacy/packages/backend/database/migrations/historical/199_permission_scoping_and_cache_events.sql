-- Migration 199: Permission scoping (JSONB) + NOTIFY for cache invalidation
-- Part of RBAC Engine Core — Phase 1.4
-- Date: 2026-03-10

-- =============================================================================
-- PHASE 1.4: Permission Scoping (scope JSONB on role_permissions)
-- =============================================================================

-- Add scope column: NULL = global (no restriction), JSONB = scoped
-- Examples:
--   NULL → permission applies everywhere
--   {"entity_code": "CNEDOGE"} → only for CNEDOGE entity
--   {"entity_codes": ["CNEDOGE", "DGT"]} → for CNEDOGE or DGT
ALTER TABLE role_permissions ADD COLUMN IF NOT EXISTS scope JSONB DEFAULT NULL;

-- Add scope to user_permissions too (for user-level scoped overrides)
ALTER TABLE user_permissions ADD COLUMN IF NOT EXISTS scope JSONB DEFAULT NULL;

-- GIN index for scope queries (containment @> operator)
CREATE INDEX IF NOT EXISTS idx_role_permissions_scope ON role_permissions USING GIN (scope) WHERE scope IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_user_permissions_scope ON user_permissions USING GIN (scope) WHERE scope IS NOT NULL;

-- =============================================================================
-- CACHE INVALIDATION VIA NOTIFY (real-time, no polling)
-- =============================================================================

-- Trigger function: emit NOTIFY on RBAC changes for instant cache invalidation
-- Listeners (Python asyncpg) receive these and purge Redis immediately
CREATE OR REPLACE FUNCTION notify_rbac_change()
RETURNS TRIGGER AS $$
DECLARE
    payload TEXT;
BEGIN
    IF TG_TABLE_NAME = 'role_permissions' THEN
        -- Role permission changed → invalidate all users with that role
        payload := json_build_object(
            'table', TG_TABLE_NAME,
            'op', TG_OP,
            'role_id', COALESCE(NEW.role_id, OLD.role_id)
        )::text;
    ELSIF TG_TABLE_NAME = 'user_permissions' THEN
        -- User permission changed → invalidate that user
        payload := json_build_object(
            'table', TG_TABLE_NAME,
            'op', TG_OP,
            'user_id', COALESCE(NEW.user_id, OLD.user_id)
        )::text;
    ELSIF TG_TABLE_NAME = 'roles' THEN
        -- Role changed → invalidate users with that role
        payload := json_build_object(
            'table', TG_TABLE_NAME,
            'op', TG_OP,
            'role_id', COALESCE(NEW.id, OLD.id)
        )::text;
    ELSIF TG_TABLE_NAME = 'users' THEN
        -- User role_id changed → invalidate that user
        IF TG_OP = 'UPDATE' AND OLD.role_id IS DISTINCT FROM NEW.role_id THEN
            payload := json_build_object(
                'table', TG_TABLE_NAME,
                'op', 'ROLE_CHANGE',
                'user_id', NEW.id,
                'old_role_id', OLD.role_id,
                'new_role_id', NEW.role_id
            )::text;
        ELSE
            RETURN COALESCE(NEW, OLD);
        END IF;
    END IF;

    -- NOTIFY channel 'rbac_changes' with JSON payload
    PERFORM pg_notify('rbac_changes', payload);

    RETURN COALESCE(NEW, OLD);
END;
$$ LANGUAGE plpgsql;

-- Drop existing NOTIFY triggers if any (idempotent)
DROP TRIGGER IF EXISTS trg_notify_role_permissions ON role_permissions;
DROP TRIGGER IF EXISTS trg_notify_user_permissions ON user_permissions;
DROP TRIGGER IF EXISTS trg_notify_roles ON roles;
DROP TRIGGER IF EXISTS trg_notify_users_role_change ON users;

-- Create NOTIFY triggers
CREATE TRIGGER trg_notify_role_permissions
    AFTER INSERT OR UPDATE OR DELETE ON role_permissions
    FOR EACH ROW EXECUTE FUNCTION notify_rbac_change();

CREATE TRIGGER trg_notify_user_permissions
    AFTER INSERT OR UPDATE OR DELETE ON user_permissions
    FOR EACH ROW EXECUTE FUNCTION notify_rbac_change();

CREATE TRIGGER trg_notify_roles
    AFTER UPDATE ON roles
    FOR EACH ROW EXECUTE FUNCTION notify_rbac_change();

CREATE TRIGGER trg_notify_users_role_change
    AFTER UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION notify_rbac_change();
