"""
Fiscal Service Declaration Models - Nota de Ingreso, etc.

Table: fiscal_service_data
Déclarations de services fiscaux (différent de tax_declarations):
- Nota de Ingreso
- Services fiscaux ponctuels
- OCR extraction support
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime, date
from decimal import Decimal
from enum import Enum


class TypeCompte(str, Enum):
    """Type de compte pour paiement — matches DB type_compte_enum"""
    CUENTA_PROPIA = "cuenta_propia"      # Particulier
    CUENTA_EMPRESA = "cuenta_empresa"    # Entreprise


class FiscalServiceDataStatus(str, Enum):
    """Status de déclaration service fiscal"""
    DRAFT = "draft"
    SUBMITTED = "submitted"
    PROCESSING = "processing"
    ACCEPTED = "accepted"
    REJECTED = "rejected"


class FiscalServiceDataBase(BaseModel):
    """Base model for fiscal service declaration (Nota de Ingreso)"""

    user_id: str = Field(..., description="User UUID")
    fiscal_service_id: int = Field(..., description="FK to fiscal_services catalog")

    # OCR/Document linkage
    uploaded_file_id: Optional[str] = Field(None, description="Lien vers fichier scanné")
    ocr_extraction_id: Optional[str] = Field(None, description="Lien vers résultats OCR")

    # Status
    status: FiscalServiceDataStatus = Field(default=FiscalServiceDataStatus.DRAFT)

    # Nota de Ingreso data (extracted by OCR or manual entry)
    numero_nota: Optional[str] = Field(None, description="Numéro de la Nota de Ingreso")
    nom_demandeur: Optional[str] = Field(None, description="Nom du demandeur")
    concepto_pago: Optional[str] = Field(None, description="Concept du paiement")
    periode: Optional[str] = Field(None, description="Période fiscale")

    # Amounts
    montant_chiffre: Optional[Decimal] = Field(None, ge=0, description="Montant en chiffres (OCR ou saisi)")
    montant_lettre: Optional[str] = Field(None, description="Montant en lettres (vérification croisée)")
    final_amount: Optional[Decimal] = Field(None, ge=0, description="Montant final validé")
    currency: str = Field(default="XAF", description="Devise (XAF par défaut)")

    # Dates
    date_emission: Optional[date] = Field(None, description="Date d'émission du document")
    date_expiration: Optional[date] = Field(None, description="Date d'expiration")

    # Organisme
    organisme_emetteur: Optional[str] = Field(None, description="Organisme émetteur")
    departement_emetteur: Optional[str] = Field(None, description="Département émetteur")

    # Account type
    type_compte: Optional[TypeCompte] = Field(None, description="Type de compte pour paiement")

    # Additional data (JSONB)
    additional_data: Optional[Dict[str, Any]] = Field(default={}, description="Données additionnelles JSONB")

    # Supporting documents
    supporting_documents: List[str] = Field(default=[], description="Array de FK vers uploaded_files")

    # Review
    review_notes: Optional[str] = Field(None, description="Notes de révision")


class FiscalServiceDataCreate(FiscalServiceDataBase):
    """Create fiscal service declaration"""
    pass


class FiscalServiceDataUpdate(BaseModel):
    """Update fiscal service declaration"""
    status: Optional[FiscalServiceDataStatus] = None
    numero_nota: Optional[str] = None
    nom_demandeur: Optional[str] = None
    concepto_pago: Optional[str] = None
    periode: Optional[str] = None
    montant_chiffre: Optional[Decimal] = None
    montant_lettre: Optional[str] = None
    final_amount: Optional[Decimal] = None
    date_emission: Optional[date] = None
    date_expiration: Optional[date] = None
    organisme_emetteur: Optional[str] = None
    departement_emetteur: Optional[str] = None
    type_compte: Optional[TypeCompte] = None
    additional_data: Optional[Dict[str, Any]] = None
    supporting_documents: Optional[List[str]] = None
    review_notes: Optional[str] = None


class FiscalServiceDataResponse(FiscalServiceDataBase):
    """Response model for fiscal service declaration"""
    id: str

    # Payment linkage
    payment_id: Optional[str] = Field(None, description="FK to payments")

    # Review tracking
    reviewed_by: Optional[str] = Field(None, description="UUID reviewer")
    reviewed_at: Optional[datetime] = Field(None, description="Date de révision")

    # Timestamps
    submitted_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    # Related data (populated by joins)
    fiscal_service_name: Optional[str] = Field(None, description="Nom du service fiscal")
    user_email: Optional[str] = Field(None, description="Email utilisateur")


class FiscalServiceDataListResponse(BaseModel):
    """List of fiscal service declarations"""
    declarations: List[FiscalServiceDataResponse]
    total: int
    page: int
    page_size: int
