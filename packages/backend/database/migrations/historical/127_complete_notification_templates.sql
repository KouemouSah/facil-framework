-- Migration 127: Complete notification templates
-- Date: 2026-02-24
-- Description:
--   1. Add 4 missing SMS templates (REQUEST_APPROVED, REQUEST_REJECTED, REQUEST_DOCUMENTS_REQUIRED, PAYMENT_ESCALATED)
--   2. Add payment_escalated email template (for supervisor escalation notifications)
--   3. Backfill html_content for email_templates that only have html_file_path
--      (required since notification_handler now reads html_content exclusively)

BEGIN;

-- =============================================================================
-- 1. MISSING SMS TEMPLATES
-- =============================================================================

-- Request Approved SMS
INSERT INTO sms_templates (template_code, name_es, name_fr, name_en, content_es, content_fr, content_en, variables, category, max_segments, is_active)
VALUES (
    'REQUEST_APPROVED',
    'Solicitud aprobada',
    'Demande approuvée',
    'Request approved',
    'Facil: Su solicitud {{reference}} ha sido aprobada. Consulte detalles en taxasge.gq',
    'Facil: Votre demande {{reference}} a été approuvée. Consultez les détails sur taxasge.gq',
    'Facil: Your request {{reference}} has been approved. Check details at taxasge.gq',
    '["reference"]'::jsonb,
    'requests',
    1,
    true
) ON CONFLICT (template_code) DO NOTHING;

-- Request Rejected SMS
INSERT INTO sms_templates (template_code, name_es, name_fr, name_en, content_es, content_fr, content_en, variables, category, max_segments, is_active)
VALUES (
    'REQUEST_REJECTED',
    'Solicitud rechazada',
    'Demande refusée',
    'Request rejected',
    'Facil: Su solicitud {{reference}} ha sido rechazada. Motivo: {{reason}}. Consulte taxasge.gq',
    'Facil: Votre demande {{reference}} a été refusée. Raison: {{reason}}. Consultez taxasge.gq',
    'Facil: Your request {{reference}} has been rejected. Reason: {{reason}}. Check taxasge.gq',
    '["reference", "reason"]'::jsonb,
    'requests',
    2,
    true
) ON CONFLICT (template_code) DO NOTHING;

-- Request Documents Required SMS
INSERT INTO sms_templates (template_code, name_es, name_fr, name_en, content_es, content_fr, content_en, variables, category, max_segments, is_active)
VALUES (
    'REQUEST_DOCUMENTS_REQUIRED',
    'Documentos requeridos',
    'Documents requis',
    'Documents required',
    'Facil: Se requieren documentos adicionales para su solicitud {{reference}}. Consulte taxasge.gq',
    'Facil: Des documents supplémentaires sont requis pour votre demande {{reference}}. Consultez taxasge.gq',
    'Facil: Additional documents are required for your request {{reference}}. Check taxasge.gq',
    '["reference"]'::jsonb,
    'requests',
    2,
    true
) ON CONFLICT (template_code) DO NOTHING;

-- Payment Escalated SMS (for supervisors)
INSERT INTO sms_templates (template_code, name_es, name_fr, name_en, content_es, content_fr, content_en, variables, category, max_segments, is_active)
VALUES (
    'PAYMENT_ESCALATED',
    'Pago escalado a supervisor',
    'Paiement escaladé au superviseur',
    'Payment escalated to supervisor',
    'Facil: Pago escalado por {{agent_name}}. Motivo: {{reason}}. Acción requerida.',
    'Facil: Paiement escaladé par {{agent_name}}. Raison: {{reason}}. Action requise.',
    'Facil: Payment escalated by {{agent_name}}. Reason: {{reason}}. Action required.',
    '["agent_name", "reason"]'::jsonb,
    'payments',
    1,
    true
) ON CONFLICT (template_code) DO NOTHING;

