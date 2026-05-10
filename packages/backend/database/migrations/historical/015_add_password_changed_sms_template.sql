-- Migration: Add Password Changed SMS and Email Templates
-- Date: 2025-12-20
-- Description: Add templates for password change security notifications (SMS + Email)

-- =============================================================================
-- SMS TEMPLATE - Security: Password Changed
-- =============================================================================

INSERT INTO sms_templates (
    template_code, name_es, name_fr, name_en,
    content_es, content_fr, content_en,
    category, max_segments, variables, is_active
) VALUES
(
    'SECURITY_PASSWORD_CHANGED',
    'Contraseña Modificada',
    'Mot de Passe Modifié',
    'Password Changed',
    'TaxasGE SEGURIDAD: Tu contraseña fue cambiada el {{date}} a las {{time}}. Si no fuiste tu, contacta soporte: +240222000000',
    'TaxasGE SECURITE: Votre mot de passe a ete modifie le {{date}} a {{time}}. Si ce n''etait pas vous, contactez le support: +240222000000',
    'TaxasGE SECURITY: Your password was changed on {{date}} at {{time}}. If this wasn''t you, contact support: +240222000000',
    'alerts',
    1,
    '["date", "time"]'::jsonb,
    true
)
ON CONFLICT (template_code) DO UPDATE SET
    content_es = EXCLUDED.content_es,
    content_fr = EXCLUDED.content_fr,
    content_en = EXCLUDED.content_en,
    updated_at = NOW();

-- =============================================================================
-- EMAIL TEMPLATE - Security: Password Changed (html_content stored directly)
-- =============================================================================

INSERT INTO email_templates (
    template_code,
    name_es, name_fr, name_en,
    subject_es, subject_fr, subject_en,
    description_es, description_fr, description_en,
    html_content,
    variables,
    category,
    is_active
) VALUES
(
    'SECURITY_PASSWORD_CHANGED',
    'Alerta de Seguridad - Contraseña Modificada',
    'Alerte de Sécurité - Mot de Passe Modifié',
    'Security Alert - Password Changed',
    'TaxasGE - Alerta de Seguridad: Tu contraseña fue modificada',
    'TaxasGE - Alerte de Sécurité: Votre mot de passe a été modifié',
    'TaxasGE - Security Alert: Your password was changed',
    'Notificación enviada cuando el usuario cambia su contraseña',
    'Notification envoyée lorsque l''utilisateur change son mot de passe',
    'Notification sent when the user changes their password',
    '<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Alerta de Seguridad - TaxasGE</title>
    <style>
        body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px; background-color: #f5f5f5; }
        .container { background-color: #ffffff; border-radius: 8px; padding: 30px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        .header { text-align: center; border-bottom: 3px solid #dc2626; padding-bottom: 20px; margin-bottom: 20px; }
        .header h1 { color: #dc2626; margin: 0; font-size: 24px; }
        .alert-icon { font-size: 48px; margin-bottom: 10px; }
        .info-box { background-color: #fef2f2; border-left: 4px solid #dc2626; padding: 15px; margin: 20px 0; border-radius: 0 4px 4px 0; }
        .warning-box { background-color: #fffbeb; border: 1px solid #f59e0b; border-radius: 4px; padding: 15px; margin: 20px 0; }
        .footer { text-align: center; color: #666; font-size: 12px; margin-top: 30px; padding-top: 20px; border-top: 1px solid #eee; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div class="alert-icon">🔐</div>
            <h1>Alerta de Seguridad</h1>
        </div>
        <div class="content">
            <p>Hola <strong>{{user_name}}</strong>,</p>
            <p>Te informamos que tu contraseña de TaxasGE ha sido modificada.</p>
            <div class="info-box">
                <p><strong>Fecha:</strong> {{date}}</p>
                <p><strong>Hora:</strong> {{time}} UTC</p>
            </div>
            <div class="warning-box">
                <p><strong>⚠️ ¿No fuiste tú?</strong> Si no realizaste este cambio, tu cuenta puede estar comprometida. Contacta a nuestro soporte inmediatamente.</p>
            </div>
        </div>
        <div class="footer">
            <p><strong>TaxasGE Platform</strong></p>
            <p>Servicios Fiscales Electrónicos - Guinea Ecuatorial</p>
            <p>Este es un mensaje automático, por favor no responda.</p>
        </div>
    </div>
</body>
</html>',
    '[
        {"name": "user_name", "description": "Nombre del usuario", "example": "John Doe", "required": true},
        {"name": "date", "description": "Fecha del cambio", "example": "20/12/2025", "required": true},
        {"name": "time", "description": "Hora del cambio", "example": "15:30", "required": true}
    ]'::jsonb,
    'security',
    true
)
ON CONFLICT (template_code) DO UPDATE SET
    name_es = EXCLUDED.name_es,
    name_fr = EXCLUDED.name_fr,
    name_en = EXCLUDED.name_en,
    subject_es = EXCLUDED.subject_es,
    subject_fr = EXCLUDED.subject_fr,
    subject_en = EXCLUDED.subject_en,
    html_content = EXCLUDED.html_content,
    variables = EXCLUDED.variables,
    updated_at = NOW();
