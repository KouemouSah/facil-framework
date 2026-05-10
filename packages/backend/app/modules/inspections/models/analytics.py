"""Inspection Analytics Models — Pydantic v2 models for analytics endpoints."""

from datetime import date
from decimal import Decimal
from typing import Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


# ============================================================
# Request Models
# ============================================================

class AnalyticsDateRange(BaseModel):
    """Date range filter with granularity for trend analytics."""
    date_from: Optional[date] = None
    date_to: Optional[date] = None
    granularity: str = Field("weekly", pattern="^(daily|weekly|monthly)$")

    @field_validator("date_to")
    @classmethod
    def validate_date_range(cls, v, info):
        date_from = info.data.get("date_from")
        if v and date_from and v < date_from:
            raise ValueError("date_to must be after date_from")
        return v


class CompareRequest(BaseModel):
    """Compare agents, zones, or time periods side by side."""
    compare_type: str = Field(..., pattern="^(agents|zones|periods)$")
    ids: List[str] = Field(..., min_length=2, max_length=2)
    date_from: Optional[date] = None
    date_to: Optional[date] = None

    @field_validator("date_to")
    @classmethod
    def validate_date_range(cls, v, info):
        date_from = info.data.get("date_from")
        if v and date_from and v < date_from:
            raise ValueError("date_to must be after date_from")
        return v


# ============================================================
# Response Models — Agent Performance
# ============================================================

class AgentPerformanceItem(BaseModel):
    """Single agent performance metrics."""
    model_config = {"from_attributes": True}

    agent_id: UUID
    agent_name: str
    entity_code: str
    inspections_total: int = 0
    conforme: int = 0
    non_conforme: int = 0
    conformity_rate: float = 0.0
    collections_count: int = 0
    collected_amount: Decimal = Decimal("0")
    med_count: int = 0
    seal_count: int = 0
    avg_duration_minutes: Optional[float] = None
    zones_covered: int = 0
    days_active: int = 0


class AgentPerformanceResponse(BaseModel):
    """Paginated agent performance list."""
    items: List[AgentPerformanceItem]
    total: int
    period_start: date
    period_end: date


class AgentDetailResponse(AgentPerformanceItem):
    """Extended agent performance with breakdown details."""
    recent_inspections: List[Dict] = []
    zone_breakdown: List[Dict] = []
    weekly_trend: List[Dict] = []


# ============================================================
# Response Models — Zone Analytics
# ============================================================

class ZoneAnalyticsItem(BaseModel):
    """Single zone analytics metrics."""
    model_config = {"from_attributes": True}

    zone_id: Optional[UUID] = None
    zone_code: str
    zone_name: str
    zone_tier: str
    inspections: int = 0
    conforme: int = 0
    non_conforme: int = 0
    conformity_rate: float = 0.0
    collections: int = 0
    collected_amount: Decimal = Decimal("0")
    med_count: int = 0
    seal_count: int = 0
    agents_active: int = 0
    avg_duration_minutes: Optional[float] = None
    days_since_last_inspection: Optional[int] = None
    coverage_status: str = Field("ok", pattern="^(ok|warning|critical)$")


class ZoneAnalyticsResponse(BaseModel):
    """Zone analytics summary."""
    items: List[ZoneAnalyticsItem]
    total_zones: int
    covered_zones: int
    stale_zones: int


# ============================================================
# Response Models — Trends
# ============================================================

class TrendPoint(BaseModel):
    """Single data point in a time series trend."""
    model_config = {"from_attributes": True}

    period: str
    period_start: date
    inspections: int = 0
    conforme: int = 0
    non_conforme: int = 0
    conformity_rate: float = 0.0
    collections: int = 0
    collected_amount: Decimal = Decimal("0")
    med_count: int = 0
    seal_count: int = 0


class TrendResponse(BaseModel):
    """Time series trend data."""
    data: List[TrendPoint]
    granularity: str
    date_from: date
    date_to: date


# ============================================================
# Response Models — Comparison
# ============================================================

class CompareItem(BaseModel):
    """Single item in a comparison."""
    model_config = {"from_attributes": True}

    label: str
    inspections: int = 0
    conforme: int = 0
    non_conforme: int = 0
    conformity_rate: float = 0.0
    collections: int = 0
    collected_amount: Decimal = Decimal("0")
    med_count: int = 0
    seal_count: int = 0


class CompareResponse(BaseModel):
    """Side-by-side comparison result."""
    compare_type: str
    items: List[CompareItem]
    date_from: date
    date_to: date


# ============================================================
# Response Models — Priority Zones
# ============================================================

class PriorityZoneItem(BaseModel):
    """Zone prioritized for next inspection round."""
    model_config = {"from_attributes": True}

    zone_id: Optional[UUID] = None
    zone_code: str
    zone_name: str
    zone_tier: str
    days_since_last_inspection: int = 0
    pending_obligations: int = 0
    pending_amount: Decimal = Decimal("0")
    priority_score: float = 0.0
    recommended_agents: int = 0


class PriorityZonesResponse(BaseModel):
    """Prioritized zones list."""
    items: List[PriorityZoneItem]
    total: int
