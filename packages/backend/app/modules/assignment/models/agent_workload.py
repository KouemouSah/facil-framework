"""
Agent Workload Models - Pydantic schemas for agent workload tracking

Based on DATABASE_SCHEMA_REFERENCE.md (2026-01-18):
- Table: agent_workloads
- Table: agent_profiles
- Table: assignments
- Migration 054: agent_profile_id is the primary identifier
"""

from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Dict, Any
from datetime import datetime, date
from uuid import UUID
import json


class AgentWorkload(BaseModel):
    """Agent workload information - aligned with agent_workloads table

    Primary identifier: agent_profile_id (from agent_profiles table)
    """
    # Primary identifier (Migration 054) - from agent_profiles.id
    agent_profile_id: UUID = Field(..., description="UUID from agent_profiles table")
    # Reference to users table via agent_profiles.user_id
    user_id: Optional[UUID] = Field(None, description="Reference to users.id via agent_profiles.user_id")

    # From users table join
    agent_name: str = Field(..., description="COALESCE(users.full_name, first_name || ' ' || last_name)")
    agent_email: Optional[str] = Field(None, description="users.email")

    # From agent_workloads table (DB column names)
    current_assignments: int = Field(0, description="DB: current_assignments")
    max_concurrent_assignments: int = Field(20, description="DB: max_concurrent_assignments")
    pending_declarations: int = Field(0, description="DB: pending_declarations")
    in_progress_declarations: int = Field(0, description="DB: in_progress_declarations")
    capacity_percentage: float = Field(0.0, description="DB: capacity_percentage")
    workload_status: str = Field("available", description="DB: workload_status (workload_status_enum)")
    availability: str = Field("available", description="DB: availability (agent_availability_enum)")
    success_rate: float = Field(0.0, description="DB: success_rate")
    avg_processing_time_hours: Optional[float] = Field(None, description="DB: avg_processing_time_hours")
    last_assignment_at: Optional[datetime] = Field(None, description="DB: last_assignment_at")

    # From agent_profiles table
    specializations: Optional[List[str]] = Field(None, description="DB: agent_profiles.specializations (JSONB)")

    @field_validator("specializations", mode="before")
    @classmethod
    def parse_jsonb_specializations(cls, v):
        if v is None:
            return None
        if isinstance(v, str):
            try:
                parsed = json.loads(v)
                return parsed if isinstance(parsed, list) else None
            except (json.JSONDecodeError, TypeError):
                return None
        return v

    # Computed fields (not in DB)
    completed_today: int = Field(0, description="Computed from assignments")
    is_available: bool = Field(True, description="Computed from workload_status")

    class Config:
        from_attributes = True


class AgentWorkloadStats(BaseModel):
    """Agent workload statistics - computed from assignments table"""
    period_start: date
    period_end: date
    total_assigned: int = 0
    total_completed: int = 0
    average_processing_time_hours: float = 0.0
    completion_rate: float = 0.0


class AgentPerformanceMetrics(BaseModel):
    """Agent performance metrics - aligned with agent_performance_stats table

    Primary identifier: agent_profile_id (from agent_profiles table)
    """
    agent_profile_id: UUID = Field(..., description="UUID from agent_profiles table")
    agent_name: str
    period: str
    declarations_processed: int = 0
    average_time_to_complete_hours: float = 0.0
    on_time_completion_rate: float = 0.0
    rejection_rate: float = 0.0
    quality_score: float = 0.0
    ranking: Optional[int] = None


class WorkloadBalanceReport(BaseModel):
    """Workload balance report - computed metrics for team workload distribution

    Used by supervisor dashboard to assess team balance
    """
    total_agents: int = 0
    available_agents: int = 0
    busy_agents: int = 0
    overloaded_agents: int = 0
    unavailable_agents: int = 0
    total_assignments: int = 0
    avg_assignments_per_agent: float = 0.0
    min_assignments: int = 0
    max_assignments: int = 0
    balance_score: float = Field(
        default=100.0,
        ge=0,
        le=100,
        description="Balance score 0-100 (100=perfect balance)"
    )
    rebalancing_needed: bool = False
    rebalancing_recommendation: Optional[str] = None


class AgentCapacityForecast(BaseModel):
    """Agent capacity forecast - predictive metrics for workload planning

    Used by supervisor to plan future assignments
    """
    agent_profile_id: UUID = Field(..., description="UUID from agent_profiles table")
    agent_name: str
    horizon_days: int = Field(default=7, description="Forecast horizon in days")
    # Current state
    current_assignments: int = 0
    current_capacity_pct: float = 0.0
    max_concurrent_assignments: int = 20
    # Forecast
    forecasted_completions: int = Field(
        default=0,
        description="Estimated assignments to complete in horizon period"
    )
    forecasted_new_assignments: int = Field(
        default=0,
        description="Estimated new assignments expected in horizon period"
    )
    forecasted_capacity_pct: float = Field(
        default=0.0,
        description="Estimated capacity % at end of horizon"
    )
    # Recommendations
    can_accept_new: bool = True
    max_recommended_new: int = Field(
        default=5,
        description="Maximum new assignments recommended"
    )
    forecast_confidence: float = Field(
        default=0.5,
        ge=0,
        le=1,
        description="Confidence level 0-1 based on historical data"
    )
