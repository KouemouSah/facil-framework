-- Migration: 026_gemini_processing_audit.sql
-- Date: 2025-12-27
-- Description: Table d'audit pour tracer tous les traitements Gemini
-- Author: TaxasGE Development Team
-- Reference: module-gemini-processor.md, module-gemini-risk_simplifie.md

-- ============================================================================
-- 1. CREATE GEMINI_PROCESSING_LOGS TABLE
-- ============================================================================
-- Trace TOUS les appels a Gemini pour audit, debug et analytics

CREATE TABLE IF NOT EXISTS gemini_processing_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Contexte de la demande
    service_request_id UUID REFERENCES service_requests(id) ON DELETE SET NULL,
    document_id UUID REFERENCES service_request_documents(id) ON DELETE SET NULL,
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,

    -- Document traite
    document_code VARCHAR(100),
    document_name VARCHAR(255),
    mime_type VARCHAR(100),
    file_size_bytes INTEGER,

    -- Processeur utilise
    processor VARCHAR(20) NOT NULL DEFAULT 'gemini',
    -- gemini, tesseract, hybrid

    -- Modele Gemini
    gemini_model VARCHAR(100),
    -- gemini-2.0-flash-exp, etc.

    -- Classification
    document_type_detected VARCHAR(100),
    document_category VARCHAR(50),
    -- identity, medical, contract, license, certificate, fiscal

    classification_confidence NUMERIC(5,4),
    -- 0.0000 a 1.0000

    -- Extraction
    extraction_result JSONB DEFAULT '{}',
    -- Structure par blocs: {"bloc_admin": {...}, "bloc_validite": {...}}

    extraction_confidence NUMERIC(5,4),
    fields_extracted INTEGER DEFAULT 0,
    fields_missing INTEGER DEFAULT 0,
    required_fields_present BOOLEAN,

    -- Analyse de risque
    risk_score NUMERIC(5,4),
    risk_level VARCHAR(20),
    -- low, medium, high, critical

    risk_factors JSONB DEFAULT '[]',
    -- ["document_expired", "nif_invalid", ...]

    coherence_valid BOOLEAN,
    coherence_checks_passed TEXT[],
    coherence_checks_failed TEXT[],

    recommendation VARCHAR(30),
    -- auto_approve, manual_review, request_documents, reject

    -- Matching document
    is_match BOOLEAN,
    match_confidence NUMERIC(5,4),
    matched_document_code VARCHAR(100),

    -- Performance
    processing_time_ms INTEGER,
    gemini_latency_ms INTEGER,
    tesseract_latency_ms INTEGER,

    -- Fallback info
    used_fallback BOOLEAN DEFAULT FALSE,
    fallback_reason VARCHAR(255),

    -- Erreurs
    has_error BOOLEAN DEFAULT FALSE,
    error_type VARCHAR(100),
    error_message TEXT,
    error_details JSONB,

    -- Prompt utilise (pour debug/amelioration)
    prompt_template_id VARCHAR(100),
    prompt_version VARCHAR(20),

    -- Tokens utilises (pour monitoring couts)
    input_tokens INTEGER,
    output_tokens INTEGER,
    total_tokens INTEGER,

    -- Schema utilise
    schema_category VARCHAR(50),
    schema_filename VARCHAR(100),

    -- Contexte additionnel
    workflow_code VARCHAR(100),
    solicitud_type VARCHAR(50),
    -- expedicion, renovacion, duplicado

    -- Metadata
    request_metadata JSONB DEFAULT '{}',
    -- ip_address, user_agent, etc.

    -- Audit
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Contraintes
    CONSTRAINT valid_confidence CHECK (
        (classification_confidence IS NULL OR (classification_confidence >= 0 AND classification_confidence <= 1)) AND
        (extraction_confidence IS NULL OR (extraction_confidence >= 0 AND extraction_confidence <= 1)) AND
        (risk_score IS NULL OR (risk_score >= 0 AND risk_score <= 1))
    )
);

-- ============================================================================
-- 2. CREATE INDEXES
-- ============================================================================

-- Recherche par service_request
CREATE INDEX IF NOT EXISTS idx_gpl_service_request ON gemini_processing_logs(service_request_id);

-- Recherche par document
CREATE INDEX IF NOT EXISTS idx_gpl_document_id ON gemini_processing_logs(document_id);

-- Recherche par utilisateur
CREATE INDEX IF NOT EXISTS idx_gpl_user_id ON gemini_processing_logs(user_id);

-- Recherche par date
CREATE INDEX IF NOT EXISTS idx_gpl_created_at ON gemini_processing_logs(created_at DESC);

-- Recherche par type de document
CREATE INDEX IF NOT EXISTS idx_gpl_document_type ON gemini_processing_logs(document_type_detected);

-- Recherche par categorie
CREATE INDEX IF NOT EXISTS idx_gpl_category ON gemini_processing_logs(document_category);

