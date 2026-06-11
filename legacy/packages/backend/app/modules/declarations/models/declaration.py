"""
Declaration Models - Pydantic schemas for tax declarations

Aligned with DATABASE_SCHEMA_REFERENCE.md:
- Table: tax_declarations (main table)
- Enums: declaration_status_enum, declaration_type_enum (28 types)
- Related: declaration_iva_details, declaration_irpf_data, declaration_petroliferos_details,
           declaration_retencion_details, declaration_other_details
"""

from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any
from datetime import datetime, date
from decimal import Decimal
from enum import Enum


class DeclarationStatus(str, Enum):
    """
    Status enum for tax declarations
    Source: DATABASE_SCHEMA_REFERENCE.md declaration_status_enum
    """
    DRAFT = "draft"                    # En cours de rédaction
    SUBMITTED = "submitted"            # Soumise (envoyée)
    PROCESSING = "processing"          # En traitement par agent
    ACCEPTED = "accepted"              # Acceptée/Approuvée
    REJECTED = "rejected"              # Rejetée
    AMENDED = "amended"                # Amendée/Corrigée


class DeclarationType(str, Enum):
    """
    Type enum for tax declarations — MUST match DB declaration_type_enum exactly.
    Source: SELECT enumlabel FROM pg_enum (34 values, verified 2026-03-10)
    """
    # General taxes
    INCOME_TAX = "income_tax"
    CORPORATE_TAX = "corporate_tax"
    VAT_DECLARATION = "vat_declaration"
    SOCIAL_CONTRIBUTION = "social_contribution"
    PROPERTY_TAX = "property_tax"
    OTHER_TAX = "other_tax"

    # Settlement & vouchers
    SETTLEMENT_VOUCHER = "settlement_voucher"
    COMMON_VOUCHER = "common_voucher"

    # Minimum fiscal contributions
    MINIMUM_FISCAL_CONTRIBUTION = "minimum_fiscal_contribution"
    MINIMUM_FISCAL_OIL_MINING = "minimum_fiscal_oil_mining"
    CUOTA_MIN_PETROLERA = "cuota_min_petrolera"
    CUOTA_MIN_COMUN = "cuota_min_comun"

    # IVA (90% volume)
    IVA_DESTAJO = "iva_destajo"
    IVA_REAL = "iva_real"
    WITHHELD_VAT = "withheld_vat"
    ACTUAL_VAT = "actual_vat"

    # Petroleum products
    PETROLEUM_PRODUCTS_TAX = "petroleum_products_tax"
    PETROLEUM_PRODUCTS_TAX_IVS = "petroleum_products_tax_ivs"
    IMP_PROD_PETROLEROS_IVS = "imp_prod_petroleros_ivs"
    IMP_PROD_PETROLEROS_FMI = "imp_prod_petroleros_fmi"

    # Wages taxes
    WAGES_TAX_OIL_MINING = "wages_tax_oil_mining"
    WAGES_TAX_COMMON_SECTOR = "wages_tax_common_sector"
    IMP_SUELDOS_PETROLERO = "imp_sueldos_petrolero"
    IMP_SUELDOS_COMUN = "imp_sueldos_comun"

    # Withholdings — petroleum sector
    RETENCION_3PCT_PETROLERO = "retencion_3pct_petrolero"
    RETENCION_5PCT_PETROLERO = "retencion_5pct_petrolero"
    RETENCION_10PCT_NO_RESIDENTES_PETROLERO = "retencion_10pct_no_residentes_petrolero"
    WITHHOLDING_3PCT_OIL_MINING_RESIDENTS = "withholding_3pct_oil_mining_residents"
    WITHHOLDING_5PCT_OIL_MINING_RESIDENTS = "withholding_5pct_oil_mining_residents"
    WITHHOLDING_10PCT_OIL_MINING_NONRESIDENTS = "withholding_10pct_oil_mining_nonresidents"

    # Withholdings — common sector
    WITHHOLDING_10PCT_COMMON_RESIDENTS = "withholding_10pct_common_residents"
    RETENCION_10PCT_NO_RESIDENTES_COMUN = "retencion_10pct_no_residentes_comun"

    # Printed forms
    IMPRESO_COMUN = "impreso_comun"
    IMPRESO_LIQUIDACION = "impreso_liquidacion"


