-- Migration: Complete Notification Templates
-- Date: 2026-01-23
-- Description: Add missing SMS templates for notification completeness
--
-- Missing templates identified:
-- 1. PAYMENT_FAILED - When BANGE API fails
-- 2. REQUEST_SUBMITTED - When request is created (SMS version)
-- 3. REQUEST_COMPLETED - When request workflow is finished
-- 4. DOCUMENT_VALIDATED - When agent validates document
-- 5. DOCUMENT_REJECTED - When agent rejects document
-- 6. APPOINTMENT_CONFIRMED - When hold is confirmed after payment

-- =============================================================================
-- SMS TEMPLATES
-- =============================================================================

-- Payment Cash Pending SMS
INSERT INTO sms_templates (template_code, name_es, name_fr, name_en, content_es, content_fr, content_en, variables, category, max_segments, is_active)
VALUES (
    'PAYMENT_CASH_PENDING',
    'Pago en efectivo pendiente',
    'Paiement en espèces en attente',
    'Cash payment pending',
    'TaxasGE: Su pago en efectivo de {{amount}} XAF está pendiente de validación. Ref: {{reference}}.',
    'TaxasGE: Votre paiement en espèces de {{amount}} XAF est en attente de validation. Réf: {{reference}}.',
    'TaxasGE: Your cash payment of {{amount}} XAF is pending validation. Ref: {{reference}}.',
    '["amount", "reference"]'::jsonb,
    'payments',
    1,
    true
) ON CONFLICT (template_code) DO NOTHING;

-- Payment Failed SMS
INSERT INTO sms_templates (template_code, name_es, name_fr, name_en, content_es, content_fr, content_en, variables, category, max_segments, is_active)
VALUES (
    'PAYMENT_FAILED',
    'Pago fallido',
    'Paiement échoué',
    'Payment failed',
    'TaxasGE: Su pago de {{amount}} XAF ha fallado. Motivo: {{reason}}. Intente nuevamente.',
    'TaxasGE: Votre paiement de {{amount}} XAF a échoué. Raison: {{reason}}. Réessayez.',
    'TaxasGE: Your payment of {{amount}} XAF failed. Reason: {{reason}}. Please try again.',
    '["amount", "reason"]'::jsonb,
    'payments',
    1,
    true
) ON CONFLICT (template_code) DO NOTHING;

-- Request Submitted SMS
INSERT INTO sms_templates (template_code, name_es, name_fr, name_en, content_es, content_fr, content_en, variables, category, max_segments, is_active)
VALUES (
    'REQUEST_SUBMITTED',
    'Solicitud recibida',
    'Demande reçue',
    'Request received',
    'TaxasGE: Su solicitud ha sido recibida. Ref: {{reference}}. Consulte el estado en taxasge.gq',
    'TaxasGE: Votre demande a été reçue. Réf: {{reference}}. Consultez le statut sur taxasge.gq',
    'TaxasGE: Your request has been received. Ref: {{reference}}. Check status at taxasge.gq',
    '["reference"]'::jsonb,
    'requests',
    1,
    true
) ON CONFLICT (template_code) DO NOTHING;

-- Request Completed SMS
INSERT INTO sms_templates (template_code, name_es, name_fr, name_en, content_es, content_fr, content_en, variables, category, max_segments, is_active)
VALUES (
    'REQUEST_COMPLETED',
    'Solicitud completada',
    'Demande terminée',
    'Request completed',
    'TaxasGE: Su solicitud {{reference}} ha sido completada. Puede retirar su documento.',
    'TaxasGE: Votre demande {{reference}} est terminée. Vous pouvez retirer votre document.',
    'TaxasGE: Your request {{reference}} is complete. You can collect your document.',
    '["reference"]'::jsonb,
    'requests',
    1,
    true
) ON CONFLICT (template_code) DO NOTHING;

