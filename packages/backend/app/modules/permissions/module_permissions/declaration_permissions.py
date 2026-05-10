"""
Declaration Module Permissions

Defines permissions for tax declaration management:
- Declaration CRUD operations
- Batch operations (accountant)
- Agent processing
- Corrections and amendments

Uses SINGULAR resource names and DOT notation per convention.

SECURITY NOTE: Declaration routes currently only check authentication.
Routes should be updated to use permission_required() for RBAC.
"""

MODULE_NAME = "declaration"

# Format: (name, resource, action, description_es, is_critical)
PERMISSIONS = [
    # =========================================================================
    # DECLARATION CRUD (Citizen)
    # =========================================================================
    (
        "declaration.view",
        "declaration",
        "view",
        "Ver declaraciones propias",
        False
    ),
    (
        "declaration.list",
        "declaration",
        "list",
        "Listar declaraciones",
        False
    ),
    (
        "declaration.search",
        "declaration",
        "search",
        "Buscar declaraciones (búsqueda avanzada)",
        False
    ),
    (
        "declaration.create",
        "declaration",
        "create",
        "Crear nuevas declaraciones",
        False  # Citizens can create their own
    ),
    (
        "declaration.update",
        "declaration",
        "update",
        "Modificar declaraciones en borrador",
        False
    ),
    (
        "declaration.submit",
        "declaration",
        "submit",
        "Enviar declaraciones para procesamiento",
        False
    ),
    (
        "declaration.withdraw",
        "declaration",
        "withdraw",
        "Retirar declaración enviada (antes de revisión)",
        False
    ),
    (
        "declaration.delete",
        "declaration",
        "delete",
        "Eliminar declaraciones en borrador",
        False
    ),

    # =========================================================================
    # DOCUMENT MANAGEMENT
    # =========================================================================
    (
        "declaration.upload_documents",
        "declaration",
        "upload_documents",
        "Subir documentos adjuntos",
        False
    ),
    (
        "declaration.view_documents",
        "declaration",
        "view_documents",
        "Ver documentos adjuntos",
        False
    ),
    (
        "declaration.delete_documents",
        "declaration",
        "delete_documents",
        "Eliminar documentos adjuntos",
        False
    ),

    # =========================================================================
    # ADMIN/AGENT OPERATIONS
    # =========================================================================
    (
        "declaration.view_all",
        "declaration",
        "view_all",
        "Ver todas las declaraciones del sistema",
        False
    ),
    (
        "declaration.assign",
        "declaration",
        "assign",
        "Asignar declaración a operador",
        False
    ),
    (
        "declaration.review",
        "declaration",
        "review",
        "Revisar declaración (cambiar a processing)",
        False
    ),
    (
        "declaration.process",
        "declaration",
        "process",
        "Procesar declaraciones (aceptar/rechazar)",
        True  # Critical - affects tax compliance
    ),
    (
        "declaration.approve",
        "declaration",
        "approve",
        "Aprobar declaraciones",
        True
    ),
    (
        "declaration.reject",
        "declaration",
        "reject",
        "Rechazar declaraciones",
        True
    ),
    (
        "declaration.request_correction",
        "declaration",
        "request_correction",
        "Solicitar correcciones al contribuyente",
        False
    ),
    (
        "declaration.bulk_operations",
        "declaration",
        "bulk_operations",
        "Operaciones en masa",
        True  # Critical
    ),

    # =========================================================================
    # CORRECTIONS & AMENDMENTS
    # =========================================================================
    (
        "declaration.amend",
        "declaration",
        "amend",
        "Crear declaraciones rectificativas",
        False
    ),
    (
        "declaration.adjust_amount",
        "declaration",
        "adjust_amount",
        "Ajustar montos de declaracion",
        True  # Critical - affects tax amounts
    ),

    # =========================================================================
    # BATCH OPERATIONS (Accountant)
    # =========================================================================
    (
        "declaration.batch_create",
        "declaration",
        "batch_create",
        "Crear declaraciones en lote (contador)",
        True
    ),
    (
        "declaration.batch_submit",
        "declaration",
        "batch_submit",
        "Enviar lote de declaraciones",
        True
    ),
    (
        "declaration.import_excel",
        "declaration",
        "import_excel",
        "Importar declaraciones desde Excel",
        True
    ),

    # =========================================================================
    # PAYMENT RELATED
    # =========================================================================
    (
        "declaration.mark_paid",
        "declaration",
        "mark_paid",
        "Marcar declaración como pagada",
        True  # Critical - affects payment status
    ),
    (
        "declaration.update_payment_info",
        "declaration",
        "update_payment_info",
        "Actualizar información de pago",
        False
    ),

    # =========================================================================
    # WORKFLOW TRACKING
    # =========================================================================
    (
        "declaration.view_workflow",
        "declaration",
        "view_workflow",
        "Ver estado del flujo de trabajo",
        False
    ),
    (
        "declaration.view_activity_log",
        "declaration",
        "view_activity_log",
        "Ver registro de actividades",
        False
    ),

    # =========================================================================
    # STATISTICS & REPORTS
    # =========================================================================
    (
        "declaration.view_stats",
        "declaration",
        "view_stats",
        "Ver estadisticas de declaraciones",
        False
    ),
    (
        "declaration.export",
        "declaration",
        "export",
        "Exportar declaraciones",
        False
    ),
]


# Default role permissions mapping
# NOTE: After Migration 051, agent types are determined by agent_profiles
ROLE_PERMISSIONS = {
    "admin": ["*"],  # All permissions

    # Supervisors (agent_profiles.is_supervisor = true)
    "supervisor": [
        "declaration.view_all",
        "declaration.process",
        "declaration.approve",
        "declaration.reject",
        "declaration.request_correction",
        "declaration.adjust_amount",
        "declaration.view_stats",
        "declaration.export",
    ],

    # Generic agent role - all agent types
    # DGI agents have full processing, others have limited access
    # Runtime check via agent_category for specific permissions
    "agent": [
        "declaration.view_all",
        "declaration.process",
        "declaration.approve",
        "declaration.reject",
        "declaration.request_correction",
        "declaration.view_stats",
    ],

    # Accountant role for batch operations
    "accountant": [
        "declaration.view",
        "declaration.create",
        "declaration.update",
        "declaration.submit",
        "declaration.delete",
        "declaration.batch_create",
        "declaration.batch_submit",
        "declaration.import_excel",
        "declaration.amend",
    ],

    # Citizen has implicit permission through ownership checks
    # Note: funcionario uses same permissions as citizen (ownership-based)
    "citizen": [
        "declaration.view",
        "declaration.create",
        "declaration.update",
        "declaration.submit",
        "declaration.delete",
        "declaration.amend",
    ],
}
