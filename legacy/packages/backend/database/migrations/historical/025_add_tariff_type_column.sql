-- Migration: 025_add_tariff_type_column.sql
-- Date: 2025-12-28
-- Description: Ajoute tariff_type et percentage_rate pour configuration admin
-- Author: TaxasGE Development Team

-- ============================================================================
-- 1. ADD TARIFF_TYPE COLUMN
-- ============================================================================
-- Types supportés:
--   FIXED: Montant fixe (utilise 'amount')
--   PERCENTAGE: Pourcentage de valeur (utilise 'percentage_rate')
--   NOTA_INGRESO: Montant extrait du document Nota de Ingreso

ALTER TABLE workflow_tariffs
ADD COLUMN IF NOT EXISTS tariff_type VARCHAR(20) NOT NULL DEFAULT 'FIXED';

-- ============================================================================
-- 2. ADD PERCENTAGE_RATE COLUMN
-- ============================================================================
-- Utilisé uniquement pour tariff_type = 'PERCENTAGE'
-- Exemple: 0.5 = 0.5% (pour CONTRATO ONRC)

ALTER TABLE workflow_tariffs
ADD COLUMN IF NOT EXISTS percentage_rate NUMERIC(5,2);

-- ============================================================================
-- 3. ADD CHECK CONSTRAINT
-- ============================================================================
-- Validation: s'assurer que les bonnes colonnes sont remplies selon le type

ALTER TABLE workflow_tariffs
DROP CONSTRAINT IF EXISTS check_tariff_config;

ALTER TABLE workflow_tariffs
ADD CONSTRAINT check_tariff_config CHECK (
    (tariff_type = 'FIXED' AND amount >= 0) OR
    (tariff_type = 'PERCENTAGE' AND percentage_rate > 0) OR
    (tariff_type = 'NOTA_INGRESO')
);

-- ============================================================================
-- 4. UPDATE EXISTING DATA
-- ============================================================================
-- Mettre à jour les workflows CONTRATO existants en PERCENTAGE

UPDATE workflow_tariffs
SET tariff_type = 'PERCENTAGE',
    percentage_rate = 0.5,
    amount = 0  -- Amount non utilisé pour PERCENTAGE
WHERE workflow_code LIKE 'CONTRATO_%'
  AND tariff_type = 'FIXED';

-- Mettre à jour RESIDENCIA en NOTA_INGRESO
UPDATE workflow_tariffs
SET tariff_type = 'NOTA_INGRESO',
    amount = 0  -- Amount vient du document
WHERE workflow_code LIKE 'RESIDENCIA_%'
  AND tariff_type = 'FIXED';

-- ============================================================================
-- 5. ADD INDEX FOR TARIFF_TYPE
-- ============================================================================

CREATE INDEX IF NOT EXISTS idx_wt_tariff_type
ON workflow_tariffs(tariff_type);

-- ============================================================================
-- 6. UPDATE FUNCTION get_workflow_tariff_total
-- ============================================================================
-- Retourne maintenant tariff_type et percentage_rate

DROP FUNCTION IF EXISTS get_workflow_tariff_total(VARCHAR, VARCHAR);

CREATE OR REPLACE FUNCTION get_workflow_tariff_total(
    p_workflow_code VARCHAR(100),
    p_solicitud_type VARCHAR(50) DEFAULT 'expedicion'
)
RETURNS TABLE (
    tariff_type VARCHAR(20),
    base_amount NUMERIC(12,2),
    percentage_rate NUMERIC(5,2),
    supplements JSONB,
    supplements_total NUMERIC(12,2),
    total_amount NUMERIC(12,2),
    currency VARCHAR(3)
) AS $$
DECLARE
    v_tariff_type VARCHAR(20);
    v_base NUMERIC(12,2);
    v_percentage NUMERIC(5,2);
    v_supplements JSONB;
    v_supplements_total NUMERIC(12,2);
BEGIN
    -- 1. Récupérer le tarif de base avec type
    SELECT wt.tariff_type, wt.amount, wt.percentage_rate
    INTO v_tariff_type, v_base, v_percentage
    FROM workflow_tariffs wt
    WHERE wt.workflow_code = p_workflow_code
      AND wt.solicitud_type = p_solicitud_type
      AND wt.is_active = TRUE
      AND wt.effective_from <= CURRENT_DATE
      AND (wt.effective_to IS NULL OR wt.effective_to > CURRENT_DATE)
    ORDER BY wt.effective_from DESC
    LIMIT 1;

    v_tariff_type := COALESCE(v_tariff_type, 'FIXED');
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
        v_tariff_type AS tariff_type,
        v_base AS base_amount,
        v_percentage AS percentage_rate,
        v_supplements AS supplements,
        v_supplements_total AS supplements_total,
        (v_base + v_supplements_total) AS total_amount,
        'XAF'::VARCHAR(3) AS currency;
END;
$$ LANGUAGE plpgsql STABLE;

COMMENT ON FUNCTION get_workflow_tariff_total IS 'Calcule le total avec type de tarif (FIXED, PERCENTAGE, NOTA_INGRESO)';

-- ============================================================================
-- 7. UPDATE VIEW
-- ============================================================================

DROP VIEW IF EXISTS v_workflow_tariffs_summary;

CREATE OR REPLACE VIEW v_workflow_tariffs_summary AS
SELECT
    wt.workflow_code,
    wt.solicitud_type,
    wt.tariff_type,
    wt.amount AS base_amount,
    wt.percentage_rate,
    COALESCE(supp.supplements_total, 0) AS supplements_total,
    CASE
        WHEN wt.tariff_type = 'FIXED' THEN wt.amount + COALESCE(supp.supplements_total, 0)
        WHEN wt.tariff_type = 'PERCENTAGE' THEN COALESCE(supp.supplements_total, 0)  -- Base calculée dynamiquement
        ELSE COALESCE(supp.supplements_total, 0)  -- NOTA_INGRESO: base from document
    END AS total_amount,
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

COMMENT ON VIEW v_workflow_tariffs_summary IS 'Vue récapitulative avec tariff_type pour interface admin';

-- ============================================================================
-- 8. ADD COMMENT
-- ============================================================================

COMMENT ON COLUMN workflow_tariffs.tariff_type IS 'Type de tarification: FIXED, PERCENTAGE, NOTA_INGRESO';
COMMENT ON COLUMN workflow_tariffs.percentage_rate IS 'Taux en % (ex: 0.5 = 0.5%) - utilisé si tariff_type = PERCENTAGE';

-- ============================================================================
-- END OF MIGRATION
-- ============================================================================
