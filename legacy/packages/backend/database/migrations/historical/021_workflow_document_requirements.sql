-- Migration: 021_workflow_document_requirements.sql
-- Date: 2025-12-27
-- Description: Documents requis par workflow avec logique conditionnelle
-- Author: TaxasGE Development Team
-- Note: Version nettoyée - traductions gérées via entity_translations

-- ============================================================================
-- 1. ADD WORKFLOW_CODE TO FISCAL_SERVICES (si pas déjà fait)
-- ============================================================================

ALTER TABLE fiscal_services
ADD COLUMN IF NOT EXISTS workflow_code VARCHAR(100);

CREATE INDEX IF NOT EXISTS idx_fiscal_services_workflow_code
    ON fiscal_services(workflow_code)
    WHERE workflow_code IS NOT NULL;

COMMENT ON COLUMN fiscal_services.workflow_code IS 'Code du workflow associé (ex: pasaporte_nuevo, residencia)';

-- ============================================================================
-- 2. CREATE CONDITION TYPE ENUM
-- ============================================================================

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'document_condition_type_enum') THEN
        CREATE TYPE document_condition_type_enum AS ENUM (
            'always',           -- Toujours requis
            'age_less_than',    -- Age < valeur
            'age_greater_than', -- Age >= valeur
            'is_renewal',       -- Si renouvellement
            'is_new',           -- Si nouvelle demande
            'is_duplicate',     -- Si duplicata
            'has_previous',     -- Si document précédent existe
            'is_minor',         -- Si mineur (<18)
            'is_adult',         -- Si majeur (>=18)
            'is_foreign',       -- Si étranger
            'is_national',      -- Si national GQ
            'custom'            -- Condition personnalisée (backend)
        );
    END IF;
END
$$;

-- ============================================================================
-- 3. CREATE WORKFLOW_DOCUMENT_REQUIREMENTS TABLE
-- ============================================================================

CREATE TABLE IF NOT EXISTS workflow_document_requirements (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Workflow associé
    workflow_code VARCHAR(100) NOT NULL,

    -- Document requis
    document_template_id INTEGER REFERENCES document_templates(id) ON DELETE SET NULL,
    document_code VARCHAR(100) NOT NULL,
    document_name_es VARCHAR(255) NOT NULL,  -- Nom en espagnol (langue principale)

    -- Conditions
    condition_type document_condition_type_enum NOT NULL DEFAULT 'always',
    condition_value JSONB DEFAULT '{}',

    -- Métadonnées
    is_required BOOLEAN DEFAULT TRUE,
    display_order INTEGER DEFAULT 0,
    instructions_es TEXT,  -- Instructions en espagnol

    -- Pour extraction Gemini
    extraction_schema_key VARCHAR(100),

    -- Audit
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    created_by UUID REFERENCES users(id),

    -- Contraintes
    CONSTRAINT unique_workflow_document UNIQUE(workflow_code, document_code)
);

-- ============================================================================
-- 4. CREATE INDEXES
-- ============================================================================

CREATE INDEX IF NOT EXISTS idx_wdr_workflow_code
    ON workflow_document_requirements(workflow_code);

CREATE INDEX IF NOT EXISTS idx_wdr_document_code
    ON workflow_document_requirements(document_code);

CREATE INDEX IF NOT EXISTS idx_wdr_condition_type
    ON workflow_document_requirements(condition_type);

CREATE INDEX IF NOT EXISTS idx_wdr_display_order
    ON workflow_document_requirements(workflow_code, display_order);

CREATE INDEX IF NOT EXISTS idx_wdr_active
    ON workflow_document_requirements(workflow_code, is_active)
    WHERE is_active = TRUE;

-- ============================================================================
-- 5. CREATE TRIGGER FOR updated_at
-- ============================================================================

CREATE OR REPLACE FUNCTION update_wdr_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_wdr_updated_at ON workflow_document_requirements;
CREATE TRIGGER trg_wdr_updated_at
    BEFORE UPDATE ON workflow_document_requirements
    FOR EACH ROW
    EXECUTE FUNCTION update_wdr_updated_at();

-- ============================================================================
-- 6. CREATE FUNCTION TO EVALUATE CONDITIONS
-- ============================================================================

CREATE OR REPLACE FUNCTION evaluate_document_condition(
    p_condition_type document_condition_type_enum,
    p_condition_value JSONB,
    p_context JSONB
)
RETURNS BOOLEAN AS $$
DECLARE
    v_age INTEGER;
    v_threshold INTEGER;
    v_nationality VARCHAR;
BEGIN
    -- Toujours = TRUE
    IF p_condition_type = 'always' THEN
        RETURN TRUE;
    END IF;

    -- Extraire du contexte
    v_age := (p_context->>'age')::INTEGER;
    v_nationality := p_context->>'nationality';

    CASE p_condition_type
        WHEN 'age_less_than' THEN
            v_threshold := (p_condition_value->>'value')::INTEGER;
            RETURN v_age IS NOT NULL AND v_age < v_threshold;

        WHEN 'age_greater_than' THEN
            v_threshold := (p_condition_value->>'value')::INTEGER;
            RETURN v_age IS NOT NULL AND v_age >= v_threshold;

        WHEN 'is_minor' THEN
            RETURN v_age IS NOT NULL AND v_age < 18;

        WHEN 'is_adult' THEN
            RETURN v_age IS NULL OR v_age >= 18;

        WHEN 'is_renewal' THEN
            RETURN COALESCE((p_context->>'solicitud_type')::TEXT, '') = 'renovacion';

        WHEN 'is_new' THEN
            RETURN COALESCE((p_context->>'solicitud_type')::TEXT, 'expedicion') = 'expedicion';

        WHEN 'is_duplicate' THEN
            RETURN COALESCE((p_context->>'solicitud_type')::TEXT, '') = 'duplicado';

        WHEN 'has_previous' THEN
            RETURN COALESCE((p_context->>'has_previous_document')::BOOLEAN, FALSE);

        WHEN 'is_foreign' THEN
            RETURN v_nationality IS NOT NULL AND v_nationality != 'GQ' AND v_nationality != 'GNQ';

        WHEN 'is_national' THEN
            RETURN v_nationality IS NULL OR v_nationality IN ('GQ', 'GNQ');

        WHEN 'custom' THEN
            -- Conditions custom évaluées par le backend
            RETURN TRUE;

        ELSE
            RETURN TRUE;
    END CASE;
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- ============================================================================
-- 7. CREATE FUNCTION TO GET REQUIRED DOCUMENTS
-- ============================================================================

