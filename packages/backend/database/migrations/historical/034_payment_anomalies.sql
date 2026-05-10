-- Migration 034: Payment Anomalies Management
-- Description: Tables pour la gestion des anomalies de paiement Treasury
-- Phase: 2 (Anomalies & Risques)
-- Date: 2026-01-XX (a executer)
-- Prerequis: Migration 033 completee

-- ============================================================================
-- ENUMS
-- ============================================================================

-- Type d'anomalie detectee
CREATE TYPE anomaly_type_enum AS ENUM (
    'amount_mismatch',           -- Montant incoherent (calcule vs paye)
    'duplicate_suspected',       -- Doublon potentiel (meme user, montant, < 24h)
    'reconciliation_failed',     -- Echec de reconciliation bancaire
    'validated_not_received',    -- Valide par agent mais pas encaisse
    'sla_breached',              -- Delai SLA depasse
    'high_amount',               -- Montant superieur au seuil (configurable)
    'suspicious_pattern',        -- Pattern suspect (multiple rejets, etc.)
    'manual_flag'                -- Signalement manuel par agent
);

-- Statut de l'anomalie
CREATE TYPE anomaly_status_enum AS ENUM (
    'open',                      -- Ouverte, en attente de traitement
    'investigating',             -- En cours d'investigation
    'resolved',                  -- Resolue (action corrective effectuee)
    'false_positive',            -- Faux positif (pas d'anomalie reelle)
    'escalated'                  -- Escaladee au superviseur
);

-- Severite de l'anomalie
CREATE TYPE anomaly_severity_enum AS ENUM (
    'low',                       -- Faible impact, info seulement
    'medium',                    -- Impact moyen, action requise
    'high',                      -- Impact eleve, action prioritaire
    'critical'                   -- Impact critique, action immediate
);

-- ============================================================================
-- TABLE PRINCIPALE: payment_anomalies
-- ============================================================================

CREATE TABLE payment_anomalies (
    -- Identifiant
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Entite concernee (polymorphique)
    entity_type VARCHAR(50) NOT NULL,
    entity_id UUID NOT NULL,
    payment_reference VARCHAR(100),

    -- Reference service_request (si applicable)
    service_request_id UUID REFERENCES service_requests(id) ON DELETE SET NULL,
    service_request_reference VARCHAR(50),

    -- Classification
    anomaly_type anomaly_type_enum NOT NULL,
    severity anomaly_severity_enum NOT NULL DEFAULT 'medium',
    status anomaly_status_enum NOT NULL DEFAULT 'open',

    -- Details descriptifs
    title VARCHAR(255) NOT NULL,
    description TEXT,
    detection_rule VARCHAR(100),
    detection_details JSONB,

    -- Montants (pour anomalies financieres)
    expected_amount NUMERIC(15, 2),
    actual_amount NUMERIC(15, 2),
    difference_amount NUMERIC(15, 2) GENERATED ALWAYS AS (
        CASE
            WHEN expected_amount IS NOT NULL AND actual_amount IS NOT NULL
            THEN ABS(expected_amount - actual_amount)
            ELSE NULL
        END
    ) STORED,

    -- Resolution
    resolution_notes TEXT,
    resolved_at TIMESTAMP WITH TIME ZONE,
    resolved_by UUID REFERENCES users(id) ON DELETE SET NULL,

    -- Audit
    detected_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    detected_by VARCHAR(50) NOT NULL DEFAULT 'system',
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),

    -- Contraintes
    CONSTRAINT valid_entity_type CHECK (
        entity_type IN ('service_payment', 'bank_transaction', 'payment')
    ),
    CONSTRAINT valid_resolution CHECK (
        (status NOT IN ('resolved', 'false_positive')) OR
        (resolved_at IS NOT NULL AND resolution_notes IS NOT NULL)
    )
);

-- Description table
COMMENT ON TABLE payment_anomalies IS
'Anomalies detectees sur les paiements Treasury - tracking et workflow de resolution';

