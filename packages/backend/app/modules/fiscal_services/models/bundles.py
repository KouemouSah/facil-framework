"""Service Bundles Models — Pydantic v2 models for commerce zone-based pricing."""

from datetime import datetime
from decimal import Decimal
from typing import List, Optional
from uuid import UUID

from enum import Enum

import json as _json

from pydantic import BaseModel, Field, ConfigDict, field_validator


class FeeType(str, Enum):
    """Fee type discriminator for bundle items."""
    tesoro = "tesoro"
    municipal = "municipal"
    chamber = "chamber"


# ============================================================
# Commerce Zones
# ============================================================

class CommerceZoneResponse(BaseModel):
    """Zone géographique pour tarification."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    zone_code: str
    zone_tier: str
    zone_rank: int
    name_es: str
    description_es: Optional[str] = None
    display_order: int


# ============================================================
# Service Bundles
# ============================================================

class ProcessingMode(str, Enum):
    """Bundle processing mode."""
    per_line = "per_line"
    consolidated = "consolidated"


class ServiceBundleBase(BaseModel):
    """Base fields for service bundles."""
    bundle_code: str = Field(..., max_length=50)
    commerce_type: str = Field(..., max_length=100)
    name_es: str = Field(..., max_length=300)
    description_es: Optional[str] = None
    legal_reference: Optional[str] = None
    is_active: bool = True
    installment_eligible: bool = False
    max_installments: int = Field(default=1, ge=1, le=12)
    installment_frequency: str = Field(default="monthly")
    public_installment_visible: bool = False
    # OMS fields (Migration 218 Phase 1.4)
    processing_mode: ProcessingMode = ProcessingMode.per_line
    deadline_month: int = Field(default=4, ge=1, le=12)
    deadline_day: int = Field(default=30, ge=1, le=31)


class ServiceBundleCreate(ServiceBundleBase):
    """Create a new service bundle."""
    pass


class ServiceBundleUpdate(BaseModel):
    """Update an existing service bundle (all fields optional)."""
    bundle_code: Optional[str] = Field(None, max_length=50)
    commerce_type: Optional[str] = Field(None, max_length=100)
    name_es: Optional[str] = Field(None, max_length=300)
    description_es: Optional[str] = None
    legal_reference: Optional[str] = None
    is_active: Optional[bool] = None
    installment_eligible: Optional[bool] = None
    max_installments: Optional[int] = Field(None, ge=1, le=12)
    installment_frequency: Optional[str] = None
    public_installment_visible: Optional[bool] = None
    processing_mode: Optional[ProcessingMode] = None
    deadline_month: Optional[int] = Field(None, ge=1, le=12)
    deadline_day: Optional[int] = Field(None, ge=1, le=31)


class ServiceBundleResponse(ServiceBundleBase):
    """Service bundle response with metadata (admin)."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    created_by: Optional[UUID] = None
    updated_by: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime
    # Enriched fields (from queries)
    item_count: int = 0
    zone_count: int = 0


class ServiceBundlePublicResponse(BaseModel):
    """Minimal bundle info for public-facing pages (no admin fields)."""
    model_config = ConfigDict(from_attributes=True)

    bundle_code: str
    commerce_type: str
    name_es: str
    description_es: Optional[str] = None
    legal_reference: Optional[str] = None
    installment_eligible: bool = False


# ============================================================
# Bundle Items
# ============================================================

class BundleItemCreate(BaseModel):
    """Create/upsert a bundle item."""
    fiscal_service_id: int
    zone_id: UUID
    ministry_id: Optional[int] = None
    amount: Decimal = Field(..., ge=0)
    fee_type: FeeType = FeeType.tesoro
    is_fixed_across_zones: bool = False
    display_order: int = 0
    notes: Optional[str] = None
    is_active: bool = True


