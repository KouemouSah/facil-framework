-- =============================================================================
-- Migration 321 — Audit + Inspections + Channel views for Grafana
-- =============================================================================
-- Created: 2026-05-04
-- Plan: GRAFANA_E1 user feedback "ajoute audit utilisateurs, mobile vs web,
-- inspections terrain (seals, mise en demeure, encaissement)".
--
-- Adds 3 enriched VIEWs grantées à looker_readonly :
--   v_user_activity_audit         (audit_logs + user.role + channel detection)
--   v_service_requests_channel    (service_requests.source + workflow + entity)
--   v_field_inspections_enriched  (field_inspections + agent + entity + location)
-- =============================================================================

BEGIN;

-- ---------------------------------------------------------------------------
-- 1. v_user_activity_audit
-- audit_logs has 3342 rows with rich actions (LOGIN_SUCCESS, PERMISSION_*, etc).
-- Channel inferred from user_agent string pattern matching.
-- Action categorized for grouping (auth / rbac / read / write / delete / dashboard).
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW v_user_activity_audit AS
SELECT
    al.id,
    al.user_id,
    u.email                                          AS user_email,
    u.full_name                                      AS user_name,
    u.role::text                                     AS user_role,
    al.entity_type,
    al.entity_id,
    al.action,
    al.ip_address::text                              AS ip_address,
    al.created_at,
    -- Channel detection from user_agent (heuristic but stable)
    CASE
        WHEN al.user_agent ILIKE '%expo%'
          OR al.user_agent ILIKE '%react-native%'
          OR al.user_agent ILIKE '%android%'
          OR al.user_agent ILIKE '%iphone%'
          OR al.user_agent ILIKE '%ipad%'
          OR al.user_agent ILIKE '%mobile%'           THEN 'mobile'
        WHEN al.user_agent ILIKE '%inspector%'        THEN 'inspector'
        WHEN al.user_agent ILIKE '%mozilla%'
          OR al.user_agent ILIKE '%chrome%'
          OR al.user_agent ILIKE '%safari%'
          OR al.user_agent ILIKE '%edge%'             THEN 'web'
        WHEN al.user_agent IS NULL OR al.user_agent = '' THEN 'unknown'
        ELSE 'other'
    END                                              AS channel,
    al.user_agent,
    -- Action categorization
    CASE
        WHEN al.action LIKE 'LOGIN%' OR al.action = 'LOGOUT' THEN 'auth'
        WHEN al.action ILIKE '%PERMISSION%' OR al.action ILIKE 'ROLE%' THEN 'rbac'
        WHEN al.action LIKE 'view_%' OR al.action LIKE 'list_%' THEN 'read'
        WHEN al.action LIKE 'update_%' OR al.action LIKE 'edit_%' THEN 'write'
        WHEN al.action LIKE 'delete_%' OR al.action LIKE 'remove_%' THEN 'delete'
        WHEN al.action LIKE 'dashboard.%' THEN 'dashboard'
        WHEN al.action LIKE 'mission.%' THEN 'mission'
        WHEN al.action LIKE 'service_request.%' THEN 'service_request'
        WHEN al.action LIKE 'payment.%' THEN 'payment'
        ELSE 'other'
    END                                              AS action_category
FROM audit_logs al
LEFT JOIN users u ON u.id = al.user_id;

COMMENT ON VIEW v_user_activity_audit IS
    'audit_logs enriched with user role + channel + action category for '
    'Grafana facil-user-activity dashboard.';
GRANT SELECT ON v_user_activity_audit TO looker_readonly;

-- ---------------------------------------------------------------------------
-- 2. v_service_requests_channel
-- service_requests.source carries the originating channel. Mapped to a
-- canonical channel taxonomy: web | mobile | inspector | unknown.
-- Joined with entities + user for filtering.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW v_service_requests_channel AS
SELECT
    sr.id,
    sr.reference,
    sr.workflow_code,
    sr.solicitud_type,
    sr.status::text                                  AS status,
    sr.priority::text                                AS priority,
    sr.entity_code,
    e.id                                             AS entity_id,
    e.name                                           AS entity_name,
    (e.workflow_codes ? 'BUNDLE_PAYMENT')            AS is_oms,
    sr.entity_location_id,
    el.city                                          AS location_city,
    el.region                                        AS location_region,
    sr.user_id,
    u.email                                          AS requester_email,
    u.full_name                                      AS requester_name,
    sr.source,
    -- Canonical channel mapping
    CASE
        WHEN sr.source IN ('mobile_app', 'mobile', 'expo')        THEN 'mobile'
        WHEN sr.source IN ('inspector_app', 'inspector')          THEN 'inspector'
        WHEN sr.source IN ('citizen_wizard', 'web', 'agent_dashboard', 'admin_dashboard') THEN 'web'
        WHEN sr.source IS NULL OR sr.source = ''                  THEN 'unknown'
        ELSE sr.source::text
    END                                              AS channel,
    sr.total_amount,
    sr.payment_status,
    sr.created_at,
    sr.updated_at,
    sr.submitted_at,
    sr.completed_at,
    sr.escalated,
    sr.bundle_id,
    sr.commercial_license_id
FROM service_requests sr
LEFT JOIN entities e ON e.code = sr.entity_code
LEFT JOIN entity_locations el ON el.id = sr.entity_location_id
LEFT JOIN users u ON u.id = sr.user_id;

COMMENT ON VIEW v_service_requests_channel IS
    'service_requests + canonical channel (web/mobile/inspector) + entity + '
    'requester. Used by Grafana facil-channel-mobile-vs-web dashboard.';
