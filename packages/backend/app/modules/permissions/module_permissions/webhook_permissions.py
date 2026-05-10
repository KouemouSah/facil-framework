"""
Webhook Module Permissions

Defines all permissions for webhook management operations:
- Webhook configuration viewing
- Webhook creation and updates
- Webhook deletion
- Webhook log viewing

Note: Uses SINGULAR resource names and DOT notation per convention.
"""

MODULE_NAME = "webhook"

# Format: (name, resource, action, description_es, is_critical)
PERMISSIONS = [
    # =========================================================================
    # WEBHOOK CONFIGURATION
    # =========================================================================
    (
        "webhook.view",
        "webhook",
        "view",
        "Ver configuración de webhooks",
        False
    ),
    (
        "webhook.create",
        "webhook",
        "create",
        "Crear nuevos webhooks",
        True  # Critical - external integrations
    ),
    (
        "webhook.update",
        "webhook",
        "update",
        "Modificar webhooks existentes",
        True
    ),
    (
        "webhook.delete",
        "webhook",
        "delete",
        "Eliminar webhooks",
        True
    ),
    (
        "webhook.test",
        "webhook",
        "test",
        "Probar webhook (enviar ping)",
        False
    ),

    # =========================================================================
    # WEBHOOK LOGS
    # =========================================================================
    (
        "webhook_log.view",
        "webhook_log",
        "view",
        "Ver historial de webhooks",
        False
    ),
    (
        "webhook_log.export",
        "webhook_log",
        "export",
        "Exportar logs de webhooks",
        False
    ),
]


# Default role permissions mapping
# NOTE: After Migration 051, agent types are determined by agent_profiles
ROLE_PERMISSIONS = {
    "admin": ["*"],  # All permissions

    # Supervisors (agent_profiles.is_supervisor = true)
    "supervisor": [
        "webhook.view",
        "webhook_log.view",
    ],

    # Regular agents have no webhook access
    "agent": [],
}
