"""
Assignment Rule Models - Pydantic schemas for assignment rules

Based on DATABASE_SCHEMA_REFERENCE.md (2026-01-18):
- Table: assignment_rules
- Uses rule_status_enum (active, inactive, draft, archived)
- JSONB columns: conditions, actions
"""

from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime
from uuid import UUID
from enum import Enum


class RuleStatus(str, Enum):
    """Rule status enum - aligned with rule_status_enum in DB"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    DRAFT = "draft"
    ARCHIVED = "archived"


class AssignmentRuleCreate(BaseModel):
    """Create assignment rule request - aligned with assignment_rules table"""
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    entity_type: str = Field(..., max_length=50, description="Entity type (e.g., ministry, dgi)")
    entity_id: Optional[str] = Field(None, max_length=100, description="Entity ID")
    conditions: Dict[str, Any] = Field(default_factory=dict, description="JSONB conditions for rule matching")
    actions: Dict[str, Any] = Field(default_factory=dict, description="JSONB actions to execute")
    priority: int = Field(default=50, ge=1, le=100, description="Rule priority (higher = more important)")
    status: RuleStatus = Field(default=RuleStatus.DRAFT, description="Rule status")


class AssignmentRuleUpdate(BaseModel):
    """Update assignment rule request"""
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    entity_type: Optional[str] = Field(None, max_length=50)
    entity_id: Optional[str] = Field(None, max_length=100)
    conditions: Optional[Dict[str, Any]] = None
    actions: Optional[Dict[str, Any]] = None
    priority: Optional[int] = Field(None, ge=1, le=100)
    status: Optional[RuleStatus] = None


class AssignmentRule(BaseModel):
    """Assignment rule response model - aligned with assignment_rules table"""
    id: UUID
    name: str
    description: Optional[str] = None
    entity_type: str
    entity_id: Optional[str] = None
    conditions: Dict[str, Any] = Field(default_factory=dict)
    actions: Dict[str, Any] = Field(default_factory=dict)
    priority: int = 50
    status: RuleStatus = RuleStatus.DRAFT
    # Statistics
    times_applied: int = 0
    times_matched: int = 0
    successful_assignments: int = 0
    failed_assignments: int = 0
    success_rate: float = 0.0
    last_applied_at: Optional[datetime] = None
    # Audit
    created_by: UUID
    created_at: datetime
    updated_at: Optional[datetime] = None
    updated_by: Optional[UUID] = None

    class Config:
        from_attributes = True


class RuleMatchResult(BaseModel):
    """Result of rule matching evaluation"""
    rule_id: UUID
    rule_name: str
    matched: bool
    score: float = 0.0
    actions: Dict[str, Any] = Field(default_factory=dict)
    reason: Optional[str] = None