-- =============================================================================
-- 2. PAYMENT_ESCALATED EMAIL TEMPLATE (for supervisor notification)
-- =============================================================================

INSERT INTO email_templates (template_code, name_es, name_fr, name_en, subject_es, subject_fr, subject_en, description_es, variables, category, is_active, html_content)
VALUES (
    'payment_escalated',
    'Pago escalado',
    'Paiement escaladé',
    'Payment escalated',
    'Pago escalado - Acción requerida - Facil',
    'Paiement escaladé - Action requise - Facil',
    'Payment escalated - Action required - Facil',
    'Notificación al supervisor cuando un agente escala un pago',
    '["user_name", "agent_name", "reason", "payment_id", "escalation_level"]'::jsonb,
    'payment',
    true,
    '<!DOCTYPE html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"><style>body{margin:0;padding:0;font-family:-apple-system,BlinkMacSystemFont,''Segoe UI'',Roboto,''Helvetica Neue'',Arial,sans-serif;line-height:1.6;color:#333;background:#f5f5f5}.wrapper{padding:20px;background:#f5f5f5}.container{max-width:600px;margin:0 auto;background:#fff;border-radius:8px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,0.1)}.header{background:linear-gradient(135deg,#f59e0b 0%,#d97706 100%);padding:30px 20px;text-align:center}.header h1{color:#fff;margin:0;font-size:24px}.body{padding:30px}.info-box{background:#fffbeb;border:1px solid #fbbf24;border-radius:8px;padding:16px;margin:16px 0}.footer{background:#f9fafb;padding:20px;text-align:center;border-top:1px solid #e5e7eb;font-size:12px;color:#6b7280}</style></head><body><div class="wrapper"><div class="container"><div class="header"><h1>⚠️ Pago Escalado</h1></div><div class="body"><p>Estimado/a {{user_name}},</p><p>Un pago ha sido escalado y requiere su atención:</p><div class="info-box"><p><strong>Agente:</strong> {{agent_name}}</p><p><strong>Motivo:</strong> {{reason}}</p><p><strong>ID Pago:</strong> {{payment_id}}</p><p><strong>Nivel:</strong> {{escalation_level}}</p></div><p>Por favor revise este pago lo antes posible en su panel de supervisor.</p></div><div class="footer"><p>Facil Platform - Mensaje automático</p></div></div></div></body></html>'
) ON CONFLICT (template_code) DO UPDATE SET
    html_content = EXCLUDED.html_content,
    subject_es = EXCLUDED.subject_es,
    subject_fr = EXCLUDED.subject_fr,
    subject_en = EXCLUDED.subject_en,
    updated_at = NOW();

-- =============================================================================
-- 3. BACKFILL html_content FOR EXISTING EMAIL TEMPLATES
-- Only templates that have html_file_path but NULL html_content
-- These are needed since notification_handler now reads html_content exclusively
-- =============================================================================

-- payment_failed
UPDATE email_templates SET html_content =
'<!DOCTYPE html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"><style>body{margin:0;padding:0;font-family:-apple-system,BlinkMacSystemFont,''Segoe UI'',Roboto,''Helvetica Neue'',Arial,sans-serif;line-height:1.6;color:#333;background:#f5f5f5}.wrapper{padding:20px;background:#f5f5f5}.container{max-width:600px;margin:0 auto;background:#fff;border-radius:8px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,0.1)}.header{background:linear-gradient(135deg,#dc2626 0%,#b91c1c 100%);padding:30px 20px;text-align:center}.header h1{color:#fff;margin:0;font-size:24px}.body{padding:30px}.alert-box{background:#fef2f2;border:1px solid #fca5a5;border-radius:8px;padding:16px;margin:16px 0}.footer{background:#f9fafb;padding:20px;text-align:center;border-top:1px solid #e5e7eb;font-size:12px;color:#6b7280}</style></head><body><div class="wrapper"><div class="container"><div class="header"><h1>❌ Pago Fallido</h1></div><div class="body"><p>Estimado/a {{user_name}},</p><p>Su pago de <strong>{{amount}} {{currency}}</strong> no pudo ser procesado.</p><div class="alert-box"><p><strong>Motivo:</strong> {{reason}}</p></div><p>Por favor intente nuevamente o contacte soporte si el problema persiste.</p></div><div class="footer"><p>Facil Platform - Mensaje automático</p></div></div></div></body></html>'
WHERE template_code = 'payment_failed' AND html_content IS NULL;

