-- Migration 076: Fix document_verification_config to match actual document_codes
-- Date: 2026-01-29
-- Purpose: Align document_codes and extraction_paths with real data structure

BEGIN;

-- ============================================================================
-- 1. Fix CNEDOGE document codes (dip_gq → dip, pasaporte_gq → pasaporte_antiguo)
-- ============================================================================

-- Update DIP configuration
UPDATE document_verification_config
SET
    document_code = 'dip',
    extraction_paths = ARRAY['numero_dip'],  -- Direct path in form_data.dip object
    updated_at = NOW()
WHERE document_code = 'dip_gq';

-- Update Pasaporte configuration
UPDATE document_verification_config
SET
    document_code = 'pasaporte_antiguo',
    extraction_paths = ARRAY['numero_pasaporte'],  -- Direct path in form_data.pasaporte_antiguo
    updated_at = NOW()
WHERE document_code = 'pasaporte_gq';

-- Update Permiso Residencia
UPDATE document_verification_config
SET
    document_code = 'permiso_residencia',
    extraction_paths = ARRAY['numero_nie', 'numero_residencia'],
    updated_at = NOW()
WHERE document_code = 'permiso_residencia_gq';

-- ============================================================================
-- 2. Add expiration_path column for automatic expiration date extraction
-- ============================================================================

ALTER TABLE document_verification_config
ADD COLUMN IF NOT EXISTS expiration_path VARCHAR(255);

COMMENT ON COLUMN document_verification_config.expiration_path IS
'JSON path to expiration date in form_data nested object';

-- Set expiration paths for existing configs
UPDATE document_verification_config SET expiration_path = 'fecha_expiracion'
WHERE document_code = 'dip';

UPDATE document_verification_config SET expiration_path = 'fecha_expiracion'
WHERE document_code = 'pasaporte_antiguo';

UPDATE document_verification_config SET expiration_path = 'fecha_expiracion'
WHERE document_code = 'permiso_residencia';

-- ============================================================================
-- 3. Add link to workflow_document_requirements for dynamic field discovery
-- ============================================================================

ALTER TABLE document_verification_config
ADD COLUMN IF NOT EXISTS workflow_document_requirement_id UUID REFERENCES workflow_document_requirements(id);

COMMENT ON COLUMN document_verification_config.workflow_document_requirement_id IS
'Link to workflow_document_requirements for dynamic field discovery from extraction schemas';

-- ============================================================================
-- 4. Create view for dynamic field detection in admin UI
-- ============================================================================

CREATE OR REPLACE VIEW v_verification_config_fields AS
SELECT
    dvc.id as config_id,
    dvc.document_code,
    dvc.identifier_type,
    dvc.source,
    dvc.extraction_paths,
    dvc.expiration_path,
    wdr.extraction_schema_key,
    wdr.document_name_es,
    CASE
        WHEN dvc.document_code = 'dip' THEN
            ARRAY['numero_dip', 'id_lateral', 'numero_registro', 'fecha_expiracion', 'fecha_emision']
        WHEN dvc.document_code = 'pasaporte_antiguo' THEN
            ARRAY['numero_pasaporte', 'numero_dip', 'fecha_expiracion', 'fecha_expedicion']
        WHEN dvc.document_code = 'permiso_residencia' THEN
            ARRAY['numero_nie', 'numero_residencia', 'fecha_expiracion']
        ELSE ARRAY[]::VARCHAR[]
    END as available_fields
FROM document_verification_config dvc
LEFT JOIN workflow_document_requirements wdr
    ON wdr.document_code = dvc.document_code
WHERE dvc.is_active = true;

COMMENT ON VIEW v_verification_config_fields IS
'View for admin UI to show available fields per document type for verification configuration';

-- ============================================================================
-- 5. Fix other entity document codes (trafico, hacienda, etc.)
-- ============================================================================

UPDATE document_verification_config
SET
    document_code = 'certificado_conducir',
    extraction_paths = ARRAY['reg_numero', 'numero_identificacion'],
    updated_at = NOW()
WHERE document_code = 'certificado_conducir_gq';

UPDATE document_verification_config
SET
    document_code = 'cuve',
    extraction_paths = ARRAY['numero_referencia', 'matricula'],
    updated_at = NOW()
WHERE document_code = 'cuve_gq';

UPDATE document_verification_config
SET
    document_code = 'itv',
    extraction_paths = ARRAY['numero_serie', 'matricula', 'numero_bastidor'],
    updated_at = NOW()
WHERE document_code = 'itv_gq';

UPDATE document_verification_config
SET
    document_code = 'permiso_circulacion',
    extraction_paths = ARRAY['matricula'],
    updated_at = NOW()
WHERE document_code = 'permiso_circulacion_gq';

UPDATE document_verification_config
SET
    document_code = 'certificado_nif',
    extraction_paths = ARRAY['nif'],
    updated_at = NOW()
WHERE document_code = 'certificado_nif_gq';

UPDATE document_verification_config
SET
    document_code = 'contrato_onrc',
    extraction_paths = ARRAY['numero_contrato', 'nif_contratista'],
    updated_at = NOW()
WHERE document_code = 'contrato_onrc_gq';

UPDATE document_verification_config
SET
    document_code = 'certificado_nacimiento',
    extraction_paths = ARRAY['numero_acta', 'numero_registro'],
    updated_at = NOW()
WHERE document_code = 'certificado_nacimiento_gq';

UPDATE document_verification_config
SET
    document_code = 'declaracion_nacimiento',
    extraction_paths = ARRAY['numero_registro'],
    updated_at = NOW()
WHERE document_code = 'declaracion_nacimiento_gq';

COMMIT;
