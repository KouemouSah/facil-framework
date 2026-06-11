-- ============================================================================
-- Migration 277: Supervisor Field Operations — Phase 1 Foundations
-- ============================================================================
-- Creates tables for mission planning, filter presets, and analytics.
-- Adds zone_id/mission_id/duration_minutes to field_inspections.
-- Creates materialized view for zone analytics.
-- Fixes missing permission assignments (migration 249 ran before role creation in 272).
--
-- Dependencies: 249 (field_inspections), 270 (OMS entities), 272 (OMS roles)
-- ============================================================================

BEGIN;

-- ============================================================================
-- 1. TABLE: field_missions — Daily mission planning
-- ============================================================================
-- Allows supervisors to plan daily field operations per location.
-- UNIQUE on (entity_id, entity_location_id, mission_date) allows multiple
-- missions per entity on the same day at different locations.

CREATE TABLE IF NOT EXISTS field_missions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_id UUID NOT NULL REFERENCES entities(id),
    entity_location_id UUID NOT NULL REFERENCES entity_locations(id),
    supervisor_id UUID NOT NULL REFERENCES users(id),
    mission_date DATE NOT NULL,
    title VARCHAR(200),
    notes TEXT,
    zone_ids UUID[],  -- Target zones for this mission (FK checked at app level)
    status VARCHAR(20) NOT NULL DEFAULT 'planned'
        CHECK (status IN ('planned', 'in_progress', 'completed', 'cancelled')),
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (entity_id, entity_location_id, mission_date)
);

COMMENT ON TABLE field_missions IS 'Daily field operation missions planned by supervisors';
COMMENT ON COLUMN field_missions.zone_ids IS 'Target commerce_zones UUIDs for this mission';
COMMENT ON COLUMN field_missions.status IS 'planned → in_progress → completed|cancelled';

-- Indexes for field_missions
CREATE INDEX IF NOT EXISTS idx_fm_entity_date
    ON field_missions (entity_id, mission_date DESC);
CREATE INDEX IF NOT EXISTS idx_fm_supervisor
    ON field_missions (supervisor_id, mission_date DESC);
CREATE INDEX IF NOT EXISTS idx_fm_status
    ON field_missions (status)
    WHERE status IN ('planned', 'in_progress');
CREATE INDEX IF NOT EXISTS idx_fm_location_date
    ON field_missions (entity_location_id, mission_date DESC);

-- ============================================================================
-- 2. TABLE: field_mission_agents — Agent assignments to missions
-- ============================================================================

CREATE TABLE IF NOT EXISTS field_mission_agents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    mission_id UUID NOT NULL REFERENCES field_missions(id) ON DELETE CASCADE,
    agent_id UUID NOT NULL REFERENCES users(id),
    agent_profile_id UUID NOT NULL REFERENCES agent_profiles(id),
    assigned_zones UUID[],  -- Subset of mission zones assigned to this agent
    target_inspections INT NOT NULL DEFAULT 10
        CHECK (target_inspections > 0 AND target_inspections <= 100),
    status VARCHAR(20) NOT NULL DEFAULT 'assigned'
        CHECK (status IN ('assigned', 'active', 'completed', 'absent')),
    actual_inspections INT NOT NULL DEFAULT 0
        CHECK (actual_inspections >= 0),
    notes TEXT,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (mission_id, agent_id)
);

COMMENT ON TABLE field_mission_agents IS 'Agent assignments within a field mission';
COMMENT ON COLUMN field_mission_agents.assigned_zones IS 'commerce_zones UUIDs this agent covers';
COMMENT ON COLUMN field_mission_agents.target_inspections IS 'Expected number of inspections (1-100)';

-- Indexes for field_mission_agents
CREATE INDEX IF NOT EXISTS idx_fma_mission
    ON field_mission_agents (mission_id);
