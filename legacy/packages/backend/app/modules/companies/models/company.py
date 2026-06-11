"""
Company Models - Pydantic schemas for companies and user_company_roles

ALIGNED WITH DB (Migration 218 Phase 1.3)
Tables: companies, user_company_roles
"""

from pydantic import BaseModel, Field, EmailStr, field_validator
from typing import Optional, List, Dict
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from uuid import UUID


class CompanyMemberRole(str, Enum):
    """Company member roles (user_company_roles table)."""
    COMPANY_OWNER = "company_owner"
    COMPANY_ADMIN = "company_admin"
    COMPANY_ACCOUNTANT = "company_accountant"
    COMPANY_MEMBER = "company_member"


class RegimenFiscal(str, Enum):
    """Fiscal regime classification result."""
    BUNDLE = "bundle"
    DECLARATIVO = "declarativo"
    EXENTO = "exento"
    PENDIENTE = "pendiente"


class CompanyBase(BaseModel):
    """Base company model — ALIGNED WITH DB."""

    # Required
    legal_name: str = Field(..., min_length=2, max_length=255)
    tax_id: str = Field(..., min_length=5, max_length=100)

    # Identity (from OCR empresa section)
    trade_name: Optional[str] = Field(None, max_length=255)
    nif: Optional[str] = Field(None, max_length=20)
    forma_juridica: Optional[str] = Field(None, max_length=50)
    nacionalidad: Optional[str] = Field(None, max_length=50)
    capital_social: Optional[Decimal] = Field(None, ge=0)
    registration_number: Optional[str] = Field(None, max_length=30)
    registration_date: Optional[date] = None

    # Legal representative (from OCR empresa.representante_legal) — REQUIRED
    representante_legal: str = Field(..., min_length=2, max_length=255)

    # Activity (from OCR actividad section)
    sector_actividad: Optional[str] = Field(None, max_length=50)
    subsector_actividad: Optional[str] = Field(None, max_length=100)
    objeto_social: Optional[str] = None

    # Classification (LLM-derived)
    commerce_type: Optional[str] = Field(None, max_length=50)
    regimen_fiscal: Optional[RegimenFiscal] = Field(default=RegimenFiscal.PENDIENTE)

    # Operational (from OCR datos_operativos)
    employee_count: Optional[int] = Field(None, ge=0)
    establishment_count: Optional[int] = Field(None, ge=0)

    # Representative
    representante_legal: Optional[str] = Field(None, max_length=255)

    # Location
    address: Optional[str] = None
    phone: Optional[str] = Field(None, max_length=20)
    email: Optional[EmailStr] = None
    zone_id: Optional[UUID] = None
    city_id: Optional[UUID] = None

    # Status
    is_active: Optional[bool] = Field(True)
    is_verified: Optional[bool] = Field(False)


class CompanyCreate(CompanyBase):
    """Create company schema."""
    pass


class AdminCompanyCreateRequest(BaseModel):
    """Admin company creation with auto-licence generation.

    The admin provides structured data (no OCR needed). The system
    auto-resolves zone, creates the company, and generates the licence
    with all obligations for the current fiscal year.
    """
    # Required
    legal_name: str = Field(..., min_length=2, max_length=255)
    commerce_type: str = Field(..., max_length=50, description="Must match a service_bundles.commerce_type")
    zone_code: str = Field(..., max_length=5, description="Commerce zone code (A1, B2, C3, etc.)")
    representante_legal: str = Field(..., min_length=2, max_length=255, description="Legal representative full name")

    # Identification (at least one required)
    nif: Optional[str] = Field(None, max_length=20)
    registration_number: Optional[str] = Field(None, max_length=30, description="PE-XXXX format for autonomos")

    # Optional details
    forma_juridica: Optional[str] = Field(None, max_length=50)
    sector_actividad: Optional[str] = Field(None, max_length=50)
    subsector_actividad: Optional[str] = Field(None, max_length=100)
    objeto_social: Optional[str] = None
    address: Optional[str] = None
    phone: Optional[str] = Field(None, max_length=20)
    email: Optional[EmailStr] = None
    employee_count: Optional[int] = Field(None, ge=0)
    city_name: Optional[str] = Field(None, max_length=100, description="City name for auto-resolution")


class AdminCompanyCreateResponse(BaseModel):
    """Response for admin company creation."""
    company_id: str
    company_name: str
    license_id: str
    license_status: str
    obligations_count: int
    total_amount: float
    zone_code: str
    fiscal_year: int
    source: str = "admin_manual"


