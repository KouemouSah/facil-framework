-- Migration 222: Remove 'mixto' from DB schema (CHECK constraints + materialized views)
--
-- The "mixto" regime does not exist in GE fiscal law.
-- Migration 221 already removed all mixto data. This migration cleans up
-- the schema to prevent future insertions.

BEGIN;

-- ── Step 1: Drop and recreate CHECK constraints without 'mixto' ──

-- companies.regimen_fiscal
ALTER TABLE companies DROP CONSTRAINT IF EXISTS companies_regimen_fiscal_check;
ALTER TABLE companies ADD CONSTRAINT companies_regimen_fiscal_check
    CHECK (regimen_fiscal IN ('bundle', 'declarativo', 'exento', 'pendiente'));

-- company_creation_drafts.regimen_fiscal (if exists)
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.columns
               WHERE table_name = 'company_creation_drafts' AND column_name = 'regimen_fiscal') THEN
        EXECUTE 'ALTER TABLE company_creation_drafts DROP CONSTRAINT IF EXISTS company_creation_drafts_regimen_fiscal_check';
        EXECUTE $chk$ALTER TABLE company_creation_drafts ADD CONSTRAINT company_creation_drafts_regimen_fiscal_check
            CHECK (regimen_fiscal IS NULL OR regimen_fiscal IN ('bundle', 'declarativo', 'exento', 'pendiente'))$chk$;
    END IF;
END $$;

-- ── Step 2: Recreate materialized views without mixto_count ──

-- mv_company_stats_by_zone
DROP MATERIALIZED VIEW IF EXISTS mv_company_stats_by_zone;
CREATE MATERIALIZED VIEW mv_company_stats_by_zone AS
SELECT
    cz.id AS zone_id,
    cz.zone_code,
    cz.zone_tier,
    COUNT(c.id) AS total_companies,
    COUNT(c.id) FILTER (WHERE c.is_active) AS active_companies,
    COUNT(c.id) FILTER (WHERE c.is_verified) AS verified_companies,
    COUNT(c.id) FILTER (WHERE NOT c.is_active) AS inactive_companies,
    COUNT(c.id) FILTER (WHERE c.regimen_fiscal = 'bundle') AS bundle_count,
    COUNT(c.id) FILTER (WHERE c.regimen_fiscal = 'declarativo') AS declarativo_count,
    COUNT(c.id) FILTER (WHERE c.regimen_fiscal = 'exento') AS exento_count,
    COUNT(c.id) FILTER (WHERE c.regimen_fiscal = 'pendiente') AS pendiente_count,
    COUNT(c.id) FILTER (WHERE c.nif IS NOT NULL) AS with_nif,
    COUNT(c.id) FILTER (WHERE c.registration_number IS NOT NULL) AS with_reg_number,
    COUNT(c.id) FILTER (WHERE c.zone_id IS NOT NULL) AS with_zone,
    COUNT(c.id) FILTER (WHERE c.nif IS NULL AND c.registration_number IS NULL) AS missing_identifier,
    NOW() AS refreshed_at
FROM commerce_zones cz
LEFT JOIN companies c ON c.zone_id = cz.id
GROUP BY cz.id, cz.zone_code, cz.zone_tier
ORDER BY cz.zone_code;

CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_zone_stats_zone_id ON mv_company_stats_by_zone (zone_id);

-- mv_company_global_stats
DROP MATERIALIZED VIEW IF EXISTS mv_company_global_stats;
CREATE MATERIALIZED VIEW mv_company_global_stats AS
SELECT
    COUNT(*) AS total_companies,
    COUNT(*) FILTER (WHERE is_active) AS active_companies,
    COUNT(*) FILTER (WHERE NOT is_active) AS pending_verification,
    COUNT(*) FILTER (WHERE regimen_fiscal = 'bundle') AS bundle_count,
    COUNT(*) FILTER (WHERE regimen_fiscal = 'declarativo') AS declarativo_count,
    COUNT(*) FILTER (WHERE regimen_fiscal = 'exento') AS exento_count,
    COUNT(*) FILTER (WHERE regimen_fiscal = 'pendiente') AS pendiente_count,
    (SELECT COUNT(*) FROM commercial_licenses WHERE status IN ('open', 'partial')) AS active_licenses,
    COALESCE((SELECT SUM(total_amount) FROM commercial_licenses), 0) AS total_obligations_amount,
    COALESCE((SELECT SUM(amount_paid) FROM commercial_licenses), 0) AS total_paid_amount,
    COALESCE((SELECT SUM(total_amount - amount_paid) FROM commercial_licenses WHERE total_amount > amount_paid), 0) AS total_debt,
    CASE
        WHEN COALESCE((SELECT SUM(total_amount) FROM commercial_licenses), 0) > 0
        THEN ROUND(COALESCE((SELECT SUM(amount_paid) FROM commercial_licenses), 0) * 100.0 /
             COALESCE((SELECT SUM(total_amount) FROM commercial_licenses), 1), 1)
        ELSE 0
    END AS recovery_rate_pct,
    NOW() AS refreshed_at
FROM companies;

COMMIT;
