"""
Fiscal Services Models - Based on DATABASE_SCHEMA_REFERENCE.md

Tables implemented:
- fiscal_services: Catalog of all fiscal services (taxes, fees, permits)
- categories: Service categorization by sector/ministry

Note: fiscal_service_data table belongs to DECLARATIONS module (user declarations)
"""

from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, Dict, Any, List
from datetime import datetime, date
from enum import Enum


# ═══════════════════════════════════════════════════════════════════════════
# ENUMS - From DATABASE_SCHEMA_REFERENCE.md
# ═══════════════════════════════════════════════════════════════════════════


class ServiceTypeEnum(str, Enum):
    """Service type categorization"""
    DOCUMENT_PROCESSING = "document_processing"
    LICENSE_PERMIT = "license_permit"
    RESIDENCE_PERMIT = "residence_permit"
    REGISTRATION_FEE = "registration_fee"
    INSPECTION_FEE = "inspection_fee"
    ADMINISTRATIVE_TAX = "administrative_tax"
    CUSTOMS_DUTY = "customs_duty"
    DECLARATION_TAX = "declaration_tax"


class CalculationMethodEnum(str, Enum):
    """Calculation method for fiscal service amounts"""
    FIXED_EXPEDITION = "fixed_expedition"          # Fixed fee for first issuance
    FIXED_RENEWAL = "fixed_renewal"                # Fixed fee for renewal only
    FIXED_BOTH = "fixed_both"                      # Same fixed fee for both
    PERCENTAGE_BASED = "percentage_based"          # Percentage of a value
    UNIT_BASED = "unit_based"                      # Price per unit
    TIERED_RATES = "tiered_rates"                  # Progressive brackets
    FORMULA_BASED = "formula_based"                # Custom formula
    FIXED_PLUS_UNIT = "fixed_plus_unit"            # Base + per-unit charge


