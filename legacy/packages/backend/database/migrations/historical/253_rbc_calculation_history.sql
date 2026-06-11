-- Migration: 025_rbc_calculation_history.sql
-- Date: 2025-12-27
-- Description: Extensions pour calculation_history + extraction_schemas
-- Author: TaxasGE Development Team
-- Reference: module-rbc-calculator_simplifie.md
-- NOTE: calculation_history existe déjà - on ajoute seulement extraction_schemas

-- ============================================================================
-- NOTE: TABLE calculation_history EXISTE DÉJÀ
-- ============================================================================
-- Structure existante:
--   id UUID, user_id UUID, fiscal_service_code VARCHAR(10),
--   calculation_type VARCHAR(20), input_parameters JSONB,
--   calculated_amount NUMERIC, calculation_details JSONB,
--   saved_for_later BOOLEAN, created_at TIMESTAMPTZ
--
-- On ne la recrée pas, elle est utilisée par le module existant.

-- ============================================================================
-- 1. CREATE EXTRACTION_SCHEMAS TABLE (pour mapping documents -> schemas JSON)
-- ============================================================================
-- Table de référence pour les schemas d'extraction JSON

CREATE TABLE IF NOT EXISTS extraction_schemas (
    id SERIAL PRIMARY KEY,

    -- Identification
    category VARCHAR(50) UNIQUE NOT NULL,
    -- identity, medical, contract, license, certificate, fiscal

    -- Référence au fichier JSON
    schema_filename VARCHAR(100) NOT NULL,
    -- identity_document.json, medical_document.json, etc.

    -- Description
    description TEXT,

    -- Types de documents supportés
    document_types TEXT[] DEFAULT '{}',
    -- {'DNI_CNI', 'PASSPORT', 'PERMISO_RESIDENCIA'}

    -- Workflows associés
    workflow_codes TEXT[] DEFAULT '{}',
    -- {'pasaporte_nuevo', 'residencia', 'carnet_funcionario'}

    -- Tarification par défaut (si le schema définit des règles)
    default_tarification JSONB,
    -- {"method": "percentage_based", "rate": 0.5, "minimum": 10000}

    -- Statut
    is_active BOOLEAN DEFAULT TRUE,

    -- Audit
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================================
-- 2. SEED EXTRACTION SCHEMAS
-- ============================================================================

INSERT INTO extraction_schemas (category, schema_filename, description, document_types, workflow_codes, default_tarification)
VALUES
    -- Identity documents
    (
        'identity',
        'identity_document.json',
        'Documents d''identité (DNI, Passeport, Permis de séjour)',
        ARRAY['DNI_CNI', 'PASSPORT', 'PERMISO_RESIDENCIA', 'DIP'],
        ARRAY['pasaporte_nuevo', 'pasaporte_renovacion', 'residencia', 'residencia_renovacion'],
        NULL
    ),

    -- Medical documents
    (
        'medical',
        'medical_document.json',
        'Certificats médicaux pour permis de conduire',
        ARRAY['CERTIFICADO_MEDICO', 'CERTIFICADO_APTITUD', 'INFORME_MEDICO'],
        ARRAY['certificado_conducir_nuevo', 'certificado_conducir_renovacion'],
        NULL
    ),

    -- Contract documents
    (
        'contract',
        'contract_document.json',
        'Contrats à enregistrer auprès de l''ONRC',
        ARRAY['CONTRATO_TRABAJO', 'CONTRATO_ALQUILER', 'CONTRATO_COMPRAVENTA', 'CONTRATO_SERVICIOS'],
        ARRAY['contrato_onrc'],
        '{"method": "percentage_based", "rate": 0.5, "minimum": 10000, "source_field": "bloc_contrat.montant_contrat"}'::JSONB
    ),

    -- License documents
    (
        'license',
        'license_document.json',
        'Licences professionnelles',
        ARRAY['LICENCIA_COMERCIO', 'LICENCIA_PROFESIONAL', 'LICENCIA_IMPORTACION'],
        ARRAY['licencia_comercio', 'licencia_importacion'],
        NULL
    ),

    -- Certificate documents
    (
        'certificate',
        'certificate_document.json',
        'Certificats et attestations',
        ARRAY['CERTIFICADO', 'ATTESTATION', 'ACTE_NAISSANCE'],
        ARRAY['certificado_administrativo'],
        NULL
    ),

    -- Fiscal documents
    (
        'fiscal',
        'fiscal_document.json',
        'Documents fiscaux (NIF, déclarations)',
        ARRAY['CERTIFICADO_NIF', 'DECLARACION_FISCAL', 'NOTA_INGRESO'],
        ARRAY['nif_expedicion', 'declaracion_irpf'],
        NULL
    )
ON CONFLICT (category) DO UPDATE SET
    document_types = EXCLUDED.document_types,
    workflow_codes = EXCLUDED.workflow_codes,
    default_tarification = EXCLUDED.default_tarification,
    updated_at = NOW();

-- ============================================================================
-- 3. CREATE TRIGGER FOR updated_at
-- ============================================================================

DROP TRIGGER IF EXISTS trg_es_updated_at ON extraction_schemas;
CREATE TRIGGER trg_es_updated_at
    BEFORE UPDATE ON extraction_schemas
    FOR EACH ROW
    EXECUTE FUNCTION update_tariff_updated_at();

-- ============================================================================
-- 4. ADD COMMENTS
-- ============================================================================

COMMENT ON TABLE extraction_schemas IS 'Mapping entre catégories de documents et schemas JSON d''extraction';
COMMENT ON COLUMN extraction_schemas.category IS 'Catégorie du schema (identity, medical, contract, etc.)';
COMMENT ON COLUMN extraction_schemas.default_tarification IS 'Règles de tarification par défaut définies dans le schema';

-- ============================================================================
-- END OF MIGRATION
-- ============================================================================
