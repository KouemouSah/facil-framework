"""
Inspection Module Permissions

Defines all permissions for field inspections, seal management,
reconciliation, and mise en demeure operations.

Note: Uses SINGULAR resource name (inspection) per convention.
"""

MODULE_NAME = "inspection"

# Format: (name, resource, action, description_es, is_critical)
PERMISSIONS = [
    # =========================================================================
    # FIELD INSPECTION CRUD
    # =========================================================================
    (
        "inspection.create",
        "inspection",
        "create",
        "Crear inspección de campo",
        False
    ),
    (
        "inspection.view_own",
        "inspection",
        "view_own",
        "Ver inspecciones propias",
        False
    ),
    (
        "inspection.view_entity",
        "inspection",
        "view_entity",
        "Ver inspecciones de la entidad (supervisor dashboard)",
        False
    ),
    # =========================================================================
    # PAYMENT COLLECTION (Field agents)
    # =========================================================================
    (
        "inspection.collect_payment",
        "inspection",
        "collect_payment",
        "Recaudar pago en campo",
        True
    ),
    # =========================================================================
    # RECONCILIATION (Supervisor validates field payments)
    # =========================================================================
    (
        "inspection.reconcile_validate",
        "inspection",
        "reconcile_validate",
        "Validar reconciliación de pagos de campo",
        True
    ),
    # =========================================================================
    # SEAL MANAGEMENT
    # =========================================================================
    (
        "inspection.seal_propose",
        "inspection",
        "seal_propose",
        "Proponer sellado de establecimiento",
        True
    ),
    (
        "inspection.seal_approve",
        "inspection",
        "seal_approve",
        "Aprobar o rechazar sellado propuesto",
        True
    ),
    # =========================================================================
    # MISE EN DEMEURE (Formal notice)
    # =========================================================================
    (
        "inspection.mise_en_demeure",
        "inspection",
        "mise_en_demeure",
        "Emitir mise en demeure (requerimiento formal)",
        True
    ),
    # =========================================================================
    # REPORTS & EXPORT
    # =========================================================================
    (
        "inspection.view_reports",
        "inspection",
        "view_reports",
        "Ver reportes de inspecciones",
        False
    ),
    (
        "inspection.export",
        "inspection",
        "export",
        "Exportar datos de inspecciones (CSV/PDF)",
        False
    ),
    # =========================================================================
    # PERFORMANCE (view agent stats)
    # =========================================================================
    (
        "inspection.view_performance",
        "inspection",
        "view_performance",
        "Ver rendimiento de agentes de inspección",
        False
    ),
    # =========================================================================
    # FIELD MISSIONS (supervisor planning)
    # =========================================================================
    (
        "inspection.manage_missions",
        "inspection",
        "manage_missions",
        "Crear y gestionar misiones de campo (supervisor)",
        True
    ),
    # =========================================================================
    # ANALYTICS (zone/agent/trend analytics)
    # =========================================================================
    (
        "inspection.view_analytics",
        "inspection",
        "view_analytics",
        "Ver analytics e indicadores de inspecciones",
        False
    ),
    # =========================================================================
    # FILTER PRESETS (save/load filter configurations)
    # =========================================================================
    (
        "inspection.manage_filter_presets",
        "inspection",
        "manage_filter_presets",
        "Guardar y gestionar presets de filtros",
        False
    ),
]


# Default role permissions mapping
ROLE_PERMISSIONS = {
    "admin": ["*"],  # All permissions

    # Supervisors: full oversight, mission planning, analytics, approvals
    "supervisor": [
        "inspection.view_entity",
        "inspection.view_own",
        "inspection.reconcile_validate",
        "inspection.seal_approve",
        "inspection.view_performance",
        "inspection.view_reports",
        "inspection.export",
        "inspection.manage_missions",
        "inspection.view_analytics",
        "inspection.manage_filter_presets",
    ],

    # Field agents: create inspections, collect payments, propose seals
    "agent": [
        "inspection.create",
        "inspection.view_own",
        "inspection.collect_payment",
        "inspection.seal_propose",
        "inspection.mise_en_demeure",
        "inspection.manage_filter_presets",
    ],
}
