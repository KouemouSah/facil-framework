"""
Agent Profile Models - New unified agent management

Based on agent_profiles table created in migration 047/048:
- agent_type: ministry_agent, entity_agent
- is_supervisor: boolean for supervisor capability
- Linked to entities and/or ministries
"""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime, time
from enum import Enum
from decimal import Decimal
from uuid import UUID


# ============================================================================
# ENUMS
# ============================================================================

class AgentType(str, Enum):
    """Type of agent based on organizational affiliation"""
    MINISTRY_AGENT = "ministry_agent"
    ENTITY_AGENT = "entity_agent"


# ============================================================================
# AGENT_PROFILES - Agent configuration and permissions
# ============================================================================

class AgentProfileBase(BaseModel):
    """Base agent profile fields"""
    user_id: UUID
    agent_type: AgentType
    is_supervisor: bool = False
    entity_id: Optional[UUID] = None
    entity_location_id: Optional[UUID] = None
    ministry_id: Optional[int] = None
    can_approve_unlimited: bool = False
    max_approval_amount: Optional[Decimal] = None
    can_escalate: bool = True
    can_assign_tasks: bool = False
    can_reassign: bool = False
    specializations: List[str] = Field(default_factory=list)
    working_hours_start: Optional[time] = None
    working_hours_end: Optional[time] = None
    working_days: List[int] = Field(default_factory=lambda: [1, 2, 3, 4, 5])
    is_active: bool = True
    is_backup_agent: bool = False
    backup_for_profile_id: Optional[UUID] = None


class AgentProfileCreate(BaseModel):
    """Create agent profile"""
    user_id: UUID
    agent_type: AgentType
    is_supervisor: bool = False
    entity_id: Optional[UUID] = None
    entity_location_id: Optional[UUID] = None
    ministry_id: Optional[int] = None
    can_approve_unlimited: bool = False
    max_approval_amount: Optional[Decimal] = None
    can_escalate: bool = True
    can_assign_tasks: bool = False
    can_reassign: bool = False
    specializations: List[str] = Field(default_factory=list)
    working_hours_start: Optional[time] = None
    working_hours_end: Optional[time] = None
    working_days: List[int] = Field(default_factory=lambda: [1, 2, 3, 4, 5])
    assigned_by: Optional[UUID] = None


class AgentProfileUpdate(BaseModel):
    """Update agent profile"""
    agent_type: Optional[AgentType] = None
    is_supervisor: Optional[bool] = None
    entity_id: Optional[UUID] = None
    entity_location_id: Optional[UUID] = None
    ministry_id: Optional[int] = None
    rbac_role_id: Optional[UUID] = Field(
        None,
        description="RBAC role ID to assign. Replaces user permissions with role's permissions."
    )
    can_approve_unlimited: Optional[bool] = None
    max_approval_amount: Optional[Decimal] = None
    can_escalate: Optional[bool] = None
    can_assign_tasks: Optional[bool] = None
    can_reassign: Optional[bool] = None
    specializations: Optional[List[str]] = None
    working_hours_start: Optional[time] = None
    working_hours_end: Optional[time] = None
    working_days: Optional[List[int]] = None
    is_active: Optional[bool] = None
    is_backup_agent: Optional[bool] = None
    backup_for_profile_id: Optional[UUID] = None


class AgentProfileResponse(AgentProfileBase):
    """Agent profile response"""
    id: UUID
    assigned_at: datetime
    assigned_by: Optional[UUID] = None
    deactivated_at: Optional[datetime] = None
    deactivated_by: Optional[UUID] = None
    deactivation_reason: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class AgentProfileWithDetails(AgentProfileResponse):
    """Agent profile with joined user/entity/ministry details"""
    # User details
    user_email: Optional[str] = None
    user_full_name: Optional[str] = None
    user_phone: Optional[str] = None

    # Entity details
    entity_code: Optional[str] = None
    entity_name: Optional[str] = None
    entity_type: Optional[str] = None  # 'entity' or 'department'
    parent_entity_id: Optional[UUID] = None
    parent_entity_code: Optional[str] = None
    parent_entity_name: Optional[str] = None

    # Location details (site-based routing)
    location_name: Optional[str] = None
    location_city: Optional[str] = None
    location_region: Optional[str] = None
    is_main_office: bool = False

    # Ministry details
    ministry_code: Optional[str] = None
    ministry_name: Optional[str] = None

    # Computed category (for filtering)
    agent_category: Optional[str] = None  # dgi, treasury, entity, ministry

    # Available workflows (inherited from entity or explicit specializations)
    available_workflows: List[str] = Field(default_factory=list)

    # Entity hierarchy (derived from DB, no hardcode)
    child_entity_codes: List[str] = Field(default_factory=list)
    ministry_entities: List[str] = Field(default_factory=list)

    # Workload info (if joined)
    current_assignments: Optional[int] = None
    capacity_percentage: Optional[Decimal] = None
    workload_status: Optional[str] = None
    availability: Optional[str] = None


