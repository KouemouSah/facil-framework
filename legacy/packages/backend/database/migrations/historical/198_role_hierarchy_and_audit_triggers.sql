-- Migration 198: Role hierarchy + RBAC audit triggers
-- Part of RBAC Engine Core — Phase 1.1 + 1.3
-- Date: 2026-03-10

-- =============================================================================
-- PHASE 1.1: Role Hierarchy (parent_role_id)
-- =============================================================================

-- Add parent_role_id column for role inheritance
ALTER TABLE roles ADD COLUMN IF NOT EXISTS parent_role_id UUID REFERENCES roles(id);

-- Create index for hierarchy queries
CREATE INDEX IF NOT EXISTS idx_roles_parent_role_id ON roles(parent_role_id) WHERE parent_role_id IS NOT NULL;

-- Set up hierarchy: admin sub-roles inherit from admin
UPDATE roles SET parent_role_id = (SELECT id FROM roles WHERE code = 'admin')
WHERE code IN ('admin_agents', 'admin_config', 'admin_security', 'admin_services', 'admin_support')
AND parent_role_id IS NULL;

-- Supervisor roles inherit from their agent counterparts
-- supervisor_tesoro inherits from agent_tesoro, etc.
DO $$
DECLARE
    sup_record RECORD;
    agent_id UUID;
BEGIN
    FOR sup_record IN
        SELECT id, code FROM roles WHERE code LIKE 'supervisor_%'
    LOOP
        -- Map supervisor_X → agent_X
        SELECT id INTO agent_id FROM roles
        WHERE code = REPLACE(sup_record.code, 'supervisor_', 'agent_');

        IF agent_id IS NOT NULL THEN
            UPDATE roles SET parent_role_id = agent_id
            WHERE id = sup_record.id AND parent_role_id IS NULL;
        END IF;
    END LOOP;
END $$;

-- =============================================================================
-- PHASE 1.3: RBAC Audit Triggers (automatic audit trail)
-- =============================================================================

-- Trigger function for role_permissions changes
CREATE OR REPLACE FUNCTION audit_role_permissions_change()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        INSERT INTO audit_logs (
            user_id, action, entity_type, entity_id,
            new_values, ip_address, created_at
        ) VALUES (
            COALESCE(current_setting('app.current_user_id', true)::uuid, '00000000-0000-0000-0000-000000000000'::uuid),
            'PERMISSION_GRANTED',
            'role_permission',
            NEW.role_id::text,
            jsonb_build_object(
                'role_id', NEW.role_id,
                'permission_id', NEW.permission_id,
                'granted', NEW.granted
            ),
            COALESCE(current_setting('app.client_ip', true)::inet, '0.0.0.0'::inet),
            NOW()
        );
        RETURN NEW;
    ELSIF TG_OP = 'DELETE' THEN
        INSERT INTO audit_logs (
            user_id, action, entity_type, entity_id,
            old_values, ip_address, created_at
        ) VALUES (
            COALESCE(current_setting('app.current_user_id', true)::uuid, '00000000-0000-0000-0000-000000000000'::uuid),
            'PERMISSION_REVOKED',
            'role_permission',
            OLD.role_id::text,
            jsonb_build_object(
                'role_id', OLD.role_id,
                'permission_id', OLD.permission_id,
                'granted', OLD.granted
            ),
            COALESCE(current_setting('app.client_ip', true)::inet, '0.0.0.0'::inet),
            NOW()
        );
        RETURN OLD;
    END IF;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

-- Trigger function for user_permissions changes
CREATE OR REPLACE FUNCTION audit_user_permissions_change()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        INSERT INTO audit_logs (
            user_id, action, entity_type, entity_id,
            new_values, ip_address, created_at
        ) VALUES (
            COALESCE(current_setting('app.current_user_id', true)::uuid, '00000000-0000-0000-0000-000000000000'::uuid),
            CASE WHEN NEW.granted THEN 'USER_PERMISSION_GRANTED' ELSE 'USER_PERMISSION_DENIED' END,
            'user_permission',
            NEW.user_id::text,
            jsonb_build_object(
                'user_id', NEW.user_id,
                'permission_id', NEW.permission_id,
                'granted', NEW.granted,
                'expires_at', NEW.expires_at,
                'reason', NEW.reason
            ),
            COALESCE(current_setting('app.client_ip', true)::inet, '0.0.0.0'::inet),
            NOW()
        );
        RETURN NEW;
    ELSIF TG_OP = 'DELETE' THEN
        INSERT INTO audit_logs (
            user_id, action, entity_type, entity_id,
            old_values, ip_address, created_at
        ) VALUES (
            COALESCE(current_setting('app.current_user_id', true)::uuid, '00000000-0000-0000-0000-000000000000'::uuid),
            'USER_PERMISSION_REVOKED',
            'user_permission',
            OLD.user_id::text,
            jsonb_build_object(
                'user_id', OLD.user_id,
                'permission_id', OLD.permission_id,
                'granted', OLD.granted
            ),
            COALESCE(current_setting('app.client_ip', true)::inet, '0.0.0.0'::inet),
            NOW()
        );
        RETURN OLD;
    ELSIF TG_OP = 'UPDATE' THEN
        INSERT INTO audit_logs (
            user_id, action, entity_type, entity_id,
            old_values, new_values, ip_address, created_at
        ) VALUES (
            COALESCE(current_setting('app.current_user_id', true)::uuid, '00000000-0000-0000-0000-000000000000'::uuid),
            'USER_PERMISSION_UPDATED',
            'user_permission',
            NEW.user_id::text,
            jsonb_build_object('granted', OLD.granted, 'expires_at', OLD.expires_at),
            jsonb_build_object('granted', NEW.granted, 'expires_at', NEW.expires_at),
            COALESCE(current_setting('app.client_ip', true)::inet, '0.0.0.0'::inet),
            NOW()
        );
        RETURN NEW;
    END IF;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

