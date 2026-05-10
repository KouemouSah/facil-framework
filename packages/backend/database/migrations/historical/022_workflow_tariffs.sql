-- Migration: 022_workflow_tariffs.sql
-- Date: 2025-12-27
-- Description: Tables pour gestion des tarifs workflows (administrable via interface)
-- Author: TaxasGE Development Team

-- ============================================================================
-- 1. CREATE WORKFLOW_TARIFFS TABLE
-- ============================================================================
-- Table pour les tarifs de base des workflows (gérables via interface admin)

CREATE TABLE IF NOT EXISTS workflow_tariffs (
    id SERIAL PRIMARY KEY,

    -- Identification
    workflow_code VARCHAR(100) NOT NULL,
    solicitud_type VARCHAR(50) NOT NULL DEFAULT 'expedicion',  -- expedicion, renovacion, duplicado

    -- Tarif
    amount NUMERIC(12,2) NOT NULL,
    currency VARCHAR(3) DEFAULT 'XAF',

    -- Référence légale (traçabilité)
    legal_reference VARCHAR(255),

    -- Versioning (permet de changer sans perdre l'historique)
    effective_from DATE NOT NULL DEFAULT CURRENT_DATE,
    effective_to DATE,  -- NULL = toujours actif

    -- Statut
    is_active BOOLEAN DEFAULT TRUE,

    -- Audit
    created_by UUID REFERENCES users(id),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_by UUID REFERENCES users(id),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    -- Contrainte: un seul tarif actif par workflow+type à une date donnée
    CONSTRAINT valid_tariff_amount CHECK (amount >= 0),
    CONSTRAINT valid_date_range CHECK (effective_to IS NULL OR effective_to > effective_from)
);

-- Index unique pour éviter les doublons actifs
CREATE UNIQUE INDEX IF NOT EXISTS idx_wt_unique_active
    ON workflow_tariffs(workflow_code, solicitud_type)
    WHERE is_active = TRUE AND effective_to IS NULL;

-- Index pour recherche
CREATE INDEX IF NOT EXISTS idx_wt_workflow_code ON workflow_tariffs(workflow_code);
CREATE INDEX IF NOT EXISTS idx_wt_lookup ON workflow_tariffs(workflow_code, solicitud_type, is_active);

-- ============================================================================
-- 2. CREATE TARIFF_SUPPLEMENTS TABLE
-- ============================================================================
-- Table pour les suppléments (cédulas, pólizas, timbres) - gérables via interface

CREATE TABLE IF NOT EXISTS tariff_supplements (
    id SERIAL PRIMARY KEY,

    -- Identification
    code VARCHAR(50) UNIQUE NOT NULL,  -- CEDULA_PERSONAL, POLIZA, TIMBRE_FISCAL
    name_es VARCHAR(255) NOT NULL,

    -- Montant
    amount NUMERIC(12,2) NOT NULL,
    currency VARCHAR(3) DEFAULT 'XAF',

    -- Référence légale
    legal_reference VARCHAR(255),

    -- Versioning
    effective_from DATE NOT NULL DEFAULT CURRENT_DATE,
    effective_to DATE,

    -- Statut
    is_active BOOLEAN DEFAULT TRUE,

    -- Audit
    created_by UUID REFERENCES users(id),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_by UUID REFERENCES users(id),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    -- Contraintes
    CONSTRAINT valid_supplement_amount CHECK (amount >= 0)
);

CREATE INDEX IF NOT EXISTS idx_ts_code ON tariff_supplements(code);
CREATE INDEX IF NOT EXISTS idx_ts_active ON tariff_supplements(code, is_active) WHERE is_active = TRUE;

-- ============================================================================
-- 3. CREATE WORKFLOW_SUPPLEMENT_CONFIG TABLE
-- ============================================================================
-- Table de liaison: quels suppléments s'appliquent à quels workflows

CREATE TABLE IF NOT EXISTS workflow_supplement_config (
    id SERIAL PRIMARY KEY,

    -- Liaison
    workflow_code VARCHAR(100) NOT NULL,
    supplement_code VARCHAR(50) NOT NULL REFERENCES tariff_supplements(code) ON DELETE CASCADE,

    -- Configuration
    quantity_per_request INTEGER NOT NULL DEFAULT 1,  -- Quantité par demande
    is_required BOOLEAN DEFAULT TRUE,  -- Obligatoire ou optionnel

    -- Statut
    is_active BOOLEAN DEFAULT TRUE,

    -- Audit
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    -- Contrainte: un supplément par workflow
    CONSTRAINT unique_workflow_supplement UNIQUE(workflow_code, supplement_code),
    CONSTRAINT valid_quantity CHECK (quantity_per_request > 0)
);

CREATE INDEX IF NOT EXISTS idx_wsc_workflow ON workflow_supplement_config(workflow_code);
CREATE INDEX IF NOT EXISTS idx_wsc_active ON workflow_supplement_config(workflow_code, is_active) WHERE is_active = TRUE;

-- ============================================================================
-- 4. CREATE TRIGGERS FOR updated_at
-- ============================================================================

CREATE OR REPLACE FUNCTION update_tariff_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_wt_updated_at ON workflow_tariffs;
CREATE TRIGGER trg_wt_updated_at
    BEFORE UPDATE ON workflow_tariffs
    FOR EACH ROW
    EXECUTE FUNCTION update_tariff_updated_at();

DROP TRIGGER IF EXISTS trg_ts_updated_at ON tariff_supplements;
CREATE TRIGGER trg_ts_updated_at
    BEFORE UPDATE ON tariff_supplements
    FOR EACH ROW
    EXECUTE FUNCTION update_tariff_updated_at();

DROP TRIGGER IF EXISTS trg_wsc_updated_at ON workflow_supplement_config;
CREATE TRIGGER trg_wsc_updated_at
    BEFORE UPDATE ON workflow_supplement_config
    FOR EACH ROW
    EXECUTE FUNCTION update_tariff_updated_at();

-- ============================================================================
-- 5. CREATE FUNCTION TO GET WORKFLOW TOTAL
-- ============================================================================
-- Fonction pour calculer le total (tarif base + suppléments)

CREATE OR REPLACE FUNCTION get_workflow_tariff_total(
    p_workflow_code VARCHAR(100),
    p_solicitud_type VARCHAR(50) DEFAULT 'expedicion'
)
RETURNS TABLE (
    base_amount NUMERIC(12,2),
    supplements JSONB,
    supplements_total NUMERIC(12,2),
    total_amount NUMERIC(12,2),
    currency VARCHAR(3)
) AS $$
DECLARE
    v_base NUMERIC(12,2);
    v_supplements JSONB;
    v_supplements_total NUMERIC(12,2);
BEGIN
    -- 1. Récupérer le tarif de base
    SELECT wt.amount
    INTO v_base
    FROM workflow_tariffs wt
    WHERE wt.workflow_code = p_workflow_code
      AND wt.solicitud_type = p_solicitud_type
      AND wt.is_active = TRUE
      AND wt.effective_from <= CURRENT_DATE
      AND (wt.effective_to IS NULL OR wt.effective_to > CURRENT_DATE)
    ORDER BY wt.effective_from DESC
    LIMIT 1;

    v_base := COALESCE(v_base, 0);

    -- 2. Récupérer les suppléments configurés
    SELECT
        jsonb_agg(
            jsonb_build_object(
                'code', ts.code,
                'name', ts.name_es,
                'unit_price', ts.amount,
                'quantity', wsc.quantity_per_request,
                'subtotal', ts.amount * wsc.quantity_per_request
            )
        ),
        COALESCE(SUM(ts.amount * wsc.quantity_per_request), 0)
    INTO v_supplements, v_supplements_total
    FROM workflow_supplement_config wsc
    JOIN tariff_supplements ts ON ts.code = wsc.supplement_code
    WHERE wsc.workflow_code = p_workflow_code
      AND wsc.is_active = TRUE
      AND ts.is_active = TRUE
      AND ts.effective_from <= CURRENT_DATE
      AND (ts.effective_to IS NULL OR ts.effective_to > CURRENT_DATE);

    v_supplements := COALESCE(v_supplements, '[]'::JSONB);
    v_supplements_total := COALESCE(v_supplements_total, 0);

    -- 3. Retourner le résultat
    RETURN QUERY SELECT
        v_base AS base_amount,
        v_supplements AS supplements,
        v_supplements_total AS supplements_total,
        (v_base + v_supplements_total) AS total_amount,
        'XAF'::VARCHAR(3) AS currency;
END;
$$ LANGUAGE plpgsql STABLE;

-- ============================================================================
-- 6. CREATE VIEW FOR ADMIN (Vue récapitulative)
-- ============================================================================

CREATE OR REPLACE VIEW v_workflow_tariffs_summary AS
SELECT
    wt.workflow_code,
    wt.solicitud_type,
    wt.amount AS base_amount,
    COALESCE(supp.supplements_total, 0) AS supplements_total,
    wt.amount + COALESCE(supp.supplements_total, 0) AS total_amount,
    wt.currency,
    wt.legal_reference,
    wt.effective_from,
    wt.is_active
FROM workflow_tariffs wt
LEFT JOIN LATERAL (
    SELECT SUM(ts.amount * wsc.quantity_per_request) AS supplements_total
    FROM workflow_supplement_config wsc
    JOIN tariff_supplements ts ON ts.code = wsc.supplement_code
    WHERE wsc.workflow_code = wt.workflow_code
      AND wsc.is_active = TRUE
      AND ts.is_active = TRUE
) supp ON TRUE
WHERE wt.is_active = TRUE
  AND (wt.effective_to IS NULL OR wt.effective_to > CURRENT_DATE)
ORDER BY wt.workflow_code, wt.solicitud_type;

COMMENT ON VIEW v_workflow_tariffs_summary IS 'Vue récapitulative des tarifs avec suppléments pour interface admin';

-- ============================================================================
-- 7. CREATE VIEW FOR SUPPLEMENTS BY WORKFLOW
-- ============================================================================

CREATE OR REPLACE VIEW v_workflow_supplements AS
SELECT
    wsc.workflow_code,
    ts.code AS supplement_code,
    ts.name_es AS supplement_name,
    ts.amount AS unit_price,
    wsc.quantity_per_request,
    ts.amount * wsc.quantity_per_request AS subtotal,
    wsc.is_required,
    wsc.is_active
FROM workflow_supplement_config wsc
JOIN tariff_supplements ts ON ts.code = wsc.supplement_code
WHERE wsc.is_active = TRUE
  AND ts.is_active = TRUE
ORDER BY wsc.workflow_code, ts.name_es;

COMMENT ON VIEW v_workflow_supplements IS 'Vue des suppléments par workflow';

-- ============================================================================
-- 8. ADD COMMENTS
-- ============================================================================

COMMENT ON TABLE workflow_tariffs IS 'Tarifs de base des workflows (administrables via interface)';
COMMENT ON COLUMN workflow_tariffs.workflow_code IS 'Code du workflow (residencia, pasaporte_nuevo, etc.)';
COMMENT ON COLUMN workflow_tariffs.solicitud_type IS 'Type de sollicitation (expedicion, renovacion, duplicado)';
COMMENT ON COLUMN workflow_tariffs.effective_from IS 'Date de début d''application du tarif';
COMMENT ON COLUMN workflow_tariffs.effective_to IS 'Date de fin d''application (NULL = toujours actif)';

COMMENT ON TABLE tariff_supplements IS 'Suppléments (cédulas, pólizas, timbres)';
COMMENT ON COLUMN tariff_supplements.code IS 'Code unique (CEDULA_PERSONAL, POLIZA, etc.)';

COMMENT ON TABLE workflow_supplement_config IS 'Configuration: quels suppléments s''appliquent à quels workflows';
COMMENT ON COLUMN workflow_supplement_config.quantity_per_request IS 'Nombre de suppléments par demande';

COMMENT ON FUNCTION get_workflow_tariff_total IS 'Calcule le total (tarif base + suppléments) pour un workflow';

-- ============================================================================
-- 9. ADD PERMISSIONS
-- ============================================================================

INSERT INTO permissions (name, resource, action, description, is_critical, module_name)
VALUES
    ('tariffs.read', 'tariffs', 'read', 'Consulter les tarifs', FALSE, 'tariffs'),
    ('tariffs.create', 'tariffs', 'create', 'Créer un tarif', TRUE, 'tariffs'),
    ('tariffs.update', 'tariffs', 'update', 'Modifier un tarif', TRUE, 'tariffs'),
    ('tariffs.delete', 'tariffs', 'delete', 'Supprimer un tarif', TRUE, 'tariffs'),
    ('supplements.read', 'supplements', 'read', 'Consulter les suppléments', FALSE, 'tariffs'),
    ('supplements.create', 'supplements', 'create', 'Créer un supplément', TRUE, 'tariffs'),
    ('supplements.update', 'supplements', 'update', 'Modifier un supplément', TRUE, 'tariffs'),
    ('supplements.delete', 'supplements', 'delete', 'Supprimer un supplément', TRUE, 'tariffs')
ON CONFLICT (name) DO NOTHING;

-- ============================================================================
-- END OF MIGRATION
-- ============================================================================
