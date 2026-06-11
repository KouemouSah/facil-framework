-- Migration: 027_notification_log.sql
-- Date: 2025-12-27
-- Description: Table d'historique des notifications envoyées (audit et traçabilité)
-- Author: TaxasGE Development Team
-- Reference: Module communications - Traçabilité des envois

-- ============================================================================
-- 1. CREATE NOTIFICATION_LOG TABLE
-- ============================================================================
-- Trace toutes les notifications envoyées pour audit et support

CREATE TABLE IF NOT EXISTS notification_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Contexte de la notification
    service_request_id UUID REFERENCES service_requests(id) ON DELETE SET NULL,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,

    -- Canal d'envoi
    channel VARCHAR(20) NOT NULL,
    -- email, sms, push, in_app, whatsapp

    -- Template utilisé
    template_code VARCHAR(100) NOT NULL,
    -- Ex: cita_scheduled, payment_confirmed, document_rejected

    -- Destinataire (pour historique même si user supprimé)
    recipient_email VARCHAR(255),
    recipient_phone VARCHAR(50),
    recipient_device_token TEXT,

    -- Contenu envoyé (pour audit)
    subject VARCHAR(500),
    content_preview VARCHAR(500),
    -- Premiers 500 caractères pour référence

    -- Variables utilisées dans le template
    template_variables JSONB DEFAULT '{}',

    -- Status de l'envoi
    status VARCHAR(30) NOT NULL DEFAULT 'queued',
    -- queued, sending, sent, delivered, failed, bounced, opened, clicked

    -- Identifiant externe (pour traçabilité avec providers)
    external_id VARCHAR(255),
    -- ID SendGrid, Twilio SID, Firebase message_id

    external_provider VARCHAR(50),
    -- sendgrid, twilio, firebase, infobip

    -- Timestamps
    queued_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    sent_at TIMESTAMPTZ,
    delivered_at TIMESTAMPTZ,
    opened_at TIMESTAMPTZ,
    clicked_at TIMESTAMPTZ,
    failed_at TIMESTAMPTZ,

    -- Erreur si échec
    error_code VARCHAR(50),
    error_message TEXT,
    retry_count INTEGER DEFAULT 0,
    next_retry_at TIMESTAMPTZ,

    -- Contexte additionnel
    trigger_event VARCHAR(100),
    -- status_change, reminder_3d, reminder_1d, payment_confirmed, etc.

    triggered_by VARCHAR(50) DEFAULT 'system',
    -- system, agent, user, scheduled_job

    -- Métadonnées
    metadata JSONB DEFAULT '{}',
    -- ip_address, user_agent, batch_id, etc.

    -- Audit
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Contraintes
    CONSTRAINT valid_channel CHECK (channel IN ('email', 'sms', 'push', 'in_app', 'whatsapp')),
    CONSTRAINT valid_status CHECK (status IN (
        'queued', 'sending', 'sent', 'delivered', 'failed', 'bounced', 'opened', 'clicked'
    ))
);

-- ============================================================================
-- 2. CREATE INDEXES
-- ============================================================================

-- Recherche par service_request (vue agent)
CREATE INDEX IF NOT EXISTS idx_nl_service_request ON notification_log(service_request_id)
    WHERE service_request_id IS NOT NULL;

-- Recherche par utilisateur
CREATE INDEX IF NOT EXISTS idx_nl_user_id ON notification_log(user_id);

-- Recherche par status (pour retry des failed)
CREATE INDEX IF NOT EXISTS idx_nl_status ON notification_log(status)
    WHERE status IN ('queued', 'failed');

-- Recherche par canal
CREATE INDEX IF NOT EXISTS idx_nl_channel ON notification_log(channel);

-- Recherche par date (pour analytics)
CREATE INDEX IF NOT EXISTS idx_nl_created_at ON notification_log(created_at DESC);

-- Recherche par external_id (webhook callback)
CREATE INDEX IF NOT EXISTS idx_nl_external_id ON notification_log(external_id)
    WHERE external_id IS NOT NULL;

-- Recherche des notifications à réessayer
CREATE INDEX IF NOT EXISTS idx_nl_retry ON notification_log(next_retry_at)
    WHERE status = 'failed' AND next_retry_at IS NOT NULL AND retry_count < 3;

