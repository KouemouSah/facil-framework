-- ============================================================================
-- Migration 064: Seed menu templates for workflow-based entities
-- ============================================================================
-- Purpose: Create reusable menu templates for entities with workflows
--
-- VERIFIED AGAINST DATABASE STATE (2026-01-25):
--   - Entity CNEDOGE_PASAPORTE: 5 PASAPORTE_* workflows
--   - Entity CNEDOGE_RESIDENCIA: 5 RESIDENCIA_* workflows
--   - Entity DGT: 5 CONDUCIR_* workflows
--   - Entity OFIVE: 6 VEHICULO_* workflows
--   - Entity ONRC: 7 CONTRATO_* workflows
--   - Entity TESORO: No workflows (module-based, handled by role menu_config)
--
-- NOTE: This migration does NOT update roles that don't exist.
-- Future roles should be created with their menu_config OR use NULL for auto-generation.
--
-- Author: Claude Code Expert
-- Date: 2026-01-19
-- Revised: 2026-01-25 (removed references to non-existent roles)
-- ============================================================================

BEGIN;

-- =============================================================================
-- 1. MENU TEMPLATES FOR WORKFLOW-BASED ENTITIES
-- =============================================================================
-- These templates provide default configurations for entities with workflows.
-- When an agent's role has menu_config = NULL, the system auto-generates menus
-- from entity.workflow_codes using workflow_menu_mapping rules.
-- These templates can be used to customize the auto-generated menus.

-- Template for CNEDOGE_PASAPORTE entity
INSERT INTO menu_templates (code, name, description, template_type, entity_code, menu_structure, dashboard_widgets)
VALUES (
    'cnedoge_pasaporte_default',
    'CNEDOGE Pasaportes Template',
    'Template par defaut pour les agents de passeports CNEDOGE',
    'workflow',
    'CNEDOGE_PASAPORTE',
    '{
        "version": "1.0",
        "source": "template",
        "default_menus": ["dashboard", "pending", "validation", "appointments", "history"],
        "permission_prefix": "service_requests",
        "workflows": ["PASAPORTE_NUEVO", "PASAPORTE_RENOVACION", "PASAPORTE_PERDIDA", "PASAPORTE_ROBO", "PASAPORTE_DETERIORO"]
    }',
    '{
        "version": "1.0",
        "layout": "grid",
        "widgets": [
            {"id": "pending_requests", "visible": true, "position": 1, "size": "small"},
            {"id": "appointments_today", "visible": true, "position": 2, "size": "small"},
            {"id": "completed_today", "visible": true, "position": 3, "size": "small"},
            {"id": "recent_activity", "visible": true, "position": 4, "size": "large"}
        ]
    }'
)
ON CONFLICT (code) DO UPDATE SET
    menu_structure = EXCLUDED.menu_structure,
    dashboard_widgets = EXCLUDED.dashboard_widgets,
    updated_at = NOW();

-- Template for CNEDOGE_RESIDENCIA entity
INSERT INTO menu_templates (code, name, description, template_type, entity_code, menu_structure, dashboard_widgets)
VALUES (
    'cnedoge_residencia_default',
    'CNEDOGE Residencias Template',
    'Template par defaut pour les agents de residencias CNEDOGE',
    'workflow',
    'CNEDOGE_RESIDENCIA',
    '{
        "version": "1.0",
        "source": "template",
        "default_menus": ["dashboard", "pending", "validation", "appointments", "history"],
        "permission_prefix": "service_requests",
        "workflows": ["RESIDENCIA_PRIMERA_VEZ", "RESIDENCIA_RENOVACION", "RESIDENCIA_DUPLICADO", "RESIDENCIA_CAMBIO_DATOS", "RESIDENCIA_REAGRUPACION"]
    }',
    '{
        "version": "1.0",
        "layout": "grid",
        "widgets": [
            {"id": "pending_requests", "visible": true, "position": 1, "size": "small"},
            {"id": "appointments_today", "visible": true, "position": 2, "size": "small"},
            {"id": "completed_today", "visible": true, "position": 3, "size": "small"},
            {"id": "recent_activity", "visible": true, "position": 4, "size": "large"}
        ]
    }'
)
ON CONFLICT (code) DO UPDATE SET
    menu_structure = EXCLUDED.menu_structure,
    dashboard_widgets = EXCLUDED.dashboard_widgets,
    updated_at = NOW();

-- Template for DGT entity (Licencias de conducir)
INSERT INTO menu_templates (code, name, description, template_type, entity_code, menu_structure, dashboard_widgets)
VALUES (
    'dgt_default',
    'DGT Licencias Template',
    'Template par defaut pour les agents DGT (licencias de conducir)',
    'workflow',
    'DGT',
    '{
        "version": "1.0",
        "source": "template",
        "default_menus": ["dashboard", "pending", "validation", "appointments", "history"],
        "permission_prefix": "service_requests",
        "workflows": ["CONDUCIR_NUEVO", "CONDUCIR_CANJE", "CONDUCIR_RENOVACION", "CONDUCIR_DUPLICADO", "CONDUCIR_EXTENSION"]
    }',
    '{
        "version": "1.0",
        "layout": "grid",
        "widgets": [
            {"id": "pending_licenses", "visible": true, "position": 1, "size": "small"},
            {"id": "appointments_today", "visible": true, "position": 2, "size": "small"},
            {"id": "completed_today", "visible": true, "position": 3, "size": "small"},
            {"id": "recent_activity", "visible": true, "position": 4, "size": "large"}
        ]
    }'
)
ON CONFLICT (code) DO UPDATE SET
    menu_structure = EXCLUDED.menu_structure,
    dashboard_widgets = EXCLUDED.dashboard_widgets,
    updated_at = NOW();

