"""Filter Preset Models — Pydantic v2 models for supervisor filter presets."""

from datetime import datetime
from typing import Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


# ============================================================
# Constants
# ============================================================

VALID_TABLE_KEYS = (
    "inspections",
    "reconciliation",
    "seals",
    "agents",
    "missions",
    "zones",
)


# ============================================================
# Request Models
# ============================================================

class FilterPresetCreate(BaseModel):
    """Create a new filter preset for a supervisor table."""
    preset_name: str = Field(..., max_length=100)
    table_key: str = Field(..., max_length=50)
    filters: Dict = Field(default_factory=dict)
    column_visibility: Optional[Dict] = None
    sort_config: Optional[Dict] = None
    is_default: bool = Field(default=False)

    @field_validator("table_key")
    @classmethod
    def validate_table_key(cls, v: str) -> str:
        if v not in VALID_TABLE_KEYS:
            raise ValueError(
                f"table_key must be one of {VALID_TABLE_KEYS}, got '{v}'"
            )
        return v


class FilterPresetUpdate(BaseModel):
    """Update an existing filter preset."""
    preset_name: Optional[str] = Field(None, max_length=100)
    filters: Optional[Dict] = None
    column_visibility: Optional[Dict] = None
    sort_config: Optional[Dict] = None
    is_default: Optional[bool] = None


# ============================================================
# Response Models
# ============================================================

class FilterPresetResponse(BaseModel):
    """Single filter preset response."""
    id: UUID
    user_id: UUID
    preset_name: str
    table_key: str
    filters: Dict
    column_visibility: Optional[Dict] = None
    sort_config: Optional[Dict] = None
    is_default: bool
    created_at: datetime
    updated_at: datetime


class FilterPresetListResponse(BaseModel):
    """Paginated list of filter presets."""
    items: List[FilterPresetResponse]
    total: int