class CompanyUpdate(BaseModel):
    """Update company schema — all fields optional for partial updates."""
    legal_name: Optional[str] = Field(None, min_length=2, max_length=255)
    trade_name: Optional[str] = Field(None, max_length=255)
    nif: Optional[str] = Field(None, max_length=20)
    forma_juridica: Optional[str] = Field(None, max_length=50)
    nacionalidad: Optional[str] = Field(None, max_length=50)
    capital_social: Optional[Decimal] = Field(None, ge=0)
    registration_number: Optional[str] = Field(None, max_length=30)
    registration_date: Optional[date] = None
    sector_actividad: Optional[str] = Field(None, max_length=50)
    subsector_actividad: Optional[str] = Field(None, max_length=100)
    objeto_social: Optional[str] = None
    commerce_type: Optional[str] = Field(None, max_length=50)
    regimen_fiscal: Optional[RegimenFiscal] = None
    employee_count: Optional[int] = Field(None, ge=0)
    establishment_count: Optional[int] = Field(None, ge=0)
    address: Optional[str] = None
    phone: Optional[str] = Field(None, max_length=20)
    email: Optional[EmailStr] = None
    zone_id: Optional[UUID] = None
    city_id: Optional[UUID] = None
    is_active: Optional[bool] = None
    is_verified: Optional[bool] = None


class CompanyResponse(CompanyBase):
    """Company response schema."""
    id: str = Field(...)
    created_at: datetime
    updated_at: datetime

    # Related data (from JOINs)
    owner_user_id: Optional[str] = None
    member_count: Optional[int] = Field(0)
    city_name: Optional[str] = None
    zone_code: Optional[str] = None

    class Config:
        from_attributes = True

    @field_validator('id', 'owner_user_id', mode='before')
    @classmethod
    def coerce_uuid_to_str(cls, v):
        """Convert UUID objects to strings for Pydantic v2 strict mode."""
        if v is not None and not isinstance(v, str):
            return str(v)
        return v


class CompanyMember(BaseModel):
    """Company member schema (user_company_roles table)."""
    user_id: str
    company_id: str
    role: CompanyMemberRole
    is_active: Optional[bool] = Field(True)
    assigned_at: Optional[datetime] = None
    user_email: Optional[str] = None
    user_name: Optional[str] = None

    class Config:
        from_attributes = True


class CompanyListResponse(BaseModel):
    """Paginated company list."""
    companies: List[CompanyResponse]
    total: int
    page: int
    page_size: int


class AddMemberRequest(BaseModel):
    """Add member to company — request body."""
    member_user_id: str
    role: CompanyMemberRole


class UpdateMemberRoleRequest(BaseModel):
    """Update member role — request body."""
    role: CompanyMemberRole


# =============================================================================
# ADMIN MODELS
# =============================================================================

class CompanyAdminResponse(CompanyResponse):
    """Extended response for admin views — includes license count + archive metadata."""
    license_count: int = 0
    total_obligations_amount: Optional[Decimal] = None
    # Archive metadata (migration 314 + Phase 4 of SOFT_DELETE_COMPANIES_PLAN).
    # Populated by company_repository.list_all when the row is archived.
    archived_at: Optional[datetime] = None
    archive_reason: Optional[str] = None
    archived_by: Optional[str] = None
    archived_by_email: Optional[str] = None
    archived_by_name: Optional[str] = None

    @field_validator('archived_by', mode='before')
    @classmethod
    def coerce_archived_by_to_str(cls, v):
        """Convert UUID objects to strings (consistent with id/owner_user_id)."""
        if v is not None and not isinstance(v, str):
            return str(v)
        return v


class CompanyAdminListResponse(BaseModel):
    """Paginated company list for admin."""
    items: List[CompanyAdminResponse]
    total: int
    page: int
    page_size: int


class CompanyStatsResponse(BaseModel):
    """Aggregated company stats for admin dashboard."""
    total: int = 0
    active: int = 0
    verified: int = 0
    inactive: int = 0
    with_licenses: int = 0
    by_regimen: Dict[str, int] = {}


class CompanySearchResult(BaseModel):
    """Lightweight company for autocomplete/search."""
    id: str
    legal_name: str
    tax_id: str
    nif: Optional[str] = None
    city_name: Optional[str] = None
    is_verified: bool = False

    class Config:
        from_attributes = True


class CompanyVerifyRequest(BaseModel):
    """Toggle company verification status."""
    is_verified: bool


class CompanyClassifyResponse(BaseModel):
    """Result of fiscal regime classification."""
    regimen_fiscal: str
    confidence: float
    reason: str
