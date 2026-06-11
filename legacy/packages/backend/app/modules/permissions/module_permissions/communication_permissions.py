"""
Communication Module Permissions

Defines permissions for communication management:
- Email/SMS/Push template management
- Provider settings
- Webhook configurations

Uses SINGULAR resource names and DOT notation per convention.
NEVER use colon format (manage:communications is WRONG)
"""

MODULE_NAME = "communication"

# Format: (name, resource, action, description_es, is_critical)
PERMISSIONS = [
    # =========================================================================
    # COMMUNICATION SETTINGS
    # =========================================================================
    (
        "communication.view",
        "communication",
        "view",
        "Ver configuracion de comunicaciones",
        False
    ),
    (
        "communication.manage",
        "communication",
        "manage",
        "Gestionar configuracion de comunicaciones",
        True  # Critical - affects notifications
    ),

    # =========================================================================
    # EMAIL TEMPLATES
    # =========================================================================
    (
        "email_template.view",
        "email_template",
        "view",
        "Ver plantillas de email",
        False
    ),
    (
        "email_template.create",
        "email_template",
        "create",
        "Crear plantillas de email",
        True
    ),
    (
        "email_template.update",
        "email_template",
        "update",
        "Modificar plantillas de email",
        True
    ),
    (
        "email_template.delete",
        "email_template",
        "delete",
        "Eliminar plantillas de email",
        True
    ),

    # =========================================================================
    # SMS TEMPLATES
    # =========================================================================
    (
        "sms_template.view",
        "sms_template",
        "view",
        "Ver plantillas de SMS",
        False
    ),
    (
        "sms_template.create",
        "sms_template",
        "create",
        "Crear plantillas de SMS",
        True
    ),
    (
        "sms_template.update",
        "sms_template",
        "update",
        "Modificar plantillas de SMS",
        True
    ),
    (
        "sms_template.delete",
        "sms_template",
        "delete",
        "Eliminar plantillas de SMS",
        True
    ),

    # =========================================================================
    # NOTIFICATION TEMPLATES
    # =========================================================================
    (
        "notification_template.view",
        "notification_template",
        "view",
        "Ver plantillas de notificaciones",
        False
    ),
    (
        "notification_template.create",
        "notification_template",
        "create",
        "Crear plantillas de notificaciones",
        True
    ),
    (
        "notification_template.update",
        "notification_template",
        "update",
        "Modificar plantillas de notificaciones",
        True
    ),
    (
        "notification_template.delete",
        "notification_template",
        "delete",
        "Eliminar plantillas de notificaciones",
        True
    ),

    # =========================================================================
    # PUSH TEMPLATES
    # =========================================================================
    (
        "push_template.view",
        "push_template",
        "view",
        "Ver plantillas de notificaciones push",
        False
    ),
    (
        "push_template.create",
        "push_template",
        "create",
        "Crear plantillas de push",
        True
    ),
    (
        "push_template.update",
        "push_template",
        "update",
        "Modificar plantillas de push",
        True
    ),
    (
        "push_template.delete",
        "push_template",
        "delete",
        "Eliminar plantillas de push",
        True
    ),

    # =========================================================================
    # PROVIDER SETTINGS
    # =========================================================================
    (
        "provider_setting.view",
        "provider_setting",
        "view",
        "Ver configuracion de proveedores",
        False
    ),
    (
        "provider_setting.manage",
        "provider_setting",
        "manage",
        "Gestionar configuracion de proveedores",
        True  # Critical - affects external integrations
    ),

    # =========================================================================
    # EMAIL/SMS SENDING (CRITICAL - abuse potential)
    # =========================================================================
    (
        "communication.send_email",
        "communication",
        "send_email",
        "Enviar emails desde el sistema",
        True  # Critical - spam/abuse potential
    ),
    (
        "communication.send_sms",
        "communication",
        "send_sms",
        "Enviar SMS desde el sistema",
        True  # Critical - cost + abuse potential
    ),
    (
        "communication.send_notification",
        "communication",
        "send_notification",
        "Enviar notificaciones push",
        False
    ),
]


# Default role permissions mapping
# NOTE: After Migration 051, agent types are determined by agent_profiles
ROLE_PERMISSIONS = {
    "admin": ["*"],  # All permissions

    # Supervisors (agent_profiles.is_supervisor = true)
    "supervisor": [
        "communication.view",
        "email_template.view",
        "sms_template.view",
        "notification_template.view",
        "push_template.view",
        "provider_setting.view",
    ],

    # Regular agents have no communication management access
    "agent": [],
}
