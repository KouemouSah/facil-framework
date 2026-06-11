-- ============================================================================
-- Migration 063: Add menu_config and dashboard_config to roles table
-- ============================================================================
-- Purpose: Enable dynamic menu and dashboard configuration per role
--
-- Changes:
--   1. ALTER TABLE roles: Add menu_config, dashboard_config, ui_config JSONB columns
--   2. ALTER TABLE agent_profiles: Add menu_overrides, dashboard_overrides JSONB columns
--   3. CREATE TABLE menu_templates: Reusable menu templates
--   4. CREATE TABLE workflow_menu_mapping: Auto-generation rules for workflow-based menus
--   5. SEED DATA: Default workflow mappings based on ACTUAL entities
--   6. SEED DATA: Menu config for agent_tesoro (only existing role)
--
-- VERIFIED AGAINST DATABASE STATE:
--   - Entities: CNEDOGE, CNEDOGE_PASAPORTE, CNEDOGE_RESIDENCIA, DGT, OFIVE, ONRC, TESORO
--   - Roles with entity_type=agent: agent_tesoro
--   - Workflows: PASAPORTE_*, RESIDENCIA_*, CONDUCIR_*, VEHICULO_*, CONTRATO_*
--
-- Author: Claude Code Expert
-- Date: 2026-01-19
-- Revised: 2026-01-25 (cleaned obsolete references)
-- ============================================================================

BEGIN;

-- =============================================================================
-- 1. ALTER TABLE: roles - Add configuration columns
-- =============================================================================

ALTER TABLE roles ADD COLUMN IF NOT EXISTS menu_config JSONB DEFAULT NULL;
COMMENT ON COLUMN roles.menu_config IS 'Configuration des menus pour ce role (JSON). NULL = utiliser generation auto depuis entity.workflow_codes';

ALTER TABLE roles ADD COLUMN IF NOT EXISTS dashboard_config JSONB DEFAULT NULL;
COMMENT ON COLUMN roles.dashboard_config IS 'Configuration du dashboard pour ce role (widgets, cards, layout). NULL = dashboard par defaut';

ALTER TABLE roles ADD COLUMN IF NOT EXISTS ui_config JSONB DEFAULT NULL;
COMMENT ON COLUMN roles.ui_config IS 'Preferences UI (theme, raccourcis, options affichage). NULL = valeurs par defaut';

-- =============================================================================
-- 2. ALTER TABLE: agent_profiles - Add per-agent override columns
-- =============================================================================

ALTER TABLE agent_profiles ADD COLUMN IF NOT EXISTS menu_overrides JSONB DEFAULT NULL;
COMMENT ON COLUMN agent_profiles.menu_overrides IS 'Surcharges de menu specifiques a cet agent (override role config)';

ALTER TABLE agent_profiles ADD COLUMN IF NOT EXISTS dashboard_overrides JSONB DEFAULT NULL;
COMMENT ON COLUMN agent_profiles.dashboard_overrides IS 'Surcharges de dashboard specifiques a cet agent';

-- =============================================================================
-- 3. CREATE TABLE: menu_templates
-- =============================================================================

CREATE TABLE IF NOT EXISTS menu_templates (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    code VARCHAR(50) NOT NULL UNIQUE,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    template_type VARCHAR(30) NOT NULL DEFAULT 'workflow'
        CHECK (template_type IN ('workflow', 'module', 'custom')),
    entity_code VARCHAR(50),
    menu_structure JSONB NOT NULL,
    dashboard_widgets JSONB,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    created_by UUID REFERENCES users(id)
);

COMMENT ON TABLE menu_templates IS 'Templates de menu reutilisables pour differents types d''agents';

CREATE INDEX IF NOT EXISTS idx_menu_templates_code ON menu_templates(code);
CREATE INDEX IF NOT EXISTS idx_menu_templates_entity ON menu_templates(entity_code);
CREATE INDEX IF NOT EXISTS idx_menu_templates_type ON menu_templates(template_type);
CREATE INDEX IF NOT EXISTS idx_menu_templates_active ON menu_templates(is_active) WHERE is_active = TRUE;

-- =============================================================================
-- 4. CREATE TABLE: workflow_menu_mapping
-- =============================================================================

