"""
Fiscal Service Module Permissions

Defines permissions for fiscal service management:
- Service CRUD operations
- Hierarchy management (ministries, sectors, categories)
- Bulk operations

Uses SINGULAR resource names and DOT notation per convention.
"""

MODULE_NAME = "fiscal_service"

# Format: (name, resource, action, description_es, is_critical)
PERMISSIONS = [
    # =========================================================================
    # SERVICE CRUD
    # =========================================================================
    (
        "fiscal_service.view",
        "fiscal_service",
        "view",
        "Ver detalles de servicio fiscal",
        False
    ),
    (
        "fiscal_service.create",
        "fiscal_service",
        "create",
        "Crear nuevos servicios fiscales",
        True
    ),
    (
        "fiscal_service.update",
        "fiscal_service",
        "update",
        "Modificar servicios fiscales",
        True
    ),
    (
        "fiscal_service.delete",
        "fiscal_service",
        "delete",
        "Eliminar servicios fiscales",
        True
    ),
    (
        "fiscal_service.view_stats",
        "fiscal_service",
        "view_stats",
        "Ver estadisticas de servicios",
        False
    ),

    # =========================================================================
    # HIERARCHY MANAGEMENT
    # =========================================================================
    (
        "fiscal_service.manage_hierarchy",
        "fiscal_service",
        "manage_hierarchy",
        "Gestionar jerarquia (ministerios, sectores, categorias)",
        True  # Critical - affects service structure
    ),
    (
        "fiscal_service.manage_ministry",
        "fiscal_service",
        "manage_ministry",
        "Gestionar ministerios",
        True
    ),
    (
        "fiscal_service.manage_sector",
        "fiscal_service",
        "manage_sector",
        "Gestionar sectores",
        True
    ),
    (
        "fiscal_service.manage_category",
        "fiscal_service",
        "manage_category",
        "Gestionar categorias",
        True
    ),

    # =========================================================================
    # BUNDLES & LICENSES (OMS)
    # =========================================================================
    (
        "fiscal_service.view_bundles",
        "fiscal_service",
        "view_bundles",
        "Ver paquetes de servicios, licencias y obligaciones",
        False
    ),
    (
        "fiscal_service.manage_bundles",
        "fiscal_service",
        "manage_bundles",
        "Gestionar paquetes, licencias, obligaciones y reglas de configuración",
        True
    ),
    (
        "fiscal_service.process_obligations",
        "fiscal_service",
        "process_obligations",
        "Validar pagos, actualizar estado de obligaciones (agentes OMS)",
        False
    ),

    # =========================================================================
    # BULK OPERATIONS
    # =========================================================================
    (
        "fiscal_service.bulk_import",
        "fiscal_service",
        "bulk_import",
        "Importar servicios en masa",
        True  # Critical - mass data change
    ),
    (
        "fiscal_service.bulk_update",
        "fiscal_service",
        "bulk_update",
        "Actualizar servicios en masa",
        True
    ),
    (
        "fiscal_service.bulk_export",
        "fiscal_service",
        "bulk_export",
        "Exportar servicios en masa",
        False
    ),
]


# Default role permissions mapping
# NOTE: After Migration 051, agent types are determined by agent_profiles
ROLE_PERMISSIONS = {
    "admin": ["*"],  # All permissions

    # Supervisors (agent_profiles.is_supervisor = true)
    "supervisor": [
        "fiscal_service.view",
        "fiscal_service.view_stats",
        "fiscal_service.bulk_export",
    ],

    # Generic agent role - all agent types
    # NOTE: view_bundles/manage_bundles NOT here — only OMS-specific roles
    # (agent_tesoro, future agent_ayuntamiento, etc.) get those via migration 219+
    "agent": [
        "fiscal_service.view",
    ],
}
