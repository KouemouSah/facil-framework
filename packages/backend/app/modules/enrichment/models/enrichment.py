"""Pydantic v2 models for the enrichment queue."""

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class EnrichmentTask(BaseModel):
    """Single enrichment queue task."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    fiscal_service_id: int
    task_type: str
    status: str
    priority: int = 0
    attempts: int = 0
    max_attempts: int = 3
    input_data: Optional[Dict[str, Any]] = None
    output_data: Optional[Dict[str, Any]] = None
    tokens_used: Optional[int] = None
    error_message: Optional[str] = None
    created_at: Optional[datetime] = None
    processed_at: Optional[datetime] = None


class EnrichmentStats(BaseModel):
    """Aggregated enrichment statistics."""

    total_services: int = 0
    with_description: int = 0
    with_description_pct: float = 0.0
    desc_manual: int = 0
    desc_ai_generated: int = 0
    desc_ai_draft: int = 0
    desc_ai_approved: int = 0
    with_keywords: int = 0
    with_keywords_pct: float = 0.0
    with_translations_fr: int = 0
    with_translations_en: int = 0
    queue_pending: int = 0
    queue_processing: int = 0
    queue_completed: int = 0
    queue_failed: int = 0
    breakdown: List[Dict[str, Any]] = Field(default_factory=list)


class EnrichmentProcessResult(BaseModel):
    """Result of a cron batch processing run."""

    processed: int = 0
    failed: int = 0
    skipped: int = 0
    tokens_total: int = 0
    details: List[Dict[str, Any]] = Field(default_factory=list)


class EnrichmentSeedResult(BaseModel):
    """Result of seed-batch operation."""

    enqueued_descriptions: int = 0
    enqueued_translations: int = 0
    enqueued_keywords: int = 0
    auto_processing: bool = False


class EnrichmentProgressResponse(BaseModel):
    """Progress of the background enrichment agent."""

    job_id: Optional[str] = None
    total: int = 0
    processed: int = 0
    failed: int = 0
    skipped: int = 0
    tokens_total: int = 0
    status: str = "idle"  # idle, running, circuit_breaker_pause, completed, already_running


class EnrichmentReviewRequest(BaseModel):
    """Admin review action for AI-generated description."""

    action: Literal["approve", "reject"]
    edited_text: Optional[str] = Field(None, max_length=500,
        description="Optional edited description text (on approve, replaces AI text)")

    @field_validator("edited_text")
    @classmethod
    def strip_edited_text(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            v = v.strip()
            return v if v else None
        return v


class EnrichmentReviewResponse(BaseModel):
    """Response after admin reviews a description."""

    service_id: int
    action: str
    previous_source: Optional[str] = None
    new_source: Optional[str] = None


class BulkVisibilityRequest(BaseModel):
    """Bulk toggle description_visible for fiscal services."""

    visible: bool = Field(..., description="Target visibility state")
    description_source: Optional[Literal[
        "manual", "ai_generated", "ai_draft", "ai_approved"
    ]] = Field(None, description="Filter by description source (optional)")
    ministry_id: Optional[int] = Field(None, description="Filter by ministry (optional)")


class BulkVisibilityResponse(BaseModel):
    """Result of bulk visibility toggle."""

    affected: int = 0
    visible: bool = False
    filters_applied: Dict[str, Any] = Field(default_factory=dict)


class PendingDraftItem(BaseModel):
    """A service/ministry with an AI draft description awaiting review."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    service_code: Optional[str] = None
    name_es: str
    description_es: Optional[str] = None
    description_source: Optional[str] = None
    category_name: Optional[str] = None
    ministry_name: Optional[str] = None
    updated_at: Optional[datetime] = None
