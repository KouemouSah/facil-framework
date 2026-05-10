-- =============================================================================
-- Migration 320 — Enriched VIEWs for Looker/Grafana decisional dashboards
-- =============================================================================
-- Created: 2026-05-04
-- Plan reference: GRAFANA_E1 evaluation phase, user feedback "dashboards
-- not actionable enough — need entity_location, agent type, OMS filter,
-- multi-axis cross-tabulations".
--
-- Adds 3 enriched VIEWs (no MV — joins are cheap, the underlying MVs
-- already do the heavy lifting) so Grafana dashboards can filter by:
-- - Agent type (OMS vs non-OMS, supervisor vs regular)
-- - Entity code AND entity_location (city, region)
-- - Ministry, workflow, status, fee_type
--
-- These VIEWs are auto-wrapped by sync_looker_view_wrappers at boot
-- (rule #38). The granted_to looker_readonly is the explicit "expose
-- to BI" signal.
--
-- Idempotent: CREATE OR REPLACE VIEW + GRANT.
-- BD verified 2026-05-04 (agent_profiles columns, entities, entity_locations).
-- =============================================================================

BEGIN;

-- ---------------------------------------------------------------------------
-- 1. v_agent_workload_enriched — agent daily workload + entity + location
-- Joins:
--   mv_agent_daily_workload (volume per agent per day) [aggregated MV]
--     -> agent_profiles (agent_type, entity_id, entity_location_id, is_supervisor)
--     -> entities (entity code, name, type, parent)
--     -> entity_locations (city, region, location_name, is_main_office)
--     -> ministries (ministry_name)
--
-- The is_oms flag derives from entity_type IN ('ministry', 'town_hall',
-- 'chamber') — the entities that handle BUNDLE_PAYMENT in Facil.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW v_agent_workload_enriched AS
SELECT
    w.report_date,
    w.agent_profile_id,
    w.agent_name,

    -- Agent attributes
    ap.agent_type,
    ap.is_supervisor,
    ap.is_active                                     AS agent_is_active,

    -- Entity attributes
    e.id                                             AS entity_id,
    e.code                                           AS entity_code,
    e.name                                           AS entity_name,
    e.entity_type::text                              AS entity_type,
    -- OMS membership = entities that route BUNDLE_PAYMENT (per workflow_codes)
    -- Pragmatic match: ministry / town_hall / chamber entity types.
    -- OMS = entity routes BUNDLE_PAYMENT in its workflow_codes JSONB array.
-- Source of truth: entities.workflow_codes (admin-managed via UI).
(e.workflow_codes ? 'BUNDLE_PAYMENT') AS is_oms,

    -- Location attributes
    el.id                                            AS entity_location_id,
    el.city                                          AS location_city,
    el.region                                        AS location_region,
    el.location_name                                 AS location_name,
    el.is_main_office,

    -- Ministry attributes
    ap.ministry_id,

    -- Workload metrics (passthrough from mv_agent_daily_workload)
    w.approved,
    w.rejected,
    w.total_actions,
    w.avg_duration_seconds,
    w.min_duration_seconds,
    w.max_duration_seconds,
    w.p50_duration_seconds
FROM mv_agent_daily_workload w
LEFT JOIN agent_profiles ap ON ap.id = w.agent_profile_id
LEFT JOIN entities e ON e.id = ap.entity_id
LEFT JOIN entity_locations el ON el.id = ap.entity_location_id;

COMMENT ON VIEW v_agent_workload_enriched IS
    'mv_agent_daily_workload enriched with agent_type, entity, location, '
    'ministry, is_supervisor, is_oms — used by Grafana facil-agents dashboard. '
    'Auto-wrapped to vw_agent_workload_enriched at app boot (rule #38).';

GRANT SELECT ON v_agent_workload_enriched TO looker_readonly;

-- ---------------------------------------------------------------------------
-- 2. v_active_service_requests_enriched — active SR + agent + location
-- Builds on v_active_service_request_assignments (already grant-OK) but
-- adds agent_type, entity_location, is_oms via joins.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW v_active_service_requests_enriched AS
SELECT
    sr.assignment_id,
    sr.service_request_id,
    sr.workflow_code,
    sr.service_request_reference,
    sr.solicitud_type,
    sr.service_request_status,
    sr.service_request_priority,
    sr.payment_status,
    sr.total_amount,
    sr.cita_date,
    sr.cita_time,
    sr.requester_name,

    -- Agent
    sr.agent_profile_id,
    sr.agent_user_id,
    sr.agent_name,
    sr.agent_email,
    ap.agent_type,
    ap.is_supervisor,

    -- Entity (already in v_active_*, kept for joins consistency)
    sr.entity_id,
    sr.entity_code,
    e.name                                           AS entity_name,
    e.entity_type::text                              AS entity_type,
    -- OMS = entity routes BUNDLE_PAYMENT in its workflow_codes JSONB array.
-- Source of truth: entities.workflow_codes (admin-managed via UI).
(e.workflow_codes ? 'BUNDLE_PAYMENT') AS is_oms,

    -- Location
    el.id                                            AS entity_location_id,
    el.city                                          AS location_city,
    el.region                                        AS location_region,
    el.location_name                                 AS location_name,

    -- Ministry
    sr.ministry_id,
    sr.ministry_code,

    -- Assignment timing
    sr.assignment_status,
    sr.assignment_priority,
    sr.assigned_at,
    sr.assignment_deadline,
    sr.hours_since_assigned,
    sr.is_overdue,
    sr.hours_until_deadline,

    -- Aging bucket — crucial for SLA dashboards
    CASE
        WHEN sr.hours_since_assigned IS NULL THEN 'unknown'
        WHEN sr.hours_since_assigned < 24 THEN '0-24h'
        WHEN sr.hours_since_assigned < 72 THEN '24-72h'
        WHEN sr.hours_since_assigned < 168 THEN '3-7d'
        WHEN sr.hours_since_assigned < 720 THEN '7-30d'
        ELSE '30d+'
    END                                              AS age_bucket
FROM v_active_service_request_assignments sr
LEFT JOIN agent_profiles ap ON ap.id = sr.agent_profile_id
LEFT JOIN entities e ON e.id = sr.entity_id
LEFT JOIN entity_locations el ON el.id = ap.entity_location_id;

COMMENT ON VIEW v_active_service_requests_enriched IS
    'v_active_service_request_assignments + agent_type, entity, location, '
    'is_oms, age_bucket. Used by Grafana facil-service-requests dashboard.';

GRANT SELECT ON v_active_service_requests_enriched TO looker_readonly;

-- ---------------------------------------------------------------------------
-- 3. v_entity_locations_browse — entity locations for filter dropdowns
-- Simple passthrough so Grafana variables can pick city/region.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW v_entity_locations_browse AS
SELECT
    el.id                                            AS entity_location_id,
    el.entity_code,
    e.name                                           AS entity_name,
    el.location_name,
    el.city,
    el.region,
    el.is_main_office,
    el.is_active                                     AS location_is_active
FROM entity_locations el
LEFT JOIN entities e ON e.id = el.entity_id
WHERE el.is_active = true;

COMMENT ON VIEW v_entity_locations_browse IS
    'Active entity_locations exposed for Grafana variable dropdowns.';

GRANT SELECT ON v_entity_locations_browse TO looker_readonly;

-- ---------------------------------------------------------------------------
-- 4. v_entities_browse — entities catalog for filter dropdowns
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW v_entities_browse AS
SELECT
    e.id                                             AS entity_id,
    e.code                                           AS entity_code,
    e.name                                           AS entity_name,
    e.entity_type::text                              AS entity_type,
    -- OMS = entity routes BUNDLE_PAYMENT in its workflow_codes JSONB array.
-- Source of truth: entities.workflow_codes (admin-managed via UI).
(e.workflow_codes ? 'BUNDLE_PAYMENT') AS is_oms,
    e.ministry_id,
    e.parent_entity_id,
    e.workflow_codes,
    e.is_active                                      AS entity_is_active
FROM entities e
WHERE e.is_active = true;

-- Note: re-uses the `e.workflow_codes ? 'BUNDLE_PAYMENT'` operator above
-- to derive is_oms — single source of truth (no enum-based hardcoding).

COMMENT ON VIEW v_entities_browse IS
    'Active entities catalog exposed for Grafana variable dropdowns.';

GRANT SELECT ON v_entities_browse TO looker_readonly;

COMMIT;

-- ---------------------------------------------------------------------------
-- VERIFICATION
-- ---------------------------------------------------------------------------
-- 1. Views exist + granted:
--    SELECT relname, has_table_privilege('looker_readonly', 'public.'||relname, 'SELECT')
--    FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
--    WHERE n.nspname='public' AND c.relkind='v'
--      AND relname IN ('v_agent_workload_enriched', 'v_active_service_requests_enriched',
--                      'v_entity_locations_browse', 'v_entities_browse');
--
-- 2. Sample rows:
--    SELECT entity_code, agent_type, is_oms, count(*) FROM v_agent_workload_enriched
--    GROUP BY 1,2,3 ORDER BY 1;
--
-- 3. After app reboot, the auto-sync should create wrapper VIEWs:
--    vw_agent_workload_enriched, vw_active_service_requests_enriched,
--    vw_entity_locations_browse, vw_entities_browse
-- ---------------------------------------------------------------------------