CREATE INDEX IF NOT EXISTS idx_fma_agent
    ON field_mission_agents (agent_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_fma_profile
    ON field_mission_agents (agent_profile_id);
CREATE INDEX IF NOT EXISTS idx_fma_active
    ON field_mission_agents (mission_id)
    WHERE status IN ('assigned', 'active');

-- ============================================================================
-- 3. TABLE: supervisor_filter_presets — Saved table filter configurations
-- ============================================================================

CREATE TABLE IF NOT EXISTS supervisor_filter_presets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    preset_name VARCHAR(100) NOT NULL,
    table_key VARCHAR(50) NOT NULL,  -- e.g. 'inspections', 'reconciliation', 'seals', 'agents'
    filters JSONB NOT NULL DEFAULT '{}',
    column_visibility JSONB,  -- { "column_name": true/false }
    sort_config JSONB,  -- { "column": "...", "direction": "asc"|"desc" }
    is_default BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (user_id, preset_name, table_key)
);

COMMENT ON TABLE supervisor_filter_presets IS 'Saved filter/sort/column configurations per user per table';
COMMENT ON COLUMN supervisor_filter_presets.table_key IS 'Identifies which table this preset applies to';

-- Indexes for supervisor_filter_presets
CREATE INDEX IF NOT EXISTS idx_sfp_user_table
    ON supervisor_filter_presets (user_id, table_key);

-- Ensure only one default preset per user per table
CREATE UNIQUE INDEX IF NOT EXISTS idx_sfp_single_default
    ON supervisor_filter_presets (user_id, table_key)
    WHERE is_default = true;

-- ============================================================================
-- 4. ALTER field_inspections — Add zone_id, mission_id, duration_minutes
-- ============================================================================

-- zone_id: denormalized from company for analytics performance
ALTER TABLE field_inspections
    ADD COLUMN IF NOT EXISTS zone_id UUID REFERENCES commerce_zones(id);

-- mission_id: link inspection to its planned mission
ALTER TABLE field_inspections
    ADD COLUMN IF NOT EXISTS mission_id UUID REFERENCES field_missions(id);

-- duration_minutes: time spent on inspection (calculated from timestamps or manual)
ALTER TABLE field_inspections
    ADD COLUMN IF NOT EXISTS duration_minutes INT
        CHECK (duration_minutes IS NULL OR (duration_minutes > 0 AND duration_minutes <= 480));

COMMENT ON COLUMN field_inspections.zone_id IS 'Commerce zone (denormalized from company for analytics)';
COMMENT ON COLUMN field_inspections.mission_id IS 'Field mission this inspection belongs to (nullable for ad-hoc)';
COMMENT ON COLUMN field_inspections.duration_minutes IS 'Inspection duration in minutes (1-480, ~8h max)';

-- Index for zone-based analytics
CREATE INDEX IF NOT EXISTS idx_fi_zone
    ON field_inspections (zone_id, inspection_date DESC)
    WHERE zone_id IS NOT NULL;

-- Index for mission-linked inspections
CREATE INDEX IF NOT EXISTS idx_fi_mission
    ON field_inspections (mission_id)
    WHERE mission_id IS NOT NULL;

-- Backfill zone_id from company's zone_id for any existing inspections
UPDATE field_inspections fi
SET zone_id = c.zone_id
FROM companies c
WHERE fi.company_id = c.id
  AND fi.zone_id IS NULL
  AND c.zone_id IS NOT NULL;

-- ============================================================================
-- 5. MATERIALIZED VIEW: mv_inspection_zone_analytics
-- ============================================================================
-- Aggregates inspection data by entity, zone, and week for fast analytics.
-- Refreshed daily via InternalScheduler (CONCURRENTLY).

