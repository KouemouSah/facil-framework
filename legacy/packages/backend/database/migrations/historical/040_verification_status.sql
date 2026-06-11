-- Migration: 040_verification_status.sql
-- Description: Add verification status system for external document validation
-- Author: Claude Code
-- Date: 2025-01-09

-- ============================================================================
-- 1. CREATE ENUM: verification_status_enum
-- ============================================================================

DO $$ BEGIN
    CREATE TYPE verification_status_enum AS ENUM (
        'pending',              -- Not yet verified
        'in_progress',          -- Verification running
        'verified',             -- All identifiers found in verified_identifiers
        'partial_verification', -- Some verified, some not found
        'not_found',            -- No identifiers found in verified_identifiers
        'verified_manually',    -- Agent manually verified
        'verification_failed'   -- System error during verification
    );
EXCEPTION
    WHEN duplicate_object THEN NULL;
END $$;

COMMENT ON TYPE verification_status_enum IS 'Status of external document verification';

-- ============================================================================
-- 2. ADD COLUMNS TO service_requests
-- ============================================================================

ALTER TABLE service_requests
ADD COLUMN IF NOT EXISTS verification_status verification_status_enum DEFAULT 'pending';

ALTER TABLE service_requests
ADD COLUMN IF NOT EXISTS verification_details JSONB DEFAULT '{}';

COMMENT ON COLUMN service_requests.verification_status IS 'Status of external identifier verification';
COMMENT ON COLUMN service_requests.verification_details IS 'Details per document type: {dip: {verified: bool, source: string}, ...}';

-- Index for filtering by verification status (agents need to see not_found quickly)
CREATE INDEX IF NOT EXISTS idx_sr_verification_status
ON service_requests(verification_status)
WHERE verification_status IN ('not_found', 'partial_verification', 'verification_failed');

-- ============================================================================
-- 3. CREATE TABLE: verification_queue (database-backed queue for reliability)
-- ============================================================================

CREATE TABLE IF NOT EXISTS verification_queue (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    service_request_id UUID NOT NULL REFERENCES service_requests(id) ON DELETE CASCADE,
    status VARCHAR(20) DEFAULT 'pending',
    retry_count INTEGER DEFAULT 0,
    max_retries INTEGER DEFAULT 3,
    next_retry_at TIMESTAMPTZ DEFAULT NOW(),
    error_message TEXT,
    partial_results JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,

    CONSTRAINT vq_valid_status CHECK (status IN ('pending', 'processing', 'completed', 'failed'))
);

COMMENT ON TABLE verification_queue IS 'Durable queue for verification processing with retry support';
COMMENT ON COLUMN verification_queue.partial_results IS 'Store partial results between retries';
COMMENT ON COLUMN verification_queue.next_retry_at IS 'When to retry failed items (exponential backoff)';

-- Index for polling pending items efficiently
CREATE INDEX IF NOT EXISTS idx_vq_pending
ON verification_queue(next_retry_at)
WHERE status IN ('pending', 'failed') AND retry_count < max_retries;

-- Index for finding queue items by request
CREATE INDEX IF NOT EXISTS idx_vq_request
ON verification_queue(service_request_id);

-- ============================================================================
-- 4. ADD KEY VERSIONING TO verified_identifiers
-- ============================================================================

ALTER TABLE verified_identifiers
ADD COLUMN IF NOT EXISTS encryption_key_version SMALLINT DEFAULT 1;

COMMENT ON COLUMN verified_identifiers.encryption_key_version IS 'Version of encryption key used, for future key rotation';

-- ============================================================================
-- 5. CREATE TABLE: document_verification_config (configurable mapping)
-- ============================================================================

CREATE TABLE IF NOT EXISTS document_verification_config (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_code VARCHAR(50) NOT NULL,
    identifier_type identifier_type_enum NOT NULL,
    extraction_paths TEXT[] NOT NULL,
    source verification_source_enum NOT NULL,
    is_required BOOLEAN DEFAULT TRUE,
    normalization_regex VARCHAR(100),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE(document_code, identifier_type)
);

