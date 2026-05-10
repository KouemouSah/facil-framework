-- Migration 285: Fix audit trigger FK violation + branding TaxasGE → Facil
-- Date: 2026-04-01
--
-- Problem 1: audit_user_permissions_change() trigger used
--   current_setting('app.current_user_id') which defaults to UUID(0) when not set,
--   causing FK violation on audit_logs.user_id (UUID(0) not in users table).
-- Fix: Use NEW.user_id (the affected user) instead of session setting.
--
-- Problem 2: SMTP_FROM_NAME default was "TaxasGE Platform" instead of "Facil"
-- Fix: Changed in config.py (no SQL needed)

-- Fix audit trigger
CREATE OR REPLACE FUNCTION audit_user_permissions_change()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        INSERT INTO audit_logs (
            user_id, action, entity_type, entity_id,
            new_values, ip_address, created_at
        ) VALUES (
            NEW.user_id,
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
            OLD.user_id,
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
            NEW.user_id,
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