class DeclarationBase(BaseModel):
    """
    Base model for tax declaration

    ALIGNED WITH DATABASE_SCHEMA_REFERENCE.md table: tax_declarations
    """

    # Identifiers
    user_id: str = Field(..., description="User UUID owning the declaration")
    company_id: Optional[str] = Field(None, description="Company UUID (for business users)")

    # Declaration metadata - ALIGNED WITH DB
    declaration_type: DeclarationType = Field(..., description="Type of declaration (28 types)")
    fiscal_year: int = Field(..., ge=2000, le=2100, description="Fiscal year (YYYY) - DB: fiscal_year")
    fiscal_period: Optional[str] = Field(None, max_length=20, description="Fiscal period (varchar) - DB: fiscal_period")
    declaration_deadline: date = Field(..., description="Declaration deadline (NOT NULL) - DB: declaration_deadline")

    # Financial data - ALIGNED WITH DB
    taxable_base: Optional[Decimal] = Field(None, ge=0, description="Taxable base - DB: taxable_base")
    calculated_tax: Optional[Decimal] = Field(None, ge=0, description="Calculated tax - DB: calculated_tax")
    deductions: Optional[Decimal] = Field(None, ge=0, description="Deductions - DB: deductions")
    credits: Optional[Decimal] = Field(None, ge=0, description="Credits - DB: credits")
    net_tax_due: Optional[Decimal] = Field(None, ge=0, description="Net tax due - DB: net_tax_due")

    # Status and validation - ALIGNED WITH DB
    status: DeclarationStatus = Field(default=DeclarationStatus.DRAFT, description="Declaration status - DB: status")

    # Additional data (JSONB) - ALIGNED WITH DB
    declared_data: Dict[str, Any] = Field(default_factory=dict, description="Declared data (JSONB NOT NULL DEFAULT '{{}}') - DB: declared_data")
    supporting_documents: Optional[List[str]] = Field(default_factory=list, description="Supporting documents (JSONB array, nullable) - DB: supporting_documents")

    # Agent/Processor notes - ALIGNED WITH DB
    taxpayer_notes: Optional[str] = Field(None, description="Taxpayer notes - DB: taxpayer_notes")
    processor_notes: Optional[str] = Field(None, description="Processor notes - DB: processor_notes")
    rejection_reason: Optional[str] = Field(None, description="Rejection reason - DB: rejection_reason")

    # Digital signature - ALIGNED WITH DB
    digital_signature: Optional[str] = Field(None, description="Digital signature - DB: digital_signature")

    # Declaration nature - ALIGNED WITH DB
    declaration_nature: Optional[str] = Field("original", max_length=20, description="Nature: original, rectificative, complementaire, annulation - DB: declaration_nature")
    original_declaration_id: Optional[str] = Field(None, description="Reference to original declaration if rectificative - DB: original_declaration_id")


class DeclarationCreate(DeclarationBase):
    """
    Schema for creating a new declaration

    Note: declaration_deadline is required by DB but can be set to a default value
    during creation (e.g., fiscal_year end date + grace period)
    """

    # Optional fields for draft creation
    taxable_base: Optional[Decimal] = Field(None, ge=0)
    fiscal_period: Optional[str] = None
    declaration_deadline: Optional[date] = None  # Can be calculated from fiscal_year if not provided

    @validator('fiscal_year', pre=True, always=True)
    def set_default_fiscal_year(cls, v):
        """Default to current year if not provided"""
        return v or datetime.now().year

    @validator('declaration_deadline', pre=True, always=True)
    def set_default_deadline(cls, v, values):
        """
        Set default deadline if not provided
        Default: End of fiscal year + 3 months grace period
        """
        if v is None and 'fiscal_year' in values:
            from datetime import date
            fiscal_year = values['fiscal_year']
            # Default: March 31st of following year (typical tax deadline)
            return date(fiscal_year + 1, 3, 31)
        return v


