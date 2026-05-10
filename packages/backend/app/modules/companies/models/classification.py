"""
Classification Models — Pydantic schemas for company classification agent.

Tables: company_creation_drafts, company_classification_history
"""

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


# ── Enums ────────────────────────────────────────────────────────────────────

class DraftStatus(str, Enum):
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    NEEDS_INFO = "needs_info"
    AUTO_APPROVED = "auto_approved"
    ERROR = "error"


class DraftSourceType(str, Enum):
    UPLOAD = "upload"
    CSV = "csv"
    MANUAL = "manual"


class ClassificationTrigger(str, Enum):
    INITIAL = "initial"
    MANUAL = "manual"
    ANNUAL_CRON = "annual_cron"
    DATA_CHANGE = "data_change"
    CSV_IMPORT = "csv_import"


# ── Classification Results ───────────────────────────────────────────────────

class ClassificationResult(BaseModel):
    """Result of classifying a company's fiscal regime."""
    regimen_fiscal: str = Field(
        ..., description="bundle | declarativo | exento | pendiente"
    )
    confidence: float = Field(..., ge=0.0, le=1.0)
    reason: str
    rules_applied: List[str] = []
    commerce_type: Optional[str] = None
    llm_validated: bool = False
    llm_issues: List[str] = []
    flags: List[str] = []
    suggested_actions: List[str] = []
    classification_details: Dict[str, Any] = Field(
        default_factory=dict,
        description="Extra details: zone_pricing, bundle_id, etc.",
    )


class ExtractionResult(BaseModel):
    """Result of LLM document extraction."""
    company_data: Dict[str, Any]
    extraction_confidence: float = Field(0.0, ge=0.0, le=1.0)
    fields_extracted: List[str] = []
    fields_missing: List[str] = []
    warnings: List[str] = []


class BatchClassificationResult(BaseModel):
    """Result of batch classification operation."""
    total: int
    classified: int
    auto_approved: int = 0
    pending_review: int = 0
    errors: int = 0
    results: List[Dict[str, Any]] = []


# ── Request Models ───────────────────────────────────────────────────────────

class ClassifySingleRequest(BaseModel):
    """Request to classify a single company."""
    legal_name: Optional[str] = None
    nif: Optional[str] = None
    forma_juridica: Optional[str] = None
    sector_actividad: Optional[str] = None
    subsector_actividad: Optional[str] = None
    objeto_social: Optional[str] = None
    commerce_type: Optional[str] = None
    capital_social: Optional[Decimal] = None
    employee_count: Optional[int] = None
    registration_number: Optional[str] = None
    zone_id: Optional[str] = None
    city_id: Optional[str] = None


class ClassifyBatchRequest(BaseModel):
    """Request to classify a batch of companies."""
    items: List[ClassifySingleRequest] = Field(
        ..., min_length=1, max_length=1000
    )
    zone_id: Optional[str] = None


class DraftActionRequest(BaseModel):
    """Request to approve/reject/request-info on a draft."""
    notes: Optional[str] = Field(None, max_length=2000)


class ReclassifyRequest(BaseModel):
    """Request to reclassify an existing company."""
    reason: str = Field("manual", max_length=500)


# ── Response Models ──────────────────────────────────────────────────────────

class DraftResponse(BaseModel):
    """Response for a single draft."""
    id: UUID
    source_type: str
    source_file_id: Optional[UUID] = None
    batch_id: Optional[UUID] = None
    company_data: Dict[str, Any] = {}
    regimen_fiscal: Optional[str] = None
    classification_confidence: Optional[float] = 0.0
    classification_reason: Optional[str] = None
    classification_details: Dict[str, Any] = {}
    extraction_confidence: Optional[float] = 0.0
    extraction_details: Dict[str, Any] = Field(default_factory=dict)
    status: str
    reviewer_notes: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    created_company_id: Optional[UUID] = None
    created_license_id: Optional[UUID] = None
    created_by: Optional[UUID] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class DraftListResponse(BaseModel):
    """Paginated list of drafts."""
    items: List[DraftResponse]
    total: int
    page: int
    page_size: int


class ClassificationHistoryEntry(BaseModel):
    """A single classification history entry."""
    id: UUID
    company_id: UUID
    old_regimen: Optional[str] = None
    new_regimen: str
    old_commerce_type: Optional[str] = None
    new_commerce_type: Optional[str] = None
    reason: str
    confidence: Optional[float] = 0.0
    triggered_by: str
    created_at: Optional[datetime] = None


class ClassificationStatsResponse(BaseModel):
    """Classification statistics for admin dashboard."""
    total_companies: int = 0
    by_regimen: Dict[str, int] = {}
    total_drafts: int = 0
    drafts_pending: int = 0
    drafts_approved: int = 0
    drafts_auto_approved: int = 0
    drafts_rejected: int = 0
    drafts_needs_info: int = 0
    auto_approval_rate: float = 0.0
    avg_confidence: float = 0.0