CREATE MATERIALIZED VIEW IF NOT EXISTS mv_inspection_zone_analytics AS
SELECT
    fi.entity_id,
    fi.zone_id,
    cz.zone_code,
    cz.name_es AS zone_name,
    cz.zone_tier,
    DATE_TRUNC('week', fi.inspection_date)::DATE AS week_start,
    COUNT(*)::INT AS inspections,
    COUNT(*) FILTER (WHERE fi.result = 'conforme')::INT AS conforme,
    COUNT(*) FILTER (WHERE fi.result = 'non_conforme')::INT AS non_conforme,
    COUNT(*) FILTER (WHERE fi.payment_collected = true)::INT AS collections,
    COALESCE(SUM(fi.payment_amount) FILTER (WHERE fi.payment_collected = true), 0)::NUMERIC(15,2) AS collected_amount,
    COUNT(*) FILTER (WHERE fi.mise_en_demeure_issued = true)::INT AS med_count,
    COUNT(*) FILTER (WHERE fi.seal_applied = true)::INT AS seal_count,
    COUNT(DISTINCT fi.agent_id)::INT AS agents_active,
    ROUND(AVG(fi.duration_minutes) FILTER (WHERE fi.duration_minutes IS NOT NULL), 1) AS avg_duration_minutes,
    -- Derived metrics
    CASE
        WHEN COUNT(*) > 0
        THEN ROUND(100.0 * COUNT(*) FILTER (WHERE fi.result = 'conforme') / COUNT(*), 1)
        ELSE 0
    END AS conformity_rate,
    CASE
        WHEN COUNT(*) > 0
        THEN ROUND(100.0 * COUNT(*) FILTER (WHERE fi.payment_collected = true) / COUNT(*), 1)
        ELSE 0
    END AS collection_rate
FROM field_inspections fi
LEFT JOIN commerce_zones cz ON cz.id = fi.zone_id
WHERE fi.status NOT IN ('cancelled')
GROUP BY fi.entity_id, fi.zone_id, cz.zone_code, cz.name_es, cz.zone_tier,
         DATE_TRUNC('week', fi.inspection_date)::DATE;

-- UNIQUE INDEX required for REFRESH MATERIALIZED VIEW CONCURRENTLY
CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_iza_unique
    ON mv_inspection_zone_analytics (
        COALESCE(entity_id, '00000000-0000-0000-0000-000000000000'::UUID),
        COALESCE(zone_id, '00000000-0000-0000-0000-000000000000'::UUID),
        week_start
    );

-- Supporting indexes for common query patterns
CREATE INDEX IF NOT EXISTS idx_mv_iza_entity_week
    ON mv_inspection_zone_analytics (entity_id, week_start DESC);
CREATE INDEX IF NOT EXISTS idx_mv_iza_zone
    ON mv_inspection_zone_analytics (zone_id, week_start DESC);
CREATE INDEX IF NOT EXISTS idx_mv_iza_tier
    ON mv_inspection_zone_analytics (zone_tier, week_start DESC);

-- ============================================================================
-- 6. PERMISSIONS — 3 new + FIX missing assignments from migration 249
-- ============================================================================
-- Migration 249 assigned inspection permissions to roles that didn't exist yet
-- (roles were created in migration 272). Re-apply ALL assignments here.

-- Set audit context for role_permissions trigger
SET LOCAL app.current_user_id = '7c6073e3-66b0-45ba-be8d-80fcf98b7ad2';

-- 6a. Insert new + missing permissions (view_reports and export were never created)
INSERT INTO permissions (name, resource, action, description, module_name, is_critical)
VALUES
    ('inspection.view_reports', 'inspection', 'view_reports',
     'Ver reportes de inspecciones', 'inspections', false),
    ('inspection.export', 'inspection', 'export',
     'Exportar datos de inspecciones (CSV/PDF)', 'inspections', false),
    ('inspection.manage_missions', 'inspection', 'manage_missions',
     'Crear y gestionar misiones de campo (supervisor)', 'inspections', true),
    ('inspection.view_analytics', 'inspection', 'view_analytics',
     'Ver analytics e indicadores de inspecciones', 'inspections', false),
    ('inspection.manage_filter_presets', 'inspection', 'manage_filter_presets',
     'Guardar y gestionar presets de filtros', 'inspections', false)
ON CONFLICT (name) DO NOTHING;