CREATE TABLE IF NOT EXISTS workflow_menu_mapping (
    id SERIAL PRIMARY KEY,
    workflow_pattern VARCHAR(100) NOT NULL,
    menu_group_id VARCHAR(50) NOT NULL,
    menu_title_key VARCHAR(100) NOT NULL,
    menu_icon VARCHAR(50) NOT NULL,
    display_order INT DEFAULT 0,
    include_pending BOOLEAN DEFAULT TRUE,
    include_validation BOOLEAN DEFAULT TRUE,
    include_appointments BOOLEAN DEFAULT FALSE,
    include_history BOOLEAN DEFAULT TRUE,
    permission_prefix VARCHAR(50),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

COMMENT ON TABLE workflow_menu_mapping IS 'Regles de generation automatique de menus depuis les codes workflow';

CREATE UNIQUE INDEX IF NOT EXISTS idx_workflow_menu_mapping_pattern
    ON workflow_menu_mapping(workflow_pattern);

CREATE INDEX IF NOT EXISTS idx_workflow_menu_mapping_active
    ON workflow_menu_mapping(is_active) WHERE is_active = TRUE;

-- =============================================================================
-- 5. SEED DATA: Workflow menu mappings (BASED ON ACTUAL ENTITIES)
-- =============================================================================
-- VERIFIED ENTITIES AND THEIR WORKFLOWS:
--   CNEDOGE_PASAPORTE: PASAPORTE_NUEVO, PASAPORTE_RENOVACION, PASAPORTE_PERDIDA, PASAPORTE_ROBO, PASAPORTE_DETERIORO
--   CNEDOGE_RESIDENCIA: RESIDENCIA_PRIMERA_VEZ, RESIDENCIA_RENOVACION, RESIDENCIA_DUPLICADO, RESIDENCIA_CAMBIO_DATOS, RESIDENCIA_REAGRUPACION
--   DGT: CONDUCIR_NUEVO, CONDUCIR_CANJE, CONDUCIR_RENOVACION, CONDUCIR_DUPLICADO, CONDUCIR_EXTENSION
--   OFIVE: VEHICULO_PRIMERA_MATRICULACION, VEHICULO_TRANSFERENCIA, VEHICULO_RENOVACION_CUVE, VEHICULO_DUPLICADO_PERMISO, VEHICULO_DUPLICADO_CUVE, VEHICULO_CAMBIO_CARACTERISTICAS
--   ONRC: CONTRATO_OBRA, CONTRATO_SERVICIO, CONTRATO_SUMINISTRO, CONTRATO_CONCESION, CONTRATO_JOINT_VENTURE, CONTRATO_ARRENDAMIENTO, CONTRATO_OTRO
-- =============================================================================

INSERT INTO workflow_menu_mapping (
    workflow_pattern, menu_group_id, menu_title_key, menu_icon,
    display_order, include_appointments, permission_prefix
) VALUES
    -- CNEDOGE_PASAPORTE: Pasaportes (5 workflows)
    ('PASAPORTE_%', 'pasaportes', 'agent.nav.passports', 'Plane', 1, TRUE, 'service_requests'),

    -- CNEDOGE_RESIDENCIA: Residencias (5 workflows)
    ('RESIDENCIA_%', 'residencias', 'agent.nav.residences', 'Globe', 2, TRUE, 'service_requests'),

    -- DGT: Permisos de Conducir (5 workflows)
    ('CONDUCIR_%', 'licencias', 'agent.nav.licenses', 'Car', 3, TRUE, 'service_requests'),

    -- OFIVE: Vehiculos (6 workflows)
    ('VEHICULO_%', 'vehiculos', 'agent.nav.vehicles', 'Truck', 4, TRUE, 'service_requests'),

    -- ONRC: Contratos (7 workflows) - No appointments for contracts
    ('CONTRATO_%', 'contratos', 'agent.nav.contracts', 'FileSignature', 5, FALSE, 'service_requests')

ON CONFLICT (workflow_pattern) DO NOTHING;

-- =============================================================================
-- 6. SEED DATA: Menu config for agent_tesoro (ONLY EXISTING ROLE)
-- =============================================================================
-- TESORO is module-based (no workflows), needs explicit menu_config
-- ALIGNED WITH: packages/web/src/modules/agent-dashboard/config/entity-menus.ts TESORO_CONFIG

UPDATE roles SET
    menu_config = '{
        "version": "1.0",
        "source": "role",
        "menus": [
            {
                "id": "dashboard",
                "titleKey": "agent.nav.dashboard",
                "href": "/dashboard/agent/treasury",
                "icon": "LayoutDashboard"
            },
            {
                "id": "payments",
                "titleKey": "agent.nav.payments",
                "icon": "CreditCard",
                "items": [
                    {"id": "validation", "titleKey": "agent.nav.validation", "href": "/dashboard/agent/treasury/validation", "icon": "CheckCircle", "permission": "treasury.validate_payment"},
                    {"id": "reconciliation", "titleKey": "agent.nav.reconciliation", "href": "/dashboard/agent/treasury/reconciliation", "icon": "RefreshCw", "permission": "treasury.reconcile"},
                    {"id": "transactions", "titleKey": "agent.nav.transactions", "href": "/dashboard/agent/treasury/transactions", "icon": "History", "permission": "treasury.view_payment"}
                ]
            },
            {
                "id": "reports",
                "titleKey": "agent.nav.reports",
                "icon": "BarChart3",
                "items": [
                    {"id": "stats", "titleKey": "agent.nav.stats", "href": "/dashboard/agent/treasury/stats", "icon": "TrendingUp", "permission": "treasury_stat.view"},
                    {"id": "analytics", "titleKey": "agent.nav.analytics", "href": "/dashboard/agent/treasury/analytics", "icon": "Activity", "permission": "treasury_stat.view"},
                    {"id": "audit", "titleKey": "agent.nav.audit", "href": "/dashboard/agent/treasury/audit", "icon": "FileSearch", "permission": "treasury_audit.view"},
                    {"id": "sla", "titleKey": "agent.nav.slaStats", "href": "/dashboard/agent/treasury/stats/sla", "icon": "BarChart3", "permission": "treasury_stat.view"},
                    {"id": "anomalies", "titleKey": "agent.nav.anomalies", "href": "/dashboard/agent/treasury/anomalies", "icon": "ShieldAlert", "permission": "treasury_anomaly.view"},
                    {"id": "exports", "titleKey": "agent.nav.exports", "href": "/dashboard/agent/treasury/exports", "icon": "FileSpreadsheet", "permission": "treasury_export.view"}
                ]
            },
            {
                "id": "settings",
                "titleKey": "agent.nav.settings",
                "icon": "Settings",
                "permission": "treasury.manage_settings",
                "items": [
                    {"id": "banks", "titleKey": "agent.nav.banks", "href": "/dashboard/agent/treasury/settings/banks", "icon": "Building2", "permission": "treasury.manage_settings"},
                    {"id": "payment-methods", "titleKey": "agent.nav.paymentMethods", "href": "/dashboard/agent/treasury/settings/payment-methods", "icon": "Banknote", "permission": "treasury.manage_settings"}
                ]
            }
        ]
    }',
    dashboard_config = '{
        "version": "1.0",
        "layout": "grid",
        "widgets": [
            {"id": "pending_payments", "visible": true, "position": 1, "size": "small"},
            {"id": "in_progress_payments", "visible": true, "position": 2, "size": "small"},
            {"id": "completed_payments", "visible": true, "position": 3, "size": "small"},
            {"id": "recent_activity", "visible": true, "position": 4, "size": "large"}
        ]
    }'
