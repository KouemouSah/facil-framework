-- ============================================================================
-- Migration 083: Synchronize Agent Permissions and Unify Menu Configs
-- ============================================================================
-- Purpose:
--   1. Add missing permissions to agent_dgt, agent_ofive, agent_onrc, agent_extranjeria, agent_policia
--   2. Unify menu structure for all agent roles (same structure, different hrefs)
--
-- Permissions being added (missing from some roles):
--   - service_request.verify_manually (manual identity verification)
--   - service_request.view_extraction (view OCR extractions)
--
-- Reference role: agent_cnedoge_pasaporte (20 permissions)
--
-- Author: Claude Code
-- Date: 2026-01-30
-- ============================================================================

BEGIN;

-- =============================================================================
-- PART 1: SYNC PERMISSIONS
-- =============================================================================
-- Add missing permissions to roles that have fewer than agent_cnedoge_pasaporte

-- 1.1 Get the permission IDs we need to add
DO $$
DECLARE
    v_verify_manually_id UUID;
    v_view_extraction_id UUID;
    v_role_record RECORD;
    v_roles_to_sync TEXT[] := ARRAY['agent_dgt', 'agent_ofive', 'agent_onrc', 'agent_extranjeria', 'agent_policia'];
BEGIN
    -- Get permission IDs
    SELECT id INTO v_verify_manually_id FROM permissions WHERE name = 'service_request.verify_manually';
    SELECT id INTO v_view_extraction_id FROM permissions WHERE name = 'service_request.view_extraction';

    -- Log what we found
    RAISE NOTICE 'verify_manually permission ID: %', v_verify_manually_id;
    RAISE NOTICE 'view_extraction permission ID: %', v_view_extraction_id;

    -- If permissions don't exist, create them
    IF v_verify_manually_id IS NULL THEN
        INSERT INTO permissions (name, description, module_name, created_at, updated_at)
        VALUES (
            'service_request.verify_manually',
            'Permite verificar manualmente la identidad del ciudadano',
            'service_request',
            NOW(),
            NOW()
        )
        RETURNING id INTO v_verify_manually_id;
        RAISE NOTICE 'Created service_request.verify_manually permission';
    END IF;

    IF v_view_extraction_id IS NULL THEN
        INSERT INTO permissions (name, description, module_name, created_at, updated_at)
        VALUES (
            'service_request.view_extraction',
            'Permite ver los resultados de extraccion OCR',
            'service_request',
            NOW(),
            NOW()
        )
        RETURNING id INTO v_view_extraction_id;
        RAISE NOTICE 'Created service_request.view_extraction permission';
    END IF;

    -- Add permissions to each role that doesn't have them
    FOR v_role_record IN
        SELECT r.id, r.code
        FROM roles r
        WHERE r.code = ANY(v_roles_to_sync)
    LOOP
        -- Add verify_manually if not exists
        INSERT INTO role_permissions (role_id, permission_id, created_at)
        VALUES (v_role_record.id, v_verify_manually_id, NOW())
        ON CONFLICT (role_id, permission_id) DO NOTHING;

        -- Add view_extraction if not exists
        INSERT INTO role_permissions (role_id, permission_id, created_at)
        VALUES (v_role_record.id, v_view_extraction_id, NOW())
        ON CONFLICT (role_id, permission_id) DO NOTHING;

        RAISE NOTICE 'Added permissions to role: %', v_role_record.code;
    END LOOP;
END;
$$;

-- =============================================================================
-- PART 2: UNIFY MENU CONFIGS
-- =============================================================================
-- All agent roles get the same menu structure:
--   - Dashboard
--   - Workflow group (pending, validation, history)
--   - Appointments (if applicable)
-- The only difference is the href paths based on entity

-- 2.1 Update agent_dgt (uses dynamic route /agent/[entityCode]/[workflowGroup]/[action])
UPDATE roles SET
    menu_config = '{
        "version": "1.0",
        "source": "role",
        "menus": [
            {
                "id": "dashboard",
                "titleKey": "agent.nav.dashboard",
                "href": "/dashboard/agent/dgt",
                "icon": "LayoutDashboard"
            },
            {
                "id": "licencias",
                "titleKey": "agent.nav.driverLicenses",
                "icon": "Car",
                "items": [
                    {"id": "pending", "titleKey": "agent.nav.pending", "href": "/dashboard/agent/dgt/conducir/pending", "icon": "Clock", "permission": "service_request.view_queue"},
                    {"id": "validation", "titleKey": "agent.nav.validation", "href": "/dashboard/agent/dgt/conducir/validation", "icon": "CheckCircle", "permission": "service_request.process"},
                    {"id": "history", "titleKey": "agent.nav.history", "href": "/dashboard/agent/dgt/conducir/history", "icon": "History", "permission": "service_request.view"}
                ]
            },
            {
                "id": "appointments",
                "titleKey": "agent.nav.appointments",
                "href": "/dashboard/agent/dgt/appointments",
                "icon": "Calendar",
                "permission": "service_request.view_appointments"
            }
        ]
    }'::jsonb,
    dashboard_config = '{
        "version": "1.0",
        "layout": "grid",
        "widgets": [
            {"id": "alerts", "visible": true, "position": 1, "size": "medium"},
            {"id": "urgent_requests", "visible": true, "position": 2, "size": "medium"},
            {"id": "calendar_slots", "visible": true, "position": 3, "size": "full"},
            {"id": "today_appointments", "visible": true, "position": 4, "size": "medium"},
            {"id": "workflow_distribution", "visible": true, "position": 5, "size": "medium"}
        ]
    }'::jsonb