COMMENT ON TABLE document_verification_config IS 'Configurable mapping: document_code -> identifier_type -> extraction paths';
COMMENT ON COLUMN document_verification_config.document_code IS 'Document code from service_request_documents (e.g., dip_gq, pasaporte_gq)';
COMMENT ON COLUMN document_verification_config.identifier_type IS 'Type of identifier to verify (dni, pasaporte, etc.)';
COMMENT ON COLUMN document_verification_config.extraction_paths IS 'JSON paths to extract identifier from extraction_data';
COMMENT ON COLUMN document_verification_config.is_required IS 'If true, verification failure affects overall status';
COMMENT ON COLUMN document_verification_config.normalization_regex IS 'Regex pattern for validating/normalizing identifier format';

-- Index for active configs lookup
CREATE INDEX IF NOT EXISTS idx_dvc_active
ON document_verification_config(document_code)
WHERE is_active = TRUE;

-- Trigger for updated_at
CREATE OR REPLACE FUNCTION update_dvc_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_dvc_updated_at ON document_verification_config;
CREATE TRIGGER trg_dvc_updated_at
    BEFORE UPDATE ON document_verification_config
    FOR EACH ROW
    EXECUTE FUNCTION update_dvc_updated_at();

-- ============================================================================
-- 6. SEED INITIAL CONFIGURATIONS
-- ============================================================================

INSERT INTO document_verification_config (document_code, identifier_type, extraction_paths, source, is_required, normalization_regex) VALUES
-- ==========================================================================
-- CNEDOGE documents (DIP, Pasaporte, Permiso Residencia)
-- Based on: dip_gq.json, pasaporte_gq.json, permiso_residencia_gq.json
-- ==========================================================================
('dip_gq', 'dni', ARRAY['documento.numero_dip', 'titular.numero_dip'], 'cnedoge', TRUE, '^[0-9]{9}$'),
('pasaporte_gq', 'pasaporte', ARRAY['documento.numero_pasaporte', 'titular.numero_dip'], 'cnedoge', TRUE, '^[A-Z]{2}[0-9]{6,7}$'),

-- Permiso Residencia: identifier is NIE (Numero de Identificacion de Extranjero)
-- Schema: permiso_residencia_gq.json -> documento.numero_nie
('permiso_residencia_gq', 'permiso_residencia', ARRAY['documento.numero_nie', 'numero_nie'], 'cnedoge', TRUE, '^[A-Z][0-9]{8}$'),

-- ==========================================================================
-- HACIENDA documents (NIF - Tax ID)
-- Based on: certificado_nif_gq.json -> empresa.nif (format: 03354WC-23)
-- ==========================================================================
('certificado_nif_gq', 'nif', ARRAY['empresa.nif', 'nif'], 'hacienda', TRUE, '^[0-9]{5}[A-Z]{2}-[0-9]{2}$'),

-- ==========================================================================
-- TRAFICO documents (Vehiculos)
-- Based on: cuve_gq.json, certificado_conducir_gq.json, itv_gq.json, permiso_circulacion_gq.json
-- ==========================================================================

-- CUVE: identifier is numero_referencia (format: RIL24007009)
-- Schema: cuve_gq.json -> documento.numero_referencia
('cuve_gq', 'cuve', ARRAY['documento.numero_referencia', 'vehiculo.matricula'], 'trafico', TRUE, '^[A-Z]{3}[0-9]{8}$'),

-- Matricula vehiculo: from CUVE or Permiso Circulacion
-- Schema: cuve_gq.json -> vehiculo.matricula, permiso_circulacion_gq.json -> vehiculo.matricula
('permiso_circulacion_gq', 'matricula_vehiculo', ARRAY['vehiculo.matricula', 'matricula'], 'trafico', TRUE, '^[A-Z]{2}-[0-9]{3}-[A-Z0-9]{1,2}$'),

-- Certificado Conducir: identifier is reg_numero (format: V106)
-- Schema: certificado_conducir_gq.json -> documento.reg_numero + titular.numero_identificacion (DIP/NIE)
('certificado_conducir_gq', 'certificado_conducir', ARRAY['documento.reg_numero', 'titular.numero_identificacion'], 'trafico', TRUE, NULL),

-- ITV: identifier is numero_serie (format: R.I.2023 14707)
-- Schema: itv_gq.json -> documento.numero_serie
('itv_gq', 'permiso_circulacion', ARRAY['documento.numero_serie', 'vehiculo.matricula', 'vehiculo.numero_bastidor'], 'trafico', FALSE, NULL),