-- Descriptions colonnes
COMMENT ON COLUMN payment_anomalies.entity_type IS
'Type d entite concernee: service_payment, bank_transaction, payment';
COMMENT ON COLUMN payment_anomalies.detection_rule IS
'Identifiant de la regle metier qui a detecte l anomalie (ex: RULE_DUPLICATE_24H)';
COMMENT ON COLUMN payment_anomalies.detection_details IS
'Donnees JSONB capturees au moment de la detection (contexte, valeurs comparees)';
COMMENT ON COLUMN payment_anomalies.detected_by IS
'system pour detection automatique, sinon user_id pour signalement manuel';

-- ============================================================================
-- TABLE HISTORIQUE: anomaly_actions
-- ============================================================================

CREATE TABLE anomaly_actions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    anomaly_id UUID NOT NULL REFERENCES payment_anomalies(id) ON DELETE CASCADE,

    -- Action effectuee
    action VARCHAR(50) NOT NULL,
    from_status anomaly_status_enum,
    to_status anomaly_status_enum,
    comment TEXT,

    -- Audit
    performed_by UUID REFERENCES users(id) ON DELETE SET NULL,
    performed_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),

    -- Contrainte
    CONSTRAINT valid_action CHECK (
        action IN ('status_change', 'comment', 'escalate', 'assign', 'update_severity')
    )
);

COMMENT ON TABLE anomaly_actions IS
'Historique des actions effectuees sur les anomalies (audit trail)';

-- ============================================================================
-- INDEX
-- ============================================================================

-- Index pour anomalies ouvertes (les plus consultees)
CREATE INDEX idx_anomalies_open ON payment_anomalies(status, severity DESC, detected_at DESC)
    WHERE status IN ('open', 'investigating');

-- Index par entite
CREATE INDEX idx_anomalies_entity ON payment_anomalies(entity_type, entity_id);

-- Index par severite et statut
CREATE INDEX idx_anomalies_severity_status ON payment_anomalies(severity, status);

-- Index par type d'anomalie
CREATE INDEX idx_anomalies_type ON payment_anomalies(anomaly_type);

-- Index chronologique
CREATE INDEX idx_anomalies_detected_at ON payment_anomalies(detected_at DESC);

-- Index pour recherche par reference paiement
CREATE INDEX idx_anomalies_payment_ref ON payment_anomalies(payment_reference)
    WHERE payment_reference IS NOT NULL;

-- Index pour recherche par service_request
CREATE INDEX idx_anomalies_service_request ON payment_anomalies(service_request_id)
    WHERE service_request_id IS NOT NULL;

-- Index actions par anomalie
CREATE INDEX idx_anomaly_actions_anomaly ON anomaly_actions(anomaly_id, performed_at DESC);

-- ============================================================================
-- TRIGGER: Mise a jour automatique updated_at
-- ============================================================================

CREATE OR REPLACE FUNCTION update_anomaly_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_anomaly_updated
    BEFORE UPDATE ON payment_anomalies
    FOR EACH ROW
    EXECUTE FUNCTION update_anomaly_timestamp();

-- ============================================================================
-- VUE: Resume des anomalies pour dashboard
-- ============================================================================

CREATE OR REPLACE VIEW v_anomaly_summary AS
SELECT
    anomaly_type,
    severity,
    status,
    COUNT(*) as count,
    SUM(COALESCE(difference_amount, 0)) as total_difference,
    MIN(detected_at) as oldest_detected,
    MAX(detected_at) as newest_detected
FROM payment_anomalies
GROUP BY anomaly_type, severity, status;

COMMENT ON VIEW v_anomaly_summary IS
'Vue agregee des anomalies pour affichage dashboard rapide';

-- ============================================================================
-- FONCTION: Detection doublons potentiels
-- ============================================================================

