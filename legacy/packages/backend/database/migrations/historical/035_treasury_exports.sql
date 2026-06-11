-- Migration 035: Treasury Exports Management
-- Description: Tables pour la gestion des exports comptables Treasury
-- Phase: 3 (Exports Comptables)
-- Date: 2026-01-XX (a executer)
-- Prerequis: Migration 034 completee

-- ============================================================================
-- ENUMS
-- ============================================================================

-- Type d'export
CREATE TYPE export_type_enum AS ENUM (
    'sage_x3',           -- Export SAGE X3 (format CSV specifique)
    'ministry_report',   -- Rapport ministeriel (PDF)
    'bank_central',      -- Format banque centrale BEAC
    'audit_report',      -- Rapport d'audit interne
    'reconciliation',    -- Export reconciliation bancaire
    'custom'             -- Export personnalise
);

-- Statut d'export
CREATE TYPE export_status_enum AS ENUM (
    'pending',           -- En attente de traitement
    'processing',        -- Generation en cours
    'completed',         -- Termine avec succes
    'failed'             -- Echec de generation
);

-- ============================================================================
-- TABLE PRINCIPALE: treasury_exports
-- ============================================================================

CREATE TABLE treasury_exports (
    -- Identifiant
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Type et format
    export_type export_type_enum NOT NULL,
    export_format VARCHAR(20) NOT NULL DEFAULT 'csv',

    -- Periode couverte
    period_start DATE NOT NULL,
    period_end DATE NOT NULL,

    -- Filtres appliques (optionnels)
    filters JSONB,

    -- Statut et progression
    status export_status_enum NOT NULL DEFAULT 'pending',
    progress_percentage INT DEFAULT 0,

    -- Resultats
    total_records INT,
    total_amount NUMERIC(18, 2),
    currency VARCHAR(3) DEFAULT 'XAF',

    -- Fichier genere
    file_path TEXT,
    file_name VARCHAR(255),
    file_size_bytes BIGINT,
    file_checksum VARCHAR(64),
    file_mime_type VARCHAR(100),

    -- Erreur si echec
    error_message TEXT,
    error_details JSONB,

    -- Audit creation
    requested_by UUID NOT NULL REFERENCES users(id) ON DELETE SET NULL,
    requested_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),

    -- Audit completion
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,

    -- Audit telechargement
    downloaded_at TIMESTAMP WITH TIME ZONE,
    downloaded_by UUID REFERENCES users(id) ON DELETE SET NULL,
    download_count INT DEFAULT 0,

    -- Contraintes
    CONSTRAINT valid_period CHECK (period_end >= period_start),
    CONSTRAINT valid_format CHECK (export_format IN ('csv', 'xlsx', 'pdf', 'xml', 'json')),
    CONSTRAINT valid_progress CHECK (progress_percentage BETWEEN 0 AND 100)
);

-- Description table
COMMENT ON TABLE treasury_exports IS
'Journal des exports comptables Treasury - tracabilite complete.
Les exports incluent les donnees de service_payments JOINees avec service_requests
pour obtenir workflow_code, solicitud_type et reference.';

-- Descriptions colonnes
COMMENT ON COLUMN treasury_exports.filters IS
'Filtres JSONB appliques: {ministry_id, payment_method, workflow_code, etc.}';
COMMENT ON COLUMN treasury_exports.file_checksum IS
'SHA-256 du fichier genere pour verification integrite';
COMMENT ON COLUMN treasury_exports.file_path IS
'Chemin relatif dans le storage (Supabase ou local)';

-- ============================================================================
-- INDEX
-- ============================================================================

-- Index par statut (pour processing queue)
CREATE INDEX idx_exports_status ON treasury_exports(status)
    WHERE status IN ('pending', 'processing');

-- Index par type
CREATE INDEX idx_exports_type ON treasury_exports(export_type);

-- Index chronologique
CREATE INDEX idx_exports_requested_at ON treasury_exports(requested_at DESC);

-- Index par utilisateur
CREATE INDEX idx_exports_user ON treasury_exports(requested_by);

-- Index par periode
CREATE INDEX idx_exports_period ON treasury_exports(period_start, period_end);

-- ============================================================================
-- TABLE COMPLEMENTAIRE: export_templates
-- ============================================================================