-- Index composite pour dashboard analytics
CREATE INDEX IF NOT EXISTS idx_nl_analytics ON notification_log(created_at DESC, channel, status);

-- ============================================================================
-- 3. CREATE VIEW FOR SERVICE REQUEST NOTIFICATIONS
-- ============================================================================
-- Vue pour afficher toutes les notifications d'une demande

CREATE OR REPLACE VIEW v_service_request_notifications AS
SELECT
    nl.id,
    nl.service_request_id,
    sr.reference AS request_reference,
    nl.user_id,
    u.full_name AS user_name,
    nl.channel,
    nl.template_code,
    nl.subject,
    nl.content_preview,
    nl.status,
    nl.external_provider,
    nl.queued_at,
    nl.sent_at,
    nl.delivered_at,
    nl.opened_at,
    nl.error_message,
    nl.retry_count,
    nl.trigger_event
FROM notification_log nl
LEFT JOIN service_requests sr ON sr.id = nl.service_request_id
LEFT JOIN users u ON u.id = nl.user_id
ORDER BY nl.created_at DESC;

COMMENT ON VIEW v_service_request_notifications IS 'Vue des notifications par demande de service';

-- ============================================================================
-- 4. CREATE VIEW FOR NOTIFICATION STATISTICS
-- ============================================================================

CREATE OR REPLACE VIEW v_notification_statistics AS
SELECT
    DATE(created_at) AS date,
    channel,
    COUNT(*) AS total_sent,
    COUNT(*) FILTER (WHERE status = 'delivered') AS delivered,
    COUNT(*) FILTER (WHERE status = 'failed') AS failed,
    COUNT(*) FILTER (WHERE status = 'bounced') AS bounced,
    COUNT(*) FILTER (WHERE status = 'opened') AS opened,
    COUNT(*) FILTER (WHERE status = 'clicked') AS clicked,
    ROUND(
        COUNT(*) FILTER (WHERE status = 'delivered')::NUMERIC /
        NULLIF(COUNT(*) FILTER (WHERE status IN ('sent', 'delivered', 'opened', 'clicked')), 0) * 100,
        2
    ) AS delivery_rate_percent
FROM notification_log
WHERE created_at >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY DATE(created_at), channel
ORDER BY date DESC, channel;

COMMENT ON VIEW v_notification_statistics IS 'Statistiques des notifications sur 30 jours';

-- ============================================================================
-- 5. CREATE FUNCTION TO LOG NOTIFICATION
-- ============================================================================
-- Helper function pour enregistrer une notification

CREATE OR REPLACE FUNCTION log_notification(
    p_service_request_id UUID,
    p_user_id UUID,
    p_channel VARCHAR(20),
    p_template_code VARCHAR(100),
    p_recipient VARCHAR(255),
    p_subject VARCHAR(500),
    p_content_preview VARCHAR(500),
    p_trigger_event VARCHAR(100),
    p_template_variables JSONB DEFAULT '{}'
)
RETURNS UUID AS $$
DECLARE
    v_log_id UUID;
BEGIN
    INSERT INTO notification_log (
        service_request_id,
        user_id,
        channel,
        template_code,
        recipient_email,
        recipient_phone,
        subject,
        content_preview,
        trigger_event,
        template_variables,
        status
    ) VALUES (
        p_service_request_id,
        p_user_id,
        p_channel,
        p_template_code,
        CASE WHEN p_channel = 'email' THEN p_recipient ELSE NULL END,
        CASE WHEN p_channel IN ('sms', 'whatsapp') THEN p_recipient ELSE NULL END,
        p_subject,
        p_content_preview,
        p_trigger_event,
        p_template_variables,
        'queued'
    )
    RETURNING id INTO v_log_id;

    RETURN v_log_id;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- 6. CREATE FUNCTION TO UPDATE NOTIFICATION STATUS
-- ============================================================================
-- Appelée par webhook callback des providers

