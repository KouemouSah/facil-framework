"""
Treasury Module Permissions

Defines all permissions for treasury operations:
- Payment validation
- Audit trail viewing
- Statistics and reporting
- Anomaly detection
- Export operations

Note: Uses SINGULAR resource names and DOT notation per convention.
      For compound resources, use underscore: treasury_audit, treasury_export
"""

MODULE_NAME = "treasury"

# Format: (name, resource, action, description_es, is_critical)
PERMISSIONS = [
    # =========================================================================
    # PAYMENT VALIDATION
    # =========================================================================
    (
        "treasury.validate_payment",
        "treasury",
        "validate_payment",
        "Validar pagos manuales (efectivo, cheque)",
        True  # Critical - confirms money received
    ),
    (
        "treasury.reject_payment",
        "treasury",
        "reject_payment",
        "Rechazar pago",
        True
    ),
    (
        "treasury.view_payment",
        "treasury",
        "view_payment",
        "Ver detalles de pagos",
        False
    ),
    (
        "treasury.view_all",
        "treasury",
        "view_all",
        "Ver todos los pagos de todos los agentes (supervisor)",
        False
    ),
    (
        "treasury.process_payment",
        "treasury",
        "process_payment",
        "Procesar pagos pendientes",
        True
    ),

    # =========================================================================
    # AUDIT OPERATIONS
    # =========================================================================
    (
        "treasury_audit.view",
        "treasury_audit",
        "view",
        "Ver historial de auditoría de tesorería",
        False
    ),
    (
        "treasury_audit.export",
        "treasury_audit",
        "export",
        "Exportar registros de auditoría",
        False
    ),

    # =========================================================================
    # STATISTICS & REPORTING
    # =========================================================================
    (
        "treasury_stat.view",
        "treasury_stat",
        "view",
        "Ver estadísticas de tesorería",
        False
    ),
    (
        "treasury_stat.export",
        "treasury_stat",
        "export",
        "Exportar estadísticas",
        False
    ),

    # =========================================================================
    # ANOMALY DETECTION
    # =========================================================================
    (
        "treasury_anomaly.view",
        "treasury_anomaly",
        "view",
        "Ver anomalías detectadas",
        False
    ),
    (
        "treasury_anomaly.create",
        "treasury_anomaly",
        "create",
        "Crear reporte de anomalía manual",
        False
    ),
    (
        "treasury_anomaly.update",
        "treasury_anomaly",
        "update",
        "Actualizar estado de anomalía",
        False
    ),
    (
        "treasury_anomaly.resolve",
        "treasury_anomaly",
        "resolve",
        "Marcar anomalía como resuelta",
        True  # Critical - closes investigation
    ),

    # =========================================================================
    # EXPORT OPERATIONS
    # =========================================================================
    (
        "treasury_export.view",
        "treasury_export",
        "view",
        "Ver exportaciones disponibles",
        False
    ),
    (
        "treasury_export.create",
        "treasury_export",
        "create",
        "Crear nueva exportación",
        False
    ),
    (
        "treasury_export.download",
        "treasury_export",
        "download",
        "Descargar archivos exportados",
        False
    ),

    # =========================================================================
    # RECONCILIATION
    # =========================================================================
    (
        "treasury.reconcile",
        "treasury",
        "reconcile",
        "Ejecutar reconciliación bancaria",
        True  # Critical - financial operation
    ),
    (
        "treasury.view_reconciliation",
        "treasury",
        "view_reconciliation",
        "Ver estado de reconciliación",
        False
    ),

    # =========================================================================
    # SETTINGS MANAGEMENT (Supervisor only)
    # =========================================================================
    (
        "treasury.manage_settings",
        "treasury",
        "manage_settings",
        "Gestionar configuración de tesorería (bancos, métodos de pago)",
        True  # Critical - affects payment processing
    ),
]


# =============================================================================
# ROLE PERMISSIONS MAPPING
# =============================================================================
# Treasury roles are defined in Migration 062.
# Entity-based access is determined dynamically by agent_profiles.entity_id → entities
#
# Treasury agent roles (from roles table):
#   - agent_tesoro: Unified agent (validation + reconciliation + transactions)
#   - agent_tesoro_validation: Validation only (specific use cases)
#   - agent_tesoro_reconciliation: Reconciliation only (specific use cases)
#   - supervisor_tesoro: Full access
# =============================================================================

ROLE_PERMISSIONS = {
    "admin": ["*"],  # All permissions

    # -------------------------------------------------------------------------
    # AGENT_TESORO (Unified)
    # Menus: Validation, Reconciliation, Transactions
    # Scope: Only their own operations
    # -------------------------------------------------------------------------
    "agent_tesoro": [
        # Payment operations
        "treasury.view_payment",
        "treasury.validate_payment",
        "treasury.reject_payment",
        "treasury.process_payment",
        # Reconciliation operations
        "treasury.reconcile",
        "treasury.view_reconciliation",
        # Statistics (for dashboard)
        "treasury_stat.view",
    ],

    # -------------------------------------------------------------------------
    # AGENT_TESORO_VALIDATION (Specific - validation only)
    # Menus: Validation only
    # -------------------------------------------------------------------------
    "agent_tesoro_validation": [
        "treasury.view_payment",
        "treasury.validate_payment",
        "treasury.reject_payment",
        "treasury.process_payment",
        # Statistics (for dashboard)
        "treasury_stat.view",
    ],

    # -------------------------------------------------------------------------
    # AGENT_TESORO_RECONCILIATION (Specific - reconciliation only)
    # Menus: Reconciliation only
    # -------------------------------------------------------------------------
    "agent_tesoro_reconciliation": [
        "treasury.view_payment",
        "treasury.reconcile",
        "treasury.view_reconciliation",
    ],

    # -------------------------------------------------------------------------
    # SUPERVISOR_TESORO (Full access)
    # Menus: ALL
    # Scope: Team operations + Settings
    # -------------------------------------------------------------------------
    "supervisor_tesoro": [
        # ALL Payment operations
        "treasury.view_payment",
        "treasury.view_all",  # See all payments from all agents
        "treasury.validate_payment",
        "treasury.reject_payment",
        "treasury.process_payment",
        # ALL Reconciliation operations
        "treasury.reconcile",
        "treasury.view_reconciliation",
        # ALL Audit operations
        "treasury_audit.view",
        "treasury_audit.export",
        # ALL Statistics operations
        "treasury_stat.view",
        "treasury_stat.export",
        # ALL Anomaly operations
        "treasury_anomaly.view",
        "treasury_anomaly.create",
        "treasury_anomaly.update",
        "treasury_anomaly.resolve",
        # ALL Export operations
        "treasury_export.view",
        "treasury_export.create",
        "treasury_export.download",
        # Settings management (SUPERVISOR ONLY)
        "treasury.manage_settings",
    ],
}