CREATE OR REPLACE FUNCTION get_workflow_required_documents(
    p_workflow_code VARCHAR(100),
    p_context JSONB DEFAULT '{}'
)
RETURNS TABLE (
    document_code VARCHAR(100),
    document_name_es VARCHAR(255),
    is_required BOOLEAN,
    instructions_es TEXT,
    condition_type document_condition_type_enum,
    extraction_schema_key VARCHAR(100),
    display_order INTEGER
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        wdr.document_code,
        wdr.document_name_es,
        wdr.is_required,
        wdr.instructions_es,
        wdr.condition_type,
        wdr.extraction_schema_key,
        wdr.display_order
    FROM workflow_document_requirements wdr
    WHERE wdr.workflow_code = p_workflow_code
      AND wdr.is_active = TRUE
      AND evaluate_document_condition(wdr.condition_type, wdr.condition_value, p_context)
    ORDER BY wdr.display_order;
END;
$$ LANGUAGE plpgsql STABLE;

-- ============================================================================
-- 8. CREATE FUNCTION TO VALIDATE DOCUMENTS
-- ============================================================================

CREATE OR REPLACE FUNCTION validate_workflow_documents(
    p_workflow_code VARCHAR(100),
    p_uploaded_codes TEXT[],
    p_context JSONB DEFAULT '{}'
)
RETURNS JSONB AS $$
DECLARE
    v_required_codes TEXT[];
    v_missing_codes TEXT[];
    v_missing_docs JSONB;
BEGIN
    -- Récupérer les codes requis
    SELECT ARRAY_AGG(document_code)
    INTO v_required_codes
    FROM get_workflow_required_documents(p_workflow_code, p_context)
    WHERE is_required = TRUE;

    IF v_required_codes IS NULL THEN
        RETURN jsonb_build_object('valid', TRUE, 'missing', '[]'::JSONB);
    END IF;

    -- Trouver les manquants
    SELECT ARRAY_AGG(code)
    INTO v_missing_codes
    FROM UNNEST(v_required_codes) AS code
    WHERE code != ALL(p_uploaded_codes);

    IF v_missing_codes IS NULL OR ARRAY_LENGTH(v_missing_codes, 1) = 0 THEN
        RETURN jsonb_build_object('valid', TRUE, 'missing', '[]'::JSONB);
    END IF;

    -- Construire la liste des manquants
    SELECT jsonb_agg(
        jsonb_build_object(
            'code', wdr.document_code,
            'name_es', wdr.document_name_es
        )
    )
    INTO v_missing_docs
    FROM workflow_document_requirements wdr
    WHERE wdr.workflow_code = p_workflow_code
      AND wdr.document_code = ANY(v_missing_codes);

    RETURN jsonb_build_object(
        'valid', FALSE,
        'missing', COALESCE(v_missing_docs, '[]'::JSONB)
    );
END;
$$ LANGUAGE plpgsql STABLE;

-- ============================================================================
-- 9. ADD COMMENTS
-- ============================================================================

COMMENT ON TABLE workflow_document_requirements IS 'Documents requis par workflow avec logique conditionnelle';
COMMENT ON COLUMN workflow_document_requirements.workflow_code IS 'Code du workflow (ex: pasaporte_nuevo)';
COMMENT ON COLUMN workflow_document_requirements.document_code IS 'Code unique du document (ex: dip)';
COMMENT ON COLUMN workflow_document_requirements.condition_type IS 'Type de condition pour ce document';
COMMENT ON COLUMN workflow_document_requirements.extraction_schema_key IS 'Clé du schéma JSON pour extraction Gemini';
COMMENT ON FUNCTION evaluate_document_condition IS 'Évalue si une condition est satisfaite';
COMMENT ON FUNCTION get_workflow_required_documents IS 'Retourne les documents requis selon le contexte';
COMMENT ON FUNCTION validate_workflow_documents IS 'Valide que tous les documents requis sont présents';

-- ============================================================================
-- 10. ADD PERMISSIONS
-- ============================================================================

INSERT INTO permissions (name, resource, action, description, is_critical, module_name)
VALUES
    ('workflow_documents.read', 'workflow_documents', 'read', 'Consulter les documents requis par workflow', FALSE, 'workflow'),
    ('workflow_documents.create', 'workflow_documents', 'create', 'Ajouter un document requis à un workflow', FALSE, 'workflow'),
    ('workflow_documents.update', 'workflow_documents', 'update', 'Modifier un document requis', FALSE, 'workflow'),
    ('workflow_documents.delete', 'workflow_documents', 'delete', 'Supprimer un document requis', TRUE, 'workflow')
ON CONFLICT (name) DO NOTHING;

-- ============================================================================
-- END OF MIGRATION (Seed data dans fichier séparé)
-- ============================================================================