class DeclarationUpdate(BaseModel):
    """Schema for updating an existing declaration - ALIGNED WITH DB"""

    # Financial data (all optional for partial updates) - ALIGNED WITH DB
    taxable_base: Optional[Decimal] = Field(None, ge=0)
    calculated_tax: Optional[Decimal] = Field(None, ge=0)
    deductions: Optional[Decimal] = Field(None, ge=0)
    credits: Optional[Decimal] = Field(None, ge=0)
    net_tax_due: Optional[Decimal] = Field(None, ge=0)

    # Status updates - ALIGNED WITH DB
    status: Optional[DeclarationStatus] = None
    taxpayer_notes: Optional[str] = Field(None)
    processor_notes: Optional[str] = Field(None)
    rejection_reason: Optional[str] = Field(None)

    # Data updates - ALIGNED WITH DB
    declared_data: Optional[Dict[str, Any]] = None
    supporting_documents: Optional[List[str]] = None


class DeclarationResponse(DeclarationBase):
    """Schema for declaration response - ALIGNED WITH DB"""

    # Database fields - ALIGNED WITH DB
    id: str = Field(..., description="Declaration UUID - DB: id")
    declaration_number: str = Field(..., description="Declaration number (unique) - DB: declaration_number")
    created_at: datetime = Field(..., description="Creation timestamp - DB: created_at")
    updated_at: datetime = Field(..., description="Last update timestamp - DB: updated_at")
    submitted_at: Optional[datetime] = Field(None, description="Submission timestamp - DB: submitted_at")
    processed_at: Optional[datetime] = Field(None, description="Processing timestamp - DB: processed_at")

    # Processor info - ALIGNED WITH DB
    processed_by: Optional[str] = Field(None, description="Processor/Agent UUID - DB: processed_by")

    # Signature - ALIGNED WITH DB
    signature_timestamp: Optional[datetime] = Field(None, description="Signature timestamp - DB: signature_timestamp")

    # Related entities (populated by joins)
    user_email: Optional[str] = Field(None, description="User email (from join)")
    company_name: Optional[str] = Field(None, description="Company name (from join)")
    processor_name: Optional[str] = Field(None, description="Processor name (from join)")

    class Config:
        from_attributes = True


class DeclarationListResponse(BaseModel):
    """Schema for paginated declaration list"""

    declarations: List[DeclarationResponse] = Field(..., description="List of declarations")
    total: int = Field(..., description="Total count")
    page: int = Field(..., ge=1, description="Current page")
    page_size: int = Field(..., ge=1, le=100, description="Items per page")
    total_pages: int = Field(..., ge=0, description="Total pages")


class WorkflowStage(BaseModel):
    """Single workflow stage"""
    stage: str = Field(..., description="Stage identifier")
    name: str = Field(..., description="Stage display name")
    completed: bool = Field(..., description="Whether this stage is completed")


class DeclarationWorkflowStatus(BaseModel):
    """
    Workflow status for a declaration
    Business logic for tracking declaration progress through stages
    """
    declaration_id: str = Field(..., description="Declaration UUID")
    current_stage: str = Field(..., description="Current workflow stage")
    stages: List[WorkflowStage] = Field(..., description="All workflow stages with completion status")
    next_actions: List[str] = Field(..., description="Available actions for current stage")

    # Additional context
    status: DeclarationStatus = Field(..., description="Current declaration status")
    submitted_at: Optional[datetime] = Field(None, description="Submission timestamp")
    processed_at: Optional[datetime] = Field(None, description="Processing timestamp")
    processed_by: Optional[str] = Field(None, description="Processor UUID")


# ========== SEARCH AND FILTERING ==========