-- document_validated
UPDATE email_templates SET html_content =
'<!DOCTYPE html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"><style>body{margin:0;padding:0;font-family:-apple-system,BlinkMacSystemFont,''Segoe UI'',Roboto,''Helvetica Neue'',Arial,sans-serif;line-height:1.6;color:#333;background:#f5f5f5}.wrapper{padding:20px;background:#f5f5f5}.container{max-width:600px;margin:0 auto;background:#fff;border-radius:8px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,0.1)}.header{background:linear-gradient(135deg,#16a34a 0%,#15803d 100%);padding:30px 20px;text-align:center}.header h1{color:#fff;margin:0;font-size:24px}.body{padding:30px}.info-box{background:#f0fdf4;border:1px solid #86efac;border-radius:8px;padding:16px;margin:16px 0}.footer{background:#f9fafb;padding:20px;text-align:center;border-top:1px solid #e5e7eb;font-size:12px;color:#6b7280}</style></head><body><div class="wrapper"><div class="container"><div class="header"><h1>✅ Documento Validado</h1></div><div class="body"><p>Estimado/a {{user_name}},</p><p>Su documento <strong>{{document_type}}</strong> ha sido validado correctamente.</p><div class="info-box"><p>Su expediente continúa siendo procesado. Recibirá una notificación con el resultado final.</p></div></div><div class="footer"><p>Facil Platform - Mensaje automático</p></div></div></div></body></html>'
WHERE template_code = 'document_validated' AND html_content IS NULL;

-- document_rejected
UPDATE email_templates SET html_content =
'<!DOCTYPE html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"><style>body{margin:0;padding:0;font-family:-apple-system,BlinkMacSystemFont,''Segoe UI'',Roboto,''Helvetica Neue'',Arial,sans-serif;line-height:1.6;color:#333;background:#f5f5f5}.wrapper{padding:20px;background:#f5f5f5}.container{max-width:600px;margin:0 auto;background:#fff;border-radius:8px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,0.1)}.header{background:linear-gradient(135deg,#dc2626 0%,#b91c1c 100%);padding:30px 20px;text-align:center}.header h1{color:#fff;margin:0;font-size:24px}.body{padding:30px}.alert-box{background:#fef2f2;border:1px solid #fca5a5;border-radius:8px;padding:16px;margin:16px 0}.footer{background:#f9fafb;padding:20px;text-align:center;border-top:1px solid #e5e7eb;font-size:12px;color:#6b7280}</style></head><body><div class="wrapper"><div class="container"><div class="header"><h1>❌ Documento Rechazado</h1></div><div class="body"><p>Estimado/a {{user_name}},</p><p>Su documento <strong>{{document_type}}</strong> ha sido rechazado.</p><div class="alert-box"><p><strong>Motivo:</strong> {{reason}}</p></div><p>Por favor suba un nuevo documento corrigiendo los problemas indicados.</p></div><div class="footer"><p>Facil Platform - Mensaje automático</p></div></div></div></body></html>'
WHERE template_code = 'document_rejected' AND html_content IS NULL;

