-- Migration: Seed SMS Templates for Infobip Integration
-- Date: 2025-12-19
-- Description: Create default SMS templates by category

-- =============================================================================
-- SMS TEMPLATES - Authentication Category
-- =============================================================================

INSERT INTO sms_templates (
    template_code, name_es, name_fr, name_en,
    content_es, content_fr, content_en,
    category, max_segments, variables, is_active
) VALUES
-- OTP Login
(
    'OTP_LOGIN',
    'Codigo OTP de Inicio de Sesion',
    'Code OTP de Connexion',
    'Login OTP Code',
    'TaxasGE: Tu codigo de verificacion es {{code}}. Valido por {{expiry}} minutos. No lo compartas.',
    'TaxasGE: Votre code de verification est {{code}}. Valide pendant {{expiry}} minutes. Ne le partagez pas.',
    'TaxasGE: Your verification code is {{code}}. Valid for {{expiry}} minutes. Do not share it.',
    'auth',
    1,
    '["code", "expiry"]'::jsonb,
    true
),
-- Password Reset
(
    'PASSWORD_RESET',
    'Restablecimiento de Contrasena',
    'Reinitialisation du Mot de Passe',
    'Password Reset',
    'TaxasGE: Codigo para restablecer contrasena: {{code}}. Valido por {{expiry}} minutos.',
    'TaxasGE: Code pour reinitialiser le mot de passe: {{code}}. Valide pendant {{expiry}} minutes.',
    'TaxasGE: Password reset code: {{code}}. Valid for {{expiry}} minutes.',
    'auth',
    1,
    '["code", "expiry"]'::jsonb,
    true
),
-- 2FA Code
(
    '2FA_CODE',
    'Codigo 2FA',
    'Code 2FA',
    '2FA Code',
    'TaxasGE: Tu codigo de seguridad 2FA es {{code}}. No lo compartas con nadie.',
    'TaxasGE: Votre code de securite 2FA est {{code}}. Ne le partagez avec personne.',
    'TaxasGE: Your 2FA security code is {{code}}. Do not share with anyone.',
    'auth',
    1,
    '["code"]'::jsonb,
    true
)
ON CONFLICT (template_code) DO NOTHING;

-- =============================================================================
-- SMS TEMPLATES - Payments Category
-- =============================================================================

INSERT INTO sms_templates (
    template_code, name_es, name_fr, name_en,
    content_es, content_fr, content_en,
    category, max_segments, variables, is_active
) VALUES
-- Payment Received
(
    'PAYMENT_RECEIVED',
    'Pago Recibido',
    'Paiement Recu',
    'Payment Received',
    'TaxasGE: Pago de {{amount}} XAF recibido. Ref: {{reference}}. Fecha: {{date}}. Gracias.',
    'TaxasGE: Paiement de {{amount}} XAF recu. Ref: {{reference}}. Date: {{date}}. Merci.',
    'TaxasGE: Payment of {{amount}} XAF received. Ref: {{reference}}. Date: {{date}}. Thank you.',
    'payments',
    1,
    '["amount", "reference", "date"]'::jsonb,
    true
),
-- Payment Reminder
(
    'PAYMENT_REMINDER',
    'Recordatorio de Pago',
    'Rappel de Paiement',
    'Payment Reminder',
    'TaxasGE: Recordatorio - Pago de {{amount}} XAF vence el {{due_date}}. Evite recargos.',
    'TaxasGE: Rappel - Paiement de {{amount}} XAF expire le {{due_date}}. Evitez les penalites.',
    'TaxasGE: Reminder - Payment of {{amount}} XAF due on {{due_date}}. Avoid late fees.',
    'payments',
    1,
    '["amount", "due_date"]'::jsonb,
    true
)
ON CONFLICT (template_code) DO NOTHING;

-- =============================================================================
-- SMS TEMPLATES - Declarations Category
-- =============================================================================