-- Document Validated SMS
INSERT INTO sms_templates (template_code, name_es, name_fr, name_en, content_es, content_fr, content_en, variables, category, max_segments, is_active)
VALUES (
    'DOCUMENT_VALIDATED',
    'Documento validado',
    'Document validé',
    'Document validated',
    'TaxasGE: Su documento {{document_type}} ha sido validado correctamente.',
    'TaxasGE: Votre document {{document_type}} a été validé avec succès.',
    'TaxasGE: Your {{document_type}} document has been validated successfully.',
    '["document_type"]'::jsonb,
    'documents',
    1,
    true
) ON CONFLICT (template_code) DO NOTHING;

-- Document Rejected SMS
INSERT INTO sms_templates (template_code, name_es, name_fr, name_en, content_es, content_fr, content_en, variables, category, max_segments, is_active)
VALUES (
    'DOCUMENT_REJECTED',
    'Documento rechazado',
    'Document refusé',
    'Document rejected',
    'TaxasGE: Su documento {{document_type}} fue rechazado. Motivo: {{reason}}. Suba uno nuevo.',
    'TaxasGE: Votre document {{document_type}} a été refusé. Raison: {{reason}}. Téléchargez-en un nouveau.',
    'TaxasGE: Your {{document_type}} document was rejected. Reason: {{reason}}. Please upload a new one.',
    '["document_type", "reason"]'::jsonb,
    'documents',
    2,
    true
) ON CONFLICT (template_code) DO NOTHING;

-- Appointment Confirmed SMS (distinct from APPOINTMENT_BOOKED)
INSERT INTO sms_templates (template_code, name_es, name_fr, name_en, content_es, content_fr, content_en, variables, category, max_segments, is_active)
VALUES (
    'APPOINTMENT_CONFIRMED',
    'Cita confirmada (pago recibido)',
    'Rendez-vous confirmé (paiement reçu)',
    'Appointment confirmed (payment received)',
    'TaxasGE: Pago recibido. Cita confirmada: {{appointment_date}} {{appointment_time}} en {{location}}.',
    'TaxasGE: Paiement reçu. RDV confirmé: {{appointment_date}} {{appointment_time}} à {{location}}.',
    'TaxasGE: Payment received. Appointment confirmed: {{appointment_date}} {{appointment_time}} at {{location}}.',
    '["appointment_date", "appointment_time", "location"]'::jsonb,
    'reminders',
    1,
    true
) ON CONFLICT (template_code) DO NOTHING;

-- Request Cancelled SMS
INSERT INTO sms_templates (template_code, name_es, name_fr, name_en, content_es, content_fr, content_en, variables, category, max_segments, is_active)
VALUES (
    'REQUEST_CANCELLED',
    'Solicitud cancelada',
    'Demande annulée',
    'Request cancelled',
    'TaxasGE: Su solicitud {{reference}} ha sido cancelada. Motivo: {{reason}}.',
    'TaxasGE: Votre demande {{reference}} a été annulée. Raison: {{reason}}.',
    'TaxasGE: Your request {{reference}} has been cancelled. Reason: {{reason}}.',
    '["reference", "reason"]'::jsonb,
    'requests',
    1,
    true
) ON CONFLICT (template_code) DO NOTHING;

-- Appointment No-Show SMS
INSERT INTO sms_templates (template_code, name_es, name_fr, name_en, content_es, content_fr, content_en, variables, category, max_segments, is_active)
VALUES (
    'APPOINTMENT_NO_SHOW',
    'Cita no asistida',
    'Rendez-vous manqué',
    'Appointment no-show',
    'TaxasGE: No se presentó a su cita del {{appointment_date}}. Contacte soporte para reprogramar.',
    'TaxasGE: Vous n''êtes pas venu à votre RDV du {{appointment_date}}. Contactez le support pour reprogrammer.',
    'TaxasGE: You missed your appointment on {{appointment_date}}. Contact support to reschedule.',
    '["appointment_date"]'::jsonb,
    'reminders',
    1,
    true
) ON CONFLICT (template_code) DO NOTHING;

