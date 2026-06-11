-- Migration 293: Register BUNDLE_PAYMENT in valid_workflow_codes
-- (renamed from 292 — number 292 taken by agent_executive_audit_log)
-- Date: 2026-04-11
-- Context: Bug latent découvert lors des tests P2 (plan INSPECTION_BUNDLE_P2_DETAIL.md)
--
-- PROBLÈME:
--   - workflows table contient BUNDLE_PAYMENT (via migration 273)
--   - valid_workflow_codes table NE contient PAS BUNDLE_PAYMENT
--   - service_requests.workflow_code a une FK `fk_sr_valid_workflow_code`
--     vers valid_workflow_codes(code)
--   - Conséquence: AUCUN service_request BUNDLE_PAYMENT n'a jamais pu être
--     inséré → explique pourquoi 0 SR bundle en prod malgré 13 licences.
--     Le wizard citoyen bundle cassait silencieusement dès l'INSERT.
--
-- FIX: INSERT idempotent de BUNDLE_PAYMENT dans valid_workflow_codes.
-- Aligne avec FIELD_INSPECTION (déjà présent depuis 2026-04-07).
--
-- Vérifié 2026-04-11:
--   SELECT code FROM valid_workflow_codes → contient 'FIELD_INSPECTION',
--     NOT 'BUNDLE_PAYMENT'
--   SELECT code FROM workflows → contient 'BUNDLE_PAYMENT'

BEGIN;

INSERT INTO valid_workflow_codes (code, base_code, resolution_key, is_active)
VALUES ('BUNDLE_PAYMENT', NULL, 'BUNDLE', TRUE)
ON CONFLICT (code) DO NOTHING;

-- Sanity check
DO $$
DECLARE
    v_has_bundle BOOLEAN;
    v_has_field BOOLEAN;
BEGIN
    SELECT EXISTS (
        SELECT 1 FROM valid_workflow_codes WHERE code = 'BUNDLE_PAYMENT'
    ) INTO v_has_bundle;

    SELECT EXISTS (
        SELECT 1 FROM valid_workflow_codes WHERE code = 'FIELD_INSPECTION'
    ) INTO v_has_field;

    IF NOT v_has_bundle THEN
        RAISE EXCEPTION 'Migration 292: BUNDLE_PAYMENT insertion failed';
    END IF;

    IF NOT v_has_field THEN
        RAISE WARNING 'Migration 292: FIELD_INSPECTION also missing (expected from 287)';
    END IF;

    RAISE NOTICE 'Migration 292: BUNDLE_PAYMENT now registered in valid_workflow_codes';
END $$;

COMMIT;

-- ROLLBACK (manual, if needed):
-- BEGIN;
--   DELETE FROM valid_workflow_codes WHERE code = 'BUNDLE_PAYMENT';
-- COMMIT;
