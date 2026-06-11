"""Fiscal Config Rules Models — Pydantic v2 models for centralized configuration engine.

Specificity-based resolution: item(50) > ministry(30) > fee_type(20) > bundle(10) > global(0).
"""

from datetime import date, datetime
from typing import Dict, List, Optional
from uuid import UUID

from enum import Enum

import json

from pydantic import BaseModel, Field, ConfigDict, field_validator, model_validator


class ConfigType(str, Enum):
    """Type of configuration rule."""
    penalty = "penalty"
    deadline = "deadline"
    installment = "installment"
    processing_mode = "processing_mode"


class FeeTypeScope(str, Enum):
    """Fee type scope for config rules."""
    tesoro = "tesoro"
    municipal = "municipal"
    chamber = "chamber"


# ============================================================
# Request Models
# ============================================================

class ConfigRuleCreate(BaseModel):
    """Create a config rule."""
    config_type: ConfigType
    bundle_id: Optional[UUID] = None
    fee_type: Optional[FeeTypeScope] = None
    ministry_id: Optional[int] = None
    item_id: Optional[UUID] = None
    effective_from: Optional[date] = None  # defaults to CURRENT_DATE in DB
    effective_to: Optional[date] = None
    is_enabled: bool = True
    config: Dict = Field(..., description="Rule configuration JSON")
    name_es: Optional[str] = Field(None, max_length=200)
    description: Optional[str] = None

    @model_validator(mode="after")
    def validate_config_shape(self):
        """Validate config JSON matches config_type."""
        ct = self.config_type
        cfg = self.config

        if ct == ConfigType.penalty:
            if "rate" not in cfg:
                raise ValueError("Penalty config must include 'rate'")
            if cfg.get("rate", 0) < 0:
                raise ValueError("Penalty rate must be >= 0")

        elif ct == ConfigType.deadline:
            if "month" not in cfg or "day" not in cfg:
                raise ValueError("Deadline config must include 'month' and 'day'")
            if not (1 <= cfg["month"] <= 12):
                raise ValueError("Deadline month must be 1-12")
            if not (1 <= cfg["day"] <= 31):
                raise ValueError("Deadline day must be 1-31")

        elif ct == ConfigType.installment:
            if "max_installments" not in cfg:
                raise ValueError("Installment config must include 'max_installments'")
            if cfg["max_installments"] < 1:
                raise ValueError("max_installments must be >= 1")

        return self


class ConfigRuleUpdate(BaseModel):
    """Update a config rule (partial)."""
    effective_from: Optional[date] = None
    effective_to: Optional[date] = None
    is_enabled: Optional[bool] = None
    config: Optional[Dict] = None
    name_es: Optional[str] = Field(None, max_length=200)
    description: Optional[str] = None


# ============================================================
# Response Models
# ============================================================

class ConfigRuleResponse(BaseModel):
    """Config rule response with auto-computed specificity."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    config_type: str
    bundle_id: Optional[UUID] = None
    fee_type: Optional[str] = None
    ministry_id: Optional[int] = None
    item_id: Optional[UUID] = None
    effective_from: date
    effective_to: Optional[date] = None
    is_enabled: bool
    config: Dict

    @field_validator("config", mode="before")
    @classmethod
    def parse_config_json(cls, v):
        """Handle JSONB returned as string from asyncpg."""
        if isinstance(v, str):
            return json.loads(v)
        return v
    specificity: int
    name_es: Optional[str] = None
    description: Optional[str] = None
    created_by: Optional[UUID] = None
    updated_by: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime

    # Enriched fields (from JOINs)
    bundle_name: Optional[str] = None
    ministry_name: Optional[str] = None


class ConfigRuleListResponse(BaseModel):
    """Paginated list of config rules."""
    items: List[ConfigRuleResponse]
    total: int
    page: int
    page_size: int


class RecomputeResult(BaseModel):
    """Result of a recompute operation."""
    affected_items: int
    bundle_id: Optional[UUID] = None
