"""Field Mission Models — Pydantic v2 models for mission planning system."""

from datetime import date, datetime
from typing import Dict, List, Optional
from uuid import UUID
from enum import Enum

from pydantic import BaseModel, Field, field_validator


# ============================================================
# Enums
# ============================================================

class MissionStatus(str, Enum):
    planned = "planned"
    in_progress = "in_progress"
    completed = "completed"
    cancelled = "cancelled"


class MissionAgentStatus(str, Enum):
    assigned = "assigned"
    active = "active"
    completed = "completed"
    absent = "absent"


# ============================================================
# Request Models
# ============================================================

class MissionCreate(BaseModel):
    """Create a new field mission."""
    mission_date: date
    entity_location_id: Optional[UUID] = None  # Auto-resolved from supervisor profile if omitted
    title: Optional[str] = Field(None, max_length=200)
    notes: Optional[str] = Field(None, max_length=2000)
    zone_ids: Optional[List[UUID]] = None


class MissionUpdate(BaseModel):
    """Update an existing field mission."""
    title: Optional[str] = Field(None, max_length=200)
    notes: Optional[str] = Field(None, max_length=2000)
    zone_ids: Optional[List[UUID]] = None
    status: Optional[MissionStatus] = None


class MissionAgentAssign(BaseModel):
    """Assign a single agent to a mission."""
    agent_id: UUID
    agent_profile_id: UUID
    assigned_zones: Optional[List[UUID]] = None
    target_inspections: int = Field(10, ge=1, le=100)
    notes: Optional[str] = Field(None, max_length=2000)


class MissionAgentBatchAssign(BaseModel):
    """Batch assign agents to a mission."""
    agents: List[MissionAgentAssign] = Field(..., min_length=1)

    @field_validator("agents")
    @classmethod
    def validate_no_duplicate_agents(cls, v):
        agent_ids = [a.agent_id for a in v]
        if len(agent_ids) != len(set(agent_ids)):
            raise ValueError("Duplicate agent_id in batch assignment")
        return v


class MissionCompleteRequest(BaseModel):
    """Complete a mission."""
    notes: Optional[str] = Field(None, max_length=2000)


class AgentStatusUpdate(BaseModel):
    """Update agent status within a mission."""
    status: MissionAgentStatus
    reason: Optional[str] = Field(None, max_length=500)


# ============================================================
# Response Models
# ============================================================

class MissionAgentResponse(BaseModel):
    """Full mission agent response."""
    model_config = {"from_attributes": True}

    id: UUID
    mission_id: UUID
    agent_id: UUID
    agent_profile_id: UUID
    assigned_zones: List[UUID] = []
    target_inspections: int = 10
    status: MissionAgentStatus
    actual_inspections: int = 0
    notes: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime

    # Enriched fields (from JOINs)
    agent_name: str = ""
    progress_pct: float = 0.0


class MissionResponse(BaseModel):
    """Full mission response."""
    model_config = {"from_attributes": True}

    id: UUID
    entity_id: UUID
    entity_location_id: UUID
    supervisor_id: UUID
    mission_date: date
    title: Optional[str] = None
    notes: Optional[str] = None
    zone_ids: List[UUID] = []
    status: MissionStatus
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    # Enriched fields (from JOINs)
    entity_code: str = ""
    location_name: str = ""
    supervisor_name: str = ""
    agents: List[MissionAgentResponse] = []
    total_inspections: int = 0
    total_target: int = 0


class MissionListItem(BaseModel):
    """Compact mission for list views."""
    model_config = {"from_attributes": True}

    id: UUID
    mission_date: date
    title: Optional[str] = None
    status: MissionStatus
    agents_count: int = 0
    inspections_done: int = 0
    inspections_target: int = 0
    entity_code: str = ""
    location_name: str = ""


class MissionListResponse(BaseModel):
    """Paginated mission list."""
    items: List[MissionListItem]
    total: int


class ZoneSuggestion(BaseModel):
    """Zone suggestion for mission planning."""
    model_config = {"from_attributes": True}

    zone_id: UUID
    zone_code: str
    zone_name: str
    zone_tier: str
    days_since_last_inspection: Optional[int] = None
    pending_obligations_count: int = 0
    suggested_priority: str = Field(..., pattern="^(high|medium|low)$")


class AgentAvailability(BaseModel):
    """Agent availability for mission planning."""
    model_config = {"from_attributes": True}

    agent_id: UUID
    agent_profile_id: UUID
    agent_name: str
    is_available: bool
    current_mission: Optional[str] = None
    working_days: Optional[List[int]] = None
    availability_status: str
