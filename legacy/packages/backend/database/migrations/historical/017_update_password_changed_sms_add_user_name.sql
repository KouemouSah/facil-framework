-- Migration: Update Password Changed SMS Template - Add user_name variable
-- Date: 2025-12-20
-- Description: Add user_name variable to SMS template for consistency with email template

-- =============================================================================
-- UPDATE SMS TEMPLATE - Add user_name variable
-- =============================================================================

UPDATE sms_templates
SET
    content_es = 'TaxasGE SEGURIDAD: Hola {{user_name}}, tu contrasena fue cambiada el {{date}} a las {{time}}. Si no fuiste tu, contacta soporte: +240222000000',
    content_fr = 'TaxasGE SECURITE: Bonjour {{user_name}}, votre mot de passe a ete modifie le {{date}} a {{time}}. Si ce n''etait pas vous, contactez le support: +240222000000',
    content_en = 'TaxasGE SECURITY: Hi {{user_name}}, your password was changed on {{date}} at {{time}}. If this wasn''t you, contact support: +240222000000',
    variables = '["user_name", "date", "time"]'::jsonb,
    updated_at = NOW()
WHERE template_code = 'SECURITY_PASSWORD_CHANGED';
