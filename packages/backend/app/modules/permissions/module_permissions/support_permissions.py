"""
Support Module Permissions

Defines permissions for support ticket operations:
- Ticket viewing and management
- Message handling
- Category management

Note: Citizens can create and view their own tickets without permissions.
      These permissions are for agent/admin operations.

Uses SINGULAR resource names and DOT notation per convention.
"""

MODULE_NAME = "support"

# Format: (name, resource, action, description_es, is_critical)
PERMISSIONS = [
    # =========================================================================
    # TICKET MANAGEMENT
    # =========================================================================
    (
        "support.view",
        "support",
        "view",
        "Ver tickets de soporte asignados",
        False
    ),
    (
        "support.view_all",
        "support",
        "view_all",
        "Ver todos los tickets del sistema",
        False
    ),
    (
        "support.manage",
        "support",
        "manage",
        "Gestionar tickets (asignar, cerrar, escalar)",
        True  # Critical - affects user experience
    ),
    (
        "support.assign",
        "support",
        "assign",
        "Asignar tickets a agentes",
        False
    ),
    (
        "support.escalate",
        "support",
        "escalate",
        "Escalar tickets a supervisor",
        False
    ),
    (
        "support.close",
        "support",
        "close",
        "Cerrar tickets resueltos",
        False
    ),
    (
        "support.reopen",
        "support",
        "reopen",
        "Reabrir tickets cerrados",
        False
    ),

    # =========================================================================
    # MESSAGE MANAGEMENT
    # =========================================================================
    (
        "support_message.reply",
        "support_message",
        "reply",
        "Responder a tickets como agente",
        False
    ),
    (
        "support_message.delete",
        "support_message",
        "delete",
        "Eliminar mensajes de tickets",
        True  # Critical - permanent deletion
    ),

    # =========================================================================
    # CATEGORY MANAGEMENT
    # =========================================================================
    (
        "support_category.view",
        "support_category",
        "view",
        "Ver categorias de soporte",
        False
    ),
    (
        "support_category.create",
        "support_category",
        "create",
        "Crear categorias de soporte",
        True
    ),
    (
        "support_category.update",
        "support_category",
        "update",
        "Modificar categorias de soporte",
        True
    ),
    (
        "support_category.delete",
        "support_category",
        "delete",
        "Eliminar categorias de soporte",
        True
    ),

    # =========================================================================
    # STATISTICS
    # =========================================================================
    (
        "support_stat.view",
        "support_stat",
        "view",
        "Ver estadisticas de soporte",
        False
    ),
    (
        "support_stat.export",
        "support_stat",
        "export",
        "Exportar estadisticas de soporte",
        False
    ),
]


# Default role permissions mapping
# NOTE: After Migration 051, agent types are determined by agent_profiles
ROLE_PERMISSIONS = {
    "admin": ["*"],  # All permissions

    # Supervisors (agent_profiles.is_supervisor = true)
    "supervisor": [
        "support.view",
        "support.view_all",
        "support.manage",
        "support.assign",
        "support.escalate",
        "support.close",
        "support.reopen",
        "support_message.reply",
        "support_category.view",
        "support_stat.view",
        "support_stat.export",
    ],

    # Generic agent role - all agents can handle support
    "agent": [
        "support.view",
        "support.manage",
        "support.close",
        "support.escalate",
        "support_message.reply",
        "support_category.view",
    ],
}