-- 6b. Assign AGENT permissions (original 249 set + view_performance for stats)
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM roles r
CROSS JOIN permissions p
WHERE r.code IN (
    'agent_ayuntamiento', 'agent_camara',
    'agent_min_comercio', 'agent_min_hacienda',
    'agent_min_informacion', 'agent_min_turismo',
    'agent_min_agricultura', 'agent_min_electricidad',
    'agent_oms_polyvalent'
)
AND p.name IN (
    'inspection.create',
    'inspection.view_own',
    'inspection.seal_propose',
    'inspection.collect_payment',
    'inspection.mise_en_demeure',
    'inspection.manage_filter_presets'
)
ON CONFLICT (role_id, permission_id) DO NOTHING;

-- 6c. Assign SUPERVISOR permissions (all inspection perms)
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM roles r
CROSS JOIN permissions p
WHERE r.code IN (
    'supervisor_ayuntamiento', 'supervisor_camara',
    'supervisor_min_comercio', 'supervisor_min_hacienda',
    'supervisor_min_informacion', 'supervisor_min_turismo',
    'supervisor_min_agricultura', 'supervisor_min_electricidad',
    'supervisor_tesoro'
)
AND p.name IN (
    'inspection.create',
    'inspection.view_own',
    'inspection.view_entity',
    'inspection.seal_propose',
    'inspection.seal_approve',
    'inspection.collect_payment',
    'inspection.mise_en_demeure',
    'inspection.reconcile_validate',
    'inspection.view_performance',
    'inspection.view_reports',
    'inspection.export',
    -- NEW Phase 1 permissions
    'inspection.manage_missions',
    'inspection.view_analytics',
    'inspection.manage_filter_presets'
)
ON CONFLICT (role_id, permission_id) DO NOTHING;

-- 6d. Admin gets all inspection permissions automatically
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM roles r
CROSS JOIN permissions p
WHERE r.code = 'admin'
AND p.name LIKE 'inspection.%'
ON CONFLICT (role_id, permission_id) DO NOTHING;

-- ============================================================================
-- 7. SYSTEM RULES — Configurable thresholds for field operations
-- ============================================================================
-- rule_category CHECK: validation, penalty, exemption, calculation, workflow, compliance, feature_flag
-- value_type CHECK: number, percentage, date, boolean, string, json
-- rule_value is JSONB
INSERT INTO system_rules (rule_code, rule_category, rule_value, value_type,
                          name_es, name_fr, name_en, description, is_active, effective_from)
VALUES
    ('FIELD_MISSION_MAX_AGENTS', 'workflow', '20'::jsonb, 'number',
     'Máximo agentes por misión', 'Maximum agents par mission', 'Max agents per mission',
     'Maximum agents assignable to a single field mission', true, CURRENT_DATE),
    ('FIELD_MISSION_DEFAULT_TARGET', 'workflow', '10'::jsonb, 'number',
     'Objetivo inspecciones por agente', 'Objectif inspections par agent', 'Target inspections per agent',
     'Default target inspections per agent per mission', true, CURRENT_DATE),
    ('INSPECTION_ZONE_STALE_DAYS', 'compliance', '30'::jsonb, 'number',
     'Días sin inspección (zona obsoleta)', 'Jours sans inspection (zone obsolète)', 'Days without inspection (stale zone)',
     'Days without inspection before zone flagged as stale', true, CURRENT_DATE),
    ('INSPECTION_AGENT_INACTIVE_DAYS', 'compliance', '3'::jsonb, 'number',
     'Días inactividad agente', 'Jours inactivité agent', 'Agent inactive days',
     'Working days without inspection before agent flagged inactive', true, CURRENT_DATE),
    ('INSPECTION_MV_REFRESH_TIMEOUT_MS', 'workflow', '300000'::jsonb, 'number',
     'Timeout refresh analytics (ms)', 'Timeout refresh analytics (ms)', 'Analytics refresh timeout (ms)',
     'Statement timeout for materialized view refresh (milliseconds)', true, CURRENT_DATE)
ON CONFLICT (rule_code) DO NOTHING;

COMMIT;
