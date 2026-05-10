"""
Service Details Models - Complete service information with documents and procedures
Pydantic models for the /fiscal-services/{id}/details endpoint
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum


# ===================================================================================================
# NESTED MODELS - Documents
# ===================================================================================================

class DocumentDetailItem(BaseModel):
    """Document required for a service"""
    id: int
    template_code: str
    name: str  # Translated
    description: Optional[str] = None  # Translated
    category: Optional[str] = None
    validity_duration_months: Optional[int] = None
    validity_notes: Optional[str] = None
    is_required_expedition: bool = True
    is_required_renewal: bool = False
    display_order: int = 1
    custom_notes: Optional[str] = None


# ===================================================================================================
# NESTED MODELS - Procedures
# ===================================================================================================

class ProcedureStepDetailItem(BaseModel):
    """Single step in a procedure"""
    id: int
    step_number: int
    description: str  # Translated
    instructions: Optional[str] = None  # Translated
    estimated_duration_minutes: Optional[int] = None
    location_address: Optional[str] = None
    office_hours: Optional[str] = None
    requires_appointment: bool = False
    is_optional: bool = False


class ProcedureDetailItem(BaseModel):
    """Procedure with all steps"""
    id: int
    template_code: str
    name: str  # Translated
    description: Optional[str] = None  # Translated
    category: Optional[str] = None
    applies_to: Optional[str] = None  # expedition, renewal, both
    display_order: int = 1
    custom_notes: Optional[str] = None
    steps: List[ProcedureStepDetailItem] = []
    total_estimated_minutes: int = 0


# ===================================================================================================
# NESTED MODELS - Hierarchy
# ===================================================================================================

class CategoryDetailItem(BaseModel):
    """Category information"""
    id: int
    category_code: str
    name: str  # Translated
    description: Optional[str] = None  # Translated
    icon: Optional[str] = None
    color: Optional[str] = None


class SectorDetailItem(BaseModel):
    """Sector information"""
    id: int
    code: str
    name: str  # Translated
    description: Optional[str] = None  # Translated


class MinistryDetailItem(BaseModel):
    """Ministry information"""
    id: int
    code: str
    name: str  # Translated
    description: Optional[str] = None  # Translated


# ===================================================================================================
# NESTED MODELS - Pricing
# ===================================================================================================

class PricingInfo(BaseModel):
    """Pricing information for expedition and renewal"""
    expedition_price: float = 0
    renewal_price: float = 0
    calculation_method: str
    percentage_rate: Optional[float] = None
    unit_price: Optional[float] = None
    validity_period_months: Optional[int] = None
    renewal_frequency_months: Optional[int] = None
    currency: str = "XAF"


# ===================================================================================================
# NESTED MODELS - Related Services
# ===================================================================================================

class RelatedServiceItem(BaseModel):
    """Related or similar service"""
    id: int
    service_code: str
    name: str  # Translated
    expedition_price: float = 0
    processing_time_days: Optional[int] = None


# ===================================================================================================
# NESTED MODELS - Keywords
# ===================================================================================================

class KeywordItem(BaseModel):
    """Search keyword"""
    keyword: str
    language_code: str
    weight: int = 1


# ===================================================================================================
# MAIN RESPONSE MODEL
# ===================================================================================================

class ServiceDetailsResponse(BaseModel):
    """
    Complete service details response with all related information

    Used by: Frontend /services/[id] page
    """
    # Basic identification
    id: int
    service_code: str

    # Core information (Translated)
    name: str
    description: Optional[str] = None

    # Classification
    service_type: str
    status: str

    # Pricing
    pricing: PricingInfo

    # Processing
    processing_time_days: Optional[int] = None
    legal_reference: Optional[str] = None
    notes: Optional[str] = None

    # Hierarchy
    category: Optional[CategoryDetailItem] = None
    sector: Optional[SectorDetailItem] = None
    ministry: Optional[MinistryDetailItem] = None

    # Required Documents
    documents: List[DocumentDetailItem] = []
    documents_count: int = 0

    # Procedures
    procedures: List[ProcedureDetailItem] = []
    procedures_count: int = 0
    total_procedure_steps: int = 0

    # Related Services
    related_services: List[RelatedServiceItem] = []
    parent_service: Optional[RelatedServiceItem] = None
    child_services: List[RelatedServiceItem] = []

    # Keywords (for SEO/search)
    keywords: List[KeywordItem] = []

    # Metadata
    view_count: int = 0
    calculation_count: int = 0
    last_updated: Optional[datetime] = None

    # Computed fields
    has_documents: bool = False
    has_procedures: bool = False
    is_free: bool = False
    requires_renewal: bool = False


# ===================================================================================================
# REQUEST MODEL
# ===================================================================================================

class ServiceDetailsRequest(BaseModel):
    """Request parameters for service details"""
    language: str = Field("es", pattern="^(es|fr|en)$", description="Language for translations")
    include_related: bool = Field(True, description="Include related services")
    include_keywords: bool = Field(False, description="Include search keywords")