CREATE OR REPLACE FUNCTION detect_duplicate_payments()
RETURNS TABLE (
    payment_id_1 UUID,
    payment_id_2 UUID,
    service_request_id_1 UUID,
    service_request_id_2 UUID,
    service_request_ref_1 VARCHAR,
    service_request_ref_2 VARCHAR,
    user_id UUID,
    amount NUMERIC,
    time_diff INTERVAL
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        sp1.id as payment_id_1,
        sp2.id as payment_id_2,
        sp1.service_request_id as service_request_id_1,
        sp2.service_request_id as service_request_id_2,
        sr1.reference as service_request_ref_1,
        sr2.reference as service_request_ref_2,
        sp1.user_id,
        sp1.total_amount as amount,
        sp2.created_at - sp1.created_at as time_diff
    FROM service_payments sp1
    JOIN service_payments sp2
        ON sp1.user_id = sp2.user_id
        AND sp1.total_amount = sp2.total_amount
        AND sp1.id < sp2.id
        AND sp2.created_at - sp1.created_at < INTERVAL '24 hours'
    LEFT JOIN service_requests sr1 ON sr1.id = sp1.service_request_id
    LEFT JOIN service_requests sr2 ON sr2.id = sp2.service_request_id
    WHERE sp1.workflow_status NOT IN ('cancelled_by_user', 'cancelled_by_agent')
      AND sp2.workflow_status NOT IN ('cancelled_by_user', 'cancelled_by_agent')
      AND NOT EXISTS (
          SELECT 1 FROM payment_anomalies pa
          WHERE pa.entity_id IN (sp1.id, sp2.id)
            AND pa.anomaly_type = 'duplicate_suspected'
            AND pa.status NOT IN ('resolved', 'false_positive')
      );
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION detect_duplicate_payments IS
'Detecte les paiements potentiellement dupliques (meme user, montant, < 24h).
Retourne aussi les references service_request pour contexte.';

-- ============================================================================
-- PERMISSIONS (a inserer dans la table permissions)
-- ============================================================================

INSERT INTO permissions (name, resource, action, description, is_critical, module_name) VALUES
('treasury.anomalies.view', 'treasury_anomalies', 'view', 'Acceso a la lista de anomalias de pago', false, 'treasury'),
('treasury.anomalies.create', 'treasury_anomalies', 'create', 'Crear anomalias de pago manualmente', false, 'treasury'),
('treasury.anomalies.update', 'treasury_anomalies', 'update', 'Cambiar estado y resolver anomalias', false, 'treasury'),
('treasury.anomalies.delete', 'treasury_anomalies', 'delete', 'Eliminar anomalias (solo admin)', true, 'treasury')
ON CONFLICT (name) DO NOTHING;

-- ============================================================================
-- SEED DATA: Regles de detection (pour reference)
-- ============================================================================

-- Les regles sont implementees dans le code backend, pas en DB
-- Liste des regles supportees:
-- RULE_DUPLICATE_24H     - Doublon potentiel (meme user, montant, < 24h)
-- RULE_HIGH_AMOUNT       - Montant > seuil (default 1,000,000 XAF)
-- RULE_SLA_BREACH        - SLA depasse
-- RULE_AMOUNT_MISMATCH   - Ecart > 1% entre calcule et paye
-- RULE_UNRECONCILED_7D   - Transaction bancaire non reconciliee > 7 jours

-- ============================================================================
-- VERIFICATION
-- ============================================================================

-- Verifier la creation des tables
SELECT
    table_name,
    (SELECT COUNT(*) FROM information_schema.columns WHERE table_name = t.table_name) as columns_count
FROM information_schema.tables t
WHERE table_schema = 'public'
  AND table_name IN ('payment_anomalies', 'anomaly_actions')
ORDER BY table_name;

-- Verifier les enums
SELECT
    t.typname as enum_name,
    array_agg(e.enumlabel ORDER BY e.enumsortorder) as values
FROM pg_type t
JOIN pg_enum e ON t.oid = e.enumtypid
WHERE t.typname IN ('anomaly_type_enum', 'anomaly_status_enum', 'anomaly_severity_enum')
GROUP BY t.typname;
