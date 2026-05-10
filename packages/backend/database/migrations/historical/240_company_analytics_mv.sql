-- Migration 240: Materialized View for Company Analytics Dashboard
--
-- The /dashboard/analytics endpoint runs 6 heavy JOINs in parallel.
-- This single MV pre-computes all 6 sections as JSONB columns so the
-- endpoint can return O(1) with a single SELECT.
--
-- Sections:
--   1. by_zone_regime  — companies per zone × regime (stacked bar)
--   2. by_forma_juridica — count per legal form (pie chart)
--   3. by_city — top cities by company count + debt (geo)
--   4. debt_by_fee_type — obligations by fee_type (ministry breakdown)
--   5. top_debtors — top 10 companies by outstanding debt
--   6. monthly_trend — companies created per month (last 12 months)
--
-- Refresh: POST /cron/refresh-company-stats (CONCURRENTLY, every 15 min)
--
-- VERIFIED against actual DB columns:
--   companies: id, legal_name, nif, registration_number, regimen_fiscal,
--              forma_juridica, zone_id, city_id, is_active, is_verified, created_at
--   commerce_zones: id, zone_code, name_es
--   cities: id, name, provincia, zone_id
--   commercial_licenses: id, company_id, fiscal_year, total_amount, amount_paid
--   license_obligations: id, license_id, ministry_id, fee_type, amount,
--                         penalty_amount, status, paid_at

BEGIN;

-- ════════════════════════════════════════════════════════════════════
-- Drop if exists (idempotent re-run)
-- ════════════════════════════════════════════════════════════════════
DROP MATERIALIZED VIEW IF EXISTS mv_company_analytics;

