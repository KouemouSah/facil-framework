-- Migration 221: Fix SL/SA regimen_fiscal — remove invalid bundle/mixto assignments
--
-- Background: In GE fiscal law, only AUTONOMO (Padrón Empresarial, PE-XXXX) companies
-- use zone-based bundle pricing. SL/SA/sucursal/cooperativa use declarative regime
-- (Impuesto de Sociedades, IVA). The "mixto" regime does not exist in GE fiscal law.
--
-- This migration fixes seed data that incorrectly assigned bundle/mixto to SL/SA companies.
-- It also cleans up commercial_licenses and license_obligations for affected companies.

BEGIN;

-- ── Step 1: Identify affected companies ──
-- Log what we're about to change
DO $$
DECLARE
    affected_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO affected_count
    FROM companies
    WHERE forma_juridica NOT IN ('autonomo', 'empresa_individual')
      AND regimen_fiscal IN ('bundle', 'mixto');
    RAISE NOTICE 'Companies to fix: % (SL/SA with bundle/mixto → declarativo)', affected_count;
END $$;

-- ── Step 2: Delete license_obligations for affected licenses ──
DELETE FROM license_obligations
WHERE license_id IN (
    SELECT cl.id
    FROM commercial_licenses cl
    JOIN companies c ON cl.company_id = c.id
    WHERE c.forma_juridica NOT IN ('autonomo', 'empresa_individual')
      AND c.regimen_fiscal IN ('bundle', 'mixto')
);

-- ── Step 3: Delete commercial_licenses for affected companies ──
DELETE FROM commercial_licenses
WHERE company_id IN (
    SELECT id FROM companies
    WHERE forma_juridica NOT IN ('autonomo', 'empresa_individual')
      AND regimen_fiscal IN ('bundle', 'mixto')
);

-- ── Step 4: Update companies — SL/SA/etc → declarativo, clear commerce_type ──
UPDATE companies
SET regimen_fiscal = 'declarativo',
    commerce_type = NULL,
    updated_at = NOW()
WHERE forma_juridica NOT IN ('autonomo', 'empresa_individual')
  AND regimen_fiscal IN ('bundle', 'mixto');

-- ── Step 5: Remove 'mixto' from any remaining data ──
-- (No companies should have mixto after step 4, but be safe)
UPDATE companies
SET regimen_fiscal = 'declarativo',
    updated_at = NOW()
WHERE regimen_fiscal = 'mixto';

-- ── Step 6: Verify final state ──
DO $$
DECLARE
    bundle_non_autonomo INTEGER;
    mixto_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO bundle_non_autonomo
    FROM companies
    WHERE forma_juridica NOT IN ('autonomo', 'empresa_individual')
      AND regimen_fiscal = 'bundle';

    SELECT COUNT(*) INTO mixto_count
    FROM companies WHERE regimen_fiscal = 'mixto';

    IF bundle_non_autonomo > 0 THEN
        RAISE EXCEPTION 'ASSERTION FAILED: % non-autonomo companies still have bundle regime', bundle_non_autonomo;
    END IF;

    IF mixto_count > 0 THEN
        RAISE EXCEPTION 'ASSERTION FAILED: % companies still have mixto regime', mixto_count;
    END IF;

    RAISE NOTICE 'Verification OK: 0 non-autonomo/bundle, 0 mixto';
END $$;

COMMIT;