class BundleItemResponse(BaseModel):
    """Bundle item with enriched service/ministry names."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    bundle_id: UUID
    fiscal_service_id: int
    zone_id: UUID
    ministry_id: Optional[int] = None
    amount: Decimal
    fee_type: str = "tesoro"
    is_fixed_across_zones: bool
    display_order: int
    notes: Optional[str] = None
    is_active: bool
    # OMS fields (Migration 218 Phase 1.5)
    # asyncpg returns JSONB as str — Pydantic v2 field_validator parses before validation
    effective_penalty: Optional[dict] = None
    effective_deadline: Optional[dict] = None
    config_resolved_at: Optional[datetime] = None
    requires_document: bool = False
    document_template_id: Optional[int] = None
    # Enriched from JOINs
    service_code: Optional[str] = None
    service_name: Optional[str] = None
    ministry_name: Optional[str] = None

    @field_validator('effective_penalty', 'effective_deadline', mode='before')
    @classmethod
    def parse_jsonb_str(cls, v):
        """asyncpg returns JSONB as str without codec — parse to dict."""
        if isinstance(v, str):
            try:
                return _json.loads(v)
            except (ValueError, TypeError):
                return None
        return v


# ============================================================
# Bundle with Items (for a specific zone)
# ============================================================

class FeeTypeTotals(BaseModel):
    """Sub-totals by fee type."""
    tesoro: Decimal = Decimal("0")
    municipal: Decimal = Decimal("0")
    chamber: Decimal = Decimal("0")
    grand_total: Decimal = Decimal("0")


class BundleWithItemsResponse(BaseModel):
    """Bundle detail for a specific zone, with items and total."""
    model_config = ConfigDict(from_attributes=True)

    bundle: ServiceBundleResponse
    zone: CommerceZoneResponse
    items: List[BundleItemResponse]
    total_amount: Decimal
    fee_type_totals: Optional[FeeTypeTotals] = None
    currency: str = "XAF"
    # Installment info
    installment_eligible: bool = False
    max_installments: int = 1
    installment_preview: Optional[List["InstallmentPreviewItem"]] = None


class InstallmentPreviewItem(BaseModel):
    """Single installment in a preview."""
    installment_number: int
    amount_due: Decimal
    due_date: str  # ISO date string
    cumulative_paid: Decimal


# ============================================================
# Pricing Matrix (all zones for a bundle)
# ============================================================

class ZoneTotalItem(BaseModel):
    """Total for a single zone in the matrix."""
    zone: CommerceZoneResponse
    total_amount: Decimal
    item_count: int
    tesoro_total: Decimal = Decimal("0")
    municipal_total: Decimal = Decimal("0")
    chamber_total: Decimal = Decimal("0")


class PricingMatrixResponse(BaseModel):
    """Complete pricing matrix: all zones × all services for a bundle."""
    bundle: ServiceBundleResponse
    zones: List[CommerceZoneResponse]
    items: List[BundleItemResponse]  # All items across all zones
    zone_totals: List[ZoneTotalItem]
    currency: str = "XAF"


# ============================================================
# Bundle Documents (deduced from services)
# ============================================================

class BundleDocumentItem(BaseModel):
    """Document required by a bundle (deduced from service_document_assignments)."""
    document_template_id: int
    document_name_es: str
    template_code: Optional[str] = None
    is_required: bool = True


# ============================================================
# Simulator Response (single-call public endpoint)
# ============================================================

class FeeGroupItems(BaseModel):
    """Items grouped by fee type with sub-total."""
    fee_type: str
    label_es: str
    items: List[BundleItemResponse]
    subtotal: Decimal


class SimulatorResponse(BaseModel):
    """Complete bundle pricing simulation for commerce_type + zone."""
    model_config = ConfigDict(from_attributes=True)

    bundle: ServiceBundlePublicResponse
    zone: CommerceZoneResponse
    fee_groups: List[FeeGroupItems]
    grand_total: Decimal
    documents: List[BundleDocumentItem]
    installment_preview: Optional[dict] = None
    currency: str = "XAF"


# ============================================================
# Paginated List
# ============================================================

class BundleListResponse(BaseModel):
    """Paginated list of bundles."""
    items: List[ServiceBundleResponse]
    total: int
    page: int
    page_size: int


# ============================================================
# Copy Zone Prices
# ============================================================

class CopyZonePricesRequest(BaseModel):
    """Copy all item prices from one zone to another."""
    source_zone_id: UUID
    target_zone_id: UUID
    multiplier: Decimal = Field(default=Decimal("1.0"), ge=0)


# ============================================================
# Bulk Import
# ============================================================

class BulkImportItem(BaseModel):
    """Single item in a bulk import payload."""
    service_code: str
    zone_code: str
    amount: Decimal = Field(..., ge=0)
    fee_type: FeeType = FeeType.tesoro
    ministry_id: Optional[int] = None
    is_fixed_across_zones: bool = False


class BulkImportRequest(BaseModel):
    """Bulk import items for a bundle (from Excel/PDF parsing)."""
    items: List[BulkImportItem]


class ReorderItemRequest(BaseModel):
    """Reorder items — list of item IDs in desired order."""
    item_ids: List[UUID]


# Forward ref update
BundleWithItemsResponse.model_rebuild()
