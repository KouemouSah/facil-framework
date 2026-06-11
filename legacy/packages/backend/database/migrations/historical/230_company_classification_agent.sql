-- Migration 230: Company Classification Agent — Draft workflow + audit trail
-- Phase 3 of Agent Unification Architecture plan
-- Creates tables for company creation drafts (admin review workflow)
-- and classification history (audit trail for reclassifications).
--
-- VERIFIED against actual DB schema:
--   permissions: (id UUID, name, resource, action, description, is_critical, module_name)
--   role_permissions: PK(role_id UUID, permission_id UUID)
--   roles: code IN ('admin', 'super_admin', 'agent_onrc', 'supervisor_onrc') ✓
--   uploaded_files: EXISTS ✓

BEGIN;

-- 1. Table: company_creation_drafts (workflow admin: pending → approved/rejected)
CREATE TABLE IF NOT EXISTS company_creation_drafts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Source metadata
    source_type VARCHAR(20) NOT NULL CHECK (source_type IN ('upload', 'csv', 'manual')),
    source_file_id UUID REFERENCES uploaded_files(id) ON DELETE SET NULL,
    batch_id UUID,  -- groups CSV batch imports

    -- Extracted/entered company data (full payload)
    company_data JSONB NOT NULL DEFAULT '{}',
    -- Expected keys: nif, legal_name, forma_juridica, commerce_type, capital_social,
    --   employee_count, sector_actividad, subsector_actividad, objeto_social,
    --   localidad, provincia, registration_number, domicilio_fiscal, phone, email

    -- Classification result
    regimen_fiscal VARCHAR(20) CHECK (regimen_fiscal IS NULL OR
        regimen_fiscal IN ('bundle', 'declarativo', 'mixto', 'exento', 'pendiente')),
    classification_confidence FLOAT DEFAULT 0,
    classification_reason TEXT,
    classification_details JSONB DEFAULT '{}',
    -- Contains: rules_applied[], flags[], zone_pricing{}, commerce_type, llm_validated

    -- LLM extraction metadata (for upload source_type)
    extraction_confidence FLOAT DEFAULT 0,
    extraction_details JSONB DEFAULT '{}',
    -- Contains: fields_extracted[], fields_missing[], ocr_quality, warnings[]

    -- Workflow status
    status VARCHAR(20) NOT NULL DEFAULT 'pending_review'
        CHECK (status IN (
            'pending_review',   -- awaiting admin review
            'approved',         -- admin approved → company created
            'rejected',         -- admin rejected
            'needs_info',       -- admin requests more info
            'auto_approved',    -- high-confidence auto-approved (>= 0.90)
            'error'             -- classification or extraction error
        )),
    reviewer_id UUID REFERENCES users(id) ON DELETE SET NULL,
    reviewer_notes TEXT,
    reviewed_at TIMESTAMPTZ,

    -- Result: created company + license (after approval)
    created_company_id UUID REFERENCES companies(id) ON DELETE SET NULL,
    created_license_id UUID,  -- FK added in migration 231

    -- Audit
    created_by UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes for draft management
CREATE INDEX IF NOT EXISTS idx_draft_status
    ON company_creation_drafts(status);
CREATE INDEX IF NOT EXISTS idx_draft_batch
    ON company_creation_drafts(batch_id)
    WHERE batch_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_draft_confidence
    ON company_creation_drafts(classification_confidence)
    WHERE status = 'pending_review';