CREATE OR REPLACE FUNCTION update_notification_status(
    p_notification_id UUID,
    p_status VARCHAR(30),
    p_external_id VARCHAR(255) DEFAULT NULL,
    p_external_provider VARCHAR(50) DEFAULT NULL,
    p_error_code VARCHAR(50) DEFAULT NULL,
    p_error_message TEXT DEFAULT NULL
)
RETURNS BOOLEAN AS $$
BEGIN
    UPDATE notification_log
    SET
        status = p_status,
        external_id = COALESCE(p_external_id, external_id),
        external_provider = COALESCE(p_external_provider, external_provider),
        sent_at = CASE WHEN p_status = 'sent' AND sent_at IS NULL THEN NOW() ELSE sent_at END,
        delivered_at = CASE WHEN p_status = 'delivered' AND delivered_at IS NULL THEN NOW() ELSE delivered_at END,
        opened_at = CASE WHEN p_status = 'opened' AND opened_at IS NULL THEN NOW() ELSE opened_at END,
        clicked_at = CASE WHEN p_status = 'clicked' AND clicked_at IS NULL THEN NOW() ELSE clicked_at END,
        failed_at = CASE WHEN p_status IN ('failed', 'bounced') AND failed_at IS NULL THEN NOW() ELSE failed_at END,
        error_code = COALESCE(p_error_code, error_code),
        error_message = COALESCE(p_error_message, error_message),
        retry_count = CASE WHEN p_status = 'failed' THEN retry_count + 1 ELSE retry_count END,
        next_retry_at = CASE
            WHEN p_status = 'failed' AND retry_count < 3
            THEN NOW() + INTERVAL '5 minutes' * POWER(2, retry_count)
            ELSE NULL
        END
    WHERE id = p_notification_id;

    RETURN FOUND;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- 7. CREATE FUNCTION TO GET PENDING RETRIES
-- ============================================================================
-- Pour le job de retry des notifications échouées

CREATE OR REPLACE FUNCTION get_pending_notification_retries(p_limit INTEGER DEFAULT 100)
RETURNS TABLE (
    id UUID,
    channel VARCHAR(20),
    template_code VARCHAR(100),
    recipient_email VARCHAR(255),
    recipient_phone VARCHAR(50),
    template_variables JSONB,
    retry_count INTEGER
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        nl.id,
        nl.channel,
        nl.template_code,
        nl.recipient_email,
        nl.recipient_phone,
        nl.template_variables,
        nl.retry_count
    FROM notification_log nl
    WHERE nl.status = 'failed'
      AND nl.retry_count < 3
      AND nl.next_retry_at <= NOW()
    ORDER BY nl.next_retry_at
    LIMIT p_limit;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- 8. ADD COMMENTS
-- ============================================================================

COMMENT ON TABLE notification_log IS 'Historique de toutes les notifications envoyées (audit et traçabilité)';
COMMENT ON COLUMN notification_log.channel IS 'Canal: email, sms, push, in_app, whatsapp';
COMMENT ON COLUMN notification_log.template_code IS 'Code du template utilisé (ex: cita_scheduled)';
COMMENT ON COLUMN notification_log.external_id IS 'ID du provider externe (SendGrid, Twilio, Firebase)';
COMMENT ON COLUMN notification_log.status IS 'Status: queued, sending, sent, delivered, failed, bounced, opened, clicked';
COMMENT ON COLUMN notification_log.trigger_event IS 'Événement déclencheur (status_change, reminder_3d, etc.)';

COMMENT ON FUNCTION log_notification IS 'Enregistre une nouvelle notification dans le log';
COMMENT ON FUNCTION update_notification_status IS 'Met à jour le status (appelé par webhook callback)';
COMMENT ON FUNCTION get_pending_notification_retries IS 'Récupère les notifications à réessayer';

-- ============================================================================
-- 9. ADD PERMISSIONS
-- ============================================================================

INSERT INTO permissions (name, resource, action, description, is_critical, module_name)
VALUES
    ('notifications.log.read', 'notification_log', 'read', 'Consulter l''historique des notifications', FALSE, 'communications'),
    ('notifications.log.export', 'notification_log', 'export', 'Exporter l''historique des notifications', FALSE, 'communications'),
    ('notifications.stats.read', 'notification_stats', 'read', 'Consulter les statistiques de notifications', FALSE, 'communications')
ON CONFLICT (name) DO NOTHING;

-- ============================================================================
-- END OF MIGRATION
-- ============================================================================