-- =============================================================================
-- EMAIL TEMPLATES (manquants)
-- =============================================================================

-- Payment Failed Email
INSERT INTO email_templates (template_code, name_es, name_fr, name_en, subject_es, subject_fr, subject_en, description_es, html_file_path, variables, category, is_active)
VALUES (
    'payment_failed',
    'Pago fallido',
    'Paiement échoué',
    'Payment failed',
    'Pago fallido - TaxasGE',
    'Paiement échoué - TaxasGE',
    'Payment failed - TaxasGE',
    'Notificación enviada cuando un pago falla',
    'templates/payment_failed.html',
    '["user_name", "amount", "currency", "reason"]',
    'payment',
    true
) ON CONFLICT (template_code) DO UPDATE SET updated_at = NOW();

-- Document Validated Email
INSERT INTO email_templates (template_code, name_es, name_fr, name_en, subject_es, subject_fr, subject_en, description_es, html_file_path, variables, category, is_active)
VALUES (
    'document_validated',
    'Documento validado',
    'Document validé',
    'Document validated',
    'Documento validado - TaxasGE',
    'Document validé - TaxasGE',
    'Document validated - TaxasGE',
    'Notificación cuando un documento es validado por el agente',
    'templates/document_validated.html',
    '["user_name", "document_type", "file_name"]',
    'document',
    true
) ON CONFLICT (template_code) DO UPDATE SET updated_at = NOW();

-- Document Rejected Email
INSERT INTO email_templates (template_code, name_es, name_fr, name_en, subject_es, subject_fr, subject_en, description_es, html_file_path, variables, category, is_active)
VALUES (
    'document_rejected',
    'Documento rechazado',
    'Document refusé',
    'Document rejected',
    'Documento rechazado - TaxasGE',
    'Document refusé - TaxasGE',
    'Document rejected - TaxasGE',
    'Notificación cuando un documento es rechazado',
    'templates/document_rejected.html',
    '["user_name", "document_type", "file_name", "reason"]',
    'document',
    true
) ON CONFLICT (template_code) DO UPDATE SET updated_at = NOW();

-- Appointment Confirmed Email
INSERT INTO email_templates (template_code, name_es, name_fr, name_en, subject_es, subject_fr, subject_en, description_es, html_file_path, variables, category, is_active)
VALUES (
    'appointment_confirmed',
    'Cita confirmada',
    'Rendez-vous confirmé',
    'Appointment confirmed',
    'Cita confirmada - Pago recibido - TaxasGE',
    'Rendez-vous confirmé - Paiement reçu - TaxasGE',
    'Appointment confirmed - Payment received - TaxasGE',
    'Notificación cuando la cita es confirmada después del pago',
    'templates/appointment_confirmed.html',
    '["user_name", "appointment_date", "appointment_time", "location", "workflow_code"]',
    'appointment',
    true
) ON CONFLICT (template_code) DO UPDATE SET updated_at = NOW();

-- Request Cancelled Email
INSERT INTO email_templates (template_code, name_es, name_fr, name_en, subject_es, subject_fr, subject_en, description_es, html_file_path, variables, category, is_active)
VALUES (
    'request_cancelled',
    'Solicitud cancelada',
    'Demande annulée',
    'Request cancelled',
    'Solicitud cancelada - TaxasGE',
    'Demande annulée - TaxasGE',
    'Request cancelled - TaxasGE',
    'Notificación cuando una solicitud es cancelada',
    'templates/request_cancelled.html',
    '["user_name", "reference", "workflow_code", "reason"]',
    'request',
    true
) ON CONFLICT (template_code) DO UPDATE SET updated_at = NOW();

