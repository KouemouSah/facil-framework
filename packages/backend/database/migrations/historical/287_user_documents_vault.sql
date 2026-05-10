-- Migration 287: User Documents Vault + Agent Memory + Permissions
-- Module: "Mes Documents" + Agent IA Enrichi
-- Date: 2026-04-05
-- Ref: .claude/plans/MODULE_MES_DOCUMENTS_AGENT_IA_REPORT_V3.md

BEGIN;

-- ════════════════════════════��══════════════════════════════════
-- 1. TABLE: user_documents — Coffre-fort unifie
-- Source: personal upload | wizard import | platform generated
-- ═══════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS user_documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,

    -- Source du document
    source VARCHAR(30) NOT NULL DEFAULT 'personal'
        CHECK (source IN ('personal', 'wizard_import', 'platform_generated')),

    -- References croisees (PAS de duplication de fichiers)
    source_request_id UUID,
    source_document_id UUID,
    generation_type VARCHAR(50)
        CHECK (generation_type IS NULL OR generation_type IN (
            'payment_receipt', 'request_validation', 'request_summary',
            'appointment_confirmation', 'certificate', 'notification_letter',
            'inspection_report', 'license_dossier'
        )),

    -- Classification (derivee de GeminiDocumentProcessor)
    document_type VARCHAR(100) NOT NULL,
    document_category VARCHAR(50) NOT NULL DEFAULT 'other'
        CHECK (document_category IN (
            'identity', 'vehicle', 'legal', 'financial', 'administrative',
            'medical', 'education', 'photo', 'business', 'employment', 'other'
        )),
    template_code VARCHAR(100),

    -- Fichier (meme Firebase Storage que wizard)
    file_path TEXT NOT NULL,
    file_name VARCHAR(255) NOT NULL,
    file_size_bytes BIGINT NOT NULL CHECK (file_size_bytes >= 0),
    mime_type VARCHAR(100) NOT NULL,
    file_hash VARCHAR(64) NOT NULL,
    thumbnail_path TEXT,

    -- Extraction (meme GeminiDocumentProcessor que wizard)
    extraction_data JSONB DEFAULT '{}'::jsonb,
    extraction_confidence NUMERIC(5,4) CHECK (extraction_confidence IS NULL OR (extraction_confidence >= 0 AND extraction_confidence <= 1)),
    extraction_status VARCHAR(20) DEFAULT 'pending'
        CHECK (extraction_status IN ('pending', 'processing', 'completed', 'failed')),

    -- Informations cles denormalisees (post_process_for_vault)
    document_number VARCHAR(100),
    holder_name VARCHAR(255),
    issue_date DATE,
    expiry_date DATE,
    issuing_authority VARCHAR(255),

    -- Classification details
    classification_method VARCHAR(20) DEFAULT 'manual'
        CHECK (classification_method IN ('manual', 'gemini', 'rules')),
    classification_confidence NUMERIC(5,4),

    -- Organisation utilisateur
    display_name VARCHAR(255),
    notes TEXT,
    is_favorite BOOLEAN DEFAULT FALSE,
    color_label VARCHAR(20),

    -- Statut
    status VARCHAR(20) DEFAULT 'active'
        CHECK (status IN ('active', 'archived', 'expired', 'deleted')),
    is_verified BOOLEAN DEFAULT FALSE,
    verified_at TIMESTAMPTZ,

    -- Versioning
    replaces_document_id UUID REFERENCES user_documents(id) ON DELETE SET NULL,

    -- Documents generes : metadonnees specifiques
    title_es VARCHAR(255),
    title_fr VARCHAR(255),
    title_en VARCHAR(255),
    reference_number VARCHAR(100),
    verification_code VARCHAR(100),
    valid_until TIMESTAMPTZ,

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    archived_at TIMESTAMPTZ,
    deleted_at TIMESTAMPTZ
);

-- Index pour 1M+ users, 8M+ documents
-- Principal : listing documents d'un user
CREATE INDEX idx_ud_user_active ON user_documents(user_id, created_at DESC)
    WHERE status = 'active' AND deleted_at IS NULL;

-- Par source (separations personal / wizard / generated)
CREATE INDEX idx_ud_user_source ON user_documents(user_id, source)
    WHERE deleted_at IS NULL;

-- Par categorie (filtrage frontend)
CREATE INDEX idx_ud_user_category ON user_documents(user_id, document_category)
    WHERE status = 'active' AND deleted_at IS NULL;