CREATE INDEX IF NOT EXISTS idx_draft_created_at
    ON company_creation_drafts(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_draft_reviewer
    ON company_creation_drafts(reviewer_id)
    WHERE reviewer_id IS NOT NULL;

-- updated_at trigger
CREATE OR REPLACE FUNCTION set_updated_at_company_creation_drafts()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_updated_at_company_creation_drafts ON company_creation_drafts;
CREATE TRIGGER trg_updated_at_company_creation_drafts
    BEFORE UPDATE ON company_creation_drafts
    FOR EACH ROW
    EXECUTE FUNCTION set_updated_at_company_creation_drafts();


-- 2. Table: company_classification_history (audit trail)
CREATE TABLE IF NOT EXISTS company_classification_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    old_regimen VARCHAR(20),
    new_regimen VARCHAR(20) NOT NULL,
    old_commerce_type VARCHAR(50),
    new_commerce_type VARCHAR(50),
    reason TEXT NOT NULL,
    confidence FLOAT DEFAULT 0,
    details JSONB DEFAULT '{}',
    -- Contains: rules_applied[], llm_output, threshold_info, flags[]
    triggered_by VARCHAR(20) NOT NULL CHECK (
        triggered_by IN ('initial', 'manual', 'annual_cron', 'data_change', 'csv_import')
    ),
    created_by UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_class_history_company
    ON company_classification_history(company_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_class_history_trigger
    ON company_classification_history(triggered_by, created_at DESC);


-- 3. Permissions for classification features
-- permissions table: (id UUID, name, resource, action, description, is_critical, module_name)
INSERT INTO permissions (name, resource, action, description, is_critical, module_name)
VALUES
    ('company.classify', 'company', 'classify', 'Clasificar empresas (asignar regimen fiscal)', true, 'company'),
    ('company.validate_draft', 'company', 'validate_draft', 'Validar borradores de creacion de empresas', true, 'company'),
    ('company.import_csv', 'company', 'import_csv', 'Importar empresas desde CSV/Excel', true, 'company'),
    ('company.view_classification', 'company', 'view_classification', 'Ver detalles de clasificacion', false, 'company')
ON CONFLICT (name) DO NOTHING;

-- Assign permissions to relevant roles
-- role_permissions: PK(role_id UUID, permission_id UUID)
DO $$
DECLARE
    v_perm_classify_id UUID;
    v_perm_validate_id UUID;
    v_perm_import_id UUID;
    v_perm_view_class_id UUID;
    v_role_id UUID;
BEGIN
    -- Get permission IDs
    SELECT id INTO v_perm_classify_id FROM permissions WHERE name = 'company.classify';
    SELECT id INTO v_perm_validate_id FROM permissions WHERE name = 'company.validate_draft';
    SELECT id INTO v_perm_import_id FROM permissions WHERE name = 'company.import_csv';
    SELECT id INTO v_perm_view_class_id FROM permissions WHERE name = 'company.view_classification';

    -- Skip if permissions not found (idempotent)
    IF v_perm_classify_id IS NULL THEN
        RAISE NOTICE 'Permissions not found, skipping role assignments';
        RETURN;
    END IF;

    -- Assign all 4 to admin and super_admin
    FOR v_role_id IN (SELECT id FROM roles WHERE code IN ('admin', 'super_admin'))
    LOOP
        INSERT INTO role_permissions (role_id, permission_id)
        VALUES
            (v_role_id, v_perm_classify_id),
            (v_role_id, v_perm_validate_id),
            (v_role_id, v_perm_import_id),
            (v_role_id, v_perm_view_class_id)
        ON CONFLICT DO NOTHING;
    END LOOP;

    -- Assign view + classify to ONRC agents
    FOR v_role_id IN (SELECT id FROM roles WHERE code IN ('agent_onrc', 'supervisor_onrc'))
    LOOP
        INSERT INTO role_permissions (role_id, permission_id)
        VALUES
            (v_role_id, v_perm_view_class_id),
            (v_role_id, v_perm_classify_id)
        ON CONFLICT DO NOTHING;
    END LOOP;

    -- Assign validate + import to supervisor_onrc
    FOR v_role_id IN (SELECT id FROM roles WHERE code = 'supervisor_onrc')
    LOOP
        INSERT INTO role_permissions (role_id, permission_id)
        VALUES
            (v_role_id, v_perm_validate_id),
            (v_role_id, v_perm_import_id)
        ON CONFLICT DO NOTHING;
    END LOOP;
END $$;

COMMIT;