-- ════════════════════════════════════════════════════════════════════
-- Single MV: 6 JSONB columns, one row
-- ════════════════════════════════════════════════════════════════════
CREATE MATERIALIZED VIEW mv_company_analytics AS
SELECT
    -- Sentinel column for UNIQUE INDEX (required by REFRESH CONCURRENTLY)
    1::int AS id,

    -- ── 1. Zone × Regime distribution ──────────────────────────────
    (
        SELECT COALESCE(jsonb_agg(row_to_json(sub)::jsonb ORDER BY sub.zone_code, sub.regime), '[]'::jsonb)
        FROM (
            SELECT
                cz.zone_code,
                cz.name_es                                            AS zone_name,
                c.regimen_fiscal                                      AS regime,
                COUNT(*)                                              AS count,
                COALESCE(SUM(cl.total_amount), 0)                     AS total_amount,
                COALESCE(SUM(cl.amount_paid), 0)                      AS paid_amount,
                COALESCE(SUM(cl.total_amount - cl.amount_paid), 0)    AS debt
            FROM companies c
            LEFT JOIN commerce_zones cz ON c.zone_id = cz.id
            LEFT JOIN commercial_licenses cl
                ON cl.company_id = c.id
                AND cl.fiscal_year = EXTRACT(YEAR FROM NOW())::int
            WHERE c.is_active = true
            GROUP BY cz.zone_code, cz.name_es, c.regimen_fiscal
        ) sub
    ) AS by_zone_regime,

    -- ── 2. Forma Juridica distribution ─────────────────────────────
    (
        SELECT COALESCE(jsonb_agg(row_to_json(sub)::jsonb ORDER BY sub.count DESC), '[]'::jsonb)
        FROM (
            SELECT
                c.forma_juridica,
                COUNT(*)                                              AS count,
                COUNT(cl.id)                                          AS with_license,
                COALESCE(SUM(cl.total_amount), 0)                     AS total_amount
            FROM companies c
            LEFT JOIN commercial_licenses cl
                ON cl.company_id = c.id
                AND cl.fiscal_year = EXTRACT(YEAR FROM NOW())::int
            WHERE c.is_active = true AND c.forma_juridica IS NOT NULL
            GROUP BY c.forma_juridica
        ) sub
    ) AS by_forma_juridica,

    -- ── 3. City statistics ─────────────────────────────────────────
    (
        SELECT COALESCE(jsonb_agg(row_to_json(sub)::jsonb ORDER BY sub.companies DESC), '[]'::jsonb)
        FROM (
            SELECT
                ct.name                                               AS city_name,
                ct.provincia,
                cz.zone_code,
                COUNT(c.id)                                           AS companies,
                COUNT(cl.id)                                          AS licenses,
                COALESCE(SUM(cl.total_amount - cl.amount_paid), 0)    AS debt,
                CASE WHEN COALESCE(SUM(cl.total_amount), 0) > 0
                     THEN ROUND(SUM(cl.amount_paid) * 100.0 / SUM(cl.total_amount), 1)
                     ELSE 0 END                                       AS recovery_pct
            FROM companies c
            JOIN cities ct ON c.city_id = ct.id
            LEFT JOIN commerce_zones cz ON c.zone_id = cz.id
            LEFT JOIN commercial_licenses cl
                ON cl.company_id = c.id
                AND cl.fiscal_year = EXTRACT(YEAR FROM NOW())::int
            WHERE c.is_active = true
            GROUP BY ct.name, ct.provincia, cz.zone_code
        ) sub
    ) AS by_city,

    -- ── 4. Debt by fee_type ────────────────────────────────────────
    (
        SELECT COALESCE(jsonb_agg(row_to_json(sub)::jsonb ORDER BY sub.total_amount DESC), '[]'::jsonb)
        FROM (
            SELECT
                lo.fee_type,
                COUNT(DISTINCT cl.company_id)                         AS companies,
                COUNT(lo.id)                                          AS obligations,
                COALESCE(SUM(lo.amount), 0)                           AS total_amount,
                COALESCE(SUM(lo.amount) FILTER (WHERE lo.status = 'paid'), 0) AS paid,
                COALESCE(SUM(lo.amount) FILTER (WHERE lo.status = 'overdue'), 0) AS overdue,
                COALESCE(SUM(lo.penalty_amount), 0)                   AS penalties
            FROM license_obligations lo
            JOIN commercial_licenses cl ON lo.license_id = cl.id
            WHERE cl.fiscal_year = EXTRACT(YEAR FROM NOW())::int
            GROUP BY lo.fee_type
        ) sub
    ) AS debt_by_fee_type,

    -- ── 5. Top 10 debtors ──────────────────────────────────────────
    (
        SELECT COALESCE(jsonb_agg(row_to_json(sub)::jsonb ORDER BY sub.debt DESC), '[]'::jsonb)
        FROM (
            SELECT
                c.id,
                c.legal_name,
                c.nif,
                c.registration_number,
                c.regimen_fiscal,
                cz.zone_code,
                SUM(cl.total_amount - cl.amount_paid)                 AS debt,
                SUM(cl.total_amount)                                  AS total_amount,
                CASE WHEN SUM(cl.total_amount) > 0
                     THEN ROUND(SUM(cl.amount_paid) * 100.0 / SUM(cl.total_amount), 1)
                     ELSE 0 END                                       AS recovery_pct
            FROM companies c
            JOIN commercial_licenses cl ON cl.company_id = c.id
            LEFT JOIN commerce_zones cz ON c.zone_id = cz.id
            WHERE cl.fiscal_year = EXTRACT(YEAR FROM NOW())::int
              AND (cl.total_amount - cl.amount_paid) > 0
            GROUP BY c.id, c.legal_name, c.nif, c.registration_number, c.regimen_fiscal, cz.zone_code
            ORDER BY debt DESC
            LIMIT 10
        ) sub
    ) AS top_debtors,

    -- ── 6. Monthly trend (last 12 months) ──────────────────────────
    (
        SELECT COALESCE(jsonb_agg(row_to_json(sub)::jsonb ORDER BY sub.month), '[]'::jsonb)
        FROM (
            SELECT
                TO_CHAR(created_at, 'YYYY-MM')                        AS month,
                COUNT(*)                                              AS created,
                COUNT(*) FILTER (WHERE regimen_fiscal = 'bundle')     AS bundle,
                COUNT(*) FILTER (WHERE regimen_fiscal = 'declarativo') AS declarativo,
                COUNT(*) FILTER (WHERE is_verified)                   AS verified
            FROM companies
            WHERE created_at >= NOW() - INTERVAL '12 months'
            GROUP BY TO_CHAR(created_at, 'YYYY-MM')
        ) sub
    ) AS monthly_trend,

    -- ── Metadata ───────────────────────────────────────────────────
    NOW() AS refreshed_at;

-- ════════════════════════════════════════════════════════════════════
-- UNIQUE INDEX required for REFRESH CONCURRENTLY
-- Must be on a real column (not an expression) for CONCURRENTLY to work
-- ════════════════════════════════════════════════════════════════════
CREATE UNIQUE INDEX idx_mv_company_analytics_pk ON mv_company_analytics (id);

-- ════════════════════════════════════════════════════════════════════
-- Initial refresh (populate)
-- ════════════════════════════════════════════════════════════════════
REFRESH MATERIALIZED VIEW mv_company_analytics;

COMMIT;
