"""
Declaration Correction Models - Audit trail for corrections/amendments

ALIGNED WITH DATABASE_SCHEMA_REFERENCE.md
Table: declaration_corrections
Audit trail des corrections apportées aux déclarations (déclarations rectificatives)

IMPORTANT:
- correction_type is stored as varchar(30) in DB, not enum
- supporting_documents is PostgreSQL ARRAY type, not JSONB
- changes_detail is JSONB NOT NULL
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from decimal import Decimal
from enum import Enum


class CorrectionType(str, Enum):
    """
    Type de correction

    NOTE: Stored as varchar(30) in DB, these values must match exactly
    """
    AMOUNT_CORRECTION = "amount_correction"          # Correction de montant
    DATA_CORRECTION = "data_correction"              # Correction de données
    PERIOD_CORRECTION = "period_correction"          # Correction de période
    TAX_RATE_CORRECTION = "tax_rate_correction"      # Correction de taux
    DEDUCTION_CORRECTION = "deduction_correction"    # Correction de déductions
    FULL_RECTIFICATION = "full_rectification"        # Rectification complète
    PARTIAL_RECTIFICATION = "partial_rectification"  # Rectification partielle
    ADMINISTRATIVE_CORRECTION = "administrative_correction"  # Correction administrative


class CorrectionStatus(str, Enum):
    """Status de la correction"""
    PENDING = "pending"        # En attente
    APPROVED = "approved"      # Approuvée
    REJECTED = "rejected"      # Rejetée
    CANCELLED = "cancelled"    # Annulée


class DeclarationCorrectionBase(BaseModel):
    """
    Base model for declaration correction

    ALIGNED WITH DATABASE_SCHEMA_REFERENCE.md
    """

    # Required fields - ALIGNED WITH DB
    original_declaration_id: str = Field(..., description="UUID déclaration originale (NOT NULL) - DB: original_declaration_id")
    rectificative_declaration_id: str = Field(..., description="UUID déclaration rectificative (NOT NULL) - DB: rectificative_declaration_id")

    correction_type: CorrectionType = Field(..., description="Type de correction (varchar 30, NOT NULL) - DB: correction_type")
    correction_reason: str = Field(..., description="Raison de la correction (text, NOT NULL) - DB: correction_reason")

    # Changes detail (JSONB NOT NULL) - ALIGNED WITH DB
    changes_detail: Dict[str, Dict[str, Any]] = Field(
        ...,
        description="Détail JSON des changements: {field_name: {old: X, new: Y}} (JSONB NOT NULL) - DB: changes_detail"
    )

    # Amounts (nullable) - ALIGNED WITH DB
    original_amount: Optional[Decimal] = Field(None, description="Montant original (numeric, nullable) - DB: original_amount")
    rectified_amount: Optional[Decimal] = Field(None, description="Montant rectifié (numeric, nullable) - DB: rectified_amount")
    # difference is GENERATED in DB: rectified_amount - original_amount

    # Supporting documents (PostgreSQL ARRAY, nullable) - ALIGNED WITH DB
    supporting_documents: Optional[List[str]] = Field(
        default=None,
        description="Array de FK vers uploaded_files (PostgreSQL ARRAY type, nullable) - DB: supporting_documents"
    )


class DeclarationCorrectionCreate(DeclarationCorrectionBase):
    """Create declaration correction"""
    status: CorrectionStatus = Field(default=CorrectionStatus.PENDING)


class DeclarationCorrectionUpdate(BaseModel):
    """Update declaration correction"""
    status: Optional[CorrectionStatus] = None
    correction_reason: Optional[str] = None
    changes_detail: Optional[Dict[str, Dict[str, Any]]] = None
    supporting_documents: Optional[List[str]] = None
    approval_notes: Optional[str] = None


class DeclarationCorrectionResponse(DeclarationCorrectionBase):
    """Response model for declaration correction"""
    id: str

    # Calculated difference
    difference: Optional[Decimal] = Field(None, description="Différence (GENERATED)")

    # Approval tracking
    status: CorrectionStatus
    approved_by: Optional[str] = Field(None, description="UUID approbateur")
    approved_at: Optional[datetime] = Field(None, description="Date approbation")
    approval_notes: Optional[str] = Field(None, description="Notes approbation")

    # Timestamps
    created_at: datetime
    updated_at: datetime

    # Related data (populated by joins)
    original_declaration_type: Optional[str] = None
    rectificative_declaration_type: Optional[str] = None
    original_user_email: Optional[str] = None


class DeclarationCorrectionListResponse(BaseModel):
    """List of declaration corrections"""
    corrections: List[DeclarationCorrectionResponse]
    total: int
    page: int
    page_size: int
