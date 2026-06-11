-- Migration 222: Fix v_obligation_routing + add missing set_updated_at trigger
--
-- Fixes 2 bugs found in Phase 1-4 audit:
--
-- BUG 1 (CRITIQUE): v_obligation_routing conflates payment validators and
--   post-payment processors. All MIN_* entities had fee_type='tesoro' which
--   is semantically wrong — they don't validate payments, they process
--   obligations AFTER TESORO validates. The view now distinguishes:
--     - payment_validator: TESORO, AYUNTAMIENTO, CAMARA_COMERCIO
--     - post_payment_processor: MIN_* (Mode A per-line ministry routing)
--
-- BUG 2 (MAJEUR): fiscal_config_rules has updated_at column but NO
--   set_updated_at trigger. updated_at never changes after creation.

BEGIN;

-- ============================================================
-- Fix 1: Missing set_updated_at trigger on fiscal_config_rules
-- ============================================================

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_trigger
        WHERE tgname = 'set_updated_at_fiscal_config_rules'
        AND tgrelid = 'fiscal_config_rules'::regclass
    ) THEN
        CREATE TRIGGER set_updated_at_fiscal_config_rules
            BEFORE UPDATE ON fiscal_config_rules
            FOR EACH ROW
            EXECUTE FUNCTION update_updated_at_column();
    END IF;
END $$;

-- ============================================================
-- Fix 2: Rebuild v_obligation_routing with routing_role
-- ============================================================
--
-- 2-step OMS routing model:
--   Step 1 (payment validation): obligation.fee_type → payment_validator entity
--     - tesoro    → TESORO (validates ALL 948 tesoro items regardless of ministry)
--     - municipal → AYUNTAMIENTO (24 items, ministry_id=107)
--     - chamber   → CAMARA_COMERCIO (90 items, ministry_id=108)
--
--   Step 2 (post-payment processing, Mode A only):
--     After TESORO validates a tesoro payment, route by ministry_id:
--     - ministry_id=87  → MIN_COMERCIO
--     - ministry_id=91  → MIN_HACIENDA
--     - ministry_id=92  → MIN_INFORMACION
--     - ministry_id=103 → MIN_TURISMO
--     - ministry_id=104 → MIN_AGRICULTURA
--     - ministry_id=105 → MIN_ELECTRICIDAD

DROP VIEW IF EXISTS v_obligation_routing;
CREATE VIEW v_obligation_routing AS
SELECT
    e.id AS entity_id,
    e.code AS entity_code,
    e.name AS entity_name,
    e.ministry_id,
    el.id AS entity_location_id,
    el.city,
    el.city_id,
    el.region,

    -- routing_role: what this entity does in the OMS pipeline
    CASE
        WHEN e.code IN ('TESORO', 'AYUNTAMIENTO', 'CAMARA_COMERCIO')
            THEN 'payment_validator'
        ELSE 'post_payment_processor'
    END AS routing_role,

    -- validates_fee_type: which fee_type this entity handles
    -- For payment_validators: the fee_type they validate
    -- For post_payment_processors: always 'tesoro' (they only process after TESORO validates)
    CASE
        WHEN e.code = 'AYUNTAMIENTO' THEN 'municipal'
        WHEN e.code = 'CAMARA_COMERCIO' THEN 'chamber'
        ELSE 'tesoro'
    END AS validates_fee_type

FROM entities e
JOIN entity_locations el ON el.entity_id = e.id AND el.is_active = true
WHERE e.code IN (
    'TESORO', 'AYUNTAMIENTO', 'CAMARA_COMERCIO',
    'MIN_HACIENDA', 'MIN_COMERCIO', 'MIN_INFORMACION',
    'MIN_TURISMO', 'MIN_AGRICULTURA', 'MIN_ELECTRICIDAD'
);

COMMENT ON VIEW v_obligation_routing IS
    'OMS 2-step routing: Step 1 = payment_validator (fee_type → TESORO/AYUNT/CAMARA), '
    'Step 2 = post_payment_processor (ministry_id → MIN_* for Mode A). '
    'Query pattern: WHERE routing_role = ''payment_validator'' AND validates_fee_type = $fee_type AND region = $region';

COMMIT;
