-- ============================================================================
-- Migration 100: Batch Service Requests
-- ============================================================================
-- Enables submission of N identical requests (same workflow) for N beneficiaries
-- in a single batch. Use cases: companies (50 residences), lawyers (20 passports),
-- families (4 passports), NGOs (30 residence cards).
-- ============================================================================

BEGIN;

-- ============================================================================
-- 1. BATCH_REQUESTS - One per batch submission
-- ============================================================================
CREATE TABLE IF NOT EXISTS batch_requests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    reference VARCHAR(50) UNIQUE,                      -- LOT-2026-XXXXX (auto-generated)
    submitted_by UUID NOT NULL REFERENCES users(id),
    company_id UUID REFERENCES companies(id),           -- OPTIONAL - not limited to companies
    workflow_code VARCHAR(100) NOT NULL,
    solicitud_type VARCHAR(50) NOT NULL DEFAULT 'expedicion',
    entity_code VARCHAR(50),

    -- Counts
    total_items INT NOT NULL DEFAULT 0,
    items_ready INT NOT NULL DEFAULT 0,
    items_submitted INT NOT NULL DEFAULT 0,
    items_completed INT NOT NULL DEFAULT 0,

    -- Status: DRAFT → UPLOADING → CLASSIFYING → REVIEW → PAYMENT_PENDING → PAID → IN_PROGRESS → COMPLETED
    status VARCHAR(50) NOT NULL DEFAULT 'DRAFT',

    -- Shared documents (uploaded once, apply to all beneficiaries)
    shared_documents JSONB NOT NULL DEFAULT '[]',

    -- Payment
    per_item_amount NUMERIC(12,2),
    total_amount NUMERIC(12,2),
    currency VARCHAR(3) DEFAULT 'XAF',
    bange_transaction_id VARCHAR(255),             -- BANGE payment ID for batch (webhook lookup)

    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    submitted_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    notes TEXT
);

-- ============================================================================
-- 2. BATCH_REQUEST_ITEMS - One per beneficiary
-- ============================================================================
CREATE TABLE IF NOT EXISTS batch_request_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    batch_id UUID NOT NULL REFERENCES batch_requests(id) ON DELETE CASCADE,

    -- Beneficiary identity
    beneficiary_name VARCHAR(255) NOT NULL,
    beneficiary_identifier VARCHAR(100),               -- passport/DIP/NIE number
    beneficiary_identifier_type VARCHAR(50),            -- passport, dip, nie
    beneficiary_email VARCHAR(255),
    beneficiary_phone VARCHAR(50),

    -- Link to generated service_request (created at submission)
    service_request_id UUID REFERENCES service_requests(id),

    -- Status: PENDING → DOCUMENTS_ASSIGNED → REVIEW → READY → SUBMITTED → EXCLUDED
    status VARCHAR(50) NOT NULL DEFAULT 'PENDING',

    -- Assigned individual documents
    -- [{document_code, file_path, file_name, extraction_data, confidence, match_method, match_score}]
    assigned_documents JSONB NOT NULL DEFAULT '[]',

    -- Per-beneficiary conditions (is_minor, applicant_type, categories, etc.)
    -- {"is_minor": "true"} or {"applicant_type": "RESIDENT", "categories": ["TRAB_SALARIADO"]}
    conditions JSONB NOT NULL DEFAULT '{}',

    -- Required documents (computed from workflow_document_requirements + conditions)
    -- ["dip", "pasaporte_antiguo", "acta_nacimiento", ...]
    required_documents JSONB NOT NULL DEFAULT '[]',

    -- Form data (auto-populated from extraction, editable via DataGrid)
    form_data JSONB NOT NULL DEFAULT '{}',

    -- Per-item amount (NULL if same as batch.per_item_amount, set if tariff varies)
    item_amount NUMERIC(12,2),

    -- Validation
    validation_errors JSONB DEFAULT '[]',
    missing_documents JSONB DEFAULT '[]',

    item_order INT NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ============================================================================
-- 3. ALTER existing tables - add batch_id references
-- ============================================================================
ALTER TABLE service_requests
    ADD COLUMN IF NOT EXISTS batch_id UUID REFERENCES batch_requests(id),
    ADD COLUMN IF NOT EXISTS company_id UUID REFERENCES companies(id);

ALTER TABLE service_payments
    ADD COLUMN IF NOT EXISTS batch_id UUID REFERENCES batch_requests(id);

-- ============================================================================
-- 4. INDEXES
-- ============================================================================
CREATE INDEX IF NOT EXISTS idx_batch_requests_submitted_by ON batch_requests(submitted_by);
CREATE INDEX IF NOT EXISTS idx_batch_requests_company ON batch_requests(company_id) WHERE company_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_batch_requests_status ON batch_requests(status);
CREATE INDEX IF NOT EXISTS idx_batch_items_batch ON batch_request_items(batch_id);
CREATE INDEX IF NOT EXISTS idx_batch_items_status ON batch_request_items(status);
CREATE INDEX IF NOT EXISTS idx_batch_items_identifier ON batch_request_items(beneficiary_identifier) WHERE beneficiary_identifier IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_batch_items_sr ON batch_request_items(service_request_id) WHERE service_request_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_sr_batch ON service_requests(batch_id) WHERE batch_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_sr_company ON service_requests(company_id) WHERE company_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_sp_batch ON service_payments(batch_id) WHERE batch_id IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS idx_batch_bange_txn ON batch_requests(bange_transaction_id) WHERE bange_transaction_id IS NOT NULL;

-- ============================================================================
-- 5. AUTO-REFERENCE trigger (LOT-YYYY-NNNNN)
-- ============================================================================
CREATE OR REPLACE FUNCTION generate_batch_reference()
RETURNS TRIGGER AS $$
DECLARE
    year_str TEXT := TO_CHAR(NOW(), 'YYYY');
    seq_num INT;
BEGIN
    SELECT COALESCE(MAX(CAST(SUBSTRING(reference FROM 'LOT-' || year_str || '-(\d+)') AS INT)), 0) + 1
    INTO seq_num FROM batch_requests WHERE reference LIKE 'LOT-' || year_str || '-%';
    NEW.reference := 'LOT-' || year_str || '-' || LPAD(seq_num::TEXT, 5, '0');
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_batch_auto_reference ON batch_requests;
CREATE TRIGGER trg_batch_auto_reference
    BEFORE INSERT ON batch_requests
    FOR EACH ROW
    WHEN (NEW.reference IS NULL)
    EXECUTE FUNCTION generate_batch_reference();

-- ============================================================================
-- 6. updated_at triggers
-- ============================================================================
CREATE TRIGGER trg_batch_requests_updated_at
    BEFORE UPDATE ON batch_requests
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER trg_batch_request_items_updated_at
    BEFORE UPDATE ON batch_request_items
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- ============================================================================
-- 7. PERMISSIONS
-- ============================================================================
INSERT INTO permissions (name, resource, action, description, is_critical, module_name)
VALUES
    ('batch_requests.create', 'batch_requests', 'create', 'Crear solicitudes en lote', FALSE, 'batch_requests'),
    ('batch_requests.read', 'batch_requests', 'read', 'Ver solicitudes en lote propias', FALSE, 'batch_requests'),
    ('batch_requests.manage', 'batch_requests', 'manage', 'Gestionar solicitudes en lote', FALSE, 'batch_requests'),
    ('batch_requests.admin', 'batch_requests', 'all', 'Administrar todos los lotes (admin)', TRUE, 'batch_requests')
ON CONFLICT (name) DO NOTHING;

COMMIT;
