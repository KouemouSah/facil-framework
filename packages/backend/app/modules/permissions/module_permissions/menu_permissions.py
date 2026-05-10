"""
Menu Configuration Module Permissions

Defines all permissions for workflow menu mapping management
and full admin access to menu/dashboard configuration.

Note: Uses SINGULAR resource names and DOT notation per convention.
      NEVER use colon format (menu:manage is WRONG, use menu.manage)

Note: Role menu config (GET/PUT /roles/{id}/menu-config) uses roles.view
      and roles.update permissions, not dedicated menu permissions.

Created: 2026-01-19
Updated: 2026-02-17 - Removed 8 orphaned permissions (templates dropped,
         role/dashboard config uses roles.* permissions)
"""

MODULE_NAME = "menu"

# Format: (name, resource, action, description_es, is_critical)
PERMISSIONS = [
    # =========================================================================
    # WORKFLOW MENU MAPPING MANAGEMENT
    # =========================================================================
    (
        "menu.view_mappings",
        "menu",
        "view_mappings",
        "Ver mapeos de workflow a menú",
        False
    ),
    (
        "menu.create_mapping",
        "menu",
        "create_mapping",
        "Crear mapeos de workflow a menú",
        True  # Critical - affects menu generation
    ),
    (
        "menu.update_mapping",
        "menu",
        "update_mapping",
        "Actualizar mapeos de workflow a menú",
        True  # Critical - affects menu generation
    ),
    (
        "menu.delete_mapping",
        "menu",
        "delete_mapping",
        "Eliminar mapeos de workflow a menú",
        True  # Critical - affects menu generation
    ),

    # =========================================================================
    # ADMIN FULL ACCESS
    # =========================================================================
    (
        "menu.manage",
        "menu",
        "manage",
        "Gestión completa de menús y dashboards",
        True  # Critical - full admin access
    ),
]


def get_permissions():
    """Return all menu configuration permissions."""
    return PERMISSIONS


def get_permission_names():
    """Return list of permission names only."""
    return [p[0] for p in PERMISSIONS]


def get_critical_permissions():
    """Return only critical permissions (is_critical=True)."""
    return [p for p in PERMISSIONS if p[4] is True]
