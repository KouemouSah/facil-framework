"""
Translation Module Permissions

Defines permissions for translation management:
- Translation CRUD operations
- Entity translation management
- Enum translation management
- Bulk operations

Uses SINGULAR resource names and DOT notation per convention.

SECURITY NOTE: Translation routes currently only check authentication,
not permissions. Routes should be updated to use permission_required().
"""

MODULE_NAME = "translation"

# Format: (name, resource, action, description_es, is_critical)
PERMISSIONS = [
    # =========================================================================
    # TRANSLATION CRUD
    # =========================================================================
    (
        "translation.view",
        "translation",
        "view",
        "Ver traducciones del sistema",
        False
    ),
    (
        "translation.create",
        "translation",
        "create",
        "Crear nuevas traducciones",
        True  # Critical - affects UI across all users
    ),
    (
        "translation.update",
        "translation",
        "update",
        "Modificar traducciones existentes",
        True
    ),
    (
        "translation.delete",
        "translation",
        "delete",
        "Eliminar traducciones",
        True
    ),
    (
        "translation.batch_create",
        "translation",
        "batch_create",
        "Crear traducciones en lote",
        True
    ),

    # =========================================================================
    # ENTITY TRANSLATIONS
    # =========================================================================
    (
        "entity_translation.view",
        "entity_translation",
        "view",
        "Ver traducciones de entidades",
        False
    ),
    (
        "entity_translation.create",
        "entity_translation",
        "create",
        "Crear traducciones de entidades",
        True
    ),
    (
        "entity_translation.update",
        "entity_translation",
        "update",
        "Modificar traducciones de entidades",
        True
    ),
    (
        "entity_translation.delete",
        "entity_translation",
        "delete",
        "Eliminar traducciones de entidades",
        True
    ),

    # =========================================================================
    # ENUM TRANSLATIONS
    # =========================================================================
    (
        "enum_translation.view",
        "enum_translation",
        "view",
        "Ver traducciones de enums",
        False
    ),
    (
        "enum_translation.manage",
        "enum_translation",
        "manage",
        "Gestionar traducciones de enums",
        True
    ),

    # =========================================================================
    # FRONTEND TRANSLATIONS
    # =========================================================================
    (
        "frontend_translation.export",
        "frontend_translation",
        "export",
        "Exportar traducciones para frontend",
        False
    ),
    (
        "frontend_translation.sync",
        "frontend_translation",
        "sync",
        "Sincronizar traducciones con frontend",
        True
    ),
]


# Default role permissions mapping
# NOTE: After Migration 051, agent types are determined by agent_profiles
ROLE_PERMISSIONS = {
    "admin": ["*"],  # All permissions

    # Supervisors (agent_profiles.is_supervisor = true)
    "supervisor": [
        "translation.view",
        "entity_translation.view",
        "enum_translation.view",
        "frontend_translation.export",
    ],

    # Regular agents have no translation management access
    "agent": [],
}
