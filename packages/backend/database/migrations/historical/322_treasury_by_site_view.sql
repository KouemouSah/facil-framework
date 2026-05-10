-- =============================================================================
-- Migration 322 — v_treasury_payments_by_site (real per-site granularity)
-- =============================================================================
-- Created: 2026-05-04
-- User feedback: "je veux qu'on aille jusqu'aux sites pour connaître les
-- performances de chaque site". The existing mv_treasury_daily_kpis aggregates
-- by entity_code only (no location). This migration adds a NEW derived view
-- that resolves the effective entity_location_id per payment via 4 fallback
-- sources.
--
-- Derivation chain (priority order):
--   1. service_payments.field_inspection_id → field_inspections.entity_location_id
--      (most precise: payment collected on-site during inspection)
--   2. service_requests.entity_location_id (SR's preferred site, set at submit)
--   3. agent_profiles[collected_by].entity_location_id (collecting agent's site)
--   4. agent_profiles[validated_by_agent_id].entity_location_id
--   5. NULL (orphan — should be rare; surfaced as 'unassigned' in dashboards)
--
-- This is a VIEW (not MV) since service_payments is tiny today (5 rows). When
-- volume grows >100k, convert to a MV refreshed by the existing scheduler.
-- =============================================================================

BEGIN;

CREATE OR REPLACE VIEW v_treasury_payments_by_site AS
SELECT
    sp.id                                                AS payment_id,
    sp.payment_reference,
    sp.created_at,
    sp.paid_at,
    sp.payment_type,
    sp.payment_method::text                              AS payment_method,
    sp.status::text                                      AS payment_status,
    sp.total_amount,
    sp.base_amount,
    sp.penalties,
    sp.discounts,
    sp.currency,
    sp.fee_type,
    sp.collection_type,

    -- Bridge to SR
    sp.service_request_id,
    sr.workflow_code,
    sr.solicitud_type,
    sr.reference                                         AS sr_reference,

    -- Entity (source of truth = service_request.entity_code)
    COALESCE(sr.entity_code, sp.entity_code)             AS entity_code,
    e.name                                               AS entity_name,
    e.entity_type::text                                  AS entity_type,
    (e.workflow_codes ? 'BUNDLE_PAYMENT')                AS is_oms,
    e.ministry_id,

    -- Effective location: resolved via 4-step fallback
    COALESCE(
        fi.entity_location_id,
        sr.entity_location_id,
        ap_collected.entity_location_id,
        ap_validated.entity_location_id
    )                                                    AS effective_location_id,

    -- Effective location attributes (joined on effective_location_id)
    el.city                                              AS effective_city,
    el.region                                            AS effective_region,
    el.location_name                                     AS effective_location_name,
    el.is_main_office                                    AS effective_is_main,

    -- Provenance trail (which source resolved the location)
    CASE
        WHEN fi.entity_location_id IS NOT NULL                     THEN 'field_inspection'
        WHEN sr.entity_location_id IS NOT NULL                     THEN 'service_request'
        WHEN ap_collected.entity_location_id IS NOT NULL           THEN 'agent_collected'
        WHEN ap_validated.entity_location_id IS NOT NULL           THEN 'agent_validated'
        ELSE 'unassigned'
    END                                                  AS location_source,

    -- Channel detection from SR.source
    CASE
        WHEN sr.source IN ('mobile_app', 'mobile', 'expo')         THEN 'mobile'
        WHEN sr.source IN ('inspector_app', 'inspector')           THEN 'inspector'
        WHEN sr.source IN ('citizen_wizard', 'web', 'agent_dashboard', 'admin_dashboard') THEN 'web'
        WHEN sr.source IS NULL OR sr.source = ''                   THEN 'unknown'
        ELSE sr.source::text
    END                                                  AS channel
FROM service_payments sp
LEFT JOIN service_requests   sr            ON sr.id = sp.service_request_id
LEFT JOIN entities           e             ON e.code = COALESCE(sr.entity_code, sp.entity_code)
LEFT JOIN field_inspections  fi            ON fi.id = sp.field_inspection_id
LEFT JOIN agent_profiles     ap_collected  ON ap_collected.user_id = sp.collected_by
LEFT JOIN agent_profiles     ap_validated  ON ap_validated.id = sp.validated_by_agent_id
LEFT JOIN entity_locations   el            ON el.id = COALESCE(
    fi.entity_location_id,
    sr.entity_location_id,
    ap_collected.entity_location_id,
    ap_validated.entity_location_id
);

COMMENT ON VIEW v_treasury_payments_by_site IS
    'Service_payments enriched with effective entity_location_id (resolved via '
    '4-step fallback: field_inspection → SR → collecting agent → validating agent). '
    'Real per-site granularity. Convert to MV when volume > 100k rows.';

GRANT SELECT ON v_treasury_payments_by_site TO looker_readonly;

COMMIT;

-- ---------------------------------------------------------------------------
-- VERIFICATION
-- ---------------------------------------------------------------------------
-- 1. Counts by location source (should not be 100% 'unassigned'):
--    SELECT location_source, count(*), sum(total_amount) FROM v_treasury_payments_by_site GROUP BY 1;
--
-- 2. Per-site breakdown:
--    SELECT effective_city, count(*), sum(total_amount) FROM v_treasury_payments_by_site GROUP BY 1 ORDER BY 3 DESC;
-- ---------------------------------------------------------------------------