-- Template for OFIVE entity (Vehiculos)
INSERT INTO menu_templates (code, name, description, template_type, entity_code, menu_structure, dashboard_widgets)
VALUES (
    'ofive_default',
    'OFIVE Vehiculos Template',
    'Template par defaut pour les agents OFIVE (vehiculos, CUVE)',
    'workflow',
    'OFIVE',
    '{
        "version": "1.0",
        "source": "template",
        "default_menus": ["dashboard", "pending", "validation", "appointments", "history"],
        "permission_prefix": "service_requests",
        "workflows": ["VEHICULO_PRIMERA_MATRICULACION", "VEHICULO_TRANSFERENCIA", "VEHICULO_RENOVACION_CUVE", "VEHICULO_DUPLICADO_PERMISO", "VEHICULO_DUPLICADO_CUVE", "VEHICULO_CAMBIO_CARACTERISTICAS"]
    }',
    '{
        "version": "1.0",
        "layout": "grid",
        "widgets": [
            {"id": "pending_vehicles", "visible": true, "position": 1, "size": "small"},
            {"id": "appointments_today", "visible": true, "position": 2, "size": "small"},
            {"id": "completed_today", "visible": true, "position": 3, "size": "small"},
            {"id": "recent_activity", "visible": true, "position": 4, "size": "large"}
        ]
    }'
)
ON CONFLICT (code) DO UPDATE SET
    menu_structure = EXCLUDED.menu_structure,
    dashboard_widgets = EXCLUDED.dashboard_widgets,
    updated_at = NOW();

-- Template for ONRC entity (Contratos)
INSERT INTO menu_templates (code, name, description, template_type, entity_code, menu_structure, dashboard_widgets)
VALUES (
    'onrc_default',
    'ONRC Contratos Template',
    'Template par defaut pour les agents ONRC (contratos)',
    'workflow',
    'ONRC',
    '{
        "version": "1.0",
        "source": "template",
        "default_menus": ["dashboard", "pending", "validation", "history"],
        "permission_prefix": "service_requests",
        "workflows": ["CONTRATO_OBRA", "CONTRATO_SERVICIO", "CONTRATO_SUMINISTRO", "CONTRATO_CONCESION", "CONTRATO_JOINT_VENTURE", "CONTRATO_ARRENDAMIENTO", "CONTRATO_OTRO"]
    }',
    '{
        "version": "1.0",
        "layout": "grid",
        "widgets": [
            {"id": "pending_contracts", "visible": true, "position": 1, "size": "small"},
            {"id": "in_review", "visible": true, "position": 2, "size": "small"},
            {"id": "completed_today", "visible": true, "position": 3, "size": "small"},
            {"id": "recent_activity", "visible": true, "position": 4, "size": "large"}
        ]
    }'
)
ON CONFLICT (code) DO UPDATE SET
    menu_structure = EXCLUDED.menu_structure,
    dashboard_widgets = EXCLUDED.dashboard_widgets,
    updated_at = NOW();

-- Template for TESORO entity (Module-based, explicit menu)
INSERT INTO menu_templates (code, name, description, template_type, entity_code, menu_structure, dashboard_widgets)
VALUES (
    'tesoro_default',
    'Tesoro Treasury Template',
    'Template par defaut pour les agents Tesoro (validation paiements)',
    'module',
    'TESORO',
    '{
        "version": "1.0",
        "source": "template",
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
                    {"id": "transactions", "titleKey": "agent.nav.transactions", "href": "/dashboard/agent/treasury/transactions", "icon": "History", "permission": "treasury.view_payment"}
                ]
            },
            {
                "id": "reports",
                "titleKey": "agent.nav.reports",
                "icon": "BarChart3",
                "permission": "treasury_stat.view",
                "items": [
                    {"id": "stats", "titleKey": "agent.nav.stats", "href": "/dashboard/agent/treasury/stats", "icon": "TrendingUp", "permission": "treasury_stat.view"}
                ]
            }
        ]
    }',
    '{
        "version": "1.0",
        "layout": "grid",
        "widgets": [
            {"id": "pending_payments", "visible": true, "position": 1, "size": "small"},
            {"id": "in_progress_payments", "visible": true, "position": 2, "size": "small"},
            {"id": "completed_payments", "visible": true, "position": 3, "size": "small"},
            {"id": "recent_activity", "visible": true, "position": 4, "size": "large"}
        ]
    }'
)
ON CONFLICT (code) DO UPDATE SET
    menu_structure = EXCLUDED.menu_structure,
    dashboard_widgets = EXCLUDED.dashboard_widgets,
    updated_at = NOW();

COMMIT;

-- =============================================================================
-- VERIFICATION
-- =============================================================================

SELECT
    'Migration 064 completed' AS status,
    COUNT(*) AS menu_templates_count
FROM menu_templates;

SELECT
    code,
    name,
    template_type,
    entity_code
FROM menu_templates
ORDER BY entity_code, code;

-- ============================================================================
-- END OF MIGRATION 064
-- ============================================================================