class ServiceStatusEnum(str, Enum):
    """Service status"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    DRAFT = "draft"
    DEPRECATED = "deprecated"


# ═══════════════════════════════════════════════════════════════════════════
# MINISTRIES Models (for hierarchy)
# ═══════════════════════════════════════════════════════════════════════════


class MinistryCreate(BaseModel):
    """Create ministry request"""
    ministry_code: str = Field(..., max_length=10, description="Unique ministry code")
    name_es: str = Field(..., max_length=255, description="Ministry name (Spanish)")
    description_es: Optional[str] = Field(None, description="Ministry description (Spanish)")
    display_order: int = Field(0, description="Display order for sorting")
    icon: Optional[str] = Field(None, max_length=100, description="Icon identifier")
    color: Optional[str] = Field(None, max_length=7, pattern=r"^#[0-9A-Fa-f]{6}$", description="Hex color code")
    website_url: Optional[str] = Field(None, max_length=255, description="Ministry website URL")
    contact_email: Optional[str] = Field(None, max_length=255, description="Contact email")
    contact_phone: Optional[str] = Field(None, max_length=50, description="Contact phone")
    is_active: bool = Field(True, description="Whether ministry is active")

    class Config:
        json_schema_extra = {
            "example": {
                "ministry_code": "MHAP",
                "name_es": "Ministerio de Hacienda y Presupuestos",
                "description_es": "Gestión de la política fiscal y presupuestaria",
                "display_order": 1,
                "icon": "building-columns",
                "color": "#3B82F6",
                "website_url": "https://www.hacienda.gq",
                "contact_email": "info@hacienda.gq",
                "contact_phone": "+240 222 123 456",
                "is_active": True
            }
        }


class MinistryUpdate(BaseModel):
    """Update ministry request - all fields optional"""
    name_es: Optional[str] = Field(None, max_length=255, description="Ministry name (Spanish)")
    description_es: Optional[str] = Field(None, description="Ministry description (Spanish)")
    display_order: Optional[int] = Field(None, description="Display order for sorting")
    icon: Optional[str] = Field(None, max_length=100, description="Icon identifier")
    color: Optional[str] = Field(None, max_length=7, pattern=r"^#[0-9A-Fa-f]{6}$", description="Hex color code")
    website_url: Optional[str] = Field(None, max_length=255, description="Ministry website URL")
    contact_email: Optional[str] = Field(None, max_length=255, description="Contact email")
    contact_phone: Optional[str] = Field(None, max_length=50, description="Contact phone")
    is_active: Optional[bool] = Field(None, description="Whether ministry is active")


class MinistryResponse(BaseModel):
    """Ministry response model"""
    id: int
    code: str = Field(..., max_length=10, description="Unique ministry code", alias="ministry_code")
    name_es: str = Field(..., max_length=255, description="Ministry name (Spanish)")
    description_es: Optional[str] = Field(None, description="Ministry description (Spanish)")
    display_order: int = Field(0, description="Display order for sorting")
    icon: Optional[str] = Field(None, description="Icon identifier")
    color: Optional[str] = Field(None, description="Hex color code")
    website_url: Optional[str] = Field(None, description="Ministry website URL")
    contact_email: Optional[str] = Field(None, description="Contact email")
    contact_phone: Optional[str] = Field(None, description="Contact phone")
    is_active: bool = Field(True, description="Whether ministry is active")
    description_source: Optional[str] = Field(None, description="Source of description: manual, ai_draft, ai_generated")
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True
        populate_by_name = True


# ═══════════════════════════════════════════════════════════════════════════
# SECTORS Models (for hierarchy)
# ═══════════════════════════════════════════════════════════════════════════


class SectorCreate(BaseModel):
    """Create sector request"""
    sector_code: str = Field(..., max_length=10, description="Unique sector code")
    ministry_id: int = Field(..., description="Parent ministry ID")
    name_es: str = Field(..., max_length=255, description="Sector name (Spanish)")
    description_es: Optional[str] = Field(None, description="Sector description (Spanish)")
    display_order: int = Field(0, description="Display order for sorting")
    icon: Optional[str] = Field(None, max_length=100, description="Icon identifier")
    color: Optional[str] = Field(None, max_length=7, pattern=r"^#[0-9A-Fa-f]{6}$", description="Hex color code")
    is_active: bool = Field(True, description="Whether sector is active")

    class Config:
        json_schema_extra = {
            "example": {
                "sector_code": "IMPUESTOS",
                "ministry_id": 1,
                "name_es": "Impuestos Directos",
                "description_es": "Gestión de impuestos directos",
                "display_order": 1,
                "icon": "receipt-tax",
                "color": "#10B981",
                "is_active": True
            }
        }


class SectorUpdate(BaseModel):
    """Update sector request - all fields optional"""
    ministry_id: Optional[int] = Field(None, description="Parent ministry ID")
    name_es: Optional[str] = Field(None, max_length=255, description="Sector name (Spanish)")
    description_es: Optional[str] = Field(None, description="Sector description (Spanish)")
    display_order: Optional[int] = Field(None, description="Display order for sorting")
    icon: Optional[str] = Field(None, max_length=100, description="Icon identifier")
    color: Optional[str] = Field(None, max_length=7, pattern=r"^#[0-9A-Fa-f]{6}$", description="Hex color code")
    is_active: Optional[bool] = Field(None, description="Whether sector is active")


class SectorResponse(BaseModel):
    """Sector response model"""
    id: int
    code: str = Field(..., max_length=10, description="Unique sector code", alias="sector_code")
    ministry_id: int = Field(..., description="Parent ministry ID")
    name_es: str = Field(..., max_length=255, description="Sector name (Spanish)")
    description_es: Optional[str] = Field(None, description="Sector description (Spanish)")
    display_order: int = Field(0, description="Display order for sorting")
    icon: Optional[str] = Field(None, description="Icon identifier")
    color: Optional[str] = Field(None, description="Hex color code")
    is_active: bool = Field(True, description="Whether sector is active")
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True
        populate_by_name = True


# ═══════════════════════════════════════════════════════════════════════════
# CATEGORIES Models
# ═══════════════════════════════════════════════════════════════════════════


class CategoryCreate(BaseModel):
    """Create category request"""
    category_code: str = Field(..., max_length=10, description="Unique category code")
    sector_id: Optional[int] = Field(None, description="Sector this category belongs to")
    ministry_id: Optional[int] = Field(None, description="Ministry managing this category")
    service_type: Optional[ServiceTypeEnum] = Field(None, description="Type of services in this category")
    name_es: str = Field(..., max_length=255, description="Category name (Spanish)")
    description_es: Optional[str] = Field(None, description="Category description (Spanish)")
    display_order: int = Field(0, description="Display order for sorting")
    icon: Optional[str] = Field(None, max_length=100, description="Icon identifier")
    color: Optional[str] = Field(None, max_length=7, pattern=r"^#[0-9A-Fa-f]{6}$", description="Hex color code")
    is_active: bool = Field(True, description="Whether category is active")

    class Config:
        json_schema_extra = {
            "example": {
                "category_code": "IVA",
                "sector_id": 1,
                "ministry_id": 1,
                "service_type": "declaration_tax",
                "name_es": "IVA - Impuesto sobre el Valor Añadido",
                "description_es": "Declaraciones de IVA",
                "display_order": 1,
                "icon": "calculator",
                "color": "#F59E0B",
                "is_active": True
            }
        }


class CategoryUpdate(BaseModel):
    """Update category request - all fields optional"""
    sector_id: Optional[int] = None
    ministry_id: Optional[int] = None
    service_type: Optional[ServiceTypeEnum] = None
    name_es: Optional[str] = Field(None, max_length=255)
    description_es: Optional[str] = None
    display_order: Optional[int] = None
    icon: Optional[str] = Field(None, max_length=100)
    color: Optional[str] = Field(None, max_length=7, pattern=r"^#[0-9A-Fa-f]{6}$")
    is_active: Optional[bool] = None


class CategoryResponse(BaseModel):
    """Category response"""
    id: int
    category_code: str = Field(..., max_length=10, description="Unique category code")
    sector_id: Optional[int] = Field(None, description="Sector this category belongs to")
    ministry_id: Optional[int] = Field(None, description="Ministry managing this category")
    service_type: Optional[ServiceTypeEnum] = Field(None, description="Type of services in this category")
    name_es: str = Field(..., max_length=255, description="Category name (Spanish)")
    description_es: Optional[str] = Field(None, description="Category description (Spanish)")
    display_order: int = Field(0, description="Display order for sorting")
    icon: Optional[str] = Field(None, description="Icon identifier")
    color: Optional[str] = Field(None, description="Hex color code")
    is_active: bool = Field(True, description="Whether category is active")
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ═══════════════════════════════════════════════════════════════════════════
# FISCAL_SERVICES Models
# ═══════════════════════════════════════════════════════════════════════════


class FiscalServiceBase(BaseModel):
    """Base fiscal service model - matches database schema exactly"""

    model_config = ConfigDict(extra='ignore', from_attributes=True)

    # Core identification
    service_code: str = Field(..., max_length=20, description="Unique service code")
    category_id: int = Field(..., description="Category ID (references categories.id)")

    # Naming and description (Spanish)
    name_es: str = Field(..., max_length=255, description="Service name (Spanish)")
    description_es: Optional[str] = Field(None, description="Service description (Spanish)")

    # Service classification
    service_type: ServiceTypeEnum = Field(..., description="Type of service")
    calculation_method: CalculationMethodEnum = Field(..., description="How to calculate the amount")

    # Fixed amounts for expedition and renewal
    tasa_expedicion: Optional[float] = Field(None, ge=0, description="Fixed fee for first issuance (XAF)")
    tasa_renovacion: Optional[float] = Field(None, ge=0, description="Fixed fee for renewal (XAF)")

    # Variable calculation parameters (matching database column names)
    base_percentage: Optional[float] = Field(None, ge=0, le=100, description="Percentage rate if percentage_based")
    percentage_of: Optional[str] = Field(None, max_length=100, description="What the percentage applies to")
    unit_rate: Optional[float] = Field(None, ge=0, description="Price per unit if unit_based")
    unit_type: Optional[str] = Field(None, max_length=50, description="Type of unit (quantity, weight, etc.)")

    # Formulas for expedition and renewal
    expedition_formula: Optional[str] = Field(None, description="Formula for expedition calculation")
    expedition_unit_measure: Optional[str] = Field(None, max_length=50, description="Unit of measure for expedition")
    renewal_formula: Optional[str] = Field(None, description="Formula for renewal calculation")
    renewal_unit_measure: Optional[str] = Field(None, max_length=50, description="Unit of measure for renewal")

    # Advanced calculation configuration
    calculation_config: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="JSON config for complex calculations (formulas, variables, conditions)"
    )
    rate_tiers: Optional[List[Dict[str, Any]]] = Field(
        default_factory=list,
        description="Progressive rate brackets for tiered_rates method"
    )

    # Tier grouping
    tier_group_name: Optional[str] = Field(None, max_length=100, description="Name of tier grouping")
    is_tier_component: Optional[bool] = Field(False, description="Whether this is part of tiered calculation")

    # Validity and renewal
    validity_period_months: Optional[int] = Field(None, ge=0, description="How long the service is valid (months)")
    renewal_frequency_months: Optional[int] = Field(None, ge=0, description="How often renewal is required")
    grace_period_days: Optional[int] = Field(0, ge=0, description="Grace period before penalties")

    # Penalty configuration
    late_penalty_percentage: Optional[float] = Field(None, description="Late payment penalty percentage")
    late_penalty_fixed: Optional[float] = Field(None, description="Fixed late payment penalty")
    penalty_calculation_rules: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Rules for penalty calculation")

    # Eligibility and exemptions
    eligibility_criteria: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Eligibility requirements")
    exemption_conditions: Optional[List[Dict[str, Any]]] = Field(default_factory=list, description="Exemption conditions")

    # Hierarchical services
    parent_service_id: Optional[int] = Field(None, description="Parent service for sub-services")

    # Legal and regulatory
    legal_reference: Optional[str] = Field(None, description="Legal basis for this service")
    regulatory_articles: Optional[List[str]] = Field(None, description="Regulatory articles")

    # Tariff dates
    tariff_effective_from: Optional[date] = Field(None, description="When tariff is effective")
    tariff_effective_to: Optional[date] = Field(None, description="When tariff expires")

    # Processing and priority
    processing_time_days: Optional[int] = Field(None, ge=0, description="Estimated processing time")
    priority: Optional[int] = Field(0, description="Service priority")
    complexity_level: Optional[int] = Field(1, ge=1, le=5, description="Complexity level 1-5")

    # Status
    status: Optional[ServiceStatusEnum] = Field(ServiceStatusEnum.ACTIVE, description="Service status")

    # Description visibility (admin toggle — hides description on public site)
    description_visible: Optional[bool] = Field(True, description="Show description on public site")

    # Computed field for API compatibility (not in DB, populated by repository)
    required_documents: Optional[List[str]] = Field(None, description="List of required document types")


class FiscalServiceCreate(FiscalServiceBase):
    """Create fiscal service request"""
    pass


class FiscalServiceUpdate(BaseModel):
    """Update fiscal service request - all fields optional, matching database schema"""
    model_config = ConfigDict(extra='ignore')

    category_id: Optional[int] = None
    name_es: Optional[str] = Field(None, max_length=255)
    description_es: Optional[str] = None
    service_type: Optional[ServiceTypeEnum] = None
    calculation_method: Optional[CalculationMethodEnum] = None
    tasa_expedicion: Optional[float] = Field(None, ge=0)
    tasa_renovacion: Optional[float] = Field(None, ge=0)
    base_percentage: Optional[float] = Field(None, ge=0, le=100)
    percentage_of: Optional[str] = Field(None, max_length=100)
    unit_rate: Optional[float] = Field(None, ge=0)
    unit_type: Optional[str] = Field(None, max_length=50)
    expedition_formula: Optional[str] = None
    expedition_unit_measure: Optional[str] = Field(None, max_length=50)
    renewal_formula: Optional[str] = None
    renewal_unit_measure: Optional[str] = Field(None, max_length=50)
    calculation_config: Optional[Dict[str, Any]] = None
    rate_tiers: Optional[List[Dict[str, Any]]] = None
    tier_group_name: Optional[str] = Field(None, max_length=100)
    is_tier_component: Optional[bool] = None
    validity_period_months: Optional[int] = Field(None, ge=0)
    renewal_frequency_months: Optional[int] = Field(None, ge=0)
    grace_period_days: Optional[int] = Field(None, ge=0)
    late_penalty_percentage: Optional[float] = None
    late_penalty_fixed: Optional[float] = None
    penalty_calculation_rules: Optional[Dict[str, Any]] = None
    eligibility_criteria: Optional[Dict[str, Any]] = None
    exemption_conditions: Optional[List[Dict[str, Any]]] = None
    parent_service_id: Optional[int] = None
    legal_reference: Optional[str] = None
    regulatory_articles: Optional[List[str]] = None
    tariff_effective_from: Optional[date] = None
    tariff_effective_to: Optional[date] = None
    processing_time_days: Optional[int] = Field(None, ge=0)
    priority: Optional[int] = None
    complexity_level: Optional[int] = Field(None, ge=1, le=5)
    status: Optional[ServiceStatusEnum] = None
    description_visible: Optional[bool] = None


class FiscalServiceResponse(FiscalServiceBase):
    """Fiscal service response - inherits model_config from FiscalServiceBase"""
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    # Additional computed/joined fields from repository
    category_name: Optional[str] = None
    sector_name: Optional[str] = None
    ministry_name: Optional[str] = None
    keywords: Optional[List[str]] = None

    # Enrichment metadata
    description_source: Optional[str] = None

    # Usage statistics
    view_count: Optional[int] = 0
    calculation_count: Optional[int] = 0
    payment_count: Optional[int] = 0
    favorite_count: Optional[int] = 0


class FiscalServiceWithCategory(FiscalServiceResponse):
    """Fiscal service with category information"""
    category: Optional[CategoryResponse] = None


# ═══════════════════════════════════════════════════════════════════════════
# Calculation Models
# ═══════════════════════════════════════════════════════════════════════════


class CalculationInput(BaseModel):
    """Input for fiscal service calculation"""
    fiscal_service_id: int = Field(..., description="Service to calculate")
    is_renewal: bool = Field(False, description="Is this a renewal (vs first expedition)")

    # For percentage_based
    base_value: Optional[float] = Field(None, description="Base value for percentage calculation")

    # For unit_based
    quantity: Optional[int] = Field(None, ge=1, description="Number of units")

    # For tiered_rates
    total_amount: Optional[float] = Field(None, ge=0, description="Amount to apply tiered rates to")

    # For formula_based or custom
    variables: Optional[Dict[str, Any]] = Field(None, description="Variables for formula calculation")


class RateTier(BaseModel):
    """Rate tier for progressive calculations"""
    min_value: float = Field(..., ge=0)
    max_value: Optional[float] = Field(None, ge=0)  # None = unlimited
    rate: float = Field(..., ge=0)  # Can be percentage or fixed amount
    fixed_amount: Optional[float] = Field(None, ge=0)  # Fixed amount for this tier


class CalculationBreakdown(BaseModel):
    """Detailed breakdown of calculation"""
    method: CalculationMethodEnum
    is_renewal: bool
    base_fee: Optional[float] = None
    variable_amount: Optional[float] = None
    tiers_applied: Optional[List[Dict[str, Any]]] = None
    formula_used: Optional[str] = None
    subtotal: float
    additional_fees: Optional[Dict[str, float]] = None
    total: float


class CalculationResult(BaseModel):
    """Result of fiscal service calculation"""
    fiscal_service_id: int
    service_code: str
    service_name: str
    calculation_method: CalculationMethodEnum
    breakdown: CalculationBreakdown
    amount_gnf: float = Field(..., description="Final amount in GNF")
    currency: str = Field("GNF", description="Currency code")
    calculated_at: datetime = Field(default_factory=datetime.utcnow)


# ═══════════════════════════════════════════════════════════════════════════
# Search and Filtering Models
# ═══════════════════════════════════════════════════════════════════════════


class FiscalServiceFilter(BaseModel):
    """Filters for searching fiscal services"""
    category_id: Optional[int] = None
    sector_id: Optional[int] = None
    ministry_id: Optional[int] = None
    service_type: Optional[ServiceTypeEnum] = None
    calculation_method: Optional[CalculationMethodEnum] = None
    status: Optional[ServiceStatusEnum] = None
    search_term: Optional[str] = Field(None, description="Full-text search in name/description")
    min_amount: Optional[float] = Field(None, ge=0)
    max_amount: Optional[float] = Field(None, ge=0)


# Alias for compatibility with routes
FiscalServiceSearchRequest = FiscalServiceFilter


# ═══════════════════════════════════════════════════════════════════════════
# Statistics Models
# ═══════════════════════════════════════════════════════════════════════════


class FiscalServiceStats(BaseModel):
    """
    Statistics model for fiscal services

    Provides comprehensive statistics for admin dashboards
    """
    total_services: int = Field(..., description="Total number of services")
    active_services: int = Field(..., description="Number of active services")
    inactive_services: int = Field(..., description="Number of inactive services")
    services_by_type: Dict[str, int] = Field(..., description="Services count by service_type")
    services_by_category: Dict[str, int] = Field(..., description="Services count by category")
    services_by_ministry: Dict[str, int] = Field(..., description="Services count by ministry")
    services_by_status: Dict[str, int] = Field(..., description="Services count by status")
    average_processing_time: float = Field(..., description="Average processing time in days")
    most_used_services: List[Dict[str, Any]] = Field(..., description="Top 10 most used services")
    total_calculations: int = Field(..., description="Total number of calculations performed")
    total_views: int = Field(..., description="Total number of service views")


# Aliases for compatibility with calculation routes
CalculateServiceRequest = CalculationInput
CalculateServiceResponse = CalculationResult


class FiscalServiceListResponse(BaseModel):
    """Paginated list of fiscal services"""
    services: List[FiscalServiceResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


# ═══════════════════════════════════════════════════════════════════════════
# Complete Service Creation Models
# ═══════════════════════════════════════════════════════════════════════════


class FiscalServiceCreateComplete(BaseModel):
    """
    Complete fiscal service creation with all related entities

    Use this for creating a fiscal service with:
    - Basic service info
    - Document assignments
    - Procedure assignments
    - Keywords
    - Translations (optional)
    """
    # Main service data
    service: FiscalServiceCreate

    # Related entities
    document_assignments: Optional[List[Dict[str, Any]]] = Field(
        default=[],
        description="Documents required for this service"
    )
    procedure_assignments: Optional[List[Dict[str, Any]]] = Field(
        default=[],
        description="Procedures required for this service"
    )
    keywords: Optional[List[Dict[str, Any]]] = Field(
        default=[],
        description="Search keywords (multilingual)"
    )
    translations: Optional[List[Dict[str, Any]]] = Field(
        default=[],
        description="Translations for other languages"
    )


class FiscalServiceUpdateComplete(BaseModel):
    """
    Complete fiscal service update with cascading updates
    """
    # Main service updates
    service: FiscalServiceUpdate

    # Document assignments
    add_document_assignments: Optional[List[Dict[str, Any]]] = None
    remove_document_ids: Optional[List[int]] = None

    # Procedure assignments
    add_procedure_assignments: Optional[List[Dict[str, Any]]] = None
    remove_procedure_ids: Optional[List[int]] = None

    # Keywords
    add_keywords: Optional[List[Dict[str, Any]]] = None
    remove_keyword_ids: Optional[List[int]] = None


class FiscalServiceCompleteResponse(FiscalServiceResponse):
    """
    Complete fiscal service response with all related data
    """
    document_assignments: List[Dict[str, Any]] = []
    procedure_assignments: List[Dict[str, Any]] = []
    keywords: List[Dict[str, Any]] = []
    translations: List[Dict[str, Any]] = []