-- appointment_confirmed
UPDATE email_templates SET html_content =
'<!DOCTYPE html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"><style>body{margin:0;padding:0;font-family:-apple-system,BlinkMacSystemFont,''Segoe UI'',Roboto,''Helvetica Neue'',Arial,sans-serif;line-height:1.6;color:#333;background:#f5f5f5}.wrapper{padding:20px;background:#f5f5f5}.container{max-width:600px;margin:0 auto;background:#fff;border-radius:8px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,0.1)}.header{background:linear-gradient(135deg,#2563eb 0%,#1e40af 100%);padding:30px 20px;text-align:center}.header h1{color:#fff;margin:0;font-size:24px}.body{padding:30px}.info-box{background:#eff6ff;border:1px solid #93c5fd;border-radius:8px;padding:16px;margin:16px 0}.footer{background:#f9fafb;padding:20px;text-align:center;border-top:1px solid #e5e7eb;font-size:12px;color:#6b7280}</style></head><body><div class="wrapper"><div class="container"><div class="header"><h1>📅 Cita Confirmada</h1></div><div class="body"><p>Estimado/a {{user_name}},</p><p>Su cita ha sido confirmada con los siguientes detalles:</p><div class="info-box"><p><strong>Fecha:</strong> {{appointment_date}}</p><p><strong>Hora:</strong> {{appointment_time}}</p><p><strong>Lugar:</strong> {{location}}</p></div><p>Por favor preséntese puntualmente con un documento de identidad válido.</p></div><div class="footer"><p>Facil Platform - Mensaje automático</p></div></div></div></body></html>'
WHERE template_code = 'appointment_confirmed' AND html_content IS NULL;

-- request_cancelled
UPDATE email_templates SET html_content =
'<!DOCTYPE html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"><style>body{margin:0;padding:0;font-family:-apple-system,BlinkMacSystemFont,''Segoe UI'',Roboto,''Helvetica Neue'',Arial,sans-serif;line-height:1.6;color:#333;background:#f5f5f5}.wrapper{padding:20px;background:#f5f5f5}.container{max-width:600px;margin:0 auto;background:#fff;border-radius:8px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,0.1)}.header{background:linear-gradient(135deg,#6b7280 0%,#4b5563 100%);padding:30px 20px;text-align:center}.header h1{color:#fff;margin:0;font-size:24px}.body{padding:30px}.info-box{background:#f9fafb;border:1px solid #d1d5db;border-radius:8px;padding:16px;margin:16px 0}.footer{background:#f9fafb;padding:20px;text-align:center;border-top:1px solid #e5e7eb;font-size:12px;color:#6b7280}</style></head><body><div class="wrapper"><div class="container"><div class="header"><h1>Solicitud Cancelada</h1></div><div class="body"><p>Estimado/a {{user_name}},</p><p>Su solicitud <strong>{{reference}}</strong> ha sido cancelada.</p><div class="info-box"><p><strong>Motivo:</strong> {{reason}}</p></div><p>Si tiene alguna pregunta, contacte nuestro servicio de soporte.</p></div><div class="footer"><p>Facil Platform - Mensaje automático</p></div></div></div></body></html>'
WHERE template_code = 'request_cancelled' AND html_content IS NULL;

-- appointment_completed
UPDATE email_templates SET html_content =
'<!DOCTYPE html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"><style>body{margin:0;padding:0;font-family:-apple-system,BlinkMacSystemFont,''Segoe UI'',Roboto,''Helvetica Neue'',Arial,sans-serif;line-height:1.6;color:#333;background:#f5f5f5}.wrapper{padding:20px;background:#f5f5f5}.container{max-width:600px;margin:0 auto;background:#fff;border-radius:8px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,0.1)}.header{background:linear-gradient(135deg,#16a34a 0%,#15803d 100%);padding:30px 20px;text-align:center}.header h1{color:#fff;margin:0;font-size:24px}.body{padding:30px}.footer{background:#f9fafb;padding:20px;text-align:center;border-top:1px solid #e5e7eb;font-size:12px;color:#6b7280}</style></head><body><div class="wrapper"><div class="container"><div class="header"><h1>✅ Cita Completada</h1></div><div class="body"><p>Estimado/a {{user_name}},</p><p>Gracias por asistir a su cita. Su trámite <strong>{{reference}}</strong> continúa siendo procesado.</p><p>Recibirá una notificación cuando su solicitud esté lista.</p></div><div class="footer"><p>Facil Platform - Mensaje automático</p></div></div></div></body></html>'
WHERE template_code = 'appointment_completed' AND html_content IS NULL;