class AgentProfile(AgentProfileResponse):
    """Full agent profile model"""
    pass


# ============================================================================
# HELPER MODELS
# ============================================================================

class AgentListFilters(BaseModel):
    """Filters for listing agents"""
    agent_type: Optional[AgentType] = None
    is_supervisor: Optional[bool] = None
    ministry_id: Optional[int] = None
    entity_id: Optional[UUID] = None
    entity_code: Optional[str] = None  # Filter by entity code (e.g. CNEDOGE, DGT)
    entity_location_id: Optional[UUID] = None  # Filter by site (Malabo, Bata, etc.)
    is_active: Optional[bool] = True
    agent_category: Optional[str] = None  # dgi, treasury, entity, ministry
    availability: Optional[str] = None
    search: Optional[str] = None  # ILIKE search on user email / full_name
    sort_by: Optional[str] = None
    sort_order: str = "desc"
    limit: int = 50
    offset: int = 0


class AgentGlobalStats(BaseModel):
    """Global agent stats (independent of pagination/filters)."""
    active: int = 0
    supervisors: int = 0
    ministry: int = 0
    entity: int = 0


class AgentListResponse(BaseModel):
    """Paginated response for agent profiles list"""
    items: List["AgentProfileWithDetails"]
    total: int
    page: int
    page_size: int
    pages: int
    stats: Optional[AgentGlobalStats] = None

    class Config:
        from_attributes = True


class AgentAssignmentRequest(BaseModel):
    """Request to assign agent to entity/ministry"""
    user_id: UUID
    agent_type: AgentType
    entity_id: Optional[UUID] = None
    ministry_id: Optional[int] = None
    is_supervisor: bool = False
    assigned_by: UUID


# ============================================================================
# COMPLETE CREATION MODELS (User + Profile atomically)
# ============================================================================

class AgentUserInfo(BaseModel):
    """User information for agent/admin creation"""
    email: str = Field(..., description="Email address")
    password: str = Field(..., min_length=8, max_length=100, description="Password (8-100 chars)")
    first_name: str = Field(..., min_length=2, max_length=100, description="First name")
    last_name: str = Field(..., min_length=2, max_length=100, description="Last name")
    phone_number: Optional[str] = Field(
        None,
        pattern=r"^(222|555|551|333)\d{6}$",
        description="Guinée Équatoriale phone (9 digits: 222/555/551/333 + 6 digits)"
    )
    preferred_language: str = Field(default="es", pattern="^(es|fr|en)$")


class AgentCompleteCreate(BaseModel):
    """
    Create agent user + profile atomically.

    This model is used by POST /agents/complete to create:
    1. A user with role='agent' and email_verified=False
    2. An agent_profile linked to that user
    3. Optionally assign an RBAC role to define permissions
    """
    # User information
    user: AgentUserInfo

    # Agent profile configuration
    agent_type: AgentType
    is_supervisor: bool = False
    entity_id: Optional[UUID] = None
    entity_location_id: Optional[UUID] = None
    ministry_id: Optional[int] = None

    # RBAC role for permissions (from roles table where entity_type='agent')
    rbac_role_id: Optional[UUID] = Field(
        None,
        description="RBAC role ID to assign to the agent for permissions"
    )

    can_approve_unlimited: bool = False
    max_approval_amount: Optional[Decimal] = None
    can_escalate: bool = True
    can_assign_tasks: bool = False
    can_reassign: bool = False
    specializations: List[str] = Field(default_factory=list)
    working_hours_start: Optional[time] = None
    working_hours_end: Optional[time] = None
    working_days: List[int] = Field(default_factory=lambda: [1, 2, 3, 4, 5])


class AgentCompleteResponse(BaseModel):
    """Response for complete agent creation"""
    user_id: UUID
    user_email: str
    user_full_name: str
    profile_id: UUID
    agent_type: AgentType
    is_supervisor: bool
    message: str = "Agent created successfully. Email verification required."

    class Config:
        from_attributes = True


class AdminCreateRequest(BaseModel):
    """
    Create admin user (no agent profile needed).

    This model is used by POST /agents/admin to create:
    - A user with role='admin' and email_verified=False
    """
    email: str = Field(..., description="Email address")
    password: str = Field(..., min_length=8, max_length=100, description="Password")
    first_name: str = Field(..., min_length=2, max_length=100, description="First name")
    last_name: str = Field(..., min_length=2, max_length=100, description="Last name")
    phone_number: Optional[str] = Field(
        None,
        pattern=r"^(222|555|551|333)\d{6}$",
        description="Guinée Équatoriale phone"
    )
    preferred_language: str = Field(default="es", pattern="^(es|fr|en)$")


class AdminCreateResponse(BaseModel):
    """Response for admin creation"""
    user_id: UUID
    email: str
    full_name: str
    role: str = "admin"
    message: str = "Admin created successfully. Email verification required."

    class Config:
        from_attributes = True


# ============================================================================
# INVITATION FLOW MODELS (2-step: invite → activate)
# ============================================================================

