-- Migration 235: Materialized Views for Company Dashboards (1M+ scale)
-- Part of OMS Companies Phase 1 — Database & Performance Foundation
--
-- Creates 3 materialized views for O(1) dashboard queries:
--   1. mv_company_stats_by_zone — Choropleth map + zone KPIs
--   2. mv_obligation_stats_by_ministry — Ministry supervisor dashboard
--   3. mv_company_global_stats — Admin overview KPIs
--
-- Refreshed via: POST /cron/refresh-company-stats (Cloud Scheduler every 15 min)
-- Uses CONCURRENTLY (requires UNIQUE INDEX on each view)
--
-- VERIFIED against actual DB:
--   commerce_zones: (id UUID, zone_code, zone_tier, zone_rank, name_es)
--   companies: (id UUID, zone_id, is_active, regimen_fiscal, forma_juridica, city_id)
--   commercial_licenses: (company_id UUID, zone_id UUID, fiscal_year INT, total_amount NUMERIC, amount_paid NUMERIC, status)
--   license_obligations: (license_id UUID, ministry_id INT, fee_type VARCHAR, amount NUMERIC, penalty_amount NUMERIC, status VARCHAR, due_date DATE, paid_at TIMESTAMP)

BEGIN;

-- ════════════════════════════════════════════════════════════════════
-- 1. Stats by Zone (Choropleth map + zone supervisor dashboard)
-- ════════════════════════════════════════════════════════════════════

CREATE MATERIALIZED VIEW IF NOT EXISTS mv_company_stats_by_zone AS
SELECT
    cz.id                                                       AS zone_id,
    cz.zone_code,
    cz.zone_tier,
    cz.name_es                                                  AS zone_name,
    -- Company counts
    COUNT(c.id)                                                 AS total_companies,
    COUNT(c.id) FILTER (WHERE c.is_active)                      AS active_companies,
    COUNT(c.id) FILTER (WHERE c.is_active AND NOT c.is_verified) AS pending_verification,
    -- Regime breakdown
    COUNT(c.id) FILTER (WHERE c.regimen_fiscal = 'bundle')      AS bundle_count,
    COUNT(c.id) FILTER (WHERE c.regimen_fiscal = 'declarativo') AS declarativo_count,
    COUNT(c.id) FILTER (WHERE c.regimen_fiscal = 'mixto')       AS mixto_count,
    COUNT(c.id) FILTER (WHERE c.regimen_fiscal = 'exento')      AS exento_count,
    COUNT(c.id) FILTER (WHERE c.regimen_fiscal = 'pendiente')   AS pendiente_count,
    -- License financials (current fiscal year)
    COUNT(DISTINCT cl.id)                                       AS active_licenses,
    COALESCE(SUM(cl.total_amount), 0)                           AS total_obligations_amount,
    COALESCE(SUM(cl.amount_paid), 0)                            AS total_paid_amount,
    COALESCE(SUM(cl.total_amount) - SUM(cl.amount_paid), 0)     AS total_debt,
    -- Recovery rate (avoid division by zero)
    CASE
        WHEN COALESCE(SUM(cl.total_amount), 0) > 0
        THEN ROUND(COALESCE(SUM(cl.amount_paid), 0) * 100.0 / SUM(cl.total_amount), 1)
        ELSE 0
    END                                                         AS recovery_rate_pct,
    NOW()                                                       AS refreshed_at
FROM commerce_zones cz
LEFT JOIN companies c
    ON c.zone_id = cz.id
LEFT JOIN commercial_licenses cl
    ON cl.company_id = c.id
    AND cl.fiscal_year = EXTRACT(YEAR FROM NOW())::int
GROUP BY cz.id, cz.zone_code, cz.zone_tier, cz.name_es;

-- UNIQUE index required for REFRESH CONCURRENTLY
CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_zone_stats_pk
    ON mv_company_stats_by_zone(zone_id);

-- ════════════════════════════════════════════════════════════════════
-- 2. Stats by Ministry × Zone (Ministry supervisor dashboard)
-- ════════════════════════════════════════════════════════════════════

