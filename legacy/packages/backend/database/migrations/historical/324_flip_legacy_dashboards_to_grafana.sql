-- =============================================================================
-- Migration 324 — flip recaudacion + agentes from looker_studio to grafana
-- =============================================================================
-- Created: 2026-05-05
-- Plan reference: .claude/plans/GRAFANA_DASHBOARDS_DYNAMIC_PLAN.md (Phase 4 follow-up)
--
-- Context: mig 323 seeded all 11 dashboard rows but kept the 3 legacy ones
-- (recaudacion / agentes / services) at provider='looker_studio' to preserve
-- any admin-set Looker config (COALESCE pattern). In practice these rows had
-- no Looker config — looker_report_id NULL, so the embed was never going to
-- work as Looker either way.
--
-- The Grafana workspace already has matching dashboards:
--   recaudacion ↔ facil-treasury  (infra/grafana/dashboards/01_treasury.json)
--   agentes     ↔ facil-agents    (infra/grafana/dashboards/02_agents.json)
--
-- This migration flips those 2 rows to provider='grafana' so they render
-- like the 8 new Grafana dashboards seeded by mig 323. Idempotent (only
-- updates rows that are still 'looker_studio' AND lack a Looker report_id).
--
-- `services` (Catálogo de Servicios) is INTENTIONALLY left as Looker — it
-- uses the Looker Studio Community Connector data API (Python service at
-- /api/v1/dashboards/services/{schema,data}), not an iframe. There is no
-- direct Grafana equivalent of that pattern; Grafana embeds full panels
-- whereas Looker connector exposes a queryable schema for ad-hoc reports.
-- =============================================================================

BEGIN;

-- Flip recaudacion → grafana facil-treasury
UPDATE dashboard_registrations
SET provider = 'grafana',
    grafana_dashboard_uid = 'facil-treasury',
    grafana_org_id = COALESCE(grafana_org_id, 1),
    updated_at = NOW()
WHERE dashboard_id = 'recaudacion'
  AND provider = 'looker_studio'
  AND looker_report_id IS NULL;  -- safety: don't trash an admin-set Looker config

-- Flip agentes → grafana facil-agents
UPDATE dashboard_registrations
SET provider = 'grafana',
    grafana_dashboard_uid = 'facil-agents',
    grafana_org_id = COALESCE(grafana_org_id, 1),
    updated_at = NOW()
WHERE dashboard_id = 'agentes'
  AND provider = 'looker_studio'
  AND looker_report_id IS NULL;

COMMIT;

-- ---------------------------------------------------------------------------
-- VERIFICATION:
--   SELECT dashboard_id, provider, grafana_dashboard_uid, looker_report_id
--   FROM dashboard_registrations
--   WHERE dashboard_id IN ('recaudacion', 'agentes', 'services')
--   ORDER BY dashboard_id;
--   -- expected:
--   --   agentes      grafana       facil-agents       NULL
--   --   recaudacion  grafana       facil-treasury     NULL
--   --   services     looker_studio NULL               NULL  (intentional)
-- ---------------------------------------------------------------------------

-- ROLLBACK (manual, if absolutely needed):
-- BEGIN;
--   UPDATE dashboard_registrations SET provider = 'looker_studio',
--          grafana_dashboard_uid = NULL
--   WHERE dashboard_id IN ('recaudacion', 'agentes')
--     AND grafana_dashboard_uid IN ('facil-treasury', 'facil-agents');
-- COMMIT;