WHERE code = 'agent_dgt';

-- 2.2 Update agent_ofive
UPDATE roles SET
    menu_config = '{
        "version": "1.0",
        "source": "role",
        "menus": [
            {
                "id": "dashboard",
                "titleKey": "agent.nav.dashboard",
                "href": "/dashboard/agent/ofive",
                "icon": "LayoutDashboard"
            },
            {
                "id": "vehiculos",
                "titleKey": "agent.nav.vehicles",
                "icon": "Car",
                "items": [
                    {"id": "pending", "titleKey": "agent.nav.pending", "href": "/dashboard/agent/ofive/vehiculos/pending", "icon": "Clock", "permission": "service_request.view_queue"},
                    {"id": "validation", "titleKey": "agent.nav.validation", "href": "/dashboard/agent/ofive/vehiculos/validation", "icon": "CheckCircle", "permission": "service_request.process"},
                    {"id": "history", "titleKey": "agent.nav.history", "href": "/dashboard/agent/ofive/vehiculos/history", "icon": "History", "permission": "service_request.view"}
                ]
            },
            {
                "id": "appointments",
                "titleKey": "agent.nav.appointments",
                "href": "/dashboard/agent/ofive/appointments",
                "icon": "Calendar",
                "permission": "service_request.view_appointments"
            }
        ]
    }'::jsonb,
    dashboard_config = '{
        "version": "1.0",
        "layout": "grid",
        "widgets": [
            {"id": "alerts", "visible": true, "position": 1, "size": "medium"},
            {"id": "urgent_requests", "visible": true, "position": 2, "size": "medium"},
            {"id": "calendar_slots", "visible": true, "position": 3, "size": "full"},
            {"id": "today_appointments", "visible": true, "position": 4, "size": "medium"},
            {"id": "workflow_distribution", "visible": true, "position": 5, "size": "medium"}
        ]
    }'::jsonb
WHERE code = 'agent_ofive';

-- 2.3 Update agent_onrc
UPDATE roles SET
    menu_config = '{
        "version": "1.0",
        "source": "role",
        "menus": [
            {
                "id": "dashboard",
                "titleKey": "agent.nav.dashboard",
                "href": "/dashboard/agent/onrc",
                "icon": "LayoutDashboard"
            },
            {
                "id": "contratos",
                "titleKey": "agent.nav.contracts",
                "icon": "FileText",
                "items": [
                    {"id": "pending", "titleKey": "agent.nav.pending", "href": "/dashboard/agent/onrc/contratos/pending", "icon": "Clock", "permission": "service_request.view_queue"},
                    {"id": "validation", "titleKey": "agent.nav.validation", "href": "/dashboard/agent/onrc/contratos/validation", "icon": "CheckCircle", "permission": "service_request.process"},
                    {"id": "history", "titleKey": "agent.nav.history", "href": "/dashboard/agent/onrc/contratos/history", "icon": "History", "permission": "service_request.view"}
                ]
            },
            {
                "id": "appointments",
                "titleKey": "agent.nav.appointments",
                "href": "/dashboard/agent/onrc/appointments",
                "icon": "Calendar",
                "permission": "service_request.view_appointments"
            }
        ]
    }'::jsonb,
    dashboard_config = '{
        "version": "1.0",
        "layout": "grid",
        "widgets": [
            {"id": "alerts", "visible": true, "position": 1, "size": "medium"},
            {"id": "urgent_requests", "visible": true, "position": 2, "size": "medium"},
            {"id": "calendar_slots", "visible": true, "position": 3, "size": "full"},
            {"id": "today_appointments", "visible": true, "position": 4, "size": "medium"},
            {"id": "workflow_distribution", "visible": true, "position": 5, "size": "medium"}
        ]
    }'::jsonb
WHERE code = 'agent_onrc';