-- Appointment Completed Email
INSERT INTO email_templates (template_code, name_es, name_fr, name_en, subject_es, subject_fr, subject_en, description_es, html_file_path, variables, category, is_active)
VALUES (
    'appointment_completed',
    'Cita completada',
    'Rendez-vous terminé',
    'Appointment completed',
    'Gracias por su visita - TaxasGE',
    'Merci pour votre visite - TaxasGE',
    'Thank you for your visit - TaxasGE',
    'Notificación cuando el ciudadano asiste a su cita',
    'templates/appointment_completed.html',
    '["user_name", "reference", "workflow_code"]',
    'appointment',
    true
) ON CONFLICT (template_code) DO UPDATE SET updated_at = NOW();

-- Appointment No-Show Email
INSERT INTO email_templates (template_code, name_es, name_fr, name_en, subject_es, subject_fr, subject_en, description_es, html_file_path, variables, category, is_active)
VALUES (
    'appointment_no_show',
    'Cita no asistida',
    'Rendez-vous manqué',
    'Appointment no-show',
    'Cita no asistida - TaxasGE',
    'Rendez-vous manqué - TaxasGE',
    'Missed appointment - TaxasGE',
    'Notificación cuando el ciudadano no asiste a su cita',
    'templates/appointment_no_show.html',
    '["user_name", "reference", "appointment_date", "workflow_code"]',
    'appointment',
    true
) ON CONFLICT (template_code) DO UPDATE SET updated_at = NOW();

-- =============================================================================
-- NOTIFICATION TEMPLATES (In-app) - manquants
-- =============================================================================

-- Payment Failed Notification
INSERT INTO notification_templates (template_code, name_es, name_fr, name_en, title_es, title_fr, title_en, body_es, body_fr, body_en, icon, action_url, variables, notification_type, priority, is_active)
VALUES (
    'payment_failed',
    'Pago fallido',
    'Paiement échoué',
    'Payment failed',
    'Pago fallido',
    'Paiement échoué',
    'Payment failed',
    'Su pago de {amount} {currency} ha fallado. Por favor intente nuevamente.',
    'Votre paiement de {amount} {currency} a échoué. Veuillez réessayer.',
    'Your payment of {amount} {currency} failed. Please try again.',
    'x-circle',
    '/payments',
    '["amount", "currency"]',
    'error',
    'high',
    true
) ON CONFLICT (template_code) DO UPDATE SET updated_at = NOW();

-- Request Completed Notification
INSERT INTO notification_templates (template_code, name_es, name_fr, name_en, title_es, title_fr, title_en, body_es, body_fr, body_en, icon, action_url, variables, notification_type, priority, is_active)
VALUES (
    'request_completed',
    'Solicitud completada',
    'Demande terminée',
    'Request completed',
    'Solicitud completada',
    'Demande terminée',
    'Request completed',
    'Su solicitud ha sido procesada exitosamente. Puede retirar su documento.',
    'Votre demande a été traitée avec succès. Vous pouvez retirer votre document.',
    'Your request has been processed successfully. You can collect your document.',
    'check-circle',
    '/requests/{request_id}',
    '["request_id"]',
    'success',
    'high',
    true
) ON CONFLICT (template_code) DO UPDATE SET updated_at = NOW();

-- Request Cancelled Notification
INSERT INTO notification_templates (template_code, name_es, name_fr, name_en, title_es, title_fr, title_en, body_es, body_fr, body_en, icon, action_url, variables, notification_type, priority, is_active)
VALUES (
    'request_cancelled',
    'Solicitud cancelada',
    'Demande annulée',
    'Request cancelled',
    'Solicitud cancelada',
    'Demande annulée',
    'Request cancelled',
    'Su solicitud ha sido cancelada.',
    'Votre demande a été annulée.',
    'Your request has been cancelled.',
    'x-circle',
    '/requests/{request_id}',
    '["request_id"]',
    'warning',
    'normal',
    true
) ON CONFLICT (template_code) DO UPDATE SET updated_at = NOW();