INSERT INTO sms_templates (
    template_code, name_es, name_fr, name_en,
    content_es, content_fr, content_en,
    category, max_segments, variables, is_active
) VALUES
-- Declaration Status
(
    'DECLARATION_STATUS',
    'Estado de Declaracion',
    'Statut de Declaration',
    'Declaration Status',
    'TaxasGE: Su declaracion {{reference}} ha sido {{status}}. Consulte detalles en taxasge.gq',
    'TaxasGE: Votre declaration {{reference}} a ete {{status}}. Consultez les details sur taxasge.gq',
    'TaxasGE: Your declaration {{reference}} has been {{status}}. Check details at taxasge.gq',
    'declarations',
    1,
    '["reference", "status"]'::jsonb,
    true
),
-- Declaration Reminder
(
    'DECLARATION_REMINDER',
    'Recordatorio de Declaracion',
    'Rappel de Declaration',
    'Declaration Reminder',
    'TaxasGE: Recordatorio - Declaracion {{type}} vence en {{days}} dias ({{due_date}}). Complete ahora.',
    'TaxasGE: Rappel - Declaration {{type}} expire dans {{days}} jours ({{due_date}}). Completez maintenant.',
    'TaxasGE: Reminder - {{type}} declaration due in {{days}} days ({{due_date}}). Complete now.',
    'declarations',
    1,
    '["type", "days", "due_date"]'::jsonb,
    true
)
ON CONFLICT (template_code) DO NOTHING;

-- =============================================================================
-- SMS TEMPLATES - Alerts Category
-- =============================================================================

INSERT INTO sms_templates (
    template_code, name_es, name_fr, name_en,
    content_es, content_fr, content_en,
    category, max_segments, variables, is_active
) VALUES
-- General Alert
(
    'GENERAL_ALERT',
    'Alerta General',
    'Alerte Generale',
    'General Alert',
    'TaxasGE: {{message}}',
    'TaxasGE: {{message}}',
    'TaxasGE: {{message}}',
    'alerts',
    2,
    '["message"]'::jsonb,
    true
),
-- Security Alert
(
    'SECURITY_ALERT',
    'Alerta de Seguridad',
    'Alerte de Securite',
    'Security Alert',
    'TaxasGE ALERTA: {{message}}. Si no fuiste tu, contacta soporte inmediatamente.',
    'TaxasGE ALERTE: {{message}}. Si ce n''etait pas vous, contactez le support immediatement.',
    'TaxasGE ALERT: {{message}}. If this wasn''t you, contact support immediately.',
    'alerts',
    2,
    '["message"]'::jsonb,
    true
),
-- Account Locked
(
    'ACCOUNT_LOCKED',
    'Cuenta Bloqueada',
    'Compte Bloque',
    'Account Locked',
    'TaxasGE: Tu cuenta ha sido bloqueada por {{reason}}. Sera desbloqueada en {{duration}}.',
    'TaxasGE: Votre compte a ete bloque pour {{reason}}. Il sera debloque dans {{duration}}.',
    'TaxasGE: Your account has been locked due to {{reason}}. It will be unlocked in {{duration}}.',
    'alerts',
    1,
    '["reason", "duration"]'::jsonb,
    true
)
ON CONFLICT (template_code) DO NOTHING;

-- =============================================================================
-- SMS TEMPLATES - Reminders Category
-- =============================================================================

INSERT INTO sms_templates (
    template_code, name_es, name_fr, name_en,
    content_es, content_fr, content_en,
    category, max_segments, variables, is_active
) VALUES
-- Appointment Reminder
(
    'APPOINTMENT_REMINDER',
    'Recordatorio de Cita',
    'Rappel de Rendez-vous',
    'Appointment Reminder',
    'TaxasGE: Recordatorio de cita para {{service}} el {{date}} a las {{time}} en {{location}}.',
    'TaxasGE: Rappel de rendez-vous pour {{service}} le {{date}} a {{time}} a {{location}}.',
    'TaxasGE: Appointment reminder for {{service}} on {{date}} at {{time}} at {{location}}.',
    'reminders',
    1,
    '["service", "date", "time", "location"]'::jsonb,
    true
)
ON CONFLICT (template_code) DO NOTHING;

-- Create index for faster lookups
CREATE INDEX IF NOT EXISTS idx_sms_templates_category ON sms_templates(category);
CREATE INDEX IF NOT EXISTS idx_sms_templates_is_active ON sms_templates(is_active);