CREATE MATERIALIZED VIEW IF NOT EXISTS mv_obligation_stats_by_ministry AS
SELECT
    lo.ministry_id,
    lo.fee_type,
    cz.id                                                        AS zone_id,
    cz.zone_code,
    -- Company & obligation counts
    COUNT(DISTINCT cl.company_id)                                AS companies_count,
    COUNT(lo.id)                                                 AS obligations_count,
    COUNT(lo.id) FILTER (WHERE lo.status = 'paid')               AS paid_count,
    COUNT(lo.id) FILTER (WHERE lo.status = 'pending')            AS pending_count,
    COUNT(lo.id) FILTER (WHERE lo.status = 'overdue')            AS overdue_count,
    -- Financial amounts
    COALESCE(SUM(lo.amount), 0)                                  AS total_amount,
    COALESCE(SUM(lo.amount) FILTER (WHERE lo.status = 'paid'), 0) AS paid_amount,
    COALESCE(SUM(lo.amount) FILTER (WHERE lo.status = 'overdue'), 0) AS overdue_amount,
    COALESCE(SUM(lo.penalty_amount), 0)                          AS total_penalties,
    -- Recovery rate
    CASE
        WHEN COALESCE(SUM(lo.amount), 0) > 0
        THEN ROUND(
            COALESCE(SUM(lo.amount) FILTER (WHERE lo.status = 'paid'), 0) * 100.0
            / SUM(lo.amount), 1
        )
        ELSE 0
    END                                                          AS recovery_rate_pct,
    NOW()                                                        AS refreshed_at
FROM license_obligations lo
JOIN commercial_licenses cl ON lo.license_id = cl.id
JOIN companies c ON cl.company_id = c.id
LEFT JOIN commerce_zones cz ON c.zone_id = cz.id
WHERE cl.fiscal_year = EXTRACT(YEAR FROM NOW())::int
GROUP BY lo.ministry_id, lo.fee_type, cz.id, cz.zone_code;

-- UNIQUE index: (ministry_id, fee_type, zone_id) is the natural key
-- zone_id can be NULL (companies without zone), so use COALESCE
CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_ministry_stats_pk
    ON mv_obligation_stats_by_ministry(
        ministry_id, fee_type, COALESCE(zone_id, '00000000-0000-0000-0000-000000000000'::uuid)
    );

-- Lookup by ministry (agent dashboard)
CREATE INDEX IF NOT EXISTS idx_mv_ministry_stats_ministry
    ON mv_obligation_stats_by_ministry(ministry_id);

-- ════════════════════════════════════════════════════════════════════
-- 3. Global Stats (Admin overview — single row)
-- ════════════════════════════════════════════════════════════════════

CREATE MATERIALIZED VIEW IF NOT EXISTS mv_company_global_stats AS
SELECT
    COUNT(*)                                                     AS total_companies,
    COUNT(*) FILTER (WHERE is_active)                            AS active_companies,
    COUNT(*) FILTER (WHERE is_verified)                          AS verified_companies,
    COUNT(*) FILTER (WHERE NOT is_active)                        AS inactive_companies,
    -- Regime breakdown
    COUNT(*) FILTER (WHERE regimen_fiscal = 'bundle')            AS bundle_count,
    COUNT(*) FILTER (WHERE regimen_fiscal = 'declarativo')       AS declarativo_count,
    COUNT(*) FILTER (WHERE regimen_fiscal = 'mixto')             AS mixto_count,
    COUNT(*) FILTER (WHERE regimen_fiscal = 'exento')            AS exento_count,
    COUNT(*) FILTER (WHERE regimen_fiscal = 'pendiente')         AS pendiente_count,
    -- Identity coverage
    COUNT(*) FILTER (WHERE nif IS NOT NULL)                      AS with_nif,
    COUNT(*) FILTER (WHERE registration_number IS NOT NULL)      AS with_reg_number,
    COUNT(*) FILTER (WHERE zone_id IS NOT NULL)                  AS with_zone,
    COUNT(*) FILTER (WHERE nif IS NULL AND registration_number IS NULL) AS missing_identifier,
    -- Timestamp
    NOW()                                                        AS refreshed_at
FROM companies;

-- Single row → needs a dummy unique column for CONCURRENTLY
-- Use a constant expression
CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_global_stats_pk
    ON mv_company_global_stats((1));

-- ════════════════════════════════════════════════════════════════════
-- 4. Supporting indexes on license_obligations for the views
-- ════════════════════════════════════════════════════════════════════

-- Ministry lookup (agent debt view)
CREATE INDEX IF NOT EXISTS idx_obligations_ministry_status
    ON license_obligations(ministry_id, status);

-- License lookup (for JOIN)
CREATE INDEX IF NOT EXISTS idx_obligations_license_id
    ON license_obligations(license_id);

-- Due date for compliance checks
CREATE INDEX IF NOT EXISTS idx_obligations_due_date
    ON license_obligations(due_date)
    WHERE status NOT IN ('paid', 'cancelled');

-- ════════════════════════════════════════════════════════════════════
-- 5. Initial refresh (populate the views)
-- ════════════════════════════════════════════════════════════════════

REFRESH MATERIALIZED VIEW mv_company_stats_by_zone;
REFRESH MATERIALIZED VIEW mv_obligation_stats_by_ministry;
REFRESH MATERIALIZED VIEW mv_company_global_stats;

COMMIT;