-- Recherche par workflow
CREATE INDEX IF NOT EXISTS idx_gpl_workflow ON gemini_processing_logs(workflow_code);

-- Recherche par processeur (pour stats fallback)
CREATE INDEX IF NOT EXISTS idx_gpl_processor ON gemini_processing_logs(processor);

-- Recherche par erreurs (pour debug)
CREATE INDEX IF NOT EXISTS idx_gpl_errors ON gemini_processing_logs(has_error) WHERE has_error = TRUE;

-- Recherche par recommendation (pour stats)
CREATE INDEX IF NOT EXISTS idx_gpl_recommendation ON gemini_processing_logs(recommendation);

-- Index composite pour dashboard analytics
CREATE INDEX IF NOT EXISTS idx_gpl_analytics ON gemini_processing_logs(created_at DESC, document_category, recommendation);

-- ============================================================================
-- 3. CREATE VIEW FOR PROCESSING STATISTICS
-- ============================================================================

CREATE OR REPLACE VIEW v_gemini_processing_stats AS
SELECT
    DATE(created_at) AS date,
    document_category,
    processor,
    COUNT(*) AS total_processings,
    COUNT(*) FILTER (WHERE is_match = TRUE) AS successful_matches,
    COUNT(*) FILTER (WHERE has_error = TRUE) AS errors,
    COUNT(*) FILTER (WHERE used_fallback = TRUE) AS fallbacks,
    AVG(processing_time_ms) AS avg_processing_time_ms,
    AVG(gemini_latency_ms) AS avg_gemini_latency_ms,
    AVG(classification_confidence) AS avg_classification_confidence,
    AVG(extraction_confidence) AS avg_extraction_confidence,
    AVG(risk_score) AS avg_risk_score,
    COUNT(*) FILTER (WHERE recommendation = 'auto_approve') AS auto_approvals,
    COUNT(*) FILTER (WHERE recommendation = 'manual_review') AS manual_reviews,
    COUNT(*) FILTER (WHERE recommendation = 'reject') AS rejections,
    SUM(total_tokens) AS total_tokens_used
FROM gemini_processing_logs
WHERE created_at >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY DATE(created_at), document_category, processor
ORDER BY date DESC, document_category;

COMMENT ON VIEW v_gemini_processing_stats IS 'Statistiques de traitement Gemini sur les 30 derniers jours';

-- ============================================================================
-- 4. CREATE VIEW FOR ERROR ANALYSIS
-- ============================================================================

CREATE OR REPLACE VIEW v_gemini_errors AS
SELECT
    id,
    created_at,
    document_category,
    document_type_detected,
    workflow_code,
    processor,
    error_type,
    error_message,
    error_details,
    processing_time_ms,
    used_fallback,
    fallback_reason
FROM gemini_processing_logs
WHERE has_error = TRUE
ORDER BY created_at DESC;

COMMENT ON VIEW v_gemini_errors IS 'Vue des erreurs de traitement Gemini pour debug';

-- ============================================================================
-- 5. CREATE VIEW FOR RISK ANALYSIS TRENDS
-- ============================================================================

CREATE OR REPLACE VIEW v_risk_analysis_trends AS
SELECT
    DATE(created_at) AS date,
    workflow_code,
    COUNT(*) AS total_analyses,
    AVG(risk_score) AS avg_risk_score,
    COUNT(*) FILTER (WHERE risk_level = 'low') AS low_risk,
    COUNT(*) FILTER (WHERE risk_level = 'medium') AS medium_risk,
    COUNT(*) FILTER (WHERE risk_level = 'high') AS high_risk,
    COUNT(*) FILTER (WHERE risk_level = 'critical') AS critical_risk,
    COUNT(*) FILTER (WHERE coherence_valid = TRUE) AS coherent_documents,
    COUNT(*) FILTER (WHERE coherence_valid = FALSE) AS incoherent_documents,
    ARRAY_AGG(DISTINCT rf.factor) FILTER (WHERE rf.factor IS NOT NULL) AS common_risk_factors
FROM gemini_processing_logs
LEFT JOIN LATERAL (
    SELECT jsonb_array_elements_text(risk_factors) AS factor
    WHERE risk_factors IS NOT NULL AND risk_factors != '[]'::jsonb
) rf ON TRUE
WHERE created_at >= CURRENT_DATE - INTERVAL '30 days'
  AND risk_score IS NOT NULL
GROUP BY DATE(created_at), workflow_code
ORDER BY date DESC;

COMMENT ON VIEW v_risk_analysis_trends IS 'Tendances d''analyse de risque par workflow';

-- ============================================================================
-- 6. CREATE FUNCTION FOR LOGGING
-- ============================================================================