-- ==========================================================================
-- REGISTRO CIVIL documents
-- Based on: certificado_nacimiento_gq.json, declaracion_nacimiento_gq.json
-- ==========================================================================
('certificado_nacimiento_gq', 'registro_civil', ARRAY['documento.numero_acta', 'numero_acta', 'documento.numero_registro'], 'registro_civil', FALSE, NULL),
('declaracion_nacimiento_gq', 'registro_civil', ARRAY['documento.numero_registro', 'numero_registro'], 'registro_civil', FALSE, NULL),

-- ==========================================================================
-- ORNC documents (Contratos)
-- Based on: contrato_onrc_gq.json -> parte_contratista.nif_contratista
-- ==========================================================================
('contrato_onrc_gq', 'contrato_ornc', ARRAY['parte_contratista.nif_contratista', 'documento.numero_contrato'], 'ornc', TRUE, '^[0-9]{5}[A-Z]{2}-[0-9]{2}$')

ON CONFLICT (document_code, identifier_type) DO UPDATE SET
    extraction_paths = EXCLUDED.extraction_paths,
    source = EXCLUDED.source,
    is_required = EXCLUDED.is_required,
    normalization_regex = EXCLUDED.normalization_regex,
    is_active = TRUE,
    updated_at = NOW();

-- ============================================================================
-- 7. CREATE FUNCTION: queue_verification
-- ============================================================================

CREATE OR REPLACE FUNCTION queue_verification(p_request_id UUID)
RETURNS UUID AS $$
DECLARE
    v_queue_id UUID;
BEGIN
    -- Insert into queue (or update if exists)
    INSERT INTO verification_queue (service_request_id, status, retry_count, next_retry_at)
    VALUES (p_request_id, 'pending', 0, NOW())
    ON CONFLICT (service_request_id) DO UPDATE SET
        status = 'pending',
        retry_count = 0,
        next_retry_at = NOW(),
        error_message = NULL,
        started_at = NULL,
        completed_at = NULL
    RETURNING id INTO v_queue_id;

    -- Update service_request status
    UPDATE service_requests
    SET verification_status = 'in_progress',
        updated_at = NOW()
    WHERE id = p_request_id;

    RETURN v_queue_id;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION queue_verification IS 'Add a service request to the verification queue';

-- Add unique constraint for queue (one active item per request)
ALTER TABLE verification_queue
ADD CONSTRAINT uq_vq_request UNIQUE (service_request_id);

-- ============================================================================
-- 8. CREATE FUNCTION: process_verification_queue
-- ============================================================================

