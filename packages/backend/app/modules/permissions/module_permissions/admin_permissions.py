"""
Admin Module Permissions

Defines all permissions for admin management operations:
- Workflow configuration
- Tariff management
- Appointment slot configuration
- System settings

Note: Uses SINGULAR resource names and DOT notation per convention.
      NEVER use colon format (admin:manage is WRONG, use admin.manage)
"""

MODULE_NAME = "admin"

# Format: (name, resource, action, description_es, is_critical)
PERMISSIONS = [
    # =========================================================================
    # WORKFLOW MANAGEMENT
    # =========================================================================
    (
        "admin.manage_workflow",
        "admin",
        "manage_workflow",
        "Gestionar configuración de workflows",
        True  # Critical - affects all service requests
    ),
    (
        "admin.view_workflow",
        "admin",
        "view_workflow",
        "Ver configuración de workflows",
        False
    ),

    # =========================================================================
    # TARIFF MANAGEMENT
    # =========================================================================
    (
        "admin.manage_tariff",
        "admin",
        "manage_tariff",
        "Gestionar tarifas y precios",
        True  # Critical - affects payments
    ),
    (
        "admin.view_tariff",
        "admin",
        "view_tariff",
        "Ver tarifas configuradas",
        False
    ),

    # =========================================================================
    # APPOINTMENT CONFIGURATION
    # =========================================================================
    (
        "admin.manage_appointment",
        "admin",
        "manage_appointment",
        "Gestionar configuración de citas (slots, horarios)",
        True
    ),
    (
        "admin.view_appointment",
        "admin",
        "view_appointment",
        "Ver configuración de citas",
        False
    ),

    # =========================================================================
    # SYSTEM SETTINGS
    # =========================================================================
    (
        "admin.manage_system",
        "admin",
        "manage_system",
        "Gestionar configuración del sistema",
        True  # Critical - system-wide impact
    ),
    (
        "admin.view_system",
        "admin",
        "view_system",
        "Ver configuración del sistema",
        False
    ),
    (
        "admin.run_migrations",
        "admin",
        "run_migrations",
        "Ejecutar migraciones de datos",
        True  # Very critical - database changes
    ),
    (
        "admin.view_diagnostics",
        "admin",
        "view_diagnostics",
        "Ver diagnósticos del sistema",
        False
    ),

    # =========================================================================
    # ENTITY MANAGEMENT
    # =========================================================================
    (
        "admin.manage_entity",
        "admin",
        "manage_entity",
        "Gestionar entidades (ministerios, direcciones)",
        True
    ),
    (
        "admin.view_entity",
        "admin",
        "view_entity",
        "Ver entidades configuradas",
        False
    ),

    # =========================================================================
    # USER MANAGEMENT
    # =========================================================================
    (
        "admin.manage_user",
        "admin",
        "manage_user",
        "Gestionar usuarios (crear, suspender, reactivar)",
        True
    ),
    (
        "admin.view_user",
        "admin",
        "view_user",
        "Ver información de usuarios",
        False
    ),
    (
        "admin.impersonate_user",
        "admin",
        "impersonate_user",
        "Impersonar usuario para diagnóstico",
        True  # Very critical - security risk
    ),
    # =========================================================================
    # MONITORING & DASHBOARD
    # =========================================================================
    (
        "admin.monitoring",
        "admin",
        "monitoring",
        "Acceder al panel de monitoreo del sistema",
        False
    ),
    (
        "admin.view_dashboard",
        "admin",
        "view_dashboard",
        "Ver dashboard administrativo global",
        False
    ),
]


# Default role permissions mapping
# NOTE: After Migration 051, agent types are determined by agent_profiles
ROLE_PERMISSIONS = {
    "admin": ["*"],  # All permissions

    # Supervisors (agent_profiles.is_supervisor = true)
    "supervisor": [
        # View-only access
        "admin.view_workflow",
        "admin.view_tariff",
        "admin.view_appointment",
        "admin.view_system",
        "admin.view_entity",
        "admin.view_user",
    ],

    # Regular agents have no admin access
    "agent": [],
}
