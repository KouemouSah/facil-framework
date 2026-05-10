"""
User Management Module Permissions

Defines permissions for user administration:
- User CRUD operations
- Role assignment
- User statistics

Uses SINGULAR resource names and DOT notation per convention.
"""

MODULE_NAME = "user"

# Format: (name, resource, action, description_es, is_critical)
PERMISSIONS = [
    # =========================================================================
    # USER CRUD
    # =========================================================================
    (
        "user.view",
        "user",
        "view",
        "Ver detalles de usuario",
        False
    ),
    (
        "user.view_all",
        "user",
        "view_all",
        "Ver todos los usuarios del sistema",
        False
    ),
    (
        "user.create",
        "user",
        "create",
        "Crear nuevos usuarios",
        True  # Critical - adds access to system
    ),
    (
        "user.update",
        "user",
        "update",
        "Modificar datos de usuario propio",
        True
    ),
    (
        "user.update_any",
        "user",
        "update_any",
        "Modificar datos de cualquier usuario",
        True  # Critical - can modify any user
    ),
    (
        "user.delete",
        "user",
        "delete",
        "Eliminar usuarios",
        True  # Very critical - permanent action
    ),
    (
        "user.search",
        "user",
        "search",
        "Buscar usuarios",
        False
    ),
    (
        "user.view_stats",
        "user",
        "view_stats",
        "Ver estadisticas de usuarios",
        False
    ),
    (
        "user.view_any_activities",
        "user",
        "view_any_activities",
        "Ver actividades de cualquier usuario",
        False
    ),

    # =========================================================================
    # ROLE & STATUS MANAGEMENT
    # =========================================================================
    (
        "user.change_role",
        "user",
        "change_role",
        "Cambiar rol de usuario",
        True  # Critical - affects permissions
    ),
    (
        "user.suspend",
        "user",
        "suspend",
        "Suspender cuenta de usuario",
        True
    ),
    (
        "user.reactivate",
        "user",
        "reactivate",
        "Reactivar cuenta suspendida",
        True
    ),
    (
        "user.impersonate",
        "user",
        "impersonate",
        "Impersonar usuario para diagnostico",
        True  # Very critical - security risk
    ),
]


# Default role permissions mapping
# NOTE: After Migration 051, agent types are determined by agent_profiles
ROLE_PERMISSIONS = {
    "admin": ["*"],  # All permissions

    # Supervisors (agent_profiles.is_supervisor = true)
    "supervisor": [
        "user.view",
        "user.view_all",
        "user.search",
        "user.view_stats",
        "user.view_any_activities",
    ],

    # Regular agents have no user management access
    "agent": [],
}
