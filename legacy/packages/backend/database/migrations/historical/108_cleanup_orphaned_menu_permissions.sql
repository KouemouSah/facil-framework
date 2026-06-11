-- ============================================================================
-- Migration 108: Cleanup orphaned menu permissions
-- ============================================================================
-- Removes 8 permissions that are no longer used by any endpoint:
--
-- 4 template permissions (menu_templates table was dropped in migration 086):
--   - menu.view_templates, menu.create_template,
--     menu.update_template, menu.delete_template
--
-- 4 role/dashboard config permissions (endpoints use roles.view/roles.update):
--   - menu.view_role_config, menu.update_role_config,
--     menu.view_dashboard_config, menu.update_dashboard_config
--
-- Date: 2026-02-17
-- ============================================================================

-- Step 1: Remove any role_permissions referencing these permissions
DELETE FROM role_permissions
WHERE permission_id IN (
    SELECT id FROM permissions
    WHERE name IN (
        'menu.view_templates',
        'menu.create_template',
        'menu.update_template',
        'menu.delete_template',
        'menu.view_role_config',
        'menu.update_role_config',
        'menu.view_dashboard_config',
        'menu.update_dashboard_config'
    )
);

-- Step 2: Remove the permissions themselves
DELETE FROM permissions
WHERE name IN (
    'menu.view_templates',
    'menu.create_template',
    'menu.update_template',
    'menu.delete_template',
    'menu.view_role_config',
    'menu.update_role_config',
    'menu.view_dashboard_config',
    'menu.update_dashboard_config'
);
