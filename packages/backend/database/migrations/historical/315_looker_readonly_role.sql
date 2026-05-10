-- =============================================================================
-- Migration 315 — looker_readonly role for Looker Studio business dashboards
-- =============================================================================
-- Created: 2026-05-01
-- Plan reference: .claude/plans/LOOKER_STUDIO_BUSINESS_DASHBOARDS_PLAN.md
--
-- Provisions a least-privilege Postgres role used by Looker Studio's
-- PostgreSQL connector to power 4 reference business dashboards
-- (Recaudación Fiscal, Adopción Ciudadana, Performance Agentes,
-- Catalogue Services). The role can SELECT only from materialized
-- views and reporting views — never from tables containing PII.
--
-- Idempotent: safe to re-run. Password reset is intentionally NOT in this
-- migration — it lives in GCP Secret Manager (`looker-readonly-pwd`) and is
-- applied by the operator via `ALTER ROLE looker_readonly WITH PASSWORD ...`
-- Pulled from SM. This file holds only the structural pieces that can live
-- in version control safely.
--
-- Operator runbook for credentials:
--   gcloud secrets versions access latest --secret=looker-readonly-pwd \
--     --project=taxasge-dev
--   psql "$DATABASE_URL" -c "ALTER ROLE looker_readonly WITH PASSWORD '<paste>';"
--
-- Free tier note (Supabase): IP allowlist is a Pro feature — this migration
-- relies on (a) strong password (43 char urlsafe) (b) per-role connection
-- limit (c) statement timeout (d) deny-by-default GRANTs.
-- =============================================================================

BEGIN;

-- ---------------------------------------------------------------------------
-- 1. CREATE ROLE — idempotent.
-- On Supabase the `postgres` user has CREATEROLE but NOT SUPERUSER, so the
-- role is created with default attributes (rolsuper=false, rolcreaterole=false,
-- rolcreatedb=false). LOGIN is added explicitly.
-- ---------------------------------------------------------------------------
DO $$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'looker_readonly') THEN
    CREATE ROLE looker_readonly WITH LOGIN;
    RAISE NOTICE 'role looker_readonly created';
  ELSE
    RAISE NOTICE 'role looker_readonly already exists';
  END IF;
END
$$;

-- ---------------------------------------------------------------------------
-- 2. PER-SESSION SAFETY — connection limit + timeouts.
-- All ALTER ROLE ... SET / CONNECTION LIMIT calls work without SUPERUSER.
-- ---------------------------------------------------------------------------
ALTER ROLE looker_readonly CONNECTION LIMIT 5;
ALTER ROLE looker_readonly SET statement_timeout = '30s';
ALTER ROLE looker_readonly SET idle_in_transaction_session_timeout = '60s';
ALTER ROLE looker_readonly SET search_path = public;

-- ---------------------------------------------------------------------------
-- 3. SCHEMA USAGE
-- ---------------------------------------------------------------------------
GRANT USAGE ON SCHEMA public TO looker_readonly;

-- ---------------------------------------------------------------------------
-- 4. SELECT GRANTS — strictly scoped to aggregated MVs / reporting views.
-- These objects already aggregate data — they expose row-level metrics, not
-- row-level PII. If we ever add a non-aggregated view to this list, audit
-- whether row-level PII (email, full_name, document content) leaks before
-- granting.
-- ---------------------------------------------------------------------------

-- 4a. Recaudación / Treasury
GRANT SELECT ON public.mv_treasury_daily_kpis              TO looker_readonly;
GRANT SELECT ON public.mv_reconciliation_stats             TO looker_readonly;
GRANT SELECT ON public.mv_obligation_stats_by_ministry     TO looker_readonly;

-- 4b. Agent performance & SLA
GRANT SELECT ON public.mv_agent_daily_workload             TO looker_readonly;
GRANT SELECT ON public.v_active_assignments                TO looker_readonly;
GRANT SELECT ON public.v_active_service_request_assignments TO looker_readonly;

-- 4c. Service catalog
GRANT SELECT ON public.mv_fiscal_services_catalog          TO looker_readonly;
GRANT SELECT ON public.mv_services_translated              TO looker_readonly;

