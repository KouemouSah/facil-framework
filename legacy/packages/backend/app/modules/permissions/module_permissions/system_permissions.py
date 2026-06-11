"""
System Permissions - Core permissions for managing the RBAC system itself

These permissions are REQUIRED for the permission management API to function.
Without them, admin cannot access /api/v1/permissions, /api/v1/roles, or /api/v1/user-permissions.

CRITICAL: This module MUST be registered at startup before any permission check.
"""

from app.modules.permissions.services.permission_registry import PermissionRegistry

MODULE_NAME = "system"

# Format: (name, resource, action, description_es, is_critical)
PERMISSIONS = [
    # =========================================================================
    # PERMISSION MANAGEMENT - /api/v1/permissions
    # =========================================================================
    (
        "permissions.view",
        "permissions",
        "view",
        "Ver catálogo de permisos del sistema",
        False
    ),
    (
        "permissions.create",
        "permissions",
        "create",
        "Crear nuevos permisos en el sistema",
        True  # Critical - affects system security
    ),
    (
        "permissions.update",
        "permissions",
        "update",
        "Modificar permisos existentes",
        True
    ),
    (
        "permissions.delete",
        "permissions",
        "delete",
        "Eliminar permisos del sistema",
        True
    ),

    # =========================================================================
    # ROLE MANAGEMENT - /api/v1/roles
    # =========================================================================
    (
        "roles.view",
        "roles",
        "view",
        "Ver roles del sistema",
        False
    ),
    (
        "roles.create",
        "roles",
        "create",
        "Crear nuevos roles personalizados",
        True
    ),
    (
        "roles.update",
        "roles",
        "update",
        "Modificar roles existentes",
        True
    ),
    (
        "roles.delete",
        "roles",
        "delete",
        "Eliminar roles personalizados",
        True
    ),
    (
        "roles.assign_permissions",
        "roles",
        "assign_permissions",
        "Asignar o revocar permisos a roles",
        True  # Critical - can escalate privileges
    ),

    # =========================================================================
    # USER PERMISSION MANAGEMENT - /api/v1/user-permissions
    # =========================================================================
    (
        "user_permissions.view",
        "user_permissions",
        "view",
        "Ver permisos específicos de usuarios",
        False
    ),
    (
        "user_permissions.grant",
        "user_permissions",
        "grant",
        "Otorgar permisos específicos a usuarios",
        True  # Critical - can escalate privileges
    ),
    (
        "user_permissions.revoke",
        "user_permissions",
        "revoke",
        "Revocar permisos específicos de usuarios",
        True
    ),
    (
        "user_permissions.update",
        "user_permissions",
        "update",
        "Modificar permisos de usuario (expiración, etc.)",
        True
    ),
    (
        "user_permissions.cleanup",
        "user_permissions",
        "cleanup",
        "Limpiar permisos expirados del sistema",
        True  # Critical - can remove access
    ),

    # =========================================================================
    # AUDIT & ANALYTICS
    # =========================================================================
    (
        "permissions.audit",
        "permissions",
        "audit",
        "Ver historial de cambios de permisos",
        False
    ),
    (
        "permissions.analytics",
        "permissions",
        "analytics",
        "Ver analíticas de uso de permisos",
        False
    ),
]

# Default role permissions mapping
# NOTE: After Migration 051, agent types are determined by agent_profiles
ROLE_PERMISSIONS = {
    "admin": ["*"],  # All permissions - admin bypasses checks anyway

    # Supervisors (agent_profiles.is_supervisor = true)
    "supervisor": [
        # View permissions only - cannot modify
        "permissions.view",
        "roles.view",
        "user_permissions.view",
        "permissions.audit",
    ],

    # Regular agents have no access to permission management
    "agent": [],
}


def register_system_permissions():
    """
    Register core system permissions.

    MUST be called at application startup BEFORE any permission checks.
    This enables access to /api/v1/permissions, /api/v1/roles, /api/v1/user-permissions.
    """
    PermissionRegistry.register_module_permissions(MODULE_NAME, PERMISSIONS)
