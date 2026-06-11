-- Migration: 020_service_requests_base.sql
-- Date: 2025-12-27
-- Description: Table principale pour les demandes de service (service_requests)
-- Author: TaxasGE Development Team

-- ============================================================================
-- 1. CREATE ENUMS
-- ============================================================================

-- Status des demandes
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'service_request_status_enum') THEN
        CREATE TYPE service_request_status_enum AS ENUM (
            -- Phase initiale
            'DRAFT',                    -- Brouillon
            'TIMBRES_PENDING',          -- En attente paiement timbres
            'TIMBRES_PAID',             -- Timbres payés

            -- Phase soumission
            'SUBMITTED',                -- Soumis
            'DOCUMENTS_REQUIRED',       -- Documents manquants

            -- Phase validation
            'UNDER_REVIEW',             -- En cours d'examen
            'DOSSIER_VALIDE',           -- Dossier validé
            'REJECTED',                 -- Rejeté

            -- Phase Nota de Ingreso (si applicable)
            'PENDING_NOTA_INGRESO',     -- En attente de Nota
            'NOTA_UPLOADED',            -- Nota uploadée

            -- Phase paiement principal
            'PAYMENT_PENDING',          -- En attente de paiement
            'PAYMENT_PROCESSING',       -- Paiement en cours
            'PAID',                     -- Payé
            'PAYMENT_FAILED',           -- Paiement échoué

            -- Phase finale
            'CITA_SCHEDULED',           -- RDV programmé
            'IN_PROGRESS',              -- En cours de traitement
            'COMPLETED',                -- Terminé
            'CANCELLED',                -- Annulé
            'EXPIRED'                   -- Expiré
        );
    END IF;
END
$$;

-- Priorité des demandes
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'service_request_priority_enum') THEN
        CREATE TYPE service_request_priority_enum AS ENUM (
            'LOW',
            'NORMAL',
            'HIGH',
            'URGENT'
        );
    END IF;
END
$$;

-- ============================================================================
-- 2. CREATE SERVICE_REQUESTS TABLE
-- ============================================================================

CREATE TABLE IF NOT EXISTS service_requests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Référence unique lisible
    reference VARCHAR(50) UNIQUE NOT NULL,  -- Ex: RES-2025-00001, PAS-2025-00042

    -- Utilisateur demandeur
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,

    -- Type de workflow
    workflow_code VARCHAR(100) NOT NULL,  -- Ex: residencia, pasaporte_nuevo, carnet_funcionario
    solicitud_type VARCHAR(50) NOT NULL DEFAULT 'expedicion',  -- expedicion, renovacion, duplicado

    -- Service fiscal lié (si applicable)
    fiscal_service_id INTEGER REFERENCES fiscal_services(id) ON DELETE SET NULL,

    -- Status
    status service_request_status_enum NOT NULL DEFAULT 'DRAFT',
    priority service_request_priority_enum NOT NULL DEFAULT 'NORMAL',

    -- Données du formulaire (extraction + saisie utilisateur)
    form_data JSONB NOT NULL DEFAULT '{}',

    -- Données extraites par Gemini (séparées pour traçabilité)
    extracted_data JSONB DEFAULT '{}',
    extraction_confidence NUMERIC(5,4),  -- 0.0000 à 1.0000

    -- Validations
    validations JSONB DEFAULT '{}',  -- Résultats des validations croisées

    -- Agent assigné
    assigned_to UUID REFERENCES users(id) ON DELETE SET NULL,
    assigned_at TIMESTAMPTZ,

    -- Entité responsable
    entity_code VARCHAR(50),  -- CNEDOGE, EXTRANJERIA, DGT, etc.

    -- Montants
    base_amount NUMERIC(12,2),
    supplements_amount NUMERIC(12,2) DEFAULT 0,
    penalties_amount NUMERIC(12,2) DEFAULT 0,
    total_amount NUMERIC(12,2),
    currency VARCHAR(3) DEFAULT 'XAF',

    -- Paiement
    payment_id UUID,  -- Référence vers payments table
    payment_status VARCHAR(50),
    paid_at TIMESTAMPTZ,

    -- RDV (cita)
    cita_date DATE,
    cita_time TIME,
    cita_location VARCHAR(255),

    -- Dates importantes
    submitted_at TIMESTAMPTZ,
    validated_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    expires_at TIMESTAMPTZ,  -- Date limite de validité

    -- Métadonnées
    notes TEXT,  -- Notes internes
    rejection_reason TEXT,

    -- Audit
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by UUID REFERENCES users(id),

    -- Contraintes
    CONSTRAINT valid_amounts CHECK (
        (base_amount IS NULL OR base_amount >= 0) AND
        (supplements_amount >= 0) AND
        (penalties_amount >= 0) AND
        (total_amount IS NULL OR total_amount >= 0)
    )
);

