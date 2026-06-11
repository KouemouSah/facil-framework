"""
City Module Permissions

Defines permissions for city and entity management:
- City CRUD operations
- Entity (government bodies) CRUD operations

Uses SINGULAR resource names and DOT notation per convention.

NOTE: Cities routes currently use require_admin (role-based).
      Should be updated to use permission_required() for granular RBAC.
"""

MODULE_NAME = "city"

# Format: (name, resource, action, description_es, is_critical)
PERMISSIONS = [
    # =========================================================================
    # CITY MANAGEMENT
    # =========================================================================
    (
        "city.view",
        "city",
        "view",
        "Ver ciudades del sistema",
        False
    ),
    (
        "city.create",
        "city",
        "create",
        "Crear nuevas ciudades",
        True  # Critical - affects service availability
    ),
    (
        "city.update",
        "city",
        "update",
        "Modificar ciudades existentes",
        True
    ),
    (
        "city.delete",
        "city",
        "delete",
        "Eliminar ciudades",
        True
    ),

    # =========================================================================
    # ENTITY MANAGEMENT (Government bodies like DGI, CNEDOGE, etc.)
    # =========================================================================
    (
        "entity.view",
        "entity",
        "view",
        "Ver entidades gubernamentales",
        False
    ),
    (
        "entity.create",
        "entity",
        "create",
        "Crear nuevas entidades",
        True
    ),
    (
        "entity.update",
        "entity",
        "update",
        "Modificar entidades existentes",
        True
    ),
    (
        "entity.delete",
        "entity",
        "delete",
        "Eliminar entidades",
        True
    ),
]


# Default role permissions mapping
# NOTE: After Migration 051, agent types are determined by agent_profiles
ROLE_PERMISSIONS = {
    "admin": ["*"],  # All permissions

    # Supervisors (agent_profiles.is_supervisor = true)
    "supervisor": [
        "city.view",
        "entity.view",
    ],

    # Regular agents have no city/entity management access
    "agent": [],
}