GRANT SELECT ON v_service_requests_channel TO looker_readonly;

-- ---------------------------------------------------------------------------
-- 3. v_field_inspections_enriched
-- field_inspections has rich operational data (seals, mise en demeure,
-- on-site payment collection). 0 rows currently in prod but schema is ready.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW v_field_inspections_enriched AS
SELECT
    fi.id,
    fi.inspection_date,
    fi.status,
    fi.result,
    fi.activity_conforme,
    fi.activity_declared,
    fi.activity_observed,
    fi.unpaid_obligations_count,
    fi.unpaid_obligations_amount,
    fi.total_obligations_count,
    -- Mise en demeure
    fi.mise_en_demeure_issued,
    fi.mise_en_demeure_deadline,
    -- Seal (scellé)
    fi.seal_applied,
    fi.seal_reason,
    fi.seal_proposed_at,
    fi.seal_approved_at,
    fi.seal_approved_by,
    -- Payment collected on-site (encaissement terrain)
    fi.payment_collected,
    fi.payment_amount,
    fi.payment_receipt_number,
    -- Photos
    jsonb_array_length(COALESCE(fi.photos, '[]'::jsonb)) AS photos_count,
    -- GPS
    fi.gps_latitude,
    fi.gps_longitude,
    fi.gps_accuracy,
    -- Duration
    fi.duration_minutes,
    -- Joins
    fi.agent_id,
    u.full_name                                      AS agent_full_name,
    u.email                                          AS agent_email,
    fi.agent_profile_id,
    ap.agent_type,
    fi.entity_id,
    e.code                                           AS entity_code,
    e.name                                           AS entity_name,
    fi.entity_location_id,
    el.city                                          AS location_city,
    el.region                                        AS location_region,
    el.location_name,
    fi.zone_id,
    fi.mission_id,
    fi.license_id,
    fi.company_id,
    fi.created_at,
    fi.updated_at
FROM field_inspections fi
LEFT JOIN users u ON u.id = fi.agent_id
LEFT JOIN agent_profiles ap ON ap.id = fi.agent_profile_id
LEFT JOIN entities e ON e.id = fi.entity_id
LEFT JOIN entity_locations el ON el.id = fi.entity_location_id;

COMMENT ON VIEW v_field_inspections_enriched IS
    'field_inspections enriched with agent, entity, location for Grafana '
    'facil-inspections dashboard. Tracks seals, mise en demeure, on-site '
    'payments, photos, GPS, duration.';
GRANT SELECT ON v_field_inspections_enriched TO looker_readonly;

-- ---------------------------------------------------------------------------
-- 4. v_service_payments_enriched
-- service_payments has 5 rows (real prod data) but is not granted.
-- payments table is empty (0 rows) — that's why facil-payments dashboard
-- showed "No data". This view exposes service_payments for the dashboard.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW v_service_payments_enriched AS
SELECT
    sp.id,
    sp.service_request_id,
    sp.payment_reference,
    sp.payment_type,
    sp.payment_method::text                          AS payment_method,
    sp.status::text                                  AS payment_status,
    sp.workflow_status::text                         AS workflow_status,
    sp.base_amount,
    sp.penalties,
    sp.discounts,
    sp.total_amount,
    sp.currency,
    sp.entity_code                                   AS sp_entity_code,
    sp.fee_type,
    sp.collection_type,
    sp.field_inspection_id,
    sp.receipt_number,
    sp.created_at,
    sp.updated_at,
    sp.paid_at,
    sp.validated_at,
    -- Bridge to SR for workflow + entity
    sr.workflow_code,
    sr.reference                                     AS sr_reference,
    sr.entity_code,
    e.name                                           AS entity_name,
    (e.workflow_codes ? 'BUNDLE_PAYMENT')            AS is_oms,
    sr.source                                        AS sr_source,
    CASE
        WHEN sr.source IN ('mobile_app', 'mobile', 'expo')        THEN 'mobile'
        WHEN sr.source IN ('inspector_app', 'inspector')          THEN 'inspector'
        WHEN sr.source IN ('citizen_wizard', 'web', 'agent_dashboard', 'admin_dashboard') THEN 'web'
        WHEN sr.source IS NULL OR sr.source = ''                  THEN 'unknown'
        ELSE sr.source::text
    END                                              AS channel
FROM service_payments sp
LEFT JOIN service_requests sr ON sr.id = sp.service_request_id
LEFT JOIN entities e ON e.code = sr.entity_code;

COMMENT ON VIEW v_service_payments_enriched IS
    'service_payments + workflow + entity + channel — replaces v_payments_dashboard '
    'as the source of truth for the facil-payments dashboard while payments '
    'table stays empty in this stage of the project.';
GRANT SELECT ON v_service_payments_enriched TO looker_readonly;

COMMIT;

-- ---------------------------------------------------------------------------
-- VERIFICATION
-- ---------------------------------------------------------------------------
-- SELECT relname,
--   has_table_privilege('looker_readonly', 'public.'||relname, 'SELECT') AS granted,
--   (SELECT count(*) FROM pg_attribute a JOIN pg_class c2 ON c2.oid=a.attrelid
--    WHERE c2.relname=c.relname AND a.attnum>0 AND NOT a.attisdropped) AS cols
-- FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
-- WHERE n.nspname='public' AND c.relkind='v'
--   AND relname IN ('v_user_activity_audit','v_service_requests_channel',
--                   'v_field_inspections_enriched','v_service_payments_enriched');
-- ---------------------------------------------------------------------------