-- ============================================================================
-- 3. CREATE SERVICE_REQUEST_DOCUMENTS TABLE
-- ============================================================================

CREATE TABLE IF NOT EXISTS service_request_documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    service_request_id UUID NOT NULL REFERENCES service_requests(id) ON DELETE CASCADE,

    -- Document info
    document_code VARCHAR(100) NOT NULL,  -- dip, acte_naissance, etc.
    document_name VARCHAR(255) NOT NULL,

    -- Fichier
    file_path TEXT NOT NULL,  -- Chemin dans Supabase Storage
    file_name VARCHAR(255) NOT NULL,
    file_size INTEGER,
    mime_type VARCHAR(100),

    -- Extraction
    extraction_data JSONB DEFAULT '{}',
    extraction_confidence NUMERIC(5,4),
    extraction_status VARCHAR(50) DEFAULT 'pending',  -- pending, success, failed

    -- Validation
    is_valid BOOLEAN,
    validation_errors JSONB DEFAULT '[]',
    validated_by UUID REFERENCES users(id),
    validated_at TIMESTAMPTZ,

    -- Source du document
    source VARCHAR(50) DEFAULT 'user_upload',  -- user_upload, agent_upload, generated
    uploaded_by UUID REFERENCES users(id),

    -- Audit
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Contrainte: un document par code par demande
    CONSTRAINT unique_document_per_request UNIQUE(service_request_id, document_code)
);

-- ============================================================================
-- 4. CREATE SERVICE_REQUEST_HISTORY TABLE (Audit Trail)
-- ============================================================================

CREATE TABLE IF NOT EXISTS service_request_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    service_request_id UUID NOT NULL REFERENCES service_requests(id) ON DELETE CASCADE,

    -- Changement
    action VARCHAR(100) NOT NULL,  -- status_change, document_added, assigned, etc.
    previous_status service_request_status_enum,
    new_status service_request_status_enum,

    -- Détails
    details JSONB DEFAULT '{}',
    comment TEXT,

    -- Acteur
    performed_by UUID REFERENCES users(id),
    performed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Contexte
    ip_address INET,
    user_agent TEXT
);

-- ============================================================================
-- 5. CREATE INDEXES
-- ============================================================================