-- Expirations (CRON quotidien)
CREATE INDEX idx_ud_expiry ON user_documents(expiry_date)
    WHERE expiry_date IS NOT NULL AND status = 'active' AND deleted_at IS NULL;

-- Deduplication (hash SHA-256)
CREATE INDEX idx_ud_hash ON user_documents(user_id, file_hash);

-- Template code (JOIN workflow_document_requirements)
CREATE INDEX idx_ud_template ON user_documents(template_code)
    WHERE template_code IS NOT NULL;

-- Source document (lien vers service_request_documents)
CREATE INDEX idx_ud_source_doc ON user_documents(source_document_id)
    WHERE source_document_id IS NOT NULL;

-- Full-text search (nom + notes)
CREATE INDEX idx_ud_search ON user_documents USING gin(
    to_tsvector('spanish',
        COALESCE(display_name, '') || ' ' ||
        COALESCE(file_name, '') || ' ' ||
        COALESCE(notes, '') || ' ' ||
        COALESCE(holder_name, '') || ' ' ||
        COALESCE(document_number, '')
    )
) WHERE deleted_at IS NULL;

-- Trigger updated_at
CREATE OR REPLACE FUNCTION update_user_documents_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_user_documents_updated_at
    BEFORE UPDATE ON user_documents
    FOR EACH ROW
    EXECUTE FUNCTION update_user_documents_updated_at();

-- ═══════════════════════════════════════════════════════════════
-- 2. TABLE: user_document_workflow_tags
-- Mapping document → workflows (derive de BD, PAS IA)
-- ═══════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS user_document_workflow_tags (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_document_id UUID NOT NULL REFERENCES user_documents(id) ON DELETE CASCADE,
    workflow_code VARCHAR(100) NOT NULL,
    document_code VARCHAR(100) NOT NULL,
    is_auto_tagged BOOLEAN DEFAULT TRUE,
    relevance_score NUMERIC(5,4) DEFAULT 1.0
        CHECK (relevance_score >= 0 AND relevance_score <= 1),
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    UNIQUE(user_document_id, workflow_code, document_code)
);

CREATE INDEX idx_udwt_doc ON user_document_workflow_tags(user_document_id);
CREATE INDEX idx_udwt_workflow ON user_document_workflow_tags(workflow_code);

-- ═══════════════════════════════════════════════════════════════
-- 3. TABLE: user_document_access_log
-- Audit trail de CHAQUE acces document (OWASP A09)
-- ═══════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS user_document_access_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_document_id UUID NOT NULL REFERENCES user_documents(id) ON DELETE CASCADE,
    accessed_by UUID NOT NULL REFERENCES users(id),
    access_type VARCHAR(30) NOT NULL
        CHECK (access_type IN ('view', 'download', 'share', 'attach', 'print', 'reclassify', 'delete', 'archive', 'upload', 'bulk_archive', 'bulk_delete', 'bulk_download')),
    access_context VARCHAR(100),
    ip_address INET,
    user_agent TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL
);

CREATE INDEX idx_udal_doc ON user_document_access_log(user_document_id, created_at DESC);
CREATE INDEX idx_udal_user ON user_document_access_log(accessed_by, created_at DESC);

-- ═══════════════════════════════════════════════════════════════
-- 4. TABLE: user_document_alerts
-- Alertes expiration + proactives
-- ═══════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS user_document_alerts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    user_document_id UUID REFERENCES user_documents(id) ON DELETE CASCADE,

    alert_type VARCHAR(30) NOT NULL
        CHECK (alert_type IN (
            'expiry_90d', 'expiry_60d', 'expiry_30d', 'expiry_7d', 'expired',
            'renewal_suggestion', 'missing_for_workflow', 'upload_suggestion',
            'quota_80', 'quota_95', 'new_generated', 'request_needs_docs',
            'proactive_preparation'
        )),
    severity VARCHAR(10) NOT NULL
        CHECK (severity IN ('info', 'warning', 'critical')),

    title_es VARCHAR(255) NOT NULL,
    title_fr VARCHAR(255),
    title_en VARCHAR(255),
    message_es TEXT NOT NULL,
    message_fr TEXT,
    message_en TEXT,

    suggested_action VARCHAR(50),
    action_params JSONB DEFAULT '{}'::jsonb,

    is_read BOOLEAN DEFAULT FALSE,
    is_dismissed BOOLEAN DEFAULT FALSE,
    is_actioned BOOLEAN DEFAULT FALSE,

    trigger_date DATE NOT NULL,
    expires_at TIMESTAMPTZ,

    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    read_at TIMESTAMPTZ,
    dismissed_at TIMESTAMPTZ,
    actioned_at TIMESTAMPTZ
);