-- appointment_no_show
UPDATE email_templates SET html_content =
'<!DOCTYPE html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"><style>body{margin:0;padding:0;font-family:-apple-system,BlinkMacSystemFont,''Segoe UI'',Roboto,''Helvetica Neue'',Arial,sans-serif;line-height:1.6;color:#333;background:#f5f5f5}.wrapper{padding:20px;background:#f5f5f5}.container{max-width:600px;margin:0 auto;background:#fff;border-radius:8px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,0.1)}.header{background:linear-gradient(135deg,#f59e0b 0%,#d97706 100%);padding:30px 20px;text-align:center}.header h1{color:#fff;margin:0;font-size:24px}.body{padding:30px}.alert-box{background:#fffbeb;border:1px solid #fbbf24;border-radius:8px;padding:16px;margin:16px 0}.footer{background:#f9fafb;padding:20px;text-align:center;border-top:1px solid #e5e7eb;font-size:12px;color:#6b7280}</style></head><body><div class="wrapper"><div class="container"><div class="header"><h1>⚠️ Cita No Asistida</h1></div><div class="body"><p>Estimado/a {{user_name}},</p><p>No se presentó a su cita programada para el <strong>{{appointment_date}}</strong>.</p><div class="alert-box"><p>Si necesita reprogramar, contacte nuestro servicio de soporte lo antes posible.</p></div></div><div class="footer"><p>Facil Platform - Mensaje automático</p></div></div></div></body></html>'
WHERE template_code = 'appointment_no_show' AND html_content IS NULL;

-- =============================================================================
-- 4. REBRAND: TaxasGE → Facil (subjects, SMS, html_content, provider settings)
-- Migration 039 inserted subjects with "TaxasGE". Migration 070 updated html_content
-- to "Facil" but did NOT update subjects or SMS. Fix all in one shot.
-- NOTE: REPLACE is case-sensitive so "taxasge.gq" (lowercase domain) is NOT affected.
-- =============================================================================

-- 4a. Email template subjects: "... - TaxasGE" → "... - Facil"
UPDATE email_templates SET
    subject_es = REPLACE(subject_es, 'TaxasGE', 'Facil'),
    subject_fr = REPLACE(subject_fr, 'TaxasGE', 'Facil'),
    subject_en = REPLACE(subject_en, 'TaxasGE', 'Facil'),
    updated_at = NOW()
WHERE subject_es LIKE '%TaxasGE%'
   OR subject_fr LIKE '%TaxasGE%'
   OR subject_en LIKE '%TaxasGE%';

-- 4b. Email template html_content: catch any "TaxasGE" remnants (e.g. password_changed from migration 015)
-- REPLACE is case-sensitive: "TaxasGE" is replaced but "taxasge.gq" (lowercase) is untouched
UPDATE email_templates SET
    html_content = REPLACE(html_content, 'TaxasGE', 'Facil'),
    updated_at = NOW()
WHERE html_content LIKE '%TaxasGE%';

-- 4c. SMS template content: "TaxasGE: ..." → "Facil: ..."
UPDATE sms_templates SET
    content_es = REPLACE(content_es, 'TaxasGE', 'Facil'),
    content_fr = REPLACE(content_fr, 'TaxasGE', 'Facil'),
    content_en = REPLACE(content_en, 'TaxasGE', 'Facil'),
    updated_at = NOW()
WHERE content_es LIKE '%TaxasGE%'
   OR content_fr LIKE '%TaxasGE%'
   OR content_en LIKE '%TaxasGE%';