-- 2.4 Update agent_extranjeria
UPDATE roles SET
    menu_config = '{
        "version": "1.0",
        "source": "role",
        "menus": [
            {
                "id": "dashboard",
                "titleKey": "agent.nav.dashboard",
                "href": "/dashboard/agent/extranjeria",
                "icon": "LayoutDashboard"
            },
            {
                "id": "residencias",
                "titleKey": "agent.nav.residences",
                "icon": "Globe",
                "items": [
                    {"id": "pending", "titleKey": "agent.nav.pending", "href": "/dashboard/agent/extranjeria/residencias/pending", "icon": "Clock", "permission": "service_request.view_queue"},
                    {"id": "validation", "titleKey": "agent.nav.validation", "href": "/dashboard/agent/extranjeria/residencias/validation", "icon": "CheckCircle", "permission": "service_request.process"},
                    {"id": "history", "titleKey": "agent.nav.history", "href": "/dashboard/agent/extranjeria/residencias/history", "icon": "History", "permission": "service_request.view"}
                ]
            },
            {
                "id": "appointments",
                "titleKey": "agent.nav.appointments",
                "href": "/dashboard/agent/extranjeria/appointments",
                "icon": "Calendar",
                "permission": "service_request.view_appointments"
            }
        ]
    }'::jsonb,
    dashboard_config = '{
        "version": "1.0",
        "layout": "grid",
        "widgets": [
            {"id": "alerts", "visible": true, "position": 1, "size": "medium"},
            {"id": "urgent_requests", "visible": true, "position": 2, "size": "medium"},
            {"id": "calendar_slots", "visible": true, "position": 3, "size": "full"},
            {"id": "today_appointments", "visible": true, "position": 4, "size": "medium"},
            {"id": "workflow_distribution", "visible": true, "position": 5, "size": "medium"}
        ]
    }'::jsonb
WHERE code = 'agent_extranjeria';

-- 2.5 Update agent_policia
UPDATE roles SET
    menu_config = '{
        "version": "1.0",
        "source": "role",
        "menus": [
            {
                "id": "dashboard",
                "titleKey": "agent.nav.dashboard",
                "href": "/dashboard/agent/policia",
                "icon": "LayoutDashboard"
            },
            {
                "id": "certificados",
                "titleKey": "agent.nav.certificates",
                "icon": "Shield",
                "items": [
                    {"id": "pending", "titleKey": "agent.nav.pending", "href": "/dashboard/agent/policia/certificados/pending", "icon": "Clock", "permission": "service_request.view_queue"},
                    {"id": "validation", "titleKey": "agent.nav.validation", "href": "/dashboard/agent/policia/certificados/validation", "icon": "CheckCircle", "permission": "service_request.process"},
                    {"id": "history", "titleKey": "agent.nav.history", "href": "/dashboard/agent/policia/certificados/history", "icon": "History", "permission": "service_request.view"}
                ]
            },
            {
                "id": "appointments",
                "titleKey": "agent.nav.appointments",
                "href": "/dashboard/agent/policia/appointments",
                "icon": "Calendar",
                "permission": "service_request.view_appointments"
            }
        ]
    }'::jsonb,
    dashboard_config = '{
        "version": "1.0",
        "layout": "grid",
        "widgets": [
            {"id": "alerts", "visible": true, "position": 1, "size": "medium"},
            {"id": "urgent_requests", "visible": true, "position": 2, "size": "medium"},
            {"id": "calendar_slots", "visible": true, "position": 3, "size": "full"},
            {"id": "today_appointments", "visible": true, "position": 4, "size": "medium"},
            {"id": "workflow_distribution", "visible": true, "position": 5, "size": "medium"}
        ]
    }'::jsonb
WHERE code = 'agent_policia';

-- =============================================================================
-- PART 3: VERIFICATION
-- =============================================================================

DO $$
DECLARE
    v_role_record RECORD;
BEGIN
    RAISE NOTICE '';
    RAISE NOTICE '=== VERIFICATION REPORT ===';
    RAISE NOTICE '';

    FOR v_role_record IN
        SELECT
            r.code,
            r.name,
            COUNT(rp.permission_id) as permission_count,
            r.menu_config IS NOT NULL as has_menu_config
        FROM roles r
        LEFT JOIN role_permissions rp ON r.id = rp.role_id
        WHERE r.code LIKE 'agent_%' OR r.code = 'supervisor'
        GROUP BY r.code, r.name, r.menu_config
        ORDER BY r.code
    LOOP
        RAISE NOTICE 'Role: % | Permissions: % | Has Menu: %',
            v_role_record.code,
            v_role_record.permission_count,
            v_role_record.has_menu_config;
    END LOOP;

    RAISE NOTICE '';
    RAISE NOTICE '=== Migration 083 completed successfully ===';
END;
$$;

COMMIT;
