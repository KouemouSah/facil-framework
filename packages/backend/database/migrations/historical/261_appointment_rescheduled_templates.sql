-- ============================================================================
-- Migration 079: Add APPOINTMENT_RESCHEDULED notification templates
-- ============================================================================
-- Purpose: Create notification templates for when appointments are rescheduled
--
-- Phase 5.5 of Dashboard Config + Appointments Management
--
-- Templates added:
--   - Email template: appointment_rescheduled
--   - SMS template: APPOINTMENT_RESCHEDULED
--   - Push template: appointment_rescheduled
--   - In-app notification template: appointment_rescheduled
--
-- Author: Claude Code
-- Date: 2026-01-26
-- ============================================================================

BEGIN;

-- =============================================================================
-- 1. EMAIL TEMPLATE
-- =============================================================================

INSERT INTO email_templates (
    template_code, name_es, name_fr, name_en,
    subject_es, subject_fr, subject_en,
    description_es, html_content, variables, category, is_active
)
VALUES (
    'appointment_rescheduled',
    'Cita reprogramada',
    'Rendez-vous reprogrammé',
    'Appointment rescheduled',
    'Su cita ha sido reprogramada - Facil',
    'Votre rendez-vous a été reprogrammé - Facil',
    'Your appointment has been rescheduled - Facil',
    'Notificación enviada cuando una cita es reprogramada por un agente',
    '<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Cita Reprogramada - Facil</title>
    <style>
        body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px; background-color: #f5f5f5; }
        .container { background-color: #ffffff; padding: 30px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        .header { text-align: center; margin-bottom: 30px; }
        .logo { max-width: 150px; }
        h1 { color: #1a1a1a; font-size: 24px; margin-bottom: 20px; }
        .highlight { background-color: #fff3cd; padding: 15px; border-radius: 6px; margin: 20px 0; border-left: 4px solid #ffc107; }
        .old-appointment { background-color: #f8d7da; padding: 15px; border-radius: 6px; margin: 20px 0; border-left: 4px solid #dc3545; text-decoration: line-through; }
        .new-appointment { background-color: #d4edda; padding: 15px; border-radius: 6px; margin: 20px 0; border-left: 4px solid #28a745; }
        .detail { display: flex; align-items: center; margin: 10px 0; }
        .detail-icon { width: 24px; height: 24px; margin-right: 10px; }
        .detail-text { font-size: 16px; }
        .footer { margin-top: 30px; text-align: center; color: #666; font-size: 12px; }
        .support { margin-top: 20px; padding: 15px; background-color: #f8f9fa; border-radius: 6px; text-align: center; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>⚠️ Cita Reprogramada</h1>
        </div>
        <p>Estimado/a {user_name},</p>
        <p>Le informamos que su cita ha sido <strong>reprogramada</strong>.</p>

        <div class="old-appointment">
            <h3>❌ Cita anterior (CANCELADA):</h3>
            <div class="detail">
                <span class="detail-text">📅 Fecha: {old_date}</span>
            </div>
            <div class="detail">
                <span class="detail-text">🕐 Hora: {old_time}</span>
            </div>
        </div>

        <div class="new-appointment">
            <h3>✅ Nueva cita:</h3>
            <div class="detail">
                <span class="detail-text">📅 Fecha: {new_date}</span>
            </div>
            <div class="detail">
                <span class="detail-text">🕐 Hora: {new_time}</span>
            </div>
            <div class="detail">
                <span class="detail-text">📍 Lugar: {location}</span>
            </div>
        </div>

        <div class="highlight">
            <p><strong>Importante:</strong> Por favor, presente se en la nueva fecha y hora indicada con todos los documentos requeridos.</p>
        </div>

        <div class="support">
            <p>Si tiene alguna pregunta, contacte nuestro servicio de atención al cliente.</p>
        </div>

        <div class="footer">
            <p>Este es un correo automático de Facil - Facil.</p>
            <p>© 2026 Ministerio de Hacienda, Guinea Ecuatorial</p>
        </div>
    </div>
</body>
</html>',
    '["user_name", "old_date", "old_time", "new_date", "new_time", "location"]'::jsonb,
    'appointment',
    true
) ON CONFLICT (template_code) DO UPDATE SET
    html_content = EXCLUDED.html_content,
    variables = EXCLUDED.variables,
    updated_at = NOW();

-- =============================================================================
-- 2. SMS TEMPLATE
-- =============================================================================

INSERT INTO sms_templates (
    template_code, name_es, name_fr, name_en,
    content_es, content_fr, content_en,
    variables, category, max_segments, is_active
)
VALUES (
    'APPOINTMENT_RESCHEDULED',
    'Cita reprogramada',
    'Rendez-vous reprogrammé',
    'Appointment rescheduled',
    'Facil: Su cita ha sido reprogramada. Nueva fecha: {{new_date}} a las {{new_time}} en {{location}}.',
    'Facil: Votre RDV a été reprogrammé. Nouvelle date: {{new_date}} à {{new_time}} à {{location}}.',
    'Facil: Your appointment has been rescheduled. New date: {{new_date}} at {{new_time}} at {{location}}.',
    '["new_date", "new_time", "location"]'::jsonb,
    'reminders',
    1,
    true
) ON CONFLICT (template_code) DO UPDATE SET
    content_es = EXCLUDED.content_es,
    content_fr = EXCLUDED.content_fr,
    content_en = EXCLUDED.content_en,
    updated_at = NOW();

-- =============================================================================
-- 3. PUSH NOTIFICATION TEMPLATE
-- =============================================================================

INSERT INTO push_templates (
    template_code, name_es, name_fr, name_en,
    title_es, title_fr, title_en,
    body_es, body_fr, body_en,
    icon_url, click_action, variables, platform, is_active
)
VALUES (
    'appointment_rescheduled',
    'Cita reprogramada',
    'Rendez-vous reprogrammé',
    'Appointment rescheduled',
    'Cita reprogramada',
    'Rendez-vous reprogrammé',
    'Appointment rescheduled',
    'Su cita ha sido reprogramada para el {new_date} a las {new_time}.',
    'Votre RDV a été reprogrammé pour le {new_date} à {new_time}.',
    'Your appointment has been rescheduled for {new_date} at {new_time}.',
    '/icons/calendar_reschedule.png',
    '/mis-citas',
    '["new_date", "new_time"]'::jsonb,
    'all',
    true
) ON CONFLICT (template_code) DO UPDATE SET
    body_es = EXCLUDED.body_es,
    body_fr = EXCLUDED.body_fr,
    body_en = EXCLUDED.body_en,
    updated_at = NOW();

-- =============================================================================
-- 4. IN-APP NOTIFICATION TEMPLATE
-- =============================================================================

INSERT INTO notification_templates (
    template_code, name_es, name_fr, name_en,
    title_es, title_fr, title_en,
    body_es, body_fr, body_en,
    icon, action_url, variables, notification_type, priority, is_active
)
VALUES (
    'appointment_rescheduled',
    'Cita reprogramada',
    'Rendez-vous reprogrammé',
    'Appointment rescheduled',
    'Cita reprogramada',
    'Rendez-vous reprogrammé',
    'Appointment rescheduled',
    'Su cita ha sido reprogramada para el {new_date} a las {new_time} en {location}.',
    'Votre rendez-vous a été reprogrammé pour le {new_date} à {new_time} à {location}.',
    'Your appointment has been rescheduled for {new_date} at {new_time} at {location}.',
    'calendar-x',
    '/mis-citas',
    '["new_date", "new_time", "location"]'::jsonb,
    'warning',
    'high',
    true
) ON CONFLICT (template_code) DO UPDATE SET
    body_es = EXCLUDED.body_es,
    body_fr = EXCLUDED.body_fr,
    body_en = EXCLUDED.body_en,
    updated_at = NOW();

COMMIT;

-- =============================================================================
-- VERIFICATION
-- =============================================================================

SELECT 'Migration 079 completed' AS status;

-- Check templates
SELECT 'Email' as type, template_code, name_es FROM email_templates WHERE template_code = 'appointment_rescheduled'
UNION ALL
SELECT 'SMS' as type, template_code, name_es FROM sms_templates WHERE template_code = 'APPOINTMENT_RESCHEDULED'
UNION ALL
SELECT 'Push' as type, template_code, name_es FROM push_templates WHERE template_code = 'appointment_rescheduled'
UNION ALL
SELECT 'In-app' as type, template_code, name_es FROM notification_templates WHERE template_code = 'appointment_rescheduled';

-- ============================================================================
-- END OF MIGRATION 079
-- ============================================================================