-- 4d. Communication provider settings: sender_id and from_name
UPDATE communication_provider_settings SET
    config = REPLACE(config::text, '"TaxasGE"', '"Facil"')::jsonb,
    updated_at = NOW()
WHERE config::text LIKE '%"TaxasGE"%';

-- =============================================================================
-- 5. EMAIL TEMPLATES THAT DON'T EXIST YET (actively published events)
-- =============================================================================

-- user_welcome (triggered by USER_REGISTERED event in auth_routes.py)
INSERT INTO email_templates (template_code, name_es, name_fr, name_en, subject_es, subject_fr, subject_en, description_es, variables, category, is_active, html_content)
VALUES (
    'user_welcome',
    'Bienvenida al usuario',
    'Bienvenue utilisateur',
    'User welcome',
    'Bienvenido a Facil Platform',
    'Bienvenue sur Facil Platform',
    'Welcome to Facil Platform',
    'Email de bienvenida al registrarse',
    '["user_name"]'::jsonb,
    'auth',
    true,
    '<!DOCTYPE html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"><style>body{margin:0;padding:0;font-family:-apple-system,BlinkMacSystemFont,''Segoe UI'',Roboto,''Helvetica Neue'',Arial,sans-serif;line-height:1.6;color:#333;background:#f5f5f5}.wrapper{padding:20px;background:#f5f5f5}.container{max-width:600px;margin:0 auto;background:#fff;border-radius:8px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,0.1)}.header{background:linear-gradient(135deg,#2563eb 0%,#1e40af 100%);padding:30px 20px;text-align:center}.header h1{color:#fff;margin:0;font-size:28px}.body{padding:30px}.info-box{background:#eff6ff;border:1px solid #93c5fd;border-radius:8px;padding:16px;margin:16px 0}.footer{background:#f9fafb;padding:20px;text-align:center;border-top:1px solid #e5e7eb;font-size:12px;color:#6b7280}</style></head><body><div class="wrapper"><div class="container"><div class="header"><h1>Bienvenido a Facil</h1></div><div class="body"><p>Estimado/a {{user_name}},</p><p>Gracias por registrarse en <strong>Facil Platform</strong>. Su cuenta ha sido creada exitosamente.</p><div class="info-box"><p>Ahora puede acceder a todos los servicios fiscales y administrativos de Guinea Ecuatorial desde su panel de control.</p></div><p>Si tiene alguna pregunta, no dude en contactar nuestro servicio de soporte.</p></div><div class="footer"><p>Facil Platform - Mensaje automático</p></div></div></div></body></html>'
) ON CONFLICT (template_code) DO UPDATE SET
    html_content = EXCLUDED.html_content,
    subject_es = EXCLUDED.subject_es,
    subject_fr = EXCLUDED.subject_fr,
    subject_en = EXCLUDED.subject_en,
    updated_at = NOW();