-- service_requests indexes
CREATE INDEX IF NOT EXISTS idx_sr_user_id ON service_requests(user_id);
CREATE INDEX IF NOT EXISTS idx_sr_workflow_code ON service_requests(workflow_code);
CREATE INDEX IF NOT EXISTS idx_sr_status ON service_requests(status);
CREATE INDEX IF NOT EXISTS idx_sr_assigned_to ON service_requests(assigned_to) WHERE assigned_to IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_sr_entity_code ON service_requests(entity_code) WHERE entity_code IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_sr_reference ON service_requests(reference);
CREATE INDEX IF NOT EXISTS idx_sr_created_at ON service_requests(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_sr_fiscal_service ON service_requests(fiscal_service_id) WHERE fiscal_service_id IS NOT NULL;

-- Recherche par workflow + status (très fréquent pour les agents)
CREATE INDEX IF NOT EXISTS idx_sr_workflow_status ON service_requests(workflow_code, status);

-- service_request_documents indexes
CREATE INDEX IF NOT EXISTS idx_srd_request_id ON service_request_documents(service_request_id);
CREATE INDEX IF NOT EXISTS idx_srd_document_code ON service_request_documents(document_code);

-- service_request_history indexes
CREATE INDEX IF NOT EXISTS idx_srh_request_id ON service_request_history(service_request_id);
CREATE INDEX IF NOT EXISTS idx_srh_performed_at ON service_request_history(performed_at DESC);

-- ============================================================================
-- 6. CREATE TRIGGER FOR updated_at
-- ============================================================================

CREATE OR REPLACE FUNCTION update_service_request_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_sr_updated_at ON service_requests;
CREATE TRIGGER trg_sr_updated_at
    BEFORE UPDATE ON service_requests
    FOR EACH ROW
    EXECUTE FUNCTION update_service_request_updated_at();

DROP TRIGGER IF EXISTS trg_srd_updated_at ON service_request_documents;
CREATE TRIGGER trg_srd_updated_at
    BEFORE UPDATE ON service_request_documents
    FOR EACH ROW
    EXECUTE FUNCTION update_service_request_updated_at();

-- ============================================================================
-- 7. CREATE FUNCTION TO GENERATE REFERENCE
-- ============================================================================

CREATE OR REPLACE FUNCTION generate_service_request_reference(
    p_workflow_code VARCHAR(100)
)
RETURNS VARCHAR(50) AS $$
DECLARE
    v_prefix VARCHAR(10);
    v_year VARCHAR(4);
    v_sequence INTEGER;
    v_reference VARCHAR(50);
BEGIN
    -- Déterminer le préfixe selon le workflow
    v_prefix := CASE
        WHEN p_workflow_code LIKE 'residencia%' THEN 'RES'
        WHEN p_workflow_code LIKE 'pasaporte%' THEN 'PAS'
        WHEN p_workflow_code LIKE 'carnet_funcionario%' THEN 'CFN'
        WHEN p_workflow_code LIKE 'certificado_conducir%' THEN 'CON'
        WHEN p_workflow_code LIKE 'transferencia_vehiculo%' THEN 'TVH'
        WHEN p_workflow_code LIKE 'renovacion_vehiculo%' THEN 'RVH'
        WHEN p_workflow_code LIKE 'contrato%' THEN 'CTR'
        ELSE 'SRV'
    END;

    v_year := TO_CHAR(NOW(), 'YYYY');

    -- Obtenir le prochain numéro de séquence pour ce préfixe et année
    SELECT COALESCE(MAX(
        CAST(SPLIT_PART(reference, '-', 3) AS INTEGER)
    ), 0) + 1
    INTO v_sequence
    FROM service_requests
    WHERE reference LIKE v_prefix || '-' || v_year || '-%';

    v_reference := v_prefix || '-' || v_year || '-' || LPAD(v_sequence::TEXT, 5, '0');

    RETURN v_reference;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- 8. CREATE TRIGGER FOR AUTO-REFERENCE
-- ============================================================================

CREATE OR REPLACE FUNCTION auto_generate_sr_reference()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.reference IS NULL OR NEW.reference = '' THEN
        NEW.reference := generate_service_request_reference(NEW.workflow_code);
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_sr_auto_reference ON service_requests;
CREATE TRIGGER trg_sr_auto_reference
    BEFORE INSERT ON service_requests
    FOR EACH ROW
    EXECUTE FUNCTION auto_generate_sr_reference();

-- ============================================================================
-- 9. ADD COMMENTS
-- ============================================================================

COMMENT ON TABLE service_requests IS 'Demandes de service (passeport, résidence, carnet, etc.)';
COMMENT ON COLUMN service_requests.reference IS 'Référence unique lisible (ex: RES-2025-00001)';
COMMENT ON COLUMN service_requests.workflow_code IS 'Code du workflow (residencia, pasaporte_nuevo, etc.)';
COMMENT ON COLUMN service_requests.solicitud_type IS 'Type de sollicitation (expedicion, renovacion, duplicado)';
COMMENT ON COLUMN service_requests.form_data IS 'Données du formulaire (extraction + saisie utilisateur)';
COMMENT ON COLUMN service_requests.extracted_data IS 'Données extraites par Gemini (pour traçabilité)';

COMMENT ON TABLE service_request_documents IS 'Documents uploadés pour une demande de service';
COMMENT ON TABLE service_request_history IS 'Historique des changements (audit trail)';

-- ============================================================================
-- 10. ADD PERMISSIONS
-- ============================================================================

INSERT INTO permissions (name, resource, action, description, is_critical, module_name)
VALUES
    ('service_requests.read', 'service_requests', 'read', 'Consulter les demandes de service', FALSE, 'service_request'),
    ('service_requests.create', 'service_requests', 'create', 'Créer une demande de service', FALSE, 'service_request'),
    ('service_requests.update', 'service_requests', 'update', 'Modifier une demande de service', FALSE, 'service_request'),
    ('service_requests.delete', 'service_requests', 'delete', 'Supprimer une demande de service', TRUE, 'service_request'),
    ('service_requests.assign', 'service_requests', 'assign', 'Assigner une demande à un agent', FALSE, 'service_request'),
    ('service_requests.validate', 'service_requests', 'validate', 'Valider une demande', FALSE, 'service_request'),
    ('service_requests.reject', 'service_requests', 'reject', 'Rejeter une demande', FALSE, 'service_request'),
    ('service_requests.all', 'service_requests', 'all', 'Voir toutes les demandes (admin)', TRUE, 'service_request')
ON CONFLICT (name) DO NOTHING;

-- ============================================================================
-- END OF MIGRATION
-- ============================================================================