-- Trigger function for roles changes
CREATE OR REPLACE FUNCTION audit_roles_change()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'UPDATE' THEN
        -- Only audit meaningful changes (not menu_config updates which are frequent)
        IF OLD.name != NEW.name OR OLD.code != NEW.code OR OLD.entity_type IS DISTINCT FROM NEW.entity_type
           OR OLD.parent_role_id IS DISTINCT FROM NEW.parent_role_id THEN
            INSERT INTO audit_logs (
                user_id, action, entity_type, entity_id,
                old_values, new_values, ip_address, created_at
            ) VALUES (
                COALESCE(current_setting('app.current_user_id', true)::uuid, '00000000-0000-0000-0000-000000000000'::uuid),
                'ROLE_UPDATED',
                'role',
                NEW.id,
                jsonb_build_object('name', OLD.name, 'code', OLD.code, 'entity_type', OLD.entity_type, 'parent_role_id', OLD.parent_role_id),
                jsonb_build_object('name', NEW.name, 'code', NEW.code, 'entity_type', NEW.entity_type, 'parent_role_id', NEW.parent_role_id),
                COALESCE(current_setting('app.client_ip', true)::inet, '0.0.0.0'::inet),
                NOW()
            );
        END IF;
        RETURN NEW;
    ELSIF TG_OP = 'INSERT' THEN
        INSERT INTO audit_logs (
            user_id, action, entity_type, entity_id,
            new_values, ip_address, created_at
        ) VALUES (
            COALESCE(current_setting('app.current_user_id', true)::uuid, '00000000-0000-0000-0000-000000000000'::uuid),
            'ROLE_CREATED',
            'role',
            NEW.id::text,
            jsonb_build_object('name', NEW.name, 'code', NEW.code, 'entity_type', NEW.entity_type),
            COALESCE(current_setting('app.client_ip', true)::inet, '0.0.0.0'::inet),
            NOW()
        );
        RETURN NEW;
    ELSIF TG_OP = 'DELETE' THEN
        INSERT INTO audit_logs (
            user_id, action, entity_type, entity_id,
            old_values, ip_address, created_at
        ) VALUES (
            COALESCE(current_setting('app.current_user_id', true)::uuid, '00000000-0000-0000-0000-000000000000'::uuid),
            'ROLE_DELETED',
            'role',
            OLD.id::text,
            jsonb_build_object('name', OLD.name, 'code', OLD.code),
            COALESCE(current_setting('app.client_ip', true)::inet, '0.0.0.0'::inet),
            NOW()
        );
        RETURN OLD;
    END IF;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

-- Drop existing triggers if any (idempotent)
DROP TRIGGER IF EXISTS trg_audit_role_permissions ON role_permissions;
DROP TRIGGER IF EXISTS trg_audit_user_permissions ON user_permissions;
DROP TRIGGER IF EXISTS trg_audit_roles ON roles;

-- Create triggers
CREATE TRIGGER trg_audit_role_permissions
    AFTER INSERT OR DELETE ON role_permissions
    FOR EACH ROW EXECUTE FUNCTION audit_role_permissions_change();

CREATE TRIGGER trg_audit_user_permissions
    AFTER INSERT OR UPDATE OR DELETE ON user_permissions
    FOR EACH ROW EXECUTE FUNCTION audit_user_permissions_change();

CREATE TRIGGER trg_audit_roles
    AFTER INSERT OR UPDATE OR DELETE ON roles
    FOR EACH ROW EXECUTE FUNCTION audit_roles_change();