-- batch_submitted (triggered by BATCH_SUBMITTED event in batch_persist_service.py)
INSERT INTO email_templates (template_code, name_es, name_fr, name_en, subject_es, subject_fr, subject_en, description_es, variables, category, is_active, html_content)
VALUES (
    'batch_submitted',
    'Lote enviado',
    'Lot envoyé',
    'Batch submitted',
    'Lote enviado correctamente - Facil',
    'Lot envoyé avec succès - Facil',
    'Batch submitted successfully - Facil',
    'Notificación cuando un lote de solicitudes es enviado',
    '["user_name", "batch_reference", "total_items", "amount", "currency", "beneficiary_names"]'::jsonb,
    'batch',
    true,
    '<!DOCTYPE html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"><style>body{margin:0;padding:0;font-family:-apple-system,BlinkMacSystemFont,''Segoe UI'',Roboto,''Helvetica Neue'',Arial,sans-serif;line-height:1.6;color:#333;background:#f5f5f5}.wrapper{padding:20px;background:#f5f5f5}.container{max-width:600px;margin:0 auto;background:#fff;border-radius:8px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,0.1)}.header{background:linear-gradient(135deg,#2563eb 0%,#1e40af 100%);padding:30px 20px;text-align:center}.header h1{color:#fff;margin:0;font-size:24px}.body{padding:30px}.info-box{background:#eff6ff;border:1px solid #93c5fd;border-radius:8px;padding:16px;margin:16px 0}.footer{background:#f9fafb;padding:20px;text-align:center;border-top:1px solid #e5e7eb;font-size:12px;color:#6b7280}</style></head><body><div class="wrapper"><div class="container"><div class="header"><h1>📦 Lote Enviado</h1></div><div class="body"><p>Estimado/a {{user_name}},</p><p>Su lote <strong>{{batch_reference}}</strong> ha sido enviado correctamente.</p><div class="info-box"><p><strong>Solicitudes creadas:</strong> {{total_items}}</p><p><strong>Monto total:</strong> {{amount}} {{currency}}</p></div><p>Recibirá una notificación cuando todas las solicitudes hayan sido procesadas.</p></div><div class="footer"><p>Facil Platform - Mensaje automático</p></div></div></div></body></html>'
) ON CONFLICT (template_code) DO UPDATE SET
    html_content = EXCLUDED.html_content,
    subject_es = EXCLUDED.subject_es,
    subject_fr = EXCLUDED.subject_fr,
    subject_en = EXCLUDED.subject_en,
    updated_at = NOW();

-- batch_completed (triggered by BATCH_COMPLETED event in batch_routes.py + agent_routes.py)
INSERT INTO email_templates (template_code, name_es, name_fr, name_en, subject_es, subject_fr, subject_en, description_es, variables, category, is_active, html_content)
VALUES (
    'batch_completed',
    'Lote completado',
    'Lot terminé',
    'Batch completed',
    'Lote procesado completamente - Facil',
    'Lot entièrement traité - Facil',
    'Batch fully processed - Facil',
    'Notificación cuando todas las solicitudes de un lote han sido procesadas',
    '["user_name", "batch_reference", "total_items"]'::jsonb,
    'batch',
    true,
    '<!DOCTYPE html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"><style>body{margin:0;padding:0;font-family:-apple-system,BlinkMacSystemFont,''Segoe UI'',Roboto,''Helvetica Neue'',Arial,sans-serif;line-height:1.6;color:#333;background:#f5f5f5}.wrapper{padding:20px;background:#f5f5f5}.container{max-width:600px;margin:0 auto;background:#fff;border-radius:8px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,0.1)}.header{background:linear-gradient(135deg,#16a34a 0%,#15803d 100%);padding:30px 20px;text-align:center}.header h1{color:#fff;margin:0;font-size:24px}.body{padding:30px}.info-box{background:#f0fdf4;border:1px solid #86efac;border-radius:8px;padding:16px;margin:16px 0}.footer{background:#f9fafb;padding:20px;text-align:center;border-top:1px solid #e5e7eb;font-size:12px;color:#6b7280}</style></head><body><div class="wrapper"><div class="container"><div class="header"><h1>✅ Lote Completado</h1></div><div class="body"><p>Estimado/a {{user_name}},</p><p>Todas las solicitudes de su lote <strong>{{batch_reference}}</strong> han sido procesadas.</p><div class="info-box"><p><strong>{{total_items}}</strong> solicitudes han sido finalizadas.</p></div><p>Puede consultar el detalle de cada solicitud en su panel de control.</p></div><div class="footer"><p>Facil Platform - Mensaje automático</p></div></div></div></body></html>'
) ON CONFLICT (template_code) DO UPDATE SET
    html_content = EXCLUDED.html_content,
    subject_es = EXCLUDED.subject_es,
    subject_fr = EXCLUDED.subject_fr,
    subject_en = EXCLUDED.subject_en,
    updated_at = NOW();

COMMIT;
