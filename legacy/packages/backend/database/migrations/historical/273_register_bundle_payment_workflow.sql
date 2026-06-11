-- Migration 245: Register BUNDLE_PAYMENT workflow in workflows table + entities
-- Date: 2026-03-20
-- Context: Session 7A — BundlePaymentWorkflow registration
--
-- Step 1: INSERT into workflows table (trigger validates entity workflow_codes against this)
-- Step 2: UPDATE entities.workflow_codes to include BUNDLE_PAYMENT
--
-- Addendum 3: Ayuntamiento and Cámara are ALWAYS independent (both modes A and B).
-- Mode A/B only affects TESORO routing (per-ministry vs polyvalent).

-- ROLLBACK (if needed):
--   DELETE FROM workflows WHERE code = 'BUNDLE_PAYMENT';
--   UPDATE entities SET workflow_codes = workflow_codes - 'BUNDLE_PAYMENT'
--     WHERE workflow_codes @> '"BUNDLE_PAYMENT"'::jsonb;

BEGIN;

-- ============================================================
-- Step 1: Register BUNDLE_PAYMENT in workflows table
-- ============================================================

INSERT INTO workflows (code, name_es, description_es, category, entity_code,
                       workflow_type, requires_agent_validation, requires_appointment,
                       is_generic, is_active, icon, display_order)
VALUES (
    'BUNDLE_PAYMENT',
    'Pago de Obligaciones Fiscales',
    'Pago de obligaciones fiscales anuales para empresas autónomas del Padrón Empresarial',
    'COMERCIO',
    'TESORO',
    'standard',
    true,       -- Agent Tesoro validates cash payments
    false,      -- No appointment needed
    false,      -- Predefined, not generic
    true,       -- Active
    'Receipt',  -- Lucide icon
    100         -- Display order (after other workflows)
)
ON CONFLICT (code) DO UPDATE SET
    name_es = EXCLUDED.name_es,
    description_es = EXCLUDED.description_es,
    category = EXCLUDED.category,
    entity_code = EXCLUDED.entity_code,
    is_active = EXCLUDED.is_active,
    updated_at = NOW();

-- ============================================================
-- Step 2: Register BUNDLE_PAYMENT on entities workflow_codes
-- ============================================================

-- TESORO: primary entity for bundle payment validation
UPDATE entities
SET workflow_codes = workflow_codes || '["BUNDLE_PAYMENT"]'::jsonb
WHERE code = 'TESORO'
  AND NOT workflow_codes @> '"BUNDLE_PAYMENT"'::jsonb;

-- AYUNTAMIENTO: independent processing of municipal obligations (Addendum 3)
UPDATE entities
SET workflow_codes = workflow_codes || '["BUNDLE_PAYMENT"]'::jsonb
WHERE code = 'AYUNTAMIENTO'
  AND NOT workflow_codes @> '"BUNDLE_PAYMENT"'::jsonb;

-- CAMARA_COMERCIO: independent processing of chamber obligations (Addendum 3)
UPDATE entities
SET workflow_codes = workflow_codes || '["BUNDLE_PAYMENT"]'::jsonb
WHERE code = 'CAMARA_COMERCIO'
  AND NOT workflow_codes @> '"BUNDLE_PAYMENT"'::jsonb;

-- MIN_* ministry entities: handle tesoro obligations in Mode A (per_line routing by ministry_id)
-- Exclude MINFP (Función Pública) — not an OMS fiscal entity
UPDATE entities
SET workflow_codes = workflow_codes || '["BUNDLE_PAYMENT"]'::jsonb
WHERE code LIKE 'MIN_%'
  AND code != 'MINFP'
  AND is_active = true
  AND NOT workflow_codes @> '"BUNDLE_PAYMENT"'::jsonb;

COMMIT;
