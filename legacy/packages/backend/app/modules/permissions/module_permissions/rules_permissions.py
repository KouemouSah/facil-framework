"""
Rules Module Permissions

Defines permissions for assignment rules management:
- Rule CRUD operations
- Rule activation/deactivation
- Effectiveness reports

Uses SINGULAR resource names and DOT notation per convention.
NEVER use colon format (rule:create is WRONG)
"""

MODULE_NAME = "rules"

# Format: (name, resource, action, description_es, is_critical)
PERMISSIONS = [
    # =========================================================================
    # RULE CRUD OPERATIONS
    # =========================================================================
    (
        "rules.view",
        "rules",
        "view",
        "Ver reglas de asignacion",
        False
    ),
    (
        "rules.create",
        "rules",
        "create",
        "Crear nuevas reglas de asignacion",
        True  # Critical - affects automatic assignment
    ),
    (
        "rules.edit",
        "rules",
        "edit",
        "Modificar reglas existentes",
        True  # Critical - affects automatic assignment
    ),
    (
        "rules.delete",
        "rules",
        "delete",
        "Eliminar/archivar reglas",
        True  # Critical - affects automatic assignment
    ),

    # =========================================================================
    # RULE ACTIVATION/DEACTIVATION
    # =========================================================================
    (
        "rules.activate",
        "rules",
        "activate",
        "Activar o desactivar reglas",
        True  # Critical - enables/disables automatic behavior
    ),

    # =========================================================================
    # RULE ANALYTICS
    # =========================================================================
    (
        "rules.view_effectiveness",
        "rules",
        "view_effectiveness",
        "Ver informe de efectividad de reglas",
        False
    ),
    (
        "rules.view_history",
        "rules",
        "view_history",
        "Ver historial de aplicacion de reglas",
        False
    ),
]


# Default role permissions mapping
# NOTE: After Migration 051, agent types are determined by agent_profiles
ROLE_PERMISSIONS = {
    "admin": ["*"],  # All permissions

    # Supervisors (agent_profiles.is_supervisor = true)
    "supervisor": [
        "rules.view",
        "rules.create",
        "rules.edit",
        "rules.delete",
        "rules.activate",
        "rules.view_effectiveness",
        "rules.view_history",
    ],

    # Regular agents have no rule management access
    "agent": [],
}
