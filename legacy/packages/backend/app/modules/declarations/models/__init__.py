"""
Declarations Models - Pydantic schemas for tax declarations

Export all declaration-related models for easy imports.

2 types de déclarations:
1. tax_declarations - Déclarations fiscales (28 types: IVA, IRPF, etc.)
2. fiscal_service_data - Déclarations services fiscaux (Nota de Ingreso, etc.)
"""

from app.modules.declarations.models.declaration import (
    DeclarationBase,
    DeclarationCreate,
    DeclarationUpdate,
    DeclarationResponse,
    DeclarationListResponse,
    DeclarationStatus,
    DeclarationType,
    WorkflowStage,
    DeclarationWorkflowStatus,
    # Search and filtering
    DeclarationSearchFilter,
    # Statistics
    DeclarationStats,
    # Bulk operations
    BulkDeclarationOperation,
    # Activity tracking
    DeclarationActivity,
    # Notifications
    DeclarationNotification,
)

from app.modules.declarations.models.fiscal_service_declaration import (
    FiscalServiceDataBase,
    FiscalServiceDataCreate,
    FiscalServiceDataUpdate,
    FiscalServiceDataResponse,
    FiscalServiceDataListResponse,
    FiscalServiceDataStatus,
    TypeCompte,
)

from app.modules.declarations.models.declaration_correction import (
    DeclarationCorrectionBase,
    DeclarationCorrectionCreate,
    DeclarationCorrectionUpdate,
    DeclarationCorrectionResponse,
    DeclarationCorrectionListResponse,
    CorrectionType,
    CorrectionStatus,
)

__all__ = [
    # Tax Declarations (28 types)
    "DeclarationBase",
    "DeclarationCreate",
    "DeclarationUpdate",
    "DeclarationResponse",
    "DeclarationListResponse",
    "DeclarationStatus",
    "DeclarationType",
    "WorkflowStage",
    "DeclarationWorkflowStatus",

    # Search and filtering
    "DeclarationSearchFilter",

    # Statistics and metrics
    "DeclarationStats",

    # Bulk operations
    "BulkDeclarationOperation",

    # Activity tracking and audit
    "DeclarationActivity",

    # Notifications
    "DeclarationNotification",

    # Fiscal Service Declarations (Nota de Ingreso)
    "FiscalServiceDataBase",
    "FiscalServiceDataCreate",
    "FiscalServiceDataUpdate",
    "FiscalServiceDataResponse",
    "FiscalServiceDataListResponse",
    "FiscalServiceDataStatus",
    "TypeCompte",

    # Declaration Corrections (Audit trail)
    "DeclarationCorrectionBase",
    "DeclarationCorrectionCreate",
    "DeclarationCorrectionUpdate",
    "DeclarationCorrectionResponse",
    "DeclarationCorrectionListResponse",
    "CorrectionType",
    "CorrectionStatus",
]