class AgentUserInfoInvite(BaseModel):
    """User information for agent invitation (NO password - agent sets it after email validation)"""
    email: str = Field(..., description="Email address")
    first_name: str = Field(..., min_length=2, max_length=100, description="First name")
    last_name: str = Field(..., min_length=2, max_length=100, description="Last name")
    phone_number: Optional[str] = Field(
        None,
        pattern=r"^(222|555|551|333)\d{6}$",
        description="Guinée Équatoriale phone (9 digits: 222/555/551/333 + 6 digits)"
    )
    preferred_language: str = Field(default="es", pattern="^(es|fr|en)$")


class AgentInviteRequest(BaseModel):
    """
    Invite agent - Step 1 of the invitation flow.

    Admin provides agent info and profile config, but NO password.
    The agent receives an email with a code and sets their password.
    """
    # User information (without password)
    user: AgentUserInfoInvite

    # Agent profile configuration
    agent_type: AgentType
    is_supervisor: bool = False
    entity_id: Optional[UUID] = None
    entity_location_id: Optional[UUID] = None
    ministry_id: Optional[int] = None

    # RBAC role for permissions
    rbac_role_id: Optional[UUID] = Field(
        None,
        description="RBAC role ID to assign to the agent for permissions"
    )

    can_approve_unlimited: bool = False
    max_approval_amount: Optional[Decimal] = None
    can_escalate: bool = True
    can_assign_tasks: bool = False
    can_reassign: bool = False
    specializations: List[str] = Field(default_factory=list)
    working_hours_start: Optional[time] = None
    working_hours_end: Optional[time] = None
    working_days: List[int] = Field(default_factory=lambda: [1, 2, 3, 4, 5])


class AgentInviteResponse(BaseModel):
    """Response for agent invitation initiation"""
    email: str
    full_name: str
    message: str = "Invitation envoyée. L'agent doit valider son email et définir son mot de passe."
    expires_in_hours: int = 24

    class Config:
        from_attributes = True


class AgentActivateRequest(BaseModel):
    """
    Activate agent - Step 2 of the invitation flow.

    Agent provides the verification code from email and chooses their password.
    """
    email: str = Field(..., description="Email address from invitation")
    verification_code: str = Field(..., min_length=6, max_length=6, description="6-digit code from email")
    password: str = Field(..., min_length=8, max_length=100, description="Password chosen by agent")


class AgentActivateResponse(BaseModel):
    """Response for agent activation"""
    user_id: UUID
    user_email: str
    user_full_name: str
    profile_id: UUID
    agent_type: AgentType
    is_supervisor: bool
    message: str = "Compte agent créé avec succès. Vous pouvez maintenant vous connecter."

    class Config:
        from_attributes = True


class AdminInviteRequest(BaseModel):
    """
    Invite admin - Step 1 of the admin invitation flow.

    Admin provides user info but NO password.
    The new admin receives an email with a code and sets their password.
    """
    email: str = Field(..., description="Email address")
    first_name: str = Field(..., min_length=2, max_length=100, description="First name")
    last_name: str = Field(..., min_length=2, max_length=100, description="Last name")
    phone_number: Optional[str] = Field(
        None,
        pattern=r"^(222|555|551|333)\d{6}$",
        description="Guinée Équatoriale phone"
    )
    preferred_language: str = Field(default="es", pattern="^(es|fr|en)$")


class AdminInviteResponse(BaseModel):
    """Response for admin invitation initiation"""
    email: str
    full_name: str
    message: str = "Invitation envoyée. L'administrateur doit valider son email et définir son mot de passe."
    expires_in_hours: int = 24

    class Config:
        from_attributes = True


class AdminActivateRequest(BaseModel):
    """
    Activate admin - Step 2 of the admin invitation flow.
    """
    email: str = Field(..., description="Email address from invitation")
    verification_code: str = Field(..., min_length=6, max_length=6, description="6-digit code from email")
    password: str = Field(..., min_length=8, max_length=100, description="Password chosen by admin")


class AdminActivateResponse(BaseModel):
    """Response for admin activation"""
    user_id: UUID
    email: str
    full_name: str
    role: str = "admin"
    message: str = "Compte administrateur créé avec succès. Vous pouvez maintenant vous connecter."

    class Config:
        from_attributes = True


# ============================================================================
# PRE-SUBMIT VALIDATION
# ============================================================================

class AgentValidationIssue(BaseModel):
    """Single validation issue (error or warning)"""
    field: str
    message: str
    severity: str  # "error" | "warning"


class AgentValidateRequest(BaseModel):
    """Request body for agent pre-submit validation"""
    email: str
    first_name: str
    last_name: str
    agent_type: AgentType
    entity_id: Optional[str] = None
    entity_location_id: Optional[str] = None
    ministry_id: Optional[int] = None
    is_supervisor: bool = False
    rbac_role_id: Optional[str] = None


class AgentValidateResponse(BaseModel):
    """Response from agent pre-submit validation"""
    valid: bool
    errors: List[AgentValidationIssue] = []
    warnings: List[AgentValidationIssue] = []