class DeclarationSearchFilter(BaseModel):
    """
    Model for declaration search and filtering
    Used for querying declarations with various filters
    """
    # User/Company filters
    user_id: Optional[str] = Field(None, description="Filter by user ID")
    company_id: Optional[str] = Field(None, description="Filter by company ID")

    # Declaration filters
    status: Optional[DeclarationStatus] = Field(None, description="Filter by status")
    declaration_type: Optional[DeclarationType] = Field(None, description="Filter by type")
    declaration_nature: Optional[str] = Field(None, description="Filter by nature (original, rectificative, etc.)")

    # Fiscal period filters
    fiscal_year: Optional[int] = Field(None, ge=2000, le=2100, description="Filter by fiscal year")
    fiscal_period: Optional[str] = Field(None, description="Filter by fiscal period")

    # Date filters
    created_after: Optional[datetime] = Field(None, description="Created after date")
    created_before: Optional[datetime] = Field(None, description="Created before date")
    submitted_after: Optional[datetime] = Field(None, description="Submitted after date")
    submitted_before: Optional[datetime] = Field(None, description="Submitted before date")
    deadline_after: Optional[date] = Field(None, description="Deadline after date")
    deadline_before: Optional[date] = Field(None, description="Deadline before date")

    # Search
    declaration_number: Optional[str] = Field(None, description="Search by declaration number")
    search_query: Optional[str] = Field(None, description="Full-text search query")

    # Administrative filters
    processed_by: Optional[str] = Field(None, description="Filter by processor/agent UUID")


# ========== STATISTICS ==========

class DeclarationStats(BaseModel):
    """
    Model for declaration statistics
    Used for dashboard and reporting
    """
    # Count metrics
    total_declarations: int = Field(..., description="Total number of declarations")
    by_status: Dict[str, int] = Field(..., description="Count by status")
    by_type: Dict[str, int] = Field(..., description="Count by type")

    # Performance metrics
    average_processing_time_hours: float = Field(..., description="Average processing time in hours")
    completion_rate: float = Field(..., ge=0, le=100, description="Completion rate percentage")

    # Financial metrics
    total_tax_collected: Decimal = Field(..., description="Total tax collected (net_tax_due sum)")
    pending_tax: Decimal = Field(..., description="Pending tax amount (draft + submitted)")

    # Time-based metrics
    declarations_this_month: int = Field(..., description="Declarations this month")
    declarations_this_week: int = Field(..., description="Declarations this week")

    # Popular types (top 5)
    popular_types: List[Dict[str, Any]] = Field(..., description="Most used declaration types")


# ========== BULK OPERATIONS ==========

class BulkDeclarationOperation(BaseModel):
    """
    Model for bulk declaration operations
    Used for batch updates, approvals, etc.
    """
    declaration_ids: List[str] = Field(..., min_length=1, max_length=50, description="Declaration UUIDs (max 50)")
    operation: str = Field(..., description="Operation to perform: approve, reject, assign, etc.")
    parameters: Optional[Dict[str, Any]] = Field(None, description="Operation parameters")
    notes: Optional[str] = Field(None, max_length=500, description="Operation notes")


# ========== ACTIVITY TRACKING ==========

class DeclarationActivity(BaseModel):
    """
    Model for declaration activity tracking
    Used for audit trail and history
    """
    declaration_id: str = Field(..., description="Declaration UUID")
    user_id: str = Field(..., description="User performing action UUID")
    action: str = Field(..., description="Action performed: created, updated, submitted, approved, rejected, etc.")
    details: Optional[Dict[str, Any]] = Field(None, description="Action details (before/after values)")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Activity timestamp")
    ip_address: Optional[str] = Field(None, description="User IP address")
    user_agent: Optional[str] = Field(None, description="User agent")


# ========== NOTIFICATIONS ==========

class DeclarationNotification(BaseModel):
    """
    Model for declaration notifications
    Used for sending notifications to users
    """
    declaration_id: str = Field(..., description="Declaration UUID")
    recipient_id: str = Field(..., description="Recipient user UUID")
    notification_type: str = Field(..., description="Notification type: status_change, deadline_reminder, etc.")
    title: str = Field(..., max_length=200, description="Notification title")
    message: str = Field(..., max_length=1000, description="Notification message")
    channels: List[str] = Field(..., description="Notification channels: email, sms, push")
    sent_at: Optional[datetime] = Field(None, description="Send timestamp")
    read_at: Optional[datetime] = Field(None, description="Read timestamp")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")
