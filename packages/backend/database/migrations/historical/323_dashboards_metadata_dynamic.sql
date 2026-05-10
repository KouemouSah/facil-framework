-- =============================================================================
-- Migration 323 — dashboards metadata dynamic (i18n + categories + 8 new Grafana)
-- =============================================================================
-- Created: 2026-05-05
-- Plan reference: .claude/plans/GRAFANA_DASHBOARDS_DYNAMIC_PLAN.md
--
-- Goal: replace the hardcoded `_REPORTS_METADATA` dict in
-- app/modules/dashboards/api/dashboards_routes.py:157 with BD-driven metadata.
-- Wires the 8 missing Grafana dashboards (10 live in Grafana → only 3 wired
-- in app: recaudacion, agentes, services) so the admin UI can manage all of
-- them without code change.
--
-- Phase 1 of the plan:
--   1. Add i18n + presentation columns to dashboard_registrations
--   2. Relax looker_report_id NOT NULL (Grafana-only rows don't need it)
--   3. Backfill the 3 existing rows with i18n titles + category + display_order
--   4. Insert 8 new Grafana dashboards (real UIDs from infra/grafana/dashboards/*.json)
--
-- BD verified 2026-05-05 BEFORE writing this migration:
--   - dashboard_registrations exists (mig 317), columns: dashboard_id, looker_report_id,
--     looker_page_id, is_active, updated_by, updated_at, created_at
--   - mig 319 added: provider (enum), grafana_dashboard_uid, grafana_org_id
--   - chk_grafana_uid_required_when_grafana enforces uid presence when provider=grafana
--   - chk_grafana_dashboard_uid_format: ^[a-zA-Z0-9_-]{4,40}$
--   - chk_looker_report_id_format: ^[a-zA-Z0-9_-]{8,64}$ (current: NOT NULL)
--   - All 10 Grafana UIDs verified in infra/grafana/dashboards/ JSON (uid field)
--
-- Phase 1 = schema + seed only. Phase 2 = backend refacto, Phase 3 = frontend.
-- Idempotent: ADD COLUMN IF NOT EXISTS, DROP CONSTRAINT IF EXISTS, ON CONFLICT.
-- =============================================================================

BEGIN;

-- ---------------------------------------------------------------------------
-- 1. Relax looker_report_id NOT NULL
--    Grafana-only rows do not need a Looker report ID. Existing rows already
--    have looker_report_id populated; this change only allows NEW rows with
--    provider='grafana' to leave it NULL.
-- ---------------------------------------------------------------------------
ALTER TABLE dashboard_registrations
    ALTER COLUMN looker_report_id DROP NOT NULL;

-- Recreate format CHECK to allow NULL.
ALTER TABLE dashboard_registrations
    DROP CONSTRAINT IF EXISTS chk_looker_report_id_format;
ALTER TABLE dashboard_registrations
    ADD CONSTRAINT chk_looker_report_id_format
    CHECK (looker_report_id IS NULL OR looker_report_id ~ '^[a-zA-Z0-9_-]{8,64}$');

-- ---------------------------------------------------------------------------
-- 2. Add metadata columns (i18n + presentation)
-- ---------------------------------------------------------------------------
ALTER TABLE dashboard_registrations
    ADD COLUMN IF NOT EXISTS title_es           text,
    ADD COLUMN IF NOT EXISTS title_fr           text,
    ADD COLUMN IF NOT EXISTS title_en           text,
    ADD COLUMN IF NOT EXISTS description_es     text,
    ADD COLUMN IF NOT EXISTS description_fr     text,
    ADD COLUMN IF NOT EXISTS description_en     text,
    ADD COLUMN IF NOT EXISTS rls_mode           text NOT NULL DEFAULT 'authenticated',
    ADD COLUMN IF NOT EXISTS embed_mode         text NOT NULL DEFAULT 'kiosk',
    ADD COLUMN IF NOT EXISTS panel_id           int,
    ADD COLUMN IF NOT EXISTS display_order      int NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS default_time_range text NOT NULL DEFAULT 'now-90d',
    ADD COLUMN IF NOT EXISTS icon_name          text,
    ADD COLUMN IF NOT EXISTS category           text;

-- CHECK constraints on new columns
ALTER TABLE dashboard_registrations
    DROP CONSTRAINT IF EXISTS chk_rls_mode_value;
ALTER TABLE dashboard_registrations
    ADD CONSTRAINT chk_rls_mode_value
    CHECK (rls_mode IN ('public', 'authenticated', 'entity', 'agent_via_join', 'admin_only'));

ALTER TABLE dashboard_registrations
    DROP CONSTRAINT IF EXISTS chk_embed_mode_value;
ALTER TABLE dashboard_registrations
    ADD CONSTRAINT chk_embed_mode_value
    CHECK (embed_mode IN ('kiosk', 'solo', 'panel'));

ALTER TABLE dashboard_registrations
    DROP CONSTRAINT IF EXISTS chk_panel_id_for_solo;
ALTER TABLE dashboard_registrations
    ADD CONSTRAINT chk_panel_id_for_solo
    CHECK (embed_mode = 'kiosk' OR panel_id IS NOT NULL);

ALTER TABLE dashboard_registrations
    DROP CONSTRAINT IF EXISTS chk_category_value;
ALTER TABLE dashboard_registrations
    ADD CONSTRAINT chk_category_value
    CHECK (category IS NULL OR category IN ('executive', 'finance', 'operations', 'security', 'business', 'product'));

ALTER TABLE dashboard_registrations
    DROP CONSTRAINT IF EXISTS chk_default_time_range_format;
ALTER TABLE dashboard_registrations
    ADD CONSTRAINT chk_default_time_range_format
    CHECK (default_time_range ~ '^now(-[0-9]+[smhdwMy])?$');

-- ---------------------------------------------------------------------------
-- 3. Index on display_order for the listing page (sorted reads)
-- ---------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_dashboard_registrations_order
    ON dashboard_registrations(display_order, dashboard_id) WHERE is_active = true;

-- ---------------------------------------------------------------------------
-- 4. Seed / backfill all 11 rows in one INSERT.
--
--    For existing rows (recaudacion, agentes, services from _REPORTS_METADATA),
--    ON CONFLICT DO UPDATE preserves provider/UID/looker_report_id/is_active
--    (set by admin via /admin/dashboards/config) and only fills the NEW
--    metadata columns when they are NULL/zero (COALESCE pattern).
--
--    For new rows (8 Grafana dashboards), ON CONFLICT DO UPDATE behaves the
--    same way — re-running this migration won't overwrite admin tweaks.
--
--    UIDs verified 2026-05-05 from infra/grafana/dashboards/*.json:
--      facil-overview, facil-treasury, facil-agents, facil-companies,
--      facil-oms, facil-payments, facil-service-requests,
--      facil-user-activity, facil-channel, facil-inspections.
-- ---------------------------------------------------------------------------
INSERT INTO dashboard_registrations (
    dashboard_id, provider, grafana_dashboard_uid, grafana_org_id,
    looker_report_id, is_active,
    rls_mode, embed_mode, default_time_range,
    title_es, title_fr, title_en,
    description_es, description_fr, description_en,
    category, display_order, icon_name
)
VALUES
    -- ===== Existing 3 (preserve admin config via COALESCE in DO UPDATE) =====

    -- recaudacion (was Looker; users can switch to Grafana via UI — UID matches facil-treasury)
    ('recaudacion', 'looker_studio', NULL, 1,
     NULL, true,
     'entity', 'kiosk', 'now-90d',
     'Recaudación Fiscal', 'Recouvrement fiscal', 'Fiscal Revenue Collection',
     'KPI de tesorería — ingresos diarios por entidad, ministerio, método de pago, flujo.',
     'KPI de trésorerie — revenus quotidiens par entité, ministère, méthode de paiement, flux.',
     'Treasury KPIs — daily revenue by entity, ministry, payment method, workflow.',
     'finance', 10, 'BanknotesIcon'),

    -- agentes
    ('agentes', 'looker_studio', NULL, 1,
     NULL, true,
     'agent_via_join', 'kiosk', 'now-30d',
     'Rendimiento de Agentes', 'Performance des agents', 'Agents Performance',
     'Carga de trabajo diaria por agente — aprobados, rechazados, p50 duración, breaches SLA.',
     'Charge de travail quotidienne par agent — approuvés, rejetés, p50 durée, dépassements SLA.',
     'Daily workload per agent — approved, rejected, p50 duration, SLA breaches.',
     'operations', 20, 'UsersIcon'),

    -- services (catalog, Looker-only — no Grafana equivalent)
    ('services', 'looker_studio', NULL, 1,
     NULL, true,
     'public', 'kiosk', 'now-90d',
     'Catálogo de Servicios', 'Catalogue de services', 'Services Catalog',
     'Catálogo de referencia de servicios fiscales — multilingüe, contadores de tráfico.',
     'Catalogue de référence des services fiscaux — multilingue, compteurs de trafic.',
     'Reference catalog of fiscal services — multilingual, traffic counters.',
     'business', 95, 'BookOpenIcon'),

    -- ===== 8 new Grafana dashboards (real UIDs from infra/grafana/dashboards/) =====

    ('overview', 'grafana', 'facil-overview', 1,
     NULL, true,
     'authenticated', 'kiosk', 'now-90d',
     'Resumen ejecutivo', 'Aperçu exécutif', 'Executive Overview',
     'Vista 360 — métricas clave de toda la plataforma (recaudación, demandas, agentes, canales).',
     'Vue 360 — métriques clés de toute la plateforme (recouvrement, demandes, agents, canaux).',
     '360 view — key metrics across the entire platform (revenue, requests, agents, channels).',
     'executive', 5, 'ChartBarIcon'),

    ('payments', 'grafana', 'facil-payments', 1,
     NULL, true,
     'authenticated', 'kiosk', 'now-30d',
     'Operaciones de Pagos', 'Opérations de paiements', 'Payments Operations',
     'Pagos por método, banco, estado workflow, tasas de éxito BANGE, reconciliación.',
     'Paiements par méthode, banque, état workflow, taux de succès BANGE, rapprochement.',
     'Payments by method, bank, workflow state, BANGE success rates, reconciliation.',
     'finance', 15, 'CreditCardIcon'),

    ('companies', 'grafana', 'facil-companies', 1,
     NULL, true,
     'authenticated', 'kiosk', 'now-90d',
     'Empresas', 'Entreprises', 'Companies',
     'Empresas activas, suspensiones, licencias comerciales y obligaciones de cumplimiento.',
     'Entreprises actives, suspensions, licences commerciales et obligations de conformité.',
     'Active companies, suspensions, commercial licenses and compliance obligations.',
     'business', 30, 'BuildingOfficeIcon'),

    ('oms', 'grafana', 'facil-oms', 1,
     NULL, true,
     'authenticated', 'kiosk', 'now-30d',
     'Módulos OMS', 'Modules OMS', 'OMS Modules',
     'Obligaciones, inspecciones y licencias — flujo end-to-end del módulo OMS.',
     'Obligations, inspections et licences — flux end-to-end du module OMS.',
     'Obligations, inspections and licenses — end-to-end OMS module flow.',
     'operations', 40, 'ClipboardDocumentCheckIcon'),

    ('service-requests', 'grafana', 'facil-service-requests', 1,
     NULL, true,
     'authenticated', 'kiosk', 'now-30d',
     'Solicitudes y Bundle', 'Demandes & Bundle', 'Service Requests & Bundle',
     'Volumen de solicitudes, estados, tiempos de procesamiento, flujo bundle multi-entidad.',
     'Volume de demandes, états, temps de traitement, flux bundle multi-entités.',
     'Request volume, states, processing times, multi-entity bundle flow.',
     'operations', 50, 'DocumentTextIcon'),

    ('channel', 'grafana', 'facil-channel', 1,
     NULL, true,
     'authenticated', 'kiosk', 'now-30d',
     'Canal Mobile vs Web vs Inspector', 'Canal Mobile vs Web vs Inspector', 'Channel Mobile vs Web vs Inspector',
     'Distribución de uso por canal — adopción mobile vs web vs app inspector.',
     'Distribution d''usage par canal — adoption mobile vs web vs app inspecteur.',
     'Usage distribution by channel — mobile vs web vs inspector app adoption.',
     'product', 60, 'DevicePhoneMobileIcon'),

    ('inspections', 'grafana', 'facil-inspections', 1,
     NULL, true,
     'authenticated', 'kiosk', 'now-30d',
     'Inspecciones de Campo', 'Inspections terrain', 'Field Inspections',
     'Inspecciones realizadas en terreno por la app inspector — sitios, agentes, hallazgos.',
     'Inspections réalisées sur le terrain via l''app inspecteur — sites, agents, observations.',
     'Field inspections via the inspector app — sites, agents, findings.',
     'operations', 70, 'MapPinIcon'),

    ('user-activity', 'grafana', 'facil-user-activity', 1,
     NULL, true,
     'admin_only', 'kiosk', 'now-7d',
     'Actividad de Usuarios (auditoría)', 'Activité utilisateurs (audit)', 'User Activity (audit)',
     'Auditoría de seguridad — accesos, logins fallidos, cambios sensibles, traza completa.',
     'Audit de sécurité — accès, logins échoués, changements sensibles, traçabilité complète.',
     'Security audit — accesses, failed logins, sensitive changes, full audit trail.',
     'security', 80, 'ShieldCheckIcon')

ON CONFLICT (dashboard_id) DO UPDATE SET
    -- Only fill metadata fields if not already set by admin (COALESCE pattern).
    -- DO NOT touch provider / grafana_dashboard_uid / looker_report_id / is_active —
    -- those are admin-managed via /admin/dashboards/config.
    title_es           = COALESCE(dashboard_registrations.title_es,           EXCLUDED.title_es),
    title_fr           = COALESCE(dashboard_registrations.title_fr,           EXCLUDED.title_fr),
    title_en           = COALESCE(dashboard_registrations.title_en,           EXCLUDED.title_en),
    description_es     = COALESCE(dashboard_registrations.description_es,     EXCLUDED.description_es),
    description_fr     = COALESCE(dashboard_registrations.description_fr,     EXCLUDED.description_fr),
    description_en     = COALESCE(dashboard_registrations.description_en,     EXCLUDED.description_en),
    category           = COALESCE(dashboard_registrations.category,           EXCLUDED.category),
    icon_name          = COALESCE(dashboard_registrations.icon_name,          EXCLUDED.icon_name),
    -- display_order column was added with DEFAULT 0; if admin already changed it (≠0) keep theirs
    display_order      = CASE WHEN dashboard_registrations.display_order = 0
                              THEN EXCLUDED.display_order
                              ELSE dashboard_registrations.display_order END,
    -- rls_mode column was added with DEFAULT 'authenticated'; if admin set non-default keep theirs
    rls_mode           = CASE WHEN dashboard_registrations.rls_mode = 'authenticated'
                                AND EXCLUDED.rls_mode IN ('entity', 'agent_via_join', 'public', 'admin_only')
                              THEN EXCLUDED.rls_mode
                              ELSE dashboard_registrations.rls_mode END,
    default_time_range = CASE WHEN dashboard_registrations.default_time_range = 'now-90d'
                              THEN EXCLUDED.default_time_range
                              ELSE dashboard_registrations.default_time_range END,
    updated_at         = NOW();

-- ---------------------------------------------------------------------------
-- 5. Comments on new columns
-- ---------------------------------------------------------------------------
COMMENT ON COLUMN dashboard_registrations.title_es IS 'Spanish title (UI display).';
COMMENT ON COLUMN dashboard_registrations.title_fr IS 'French title (UI display).';
COMMENT ON COLUMN dashboard_registrations.title_en IS 'English title (UI display).';
COMMENT ON COLUMN dashboard_registrations.description_es IS 'Spanish description (one-line summary, ≤200 chars recommended).';
COMMENT ON COLUMN dashboard_registrations.description_fr IS 'French description (one-line summary).';
COMMENT ON COLUMN dashboard_registrations.description_en IS 'English description (one-line summary).';
COMMENT ON COLUMN dashboard_registrations.rls_mode IS 'Row-level security mode: public, authenticated, entity, agent_via_join, admin_only.';
COMMENT ON COLUMN dashboard_registrations.embed_mode IS 'Embed type: kiosk (full dashboard), solo (single panel), panel (custom widget).';
COMMENT ON COLUMN dashboard_registrations.panel_id IS 'Required if embed_mode != kiosk. Grafana panel_id from dashboard JSON.';
COMMENT ON COLUMN dashboard_registrations.display_order IS 'Sort order in the listing page (lower = first; default 0 = unset).';
COMMENT ON COLUMN dashboard_registrations.default_time_range IS 'Default Grafana time range: now-7d, now-30d, now-90d, etc.';
COMMENT ON COLUMN dashboard_registrations.icon_name IS 'Heroicons name for the listing card (e.g. BanknotesIcon, UsersIcon).';
COMMENT ON COLUMN dashboard_registrations.category IS 'Logical grouping: executive, finance, operations, security, business, product.';

COMMIT;

-- ---------------------------------------------------------------------------
-- VERIFICATION (run after applying):
-- ---------------------------------------------------------------------------
-- 1. New columns:
--    SELECT column_name, data_type, column_default
--    FROM information_schema.columns
--    WHERE table_name = 'dashboard_registrations'
--    ORDER BY ordinal_position;
--    -- expected: title_es/fr/en, description_*, rls_mode, embed_mode, panel_id,
--    --           display_order, default_time_range, icon_name, category
--
-- 2. CHECK constraints:
--    SELECT conname, pg_get_constraintdef(oid) FROM pg_constraint
--    WHERE conrelid = 'dashboard_registrations'::regclass AND contype = 'c'
--    ORDER BY conname;
--    -- expected: chk_category_value, chk_default_time_range_format,
--    --           chk_embed_mode_value, chk_grafana_dashboard_uid_format,
--    --           chk_grafana_uid_required_when_grafana, chk_looker_page_id_format,
--    --           chk_looker_report_id_format, chk_panel_id_for_solo, chk_rls_mode_value
--
-- 3. 11 rows seeded with metadata:
--    SELECT dashboard_id, provider, category, display_order, title_es, rls_mode
--    FROM dashboard_registrations ORDER BY display_order, dashboard_id;
--    -- expected: 11 rows (3 existing backfilled + 8 new Grafana)
--
-- 4. CHECK reject path (bad time range):
--    INSERT INTO dashboard_registrations (dashboard_id, provider, default_time_range,
--                                          grafana_dashboard_uid, looker_report_id, title_es, title_fr, title_en)
--    VALUES ('test_bad_time', 'grafana', 'last week', 'facil-test', NULL, 't', 't', 't');
--    -- expected: ERROR violates chk_default_time_range_format
--
-- 5. CHECK reject path (panel_id missing for solo):
--    INSERT INTO dashboard_registrations (dashboard_id, provider, embed_mode,
--                                          grafana_dashboard_uid, looker_report_id, title_es, title_fr, title_en)
--    VALUES ('test_solo_no_panel', 'grafana', 'solo', 'facil-test', NULL, 't', 't', 't');
--    -- expected: ERROR violates chk_panel_id_for_solo
--
-- 6. Idempotence: re-run the migration. Expect 0 new rows.
-- ---------------------------------------------------------------------------

-- ROLLBACK (manual, if absolutely needed):
-- BEGIN;
--   DELETE FROM dashboard_registrations
--   WHERE dashboard_id IN ('overview', 'payments', 'companies', 'oms',
--                          'service-requests', 'channel', 'inspections', 'user-activity');
--   ALTER TABLE dashboard_registrations DROP CONSTRAINT IF EXISTS chk_default_time_range_format;
--   ALTER TABLE dashboard_registrations DROP CONSTRAINT IF EXISTS chk_category_value;
--   ALTER TABLE dashboard_registrations DROP CONSTRAINT IF EXISTS chk_panel_id_for_solo;
--   ALTER TABLE dashboard_registrations DROP CONSTRAINT IF EXISTS chk_embed_mode_value;
--   ALTER TABLE dashboard_registrations DROP CONSTRAINT IF EXISTS chk_rls_mode_value;
--   DROP INDEX IF EXISTS idx_dashboard_registrations_order;
--   ALTER TABLE dashboard_registrations
--     DROP COLUMN IF EXISTS category,
--     DROP COLUMN IF EXISTS icon_name,
--     DROP COLUMN IF EXISTS default_time_range,
--     DROP COLUMN IF EXISTS display_order,
--     DROP COLUMN IF EXISTS panel_id,
--     DROP COLUMN IF EXISTS embed_mode,
--     DROP COLUMN IF EXISTS rls_mode,
--     DROP COLUMN IF EXISTS description_en,
--     DROP COLUMN IF EXISTS description_fr,
--     DROP COLUMN IF EXISTS description_es,
--     DROP COLUMN IF EXISTS title_en,
--     DROP COLUMN IF EXISTS title_fr,
--     DROP COLUMN IF EXISTS title_es;
--   ALTER TABLE dashboard_registrations DROP CONSTRAINT IF EXISTS chk_looker_report_id_format;
--   ALTER TABLE dashboard_registrations
--     ADD CONSTRAINT chk_looker_report_id_format
--     CHECK (looker_report_id ~ '^[a-zA-Z0-9_-]{8,64}$');
--   ALTER TABLE dashboard_registrations ALTER COLUMN looker_report_id SET NOT NULL;
-- COMMIT;
