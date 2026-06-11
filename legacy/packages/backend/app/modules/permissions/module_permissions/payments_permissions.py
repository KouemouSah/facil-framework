"""
Payments Module Permissions

Defines permissions for payment operations:
- Payment CRUD (admin-level)
- Payment plan management
- Receipt operations

Note: Most payment routes use ownership checks for citizens.
      These permissions are for admin/agent operations.

Uses SINGULAR resource names and DOT notation per convention.
"""

MODULE_NAME = "payment"

# Format: (name, resource, action, description_es, is_critical)
PERMISSIONS = [
    # =========================================================================
    # PAYMENT CRUD (Admin)
    # =========================================================================
    (
        "payment.view",
        "payment",
        "view",
        "Ver detalles de pago (admin)",
        False
    ),
    (
        "payment.view_all",
        "payment",
        "view_all",
        "Ver todos los pagos del sistema",
        False
    ),
    (
        "payment.update",
        "payment",
        "update",
        "Modificar estado de pagos",
        True  # Critical - affects payment status
    ),
    (
        "payment.create",
        "payment",
        "create",
        "Crear pagos manualmente (admin)",
        True
    ),
    (
        "payment.cancel",
        "payment",
        "cancel",
        "Cancelar pagos pendientes",
        True
    ),
    (
        "payment.refund",
        "payment",
        "refund",
        "Iniciar reembolso de pago",
        True  # Very critical - money out
    ),

    # =========================================================================
    # PAYMENT PLAN MANAGEMENT
    # =========================================================================
    (
        "payment_plan.view",
        "payment_plan",
        "view",
        "Ver planes de pago (admin)",
        False
    ),
    (
        "payment_plan.create",
        "payment_plan",
        "create",
        "Crear plan de pago para usuario",
        False
    ),
    (
        "payment_plan.update",
        "payment_plan",
        "update",
        "Modificar plan de pago",
        True
    ),

    # =========================================================================
    # RECEIPT OPERATIONS
    # =========================================================================
    (
        "receipt.view",
        "receipt",
        "view",
        "Ver recibos emitidos",
        False
    ),
    (
        "receipt.regenerate",
        "receipt",
        "regenerate",
        "Regenerar recibo de pago",
        False
    ),
    (
        "receipt.void",
        "receipt",
        "void",
        "Anular recibo emitido",
        True  # Critical - voids financial document
    ),

    # =========================================================================
    # RECONCILIATION
    # =========================================================================
    (
        "payment.reconcile",
        "payment",
        "reconcile",
        "Ejecutar reconciliacion bancaria",
        True  # Critical - financial operation
    ),
    (
        "payment.view_reconciliation",
        "payment",
        "view_reconciliation",
        "Ver estado de reconciliacion",
        False
    ),
]


# Default role permissions mapping
# NOTE: After Migration 051, agent types are determined by agent_profiles
# Treasury-specific permissions are granted to agents with agent_category='treasury'
ROLE_PERMISSIONS = {
    "admin": ["*"],  # All permissions

    # Supervisors (agent_profiles.is_supervisor = true)
    "supervisor": [
        "payment.view",
        "payment.view_all",
        "payment_plan.view",
        "receipt.view",
        "payment.view_reconciliation",
    ],

    # Generic agent role - base payment permissions
    # Treasury agents get additional permissions via agent_category check at runtime
    "agent": [
        "payment.view",
        "receipt.view",
    ],
}
