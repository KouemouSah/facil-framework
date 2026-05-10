"""
Audit Module Permissions

Defines permissions for audit log operations:
- Audit log viewing
- Statistics access
- Export operations

Uses SINGULAR resource names and DOT notation per convention.
"""

MODULE_NAME = "audit"

# Format: (name, resource, action, description_es, is_critical)
PERMISSIONS = [
    # =========================================================================
    # AUDIT LOGS
    # =========================================================================
    (
        "audit.view",
        "audit",
        "view",
        "Ver registros de auditoria",
        False
    ),
    (
        "audit.view_stats",
        "audit",
        "view_stats",
        "Ver estadisticas de auditoria",
        False
    ),
    (
        "audit.export",
        "audit",
        "export",
        "Exportar registros de auditoria",
        False
    ),
    (
        "audit.search",
        "audit",
        "search",
        "Buscar en registros de auditoria",
        False
    ),
]


# Default role permissions mapping
# NOTE: After Migration 051, agent types are determined by agent_profiles
ROLE_PERMISSIONS = {
    "admin": ["*"],  # All permissions

    # Supervisors (agent_profiles.is_supervisor = true)
    "supervisor": [
        "audit.view",
        "audit.view_stats",
        "audit.search",
    ],

    # Regular agents have no audit access
    "agent": [],
}