-- Appointment Confirmed Notification
INSERT INTO notification_templates (template_code, name_es, name_fr, name_en, title_es, title_fr, title_en, body_es, body_fr, body_en, icon, action_url, variables, notification_type, priority, is_active)
VALUES (
    'appointment_confirmed',
    'Cita confirmada',
    'Rendez-vous confirmé',
    'Appointment confirmed',
    'Cita confirmada',
    'Rendez-vous confirmé',
    'Appointment confirmed',
    'Su pago ha sido recibido. Cita confirmada para el {appointment_date} a las {appointment_time}.',
    'Votre paiement a été reçu. Rendez-vous confirmé pour le {appointment_date} à {appointment_time}.',
    'Your payment has been received. Appointment confirmed for {appointment_date} at {appointment_time}.',
    'calendar-check',
    '/appointments/{request_id}',
    '["request_id", "appointment_date", "appointment_time"]',
    'success',
    'high',
    true
) ON CONFLICT (template_code) DO UPDATE SET updated_at = NOW();

-- =============================================================================
-- PUSH TEMPLATES - manquants
-- =============================================================================

-- Payment Failed Push
INSERT INTO push_templates (template_code, name_es, name_fr, name_en, title_es, title_fr, title_en, body_es, body_fr, body_en, icon_url, click_action, variables, platform, is_active)
VALUES (
    'payment_failed',
    'Pago fallido',
    'Paiement échoué',
    'Payment failed',
    'Pago fallido',
    'Paiement échoué',
    'Payment failed',
    'Su pago ha fallado. Por favor intente nuevamente.',
    'Votre paiement a échoué. Veuillez réessayer.',
    'Your payment failed. Please try again.',
    '/icons/payment_failed.png',
    '/payments',
    '["payment_id"]',
    'all',
    true
) ON CONFLICT (template_code) DO UPDATE SET updated_at = NOW();

-- Request Completed Push
INSERT INTO push_templates (template_code, name_es, name_fr, name_en, title_es, title_fr, title_en, body_es, body_fr, body_en, icon_url, click_action, variables, platform, is_active)
VALUES (
    'request_completed',
    'Solicitud completada',
    'Demande terminée',
    'Request completed',
    'Solicitud completada',
    'Demande terminée',
    'Request completed',
    'Su solicitud ha sido completada exitosamente.',
    'Votre demande a été traitée avec succès.',
    'Your request has been completed successfully.',
    '/icons/request_completed.png',
    '/requests',
    '["request_id"]',
    'all',
    true
) ON CONFLICT (template_code) DO UPDATE SET updated_at = NOW();

-- Document Validated Push
INSERT INTO push_templates (template_code, name_es, name_fr, name_en, title_es, title_fr, title_en, body_es, body_fr, body_en, icon_url, click_action, variables, platform, is_active)
VALUES (
    'document_validated',
    'Documento validado',
    'Document validé',
    'Document validated',
    'Documento validado',
    'Document validé',
    'Document validated',
    'Su documento ha sido validado correctamente.',
    'Votre document a été validé avec succès.',
    'Your document has been validated successfully.',
    '/icons/document_validated.png',
    '/requests',
    '["request_id"]',
    'all',
    true
) ON CONFLICT (template_code) DO UPDATE SET updated_at = NOW();

-- Appointment Confirmed Push
INSERT INTO push_templates (template_code, name_es, name_fr, name_en, title_es, title_fr, title_en, body_es, body_fr, body_en, icon_url, click_action, variables, platform, is_active)
VALUES (
    'appointment_confirmed',
    'Cita confirmada',
    'Rendez-vous confirmé',
    'Appointment confirmed',
    'Pago recibido - Cita confirmada',
    'Paiement reçu - Rendez-vous confirmé',
    'Payment received - Appointment confirmed',
    'Su pago ha sido recibido y su cita está confirmada.',
    'Votre paiement a été reçu et votre rendez-vous est confirmé.',
    'Your payment has been received and your appointment is confirmed.',
    '/icons/appointment_confirmed.png',
    '/appointments',
    '["request_id"]',
    'all',
    true
) ON CONFLICT (template_code) DO UPDATE SET updated_at = NOW();