WHERE code = 'agent_tesoro';

-- =============================================================================
-- 7. INDEXES for JSONB queries
-- =============================================================================

CREATE INDEX IF NOT EXISTS idx_roles_menu_config ON roles USING GIN (menu_config);
CREATE INDEX IF NOT EXISTS idx_roles_dashboard_config ON roles USING GIN (dashboard_config);
CREATE INDEX IF NOT EXISTS idx_agent_profiles_menu_overrides ON agent_profiles USING GIN (menu_overrides);
CREATE INDEX IF NOT EXISTS idx_agent_profiles_dashboard_overrides ON agent_profiles USING GIN (dashboard_overrides);

-- =============================================================================
-- 8. UPDATE TRIGGERS
-- =============================================================================

CREATE OR REPLACE FUNCTION update_menu_templates_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS tr_menu_templates_updated_at ON menu_templates;
CREATE TRIGGER tr_menu_templates_updated_at
    BEFORE UPDATE ON menu_templates
    FOR EACH ROW
    EXECUTE FUNCTION update_menu_templates_updated_at();

CREATE OR REPLACE FUNCTION update_workflow_menu_mapping_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS tr_workflow_menu_mapping_updated_at ON workflow_menu_mapping;
CREATE TRIGGER tr_workflow_menu_mapping_updated_at
    BEFORE UPDATE ON workflow_menu_mapping
    FOR EACH ROW
    EXECUTE FUNCTION update_workflow_menu_mapping_updated_at();

-- =============================================================================
-- 9. VALIDATION FUNCTION for menu_config JSON structure
-- =============================================================================

CREATE OR REPLACE FUNCTION validate_menu_config(config JSONB)
RETURNS BOOLEAN AS $$
BEGIN
    IF config IS NULL THEN
        RETURN TRUE;
    END IF;

    IF NOT (config ? 'version') THEN
        RAISE EXCEPTION 'menu_config must have "version" field';
    END IF;

    IF NOT (config ? 'menus') THEN
        RAISE EXCEPTION 'menu_config must have "menus" array';
    END IF;

    IF jsonb_typeof(config->'menus') != 'array' THEN
        RAISE EXCEPTION 'menu_config.menus must be an array';
    END IF;

    RETURN TRUE;
END;
$$ LANGUAGE plpgsql;

ALTER TABLE roles DROP CONSTRAINT IF EXISTS chk_roles_menu_config_valid;
ALTER TABLE roles ADD CONSTRAINT chk_roles_menu_config_valid
    CHECK (validate_menu_config(menu_config));

COMMIT;

-- =============================================================================
-- VERIFICATION
-- =============================================================================

SELECT
    'Migration 063 completed' AS status,
    (SELECT COUNT(*) FROM workflow_menu_mapping) AS workflow_mappings,
    (SELECT COUNT(*) FROM roles WHERE menu_config IS NOT NULL) AS roles_with_menu_config;

-- ============================================================================
-- END OF MIGRATION 063
-- ============================================================================