CREATE TABLE export_templates (
    id SERIAL PRIMARY KEY,
    code VARCHAR(50) UNIQUE NOT NULL,
    name_es VARCHAR(100) NOT NULL,
    export_type export_type_enum NOT NULL,
    export_format VARCHAR(20) NOT NULL DEFAULT 'csv',

    -- Configuration du template
    config JSONB NOT NULL DEFAULT '{}',

    -- Colonnes a inclure (ordre et mapping)
    columns_config JSONB NOT NULL,

    -- Metadonnees
    description_es TEXT,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

COMMENT ON TABLE export_templates IS
'Templates predefinies pour les exports (colonnes, format, mapping)';
COMMENT ON COLUMN export_templates.columns_config IS
'Configuration des colonnes: [{source, target, transform, format}]';

-- ============================================================================
-- SEED DATA: Templates d'export
-- ============================================================================

INSERT INTO export_templates (code, name_es, export_type, export_format, columns_config, description_es) VALUES
(
    'SAGE_X3_STANDARD',
    'Export SAGE X3 Standard',
    'sage_x3',
    'csv',
    '[
        {"source": "completed_at", "target": "DATE", "format": "YYYYMMDD"},
        {"source": "payment_reference", "target": "PIECE", "transform": "uppercase"},
        {"source": "journal_code", "target": "JOURNAL", "default": "TRS"},
        {"source": "account_debit", "target": "COMPTE_D"},
        {"source": "account_credit", "target": "COMPTE_C"},
        {"source": "total_amount", "target": "MONTANT", "format": "decimal_2"},
        {"source": "currency", "target": "DEVISE"},
        {"source": "description", "target": "LIBELLE", "max_length": 50}
    ]'::jsonb,
    'Export standard pour integration SAGE X3 - Journal Tresorerie'
),
(
    'MINISTRY_MONTHLY',
    'Rapport Ministeriel Mensuel',
    'ministry_report',
    'pdf',
    '[
        {"section": "header", "fields": ["period", "ministry_name", "total_collected"]},
        {"section": "summary", "fields": ["by_service", "by_payment_method"]},
        {"section": "detail", "fields": ["date", "reference", "service", "amount", "status"]}
    ]'::jsonb,
    'Rapport mensuel PDF pour les ministeres'
),
(
    'RECONCILIATION_DAILY',
    'Reconciliation Journaliere',
    'reconciliation',
    'xlsx',
    '[
        {"source": "bank_reference", "target": "Ref Bancaire"},
        {"source": "payment_reference", "target": "Ref Paiement"},
        {"source": "amount", "target": "Montant"},
        {"source": "bank_transaction_date", "target": "Date Banque"},
        {"source": "reconciled_at", "target": "Date Reconciliation"},
        {"source": "status", "target": "Statut"}
    ]'::jsonb,
    'Export journalier pour verification reconciliation'
);

-- ============================================================================
-- FONCTION: Generation numero export
-- ============================================================================

CREATE OR REPLACE FUNCTION generate_export_filename(
    p_export_type export_type_enum,
    p_period_start DATE,
    p_period_end DATE,
    p_format VARCHAR
) RETURNS VARCHAR AS $$
DECLARE
    v_prefix VARCHAR;
    v_timestamp VARCHAR;
BEGIN
    -- Prefix selon type
    v_prefix := CASE p_export_type
        WHEN 'sage_x3' THEN 'SAGE_TRS'
        WHEN 'ministry_report' THEN 'RPT_MIN'
        WHEN 'bank_central' THEN 'BEAC'
        WHEN 'audit_report' THEN 'AUDIT'
        WHEN 'reconciliation' THEN 'RECON'
        ELSE 'EXPORT'
    END;

    v_timestamp := TO_CHAR(NOW(), 'YYYYMMDD_HH24MI');

    RETURN v_prefix || '_' ||
           TO_CHAR(p_period_start, 'YYYYMMDD') || '_' ||
           TO_CHAR(p_period_end, 'YYYYMMDD') || '_' ||
           v_timestamp || '.' || p_format;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- TRIGGER: Mise a jour automatique
-- ============================================================================

CREATE OR REPLACE FUNCTION update_export_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    -- Si passage a completed, enregistrer completed_at
    IF NEW.status = 'completed' AND OLD.status != 'completed' THEN
        NEW.completed_at = NOW();
    END IF;

    -- Si passage a processing, enregistrer started_at
    IF NEW.status = 'processing' AND OLD.status = 'pending' THEN
        NEW.started_at = NOW();
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_export_status_change
    BEFORE UPDATE ON treasury_exports
    FOR EACH ROW
    WHEN (OLD.status IS DISTINCT FROM NEW.status)
    EXECUTE FUNCTION update_export_timestamp();

-- ============================================================================
-- VUE: Exports recents avec statistiques
-- ============================================================================

CREATE OR REPLACE VIEW v_recent_exports AS
SELECT
    te.id,
    te.export_type,
    te.export_format,
    te.period_start,
    te.period_end,
    te.status,
    te.total_records,
    te.total_amount,
    te.file_name,
    te.file_size_bytes,
    te.requested_at,
    te.completed_at,
    te.download_count,
    u.full_name as requested_by_name,
    EXTRACT(EPOCH FROM (te.completed_at - te.started_at)) as processing_seconds
FROM treasury_exports te
LEFT JOIN users u ON u.id = te.requested_by
WHERE te.requested_at >= CURRENT_DATE - INTERVAL '30 days'
ORDER BY te.requested_at DESC;

COMMENT ON VIEW v_recent_exports IS
'Exports des 30 derniers jours avec info utilisateur';

-- ============================================================================
-- PERMISSIONS
-- ============================================================================

INSERT INTO permissions (name, resource, action, description, is_critical, module_name) VALUES
('treasury.exports.view', 'treasury_exports', 'view', 'Ver historial de exports', false, 'treasury'),
('treasury.exports.create', 'treasury_exports', 'create', 'Generar nuevos exports comptables', false, 'treasury'),
('treasury.exports.download', 'treasury_exports', 'download', 'Descargar ficheros de export', false, 'treasury')
ON CONFLICT (name) DO NOTHING;

-- ============================================================================
-- VERIFICATION
-- ============================================================================

SELECT
    table_name,
    (SELECT COUNT(*) FROM information_schema.columns WHERE table_name = t.table_name) as columns_count
FROM information_schema.tables t
WHERE table_schema = 'public'
  AND table_name IN ('treasury_exports', 'export_templates')
ORDER BY table_name;
