-- Migration 242: Fix mv_company_stats_by_zone — restore license/debt columns + zone_name
--
-- Migration 222 recreated the MV but dropped:
--   zone_name, pending_verification, active_licenses,
--   total_obligations_amount, total_paid_amount, total_debt, recovery_rate_pct
-- These are required by GET /dashboard/zone-stats and GET /dashboard/zone-stats/mine.
-- The supervisor site dashboard shows 0 for debt, licenses, recovery rate.

BEGIN;

DROP MATERIALIZED VIEW IF EXISTS mv_company_stats_by_zone;

CREATE MATERIALIZED VIEW mv_company_stats_by_zone AS
SELECT
    cz.id                                                       AS zone_id,
    cz.zone_code,
    cz.zone_tier,
    cz.name_es                                                  AS zone_name,
    -- Company counts
    COUNT(c.id)                                                 AS total_companies,
    COUNT(c.id) FILTER (WHERE c.is_active)                      AS active_companies,
    COUNT(c.id) FILTER (WHERE c.is_verified)                    AS verified_companies,
    COUNT(c.id) FILTER (WHERE NOT c.is_active)                  AS inactive_companies,
    COUNT(c.id) FILTER (WHERE c.is_active AND NOT c.is_verified) AS pending_verification,
    -- Regime breakdown
    COUNT(c.id) FILTER (WHERE c.regimen_fiscal = 'bundle')      AS bundle_count,
    COUNT(c.id) FILTER (WHERE c.regimen_fiscal = 'declarativo') AS declarativo_count,
    COUNT(c.id) FILTER (WHERE c.regimen_fiscal = 'exento')      AS exento_count,
    COUNT(c.id) FILTER (WHERE c.regimen_fiscal = 'pendiente')   AS pendiente_count,
    -- Identity coverage
    COUNT(c.id) FILTER (WHERE c.nif IS NOT NULL)                AS with_nif,
    COUNT(c.id) FILTER (WHERE c.registration_number IS NOT NULL) AS with_reg_number,
    COUNT(c.id) FILTER (WHERE c.zone_id IS NOT NULL)            AS with_zone,
    COUNT(c.id) FILTER (WHERE c.nif IS NULL AND c.registration_number IS NULL) AS missing_identifier,
    -- License financials
    COUNT(DISTINCT cl.id)                                       AS active_licenses,
    COALESCE(SUM(cl.total_amount), 0)                           AS total_obligations_amount,
    COALESCE(SUM(cl.amount_paid), 0)                            AS total_paid_amount,
    COALESCE(SUM(cl.total_amount) - SUM(cl.amount_paid), 0)     AS total_debt,
    CASE
        WHEN COALESCE(SUM(cl.total_amount), 0) > 0
        THEN ROUND(COALESCE(SUM(cl.amount_paid), 0) * 100.0 / SUM(cl.total_amount), 1)
        ELSE 0
    END                                                         AS recovery_rate_pct,
    NOW()                                                       AS refreshed_at
FROM commerce_zones cz
LEFT JOIN companies c ON c.zone_id = cz.id
LEFT JOIN commercial_licenses cl ON cl.company_id = c.id
GROUP BY cz.id, cz.zone_code, cz.zone_tier, cz.name_es;

CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_zone_stats_zone_id
    ON mv_company_stats_by_zone (zone_id);

COMMIT;