-- Trigger updated_at for alerts
CREATE TRIGGER trg_user_document_alerts_updated_at
    BEFORE UPDATE ON user_document_alerts
    FOR EACH ROW
    EXECUTE FUNCTION update_user_documents_updated_at();

CREATE INDEX idx_uda_user_active ON user_document_alerts(user_id, is_dismissed, is_read)
    WHERE is_dismissed = FALSE;
CREATE INDEX idx_uda_trigger ON user_document_alerts(trigger_date)
    WHERE is_actioned = FALSE AND is_dismissed = FALSE;

-- ══════════════════════════════════���══════════════════════════��═
-- 5. TABLE: user_agent_memory
-- Memoire comportementale (equivalent MEMORY.md de Claude Code)
-- ═══════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS user_agent_memory (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,

    memory_type VARCHAR(30) NOT NULL
        CHECK (memory_type IN ('preference', 'behavioral', 'correction', 'capability', 'context')),

    content TEXT NOT NULL,
    content_key VARCHAR(100),
    content_value JSONB,

    -- Scoring
    confidence NUMERIC(3,2) DEFAULT 0.50
        CHECK (confidence >= 0 AND confidence <= 1),
    confirmation_count INTEGER DEFAULT 0,
    rejection_count INTEGER DEFAULT 0,

    -- Source d'apprentissage
    learned_from VARCHAR(50) NOT NULL
        CHECK (learned_from IN (
            'explicit_feedback', 'action_confirmed', 'action_rejected',
            'preference_detected', 'pattern_detected', 'conversation_analysis'
        )),
    source_conversation_id UUID,

    -- Lifecycle
    is_active BOOLEAN DEFAULT TRUE,
    last_used_at TIMESTAMPTZ,
    expires_at TIMESTAMPTZ,

    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW() NOT NULL
);

CREATE INDEX idx_uam_user_active ON user_agent_memory(user_id, is_active, confidence DESC)
    WHERE is_active = TRUE;
CREATE UNIQUE INDEX idx_uam_user_key ON user_agent_memory(user_id, content_key)
    WHERE is_active = TRUE AND content_key IS NOT NULL;

-- Trigger updated_at
CREATE TRIGGER trg_user_agent_memory_updated_at
    BEFORE UPDATE ON user_agent_memory
    FOR EACH ROW
    EXECUTE FUNCTION update_user_documents_updated_at();

-- ═══════════════════════════════════════════════════════════════
-- 6. TABLE: user_agent_permissions
-- Permissions autonomie progressive consentie
-- ══════════════════════════════════════════════��════════════════

CREATE TABLE IF NOT EXISTS user_agent_permissions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,

    permission_type VARCHAR(50) NOT NULL
        CHECK (permission_type IN (
            'prepare_renewal', 'prepare_request', 'suggest_appointments',
            'proactive_alerts', 'auto_classify'
        )),
    scope VARCHAR(100),
    level INTEGER DEFAULT 1 CHECK (level IN (1, 2)),

    usage_count INTEGER DEFAULT 0,
    last_used_at TIMESTAMPTZ,

    is_active BOOLEAN DEFAULT TRUE,
    granted_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    revoked_at TIMESTAMPTZ
);

-- Unique constraint with COALESCE requires a unique INDEX (not inline constraint)
CREATE UNIQUE INDEX idx_uap_unique ON user_agent_permissions(user_id, permission_type, COALESCE(scope, '__null__'))
    WHERE is_active = TRUE;

CREATE INDEX idx_uap_user ON user_agent_permissions(user_id, is_active)
    WHERE is_active = TRUE;

-- ════════════════════���══════════════════════════════════════════
-- VERIFICATION
-- ═══════════════════════════════════════════════��═══════════════

-- Verify all tables created
DO $$
DECLARE
    tables_expected TEXT[] := ARRAY[
        'user_documents', 'user_document_workflow_tags',
        'user_document_access_log', 'user_document_alerts',
        'user_agent_memory', 'user_agent_permissions'
    ];
    t TEXT;
BEGIN
    FOREACH t IN ARRAY tables_expected LOOP
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.tables
            WHERE table_schema = 'public' AND table_name = t
        ) THEN
            RAISE EXCEPTION 'Table % was not created!', t;
        END IF;
    END LOOP;
    RAISE NOTICE 'Migration 287: All 6 tables created successfully';
END $$;

COMMIT;