-- 4d. Adoption (homepage + ministry/category breakdowns)
GRANT SELECT ON public.homepage_stats                      TO looker_readonly;
GRANT SELECT ON public.ministries_with_stats               TO looker_readonly;
GRANT SELECT ON public.categories_with_services            TO looker_readonly;

-- 4e. Companies (compliance / business intelligence)
GRANT SELECT ON public.mv_company_stats_by_zone            TO looker_readonly;
GRANT SELECT ON public.mv_company_global_stats             TO looker_readonly;
GRANT SELECT ON public.mv_company_analytics                TO looker_readonly;

-- 4f. Inspector field activity (already aggregated by zone+week)
GRANT SELECT ON public.mv_inspection_zone_analytics        TO looker_readonly;

-- 4g. Aggregated reporting views (no row-level PII on aggregations only)
GRANT SELECT ON public.v_payments_dashboard                TO looker_readonly;
GRANT SELECT ON public.v_declarations_dashboard            TO looker_readonly;
GRANT SELECT ON public.v_payment_plans_monitoring          TO looker_readonly;
GRANT SELECT ON public.v_declarations_stats                TO looker_readonly;
GRANT SELECT ON public.v_declarations_stats_by_type        TO looker_readonly;

-- ---------------------------------------------------------------------------
-- 5. EXPLICIT REVOKE — defense in depth on PII tables.
-- These REVOKEs are no-ops if no privilege was ever granted, but they form
-- a documented contract: even a future GRANT ALL ON ALL TABLES IN SCHEMA
-- public would not silently expose these to looker_readonly without us
-- noticing this migration broken.
-- ---------------------------------------------------------------------------
REVOKE ALL ON public.users                FROM looker_readonly;
REVOKE ALL ON public.payments             FROM looker_readonly;
REVOKE ALL ON public.service_payments     FROM looker_readonly;
REVOKE ALL ON public.service_requests     FROM looker_readonly;
REVOKE ALL ON public.audit_logs           FROM looker_readonly;
REVOKE ALL ON public.permission_audit_log FROM looker_readonly;
REVOKE ALL ON public.sessions             FROM looker_readonly;
REVOKE ALL ON public.refresh_tokens       FROM looker_readonly;
REVOKE ALL ON public.agent_profiles       FROM looker_readonly;
REVOKE ALL ON public.uploaded_files       FROM looker_readonly;
REVOKE ALL ON public.ocr_extraction_results FROM looker_readonly;
REVOKE ALL ON public.support_messages     FROM looker_readonly;

COMMIT;

-- ---------------------------------------------------------------------------
-- ROLLBACK (manual, not part of forward migration):
-- ---------------------------------------------------------------------------
-- BEGIN;
--   REASSIGN OWNED BY looker_readonly TO postgres;
--   DROP OWNED BY looker_readonly;
--   DROP ROLE IF EXISTS looker_readonly;
-- COMMIT;
-- Do NOT forget to also disable the 2 GCP Secret Manager versions:
--   gcloud secrets versions disable VERSION --secret=looker-readonly-pwd \
--     --project=taxasge-dev
--   gcloud secrets versions disable VERSION --secret=looker-readonly-db-url \
--     --project=taxasge-dev

-- ---------------------------------------------------------------------------
-- VERIFICATION (run after migration applies):
-- ---------------------------------------------------------------------------
-- 1. Connect as looker_readonly:
--    psql "$(gcloud secrets versions access latest --secret=looker-readonly-db-url --project=taxasge-dev)"
-- 2. Test allowed:
--    SELECT count(*) FROM mv_treasury_daily_kpis;       -- should succeed
--    SELECT count(*) FROM mv_agent_daily_workload;      -- should succeed
--    SELECT count(*) FROM mv_fiscal_services_catalog;   -- should succeed
-- 3. Test denied (must each fail with permission denied):
--    SELECT count(*) FROM users;
--    SELECT count(*) FROM payments;
--    SELECT count(*) FROM service_payments;
--    SELECT count(*) FROM audit_logs;
