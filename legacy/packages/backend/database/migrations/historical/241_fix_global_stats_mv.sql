-- Migration 241: Fix mv_company_global_stats — restore 6 missing columns
--
-- Migration 222 recreated the MV but dropped:
--   verified_companies, inactive_companies, with_nif, with_reg_number, with_zone, missing_identifier
-- These columns are required by GET /dashboard/global-stats (GlobalStats frontend type).
-- The live query fallback had them, but the MV path returned NULLs → KPI "Verificadas" showed 0.

BEGIN;

DROP MATERIALIZED VIEW IF EXISTS mv_company_global_stats;

CREATE MATERIALIZED VIEW mv_company_global_stats AS
SELECT
    COUNT(*)                                                     AS total_companies,
    COUNT(*) FILTER (WHERE is_active)                            AS active_companies,
    COUNT(*) FILTER (WHERE is_verified)                          AS verified_companies,
    COUNT(*) FILTER (WHERE NOT is_active)                        AS inactive_companies,
    -- Regime breakdown
    COUNT(*) FILTER (WHERE regimen_fiscal = 'bundle')            AS bundle_count,
    COUNT(*) FILTER (WHERE regimen_fiscal = 'declarativo')       AS declarativo_count,
    COUNT(*) FILTER (WHERE regimen_fiscal = 'exento')            AS exento_count,
    COUNT(*) FILTER (WHERE regimen_fiscal = 'pendiente')         AS pendiente_count,
    -- Identity coverage
    COUNT(*) FILTER (WHERE nif IS NOT NULL)                      AS with_nif,
    COUNT(*) FILTER (WHERE registration_number IS NOT NULL)      AS with_reg_number,
    COUNT(*) FILTER (WHERE zone_id IS NOT NULL)                  AS with_zone,
    COUNT(*) FILTER (WHERE nif IS NULL AND registration_number IS NULL) AS missing_identifier,
    -- Licenses & debt (subqueries — fast on small table)
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
    -- Timestamp
    NOW() AS refreshed_at
FROM companies;

CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_global_stats_pk
    ON mv_company_global_stats((1));

COMMIT;