CREATE OR REPLACE FUNCTION get_pending_verifications(p_limit INTEGER DEFAULT 10)
RETURNS TABLE (
    queue_id UUID,
    service_request_id UUID,
    retry_count INTEGER,
    partial_results JSONB
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        vq.id AS queue_id,
        vq.service_request_id,
        vq.retry_count,
        vq.partial_results
    FROM verification_queue vq
    WHERE vq.status IN ('pending', 'failed')
      AND vq.retry_count < vq.max_retries
      AND vq.next_retry_at <= NOW()
    ORDER BY vq.next_retry_at ASC
    LIMIT p_limit
    FOR UPDATE SKIP LOCKED;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION get_pending_verifications IS 'Get pending verification items for processing (with locking)';

-- ============================================================================
-- 9. CREATE FUNCTION: mark_verification_result
-- ============================================================================

CREATE OR REPLACE FUNCTION mark_verification_result(
    p_queue_id UUID,
    p_status VARCHAR(20),
    p_error_message TEXT DEFAULT NULL,
    p_partial_results JSONB DEFAULT NULL
)
RETURNS VOID AS $$
DECLARE
    v_request_id UUID;
    v_retry_count INTEGER;
    v_new_retry_at TIMESTAMPTZ;
BEGIN
    -- Get current state
    SELECT service_request_id, retry_count
    INTO v_request_id, v_retry_count
    FROM verification_queue
    WHERE id = p_queue_id;

    IF p_status = 'failed' THEN
        -- Calculate exponential backoff: 5 * 2^retry minutes
        v_new_retry_at := NOW() + (INTERVAL '5 minutes' * POWER(2, v_retry_count));

        UPDATE verification_queue SET
            status = 'failed',
            retry_count = retry_count + 1,
            next_retry_at = v_new_retry_at,
            error_message = p_error_message,
            partial_results = COALESCE(p_partial_results, partial_results)
        WHERE id = p_queue_id;

        -- Update service_request if max retries reached
        IF v_retry_count + 1 >= 3 THEN
            UPDATE service_requests SET
                verification_status = 'verification_failed',
                verification_details = jsonb_build_object('error', p_error_message),
                updated_at = NOW()
            WHERE id = v_request_id;
        END IF;

    ELSIF p_status = 'completed' THEN
        UPDATE verification_queue SET
            status = 'completed',
            completed_at = NOW(),
            partial_results = COALESCE(p_partial_results, partial_results)
        WHERE id = p_queue_id;

    ELSIF p_status = 'processing' THEN
        UPDATE verification_queue SET
            status = 'processing',
            started_at = NOW()
        WHERE id = p_queue_id;
    END IF;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION mark_verification_result IS 'Update verification queue item status with exponential backoff on failure';

-- ============================================================================
-- 10. CREATE VIEW: v_verification_dashboard
-- ============================================================================

CREATE OR REPLACE VIEW v_verification_dashboard AS
SELECT
    sr.id AS request_id,
    sr.reference AS request_reference,
    sr.workflow_code,
    sr.verification_status,
    sr.verification_details,
    sr.created_at AS request_created_at,
    vq.id AS queue_id,
    vq.status AS queue_status,
    vq.retry_count,
    vq.error_message,
    vq.next_retry_at,
    u.full_name AS user_name,
    u.email AS user_email
FROM service_requests sr
LEFT JOIN verification_queue vq ON sr.id = vq.service_request_id
LEFT JOIN users u ON sr.user_id = u.id
WHERE sr.verification_status != 'pending'
   OR vq.id IS NOT NULL
ORDER BY sr.created_at DESC;

COMMENT ON VIEW v_verification_dashboard IS 'Dashboard view for monitoring verification status';

-- ============================================================================
-- 11. CREATE VIEW: v_verification_stats
-- ============================================================================

CREATE OR REPLACE VIEW v_verification_stats AS
SELECT
    verification_status,
    COUNT(*) AS count,
    COUNT(*) FILTER (WHERE created_at >= NOW() - INTERVAL '24 hours') AS last_24h,
    COUNT(*) FILTER (WHERE created_at >= NOW() - INTERVAL '7 days') AS last_7d
FROM service_requests
WHERE status NOT IN ('DRAFT')
GROUP BY verification_status;

COMMENT ON VIEW v_verification_stats IS 'Statistics for verification status distribution';

-- ============================================================================
-- 12. ADD PERMISSIONS
-- ============================================================================

INSERT INTO permissions (name, resource, action, description, module_name)
VALUES
    ('identifiers.import', 'identifiers', 'import', 'Import verified identifiers from external sources', 'verified_identifiers'),
    ('identifiers.stats', 'identifiers', 'stats', 'View verified identifiers statistics', 'verified_identifiers'),
    ('identifiers.config', 'identifiers', 'config', 'Manage document verification configuration', 'verified_identifiers'),
    ('requests.verify', 'requests', 'verify', 'Manually verify service requests', 'service_requests'),
    ('requests.reverify', 'requests', 'reverify', 'Trigger re-verification of service requests', 'service_requests')
ON CONFLICT (name) DO NOTHING;

-- Grant to admin role
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM roles r, permissions p
WHERE r.name = 'admin'
  AND p.name IN ('identifiers.import', 'identifiers.stats', 'identifiers.config', 'requests.verify', 'requests.reverify')
ON CONFLICT DO NOTHING;

-- Grant verify permissions to agents
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM roles r, permissions p
WHERE r.name IN ('dgi_agent', 'ministry_agent')
  AND p.name IN ('requests.verify', 'requests.reverify')
ON CONFLICT DO NOTHING;

-- ============================================================================
-- MIGRATION COMPLETE
-- ============================================================================

DO $$
BEGIN
    RAISE NOTICE 'Migration 040_verification_status.sql completed successfully';
    RAISE NOTICE 'Tables created: verification_queue, document_verification_config';
    RAISE NOTICE 'Columns added to service_requests: verification_status, verification_details';
    RAISE NOTICE 'Column added to verified_identifiers: encryption_key_version';
    RAISE NOTICE 'Functions created: queue_verification, get_pending_verifications, mark_verification_result';
    RAISE NOTICE 'Views created: v_verification_dashboard, v_verification_stats';
END $$;