CREATE OR REPLACE FUNCTION log_gemini_processing(
    p_service_request_id UUID,
    p_document_id UUID,
    p_user_id UUID,
    p_document_code VARCHAR(100),
    p_mime_type VARCHAR(100),
    p_file_size INTEGER,
    p_processor VARCHAR(20),
    p_gemini_model VARCHAR(100),
    p_document_type VARCHAR(100),
    p_document_category VARCHAR(50),
    p_classification_confidence NUMERIC,
    p_extraction_result JSONB,
    p_extraction_confidence NUMERIC,
    p_fields_extracted INTEGER,
    p_fields_missing INTEGER,
    p_risk_score NUMERIC,
    p_risk_level VARCHAR(20),
    p_risk_factors JSONB,
    p_coherence_valid BOOLEAN,
    p_recommendation VARCHAR(30),
    p_is_match BOOLEAN,
    p_processing_time_ms INTEGER,
    p_gemini_latency_ms INTEGER,
    p_used_fallback BOOLEAN,
    p_fallback_reason VARCHAR(255),
    p_has_error BOOLEAN,
    p_error_type VARCHAR(100),
    p_error_message TEXT,
    p_workflow_code VARCHAR(100),
    p_input_tokens INTEGER DEFAULT NULL,
    p_output_tokens INTEGER DEFAULT NULL
)
RETURNS UUID AS $$
DECLARE
    v_log_id UUID;
BEGIN
    INSERT INTO gemini_processing_logs (
        service_request_id, document_id, user_id,
        document_code, mime_type, file_size_bytes,
        processor, gemini_model,
        document_type_detected, document_category,
        classification_confidence, extraction_result, extraction_confidence,
        fields_extracted, fields_missing,
        risk_score, risk_level, risk_factors, coherence_valid,
        recommendation, is_match,
        processing_time_ms, gemini_latency_ms,
        used_fallback, fallback_reason,
        has_error, error_type, error_message,
        workflow_code,
        input_tokens, output_tokens,
        total_tokens
    ) VALUES (
        p_service_request_id, p_document_id, p_user_id,
        p_document_code, p_mime_type, p_file_size,
        p_processor, p_gemini_model,
        p_document_type, p_document_category,
        p_classification_confidence, p_extraction_result, p_extraction_confidence,
        p_fields_extracted, p_fields_missing,
        p_risk_score, p_risk_level, p_risk_factors, p_coherence_valid,
        p_recommendation, p_is_match,
        p_processing_time_ms, p_gemini_latency_ms,
        p_used_fallback, p_fallback_reason,
        p_has_error, p_error_type, p_error_message,
        p_workflow_code,
        p_input_tokens, p_output_tokens,
        COALESCE(p_input_tokens, 0) + COALESCE(p_output_tokens, 0)
    )
    RETURNING id INTO v_log_id;

    RETURN v_log_id;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION log_gemini_processing IS 'Fonction helper pour enregistrer un log de traitement Gemini';

-- ============================================================================
-- 7. ADD COMMENTS
-- ============================================================================

COMMENT ON TABLE gemini_processing_logs IS 'Audit trail de tous les traitements Gemini (classification, extraction, risk)';
COMMENT ON COLUMN gemini_processing_logs.processor IS 'Processeur utilise: gemini, tesseract, hybrid';
COMMENT ON COLUMN gemini_processing_logs.document_category IS 'Categorie schema: identity, medical, contract, etc.';
COMMENT ON COLUMN gemini_processing_logs.extraction_result IS 'Resultat extraction structure par blocs JSON';
COMMENT ON COLUMN gemini_processing_logs.risk_factors IS 'Liste des facteurs de risque detectes';
COMMENT ON COLUMN gemini_processing_logs.coherence_valid IS 'Resultat des verifications de coherence';
COMMENT ON COLUMN gemini_processing_logs.recommendation IS 'Recommendation: auto_approve, manual_review, request_documents, reject';
COMMENT ON COLUMN gemini_processing_logs.used_fallback IS 'TRUE si Tesseract fallback a ete utilise';
COMMENT ON COLUMN gemini_processing_logs.total_tokens IS 'Total tokens Gemini utilises (pour monitoring couts)';

-- ============================================================================
-- 8. CREATE RETENTION POLICY (Optional - via pg_cron si disponible)
-- ============================================================================

-- Cette fonction peut etre appelee periodiquement pour purger les vieux logs
CREATE OR REPLACE FUNCTION cleanup_old_gemini_logs(
    p_retention_days INTEGER DEFAULT 90
)
RETURNS INTEGER AS $$
DECLARE
    v_deleted INTEGER;
BEGIN
    DELETE FROM gemini_processing_logs
    WHERE created_at < CURRENT_DATE - (p_retention_days || ' days')::INTERVAL;

    GET DIAGNOSTICS v_deleted = ROW_COUNT;

    RAISE NOTICE 'Deleted % old gemini processing logs (older than % days)', v_deleted, p_retention_days;

    RETURN v_deleted;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION cleanup_old_gemini_logs IS 'Purge les logs Gemini plus vieux que N jours (defaut 90)';

-- ============================================================================
-- END OF MIGRATION
-- ============================================================================
