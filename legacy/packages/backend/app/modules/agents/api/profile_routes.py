"""
Agent Profile Routes - New unified agent profile management API

Routes for the agent_profiles table (migration 047/048).
Supports both ministry_agent and entity_agent types.

Key endpoints:
- GET /profiles/me - Get current user's agent profile
- GET /profiles - List agent profiles with filters
- POST /profiles - Create agent profile
- PUT /profiles/{id} - Update agent profile
"""

from fastapi import APIRouter, HTTPException, Depends, status, Query, Request
from typing import Dict, Any, List, Optional
from uuid import UUID
from loguru import logger

from app.core.cache import check_rate_limit

from app.modules.agents.models.agent_profile import (
    AgentProfileCreate,
    AgentProfileUpdate,
    AgentProfileResponse,
    AgentProfileWithDetails,
    AgentListFilters,
    AgentListResponse,
    AgentCompleteCreate,
    AgentCompleteResponse,
    AdminCreateRequest,
    AdminCreateResponse,
    AgentType,
    # Invitation flow models
    AgentInviteRequest,
    AgentInviteResponse,
    AgentActivateRequest,
    AgentActivateResponse,
    AdminInviteRequest,
    AdminInviteResponse,
    AdminActivateRequest,
    AdminActivateResponse,
    # Pre-submit validation
    AgentValidateRequest,
    AgentValidateResponse,
)
from app.modules.agents.repositories.agent_profile_repository import AgentProfileRepository
from app.modules.auth.middleware.auth_middleware import get_current_user
from app.modules.permissions.middleware.permission_middleware import permission_required
from app.database.connection import get_database

router = APIRouter(tags=["Agent Profiles"])

profile_repository = AgentProfileRepository()


# ============================================================================
# CURRENT USER PROFILE
# ============================================================================

@router.get("/profiles/me", response_model=AgentProfileWithDetails)
async def get_my_profile(
    current_user: Dict[str, Any] = Depends(get_current_user),
    db = Depends(get_database),
):
    """
    Get current user's agent profile.

    Returns the agent profile with entity/ministry details joined.
    Use this to determine which dashboard menu to show.
    """
    user_id = current_user.id if hasattr(current_user, 'id') else current_user.get("sub")

    profile = await profile_repository.get_with_details(db, user_id=UUID(user_id))

    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No agent profile found for current user"
        )

    return AgentProfileWithDetails(**profile)


@router.get("/profiles/me/with-menu")
async def get_my_profile_with_menu(
    current_user: Dict[str, Any] = Depends(get_current_user),
    db = Depends(get_database),
):
    """
    Get current user's agent profile WITH dynamic menu configuration.

    Returns agent profile with:
    - menu_config: Dynamic menu JSON (or NULL for auto-generate)
    - dashboard_config: Dashboard widget configuration
    - available_workflows: List of workflow codes agent can handle
    - entity_type: 'workflow' or 'module'
    - permissions: List of agent's permissions

    Use this endpoint when you need menu configuration.
    For basic profile info, use GET /profiles/me instead.
    """
    from app.modules.agents.services.agent_profile_service import AgentProfileService

    user_id = current_user.id if hasattr(current_user, 'id') else current_user.get("sub")

    service = AgentProfileService()
    profile = await service.get_agent_with_menu_config(db, UUID(user_id))

    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No agent profile found for current user"
        )

    return profile


# ============================================================================
# AGENT AVAILABLE WORKFLOWS
# ============================================================================

from pydantic import BaseModel
from enum import Enum


class WorkflowSourceType(str, Enum):
    """
    Type de source du workflow.
    - predefined: Workflow avec classe Python hardcodée (PasaporteWorkflow, etc.)
    - dynamic: Workflow créé en BD, utilise GenericWorkflow
    """
    PREDEFINED = "predefined"
    DYNAMIC = "dynamic"


class AgentWorkflowResponse(BaseModel):
    """Workflow disponible pour un agent avec détails et source_type"""
    code: str
    name_es: str
    description_es: Optional[str] = None
    category: str
    entity_code: str
    workflow_type: str
    requires_agent_validation: bool
    requires_appointment: bool
    is_generic: bool
    sla_hours: int
    display_order: int
    icon: Optional[str] = None
    color: Optional[str] = None
    is_active: bool
    # Computed field
    source_type: WorkflowSourceType


@router.get("/profiles/me/workflows", response_model=List[AgentWorkflowResponse])
async def get_my_available_workflows(
    current_user: Dict[str, Any] = Depends(get_current_user),
    db = Depends(get_database),
):
    """
    Get current agent's available workflows with details.

    Returns workflows the agent can work on based on:
    1. Explicit specializations (if set)
    2. Entity workflow_codes (inherited)
    3. Parent entity workflow_codes (if department)

    Each workflow includes source_type to distinguish:
    - predefined: Has dedicated Python class (PasaporteWorkflow, etc.)
    - dynamic: Uses GenericWorkflow, config loaded from DB
    """
    user_id = current_user.id if hasattr(current_user, 'id') else current_user.get("sub")

    # Get agent's available workflow codes
    profile = await profile_repository.get_with_details(db, user_id=UUID(user_id))

    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No agent profile found for current user"
        )

    available_codes = profile.get('available_workflows', [])

    if not available_codes:
        return []

    # Fetch workflow details from workflows table
    placeholders = ', '.join([f'${i+1}' for i in range(len(available_codes))])
    query = f"""
        SELECT
            code, name_es, description_es, category, entity_code,
            workflow_type, requires_agent_validation, requires_appointment,
            is_generic, sla_hours, display_order, icon, color, is_active
        FROM workflows
        WHERE code IN ({placeholders})
        AND is_active = true
        ORDER BY display_order, name_es
    """

    rows = await db.fetch(query, *available_codes)

    return [
        AgentWorkflowResponse(
            code=row['code'],
            name_es=row['name_es'],
            description_es=row['description_es'],
            category=row['category'],
            entity_code=row['entity_code'],
            workflow_type=row['workflow_type'],
            requires_agent_validation=row['requires_agent_validation'],
            requires_appointment=row['requires_appointment'],
            is_generic=row['is_generic'],
            sla_hours=row['sla_hours'],
            display_order=row['display_order'] or 0,
            icon=row['icon'],
            color=row['color'],
            is_active=row['is_active'],
            # Compute source_type based on is_generic
            source_type=WorkflowSourceType.DYNAMIC if row['is_generic'] else WorkflowSourceType.PREDEFINED,
        )
        for row in rows
    ]


# ============================================================================
# AVAILABLE WORKFLOWS FOR SPECIALIZATIONS
# ============================================================================

@router.get("/workflows/available", response_model=List[AgentWorkflowResponse])
async def list_available_workflows(
    entity_id: Optional[str] = Query(None, description="Filter by entity"),
    category: Optional[str] = Query(None, description="Filter by category"),
    current_user: Dict[str, Any] = Depends(get_current_user),
    db = Depends(get_database),
):
    """
    List all available workflows that can be assigned as specializations.

    Returns all active workflows, optionally filtered by entity or category.
    Used by admin UI to populate the specializations dropdown.
    """
    conditions = ["is_active = true"]
    params = []
    param_idx = 1

    if entity_id:
        conditions.append(f"entity_code = (SELECT code FROM entities WHERE id = ${param_idx})")
        params.append(entity_id)
        param_idx += 1

    if category:
        conditions.append(f"category = ${param_idx}")
        params.append(category)
        param_idx += 1

    where_clause = " AND ".join(conditions)

    query = f"""
        SELECT
            code, name_es, description_es, category, entity_code,
            workflow_type, requires_agent_validation, requires_appointment,
            is_generic, sla_hours, display_order, icon, color, is_active
        FROM workflows
        WHERE {where_clause}
        ORDER BY entity_code, category, display_order, name_es
    """

    rows = await db.fetch(query, *params)

    return [
        AgentWorkflowResponse(
            code=row['code'],
            name_es=row['name_es'],
            description_es=row['description_es'],
            category=row['category'],
            entity_code=row['entity_code'],
            workflow_type=row['workflow_type'],
            requires_agent_validation=row['requires_agent_validation'],
            requires_appointment=row['requires_appointment'],
            is_generic=row['is_generic'],
            sla_hours=row['sla_hours'],
            display_order=row['display_order'] or 0,
            icon=row['icon'],
            color=row['color'],
            is_active=row['is_active'],
            source_type=WorkflowSourceType.DYNAMIC if row['is_generic'] else WorkflowSourceType.PREDEFINED,
        )
        for row in rows
    ]


# ============================================================================
# CRUD OPERATIONS
# ============================================================================

@router.get("/profiles", response_model=AgentListResponse)
async def list_profiles(
    agent_type: Optional[AgentType] = None,
    is_supervisor: Optional[bool] = None,
    ministry_id: Optional[int] = None,
    entity_id: Optional[str] = None,
    entity_code: Optional[str] = Query(None, description="Filter by entity code"),
    entity_location_id: Optional[str] = Query(None, description="Filter by site location UUID"),
    agent_category: Optional[str] = None,
    availability: Optional[str] = None,
    is_active: Optional[bool] = None,
    search: Optional[str] = Query(None, max_length=100, description="Search by email or name (ILIKE)"),
    sort_by: Optional[str] = Query(None, regex="^(user_full_name|user_email|entity_name|agent_type|is_active|is_supervisor|availability|current_assignments|created_at)$"),
    sort_order: str = Query("desc", regex="^(asc|desc)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    current_user: Dict[str, Any] = Depends(get_current_user),
    db = Depends(get_database),
):
    """List agent profiles with filters, sorting, and pagination."""
    filters = AgentListFilters(
        agent_type=agent_type,
        is_supervisor=is_supervisor,
        ministry_id=ministry_id,
        entity_id=UUID(entity_id) if entity_id else None,
        entity_code=entity_code.strip() if entity_code else None,
        entity_location_id=UUID(entity_location_id) if entity_location_id else None,
        agent_category=agent_category,
        availability=availability,
        is_active=is_active,
        search=search.strip() if search else None,
        sort_by=sort_by,
        sort_order=sort_order,
        limit=page_size,
        offset=(page - 1) * page_size,
    )

    # list_agents returns (data, total_count)
    profiles, total = await profile_repository.list_agents(db, filters)
    items = [AgentProfileWithDetails(**p) for p in profiles]

    # Global stats (independent of filters — always shows real totals)
    from app.modules.agents.models.agent_profile import AgentGlobalStats
    stats_row = await db.fetchrow("""
        SELECT
            COUNT(*) FILTER (WHERE is_active) as active,
            COUNT(*) FILTER (WHERE is_supervisor) as supervisors,
            COUNT(*) FILTER (WHERE agent_type = 'ministry_agent') as ministry,
            COUNT(*) FILTER (WHERE agent_type = 'entity_agent') as entity
        FROM agent_profiles
    """)
    stats = AgentGlobalStats(**dict(stats_row)) if stats_row else None

    # Calculate total pages
    pages = (total + page_size - 1) // page_size if total > 0 else 1

    return AgentListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
        stats=stats,
    )


@router.get("/profiles/{profile_id}", response_model=AgentProfileWithDetails)
async def get_profile(
    profile_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db = Depends(get_database),
):
    """Get agent profile by ID"""
    profile = await profile_repository.get_with_details(db, profile_id=UUID(profile_id))

    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent profile not found"
        )

    return AgentProfileWithDetails(**profile)


@router.get("/profiles/{profile_id}/neighbors")
async def get_profile_neighbors(
    profile_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db=Depends(get_database),
):
    """Get prev/next agent IDs for navigation (lightweight — no full profiles loaded).

    Uses a single SQL window query: O(1) for the DB, returns 3 fields.
    Ordered by creation date (same as default list order).
    """
    query = """
        WITH ordered AS (
            SELECT
                ap.id,
                ROW_NUMBER() OVER (ORDER BY ap.created_at DESC, ap.id) AS rn,
                COUNT(*) OVER () AS total
            FROM agent_profiles ap
            WHERE ap.is_active = true
        )
        SELECT
            (SELECT id FROM ordered WHERE rn = o.rn - 1) AS prev_id,
            (SELECT id FROM ordered WHERE rn = o.rn + 1) AS next_id,
            o.rn AS position,
            o.total
        FROM ordered o
        WHERE o.id = $1
    """
    row = await db.fetchrow(query, UUID(profile_id))
    if not row:
        raise HTTPException(status_code=404, detail="Agent profile not found")
    return {
        "prev_id": str(row["prev_id"]) if row["prev_id"] else None,
        "next_id": str(row["next_id"]) if row["next_id"] else None,
        "position": row["position"],
        "total": row["total"],
    }


@router.get("/profiles/user/{user_id}", response_model=AgentProfileWithDetails)
async def get_profile_by_user(
    user_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db = Depends(get_database),
):
    """Get agent profile by user ID"""
    profile = await profile_repository.get_with_details(db, user_id=UUID(user_id))

    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent profile not found for user"
        )

    return AgentProfileWithDetails(**profile)


@router.post("/profiles", response_model=AgentProfileResponse, status_code=status.HTTP_201_CREATED)
async def create_profile(
    profile: AgentProfileCreate,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db = Depends(get_database),
    _: None = Depends(permission_required("agent.create"))
):
    """
    Create agent profile for existing user.

    The user must already exist with role='agent'.
    For creating user + profile atomically, use POST /complete.
    """
    user_id = current_user.id if hasattr(current_user, 'id') else current_user.get("sub")

    # Set assigned_by if not provided
    if not profile.assigned_by:
        profile.assigned_by = UUID(user_id)

    # Check if profile already exists
    existing = await profile_repository.get_by_user_id(db, profile.user_id, active_only=False)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Agent profile already exists for this user"
        )

    result = await profile_repository.create(db, profile)

    logger.info(f"User {user_id} created agent profile {result['id']} for user {profile.user_id}")
    return AgentProfileResponse(**result)


@router.put("/profiles/{profile_id}", response_model=AgentProfileResponse)
async def update_profile(
    profile_id: str,
    update_data: AgentProfileUpdate,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db = Depends(get_database),
    _: None = Depends(permission_required("agent.update"))
):
    """Update agent profile"""
    from app.modules.agents.services.agent_profile_service import AgentProfileService

    user_id = current_user.id if hasattr(current_user, 'id') else current_user.get("sub")

    # Use service to handle RBAC role updates
    service = AgentProfileService()
    updated = await service.update_agent_profile(
        db,
        UUID(profile_id),
        update_data,
        updated_by=UUID(user_id) if user_id else None
    )

    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent profile not found"
        )

    logger.info(f"Agent profile {profile_id} updated by {user_id}")
    return AgentProfileResponse(**updated)


@router.post("/profiles/{profile_id}/deactivate", status_code=status.HTTP_200_OK)
async def deactivate_profile(
    profile_id: str,
    reason: Optional[str] = None,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db = Depends(get_database),
    _: None = Depends(permission_required("agent.deactivate"))
):
    """Deactivate agent profile"""
    user_id = current_user.id if hasattr(current_user, 'id') else current_user.get("sub")

    success = await profile_repository.deactivate(db, UUID(profile_id), UUID(user_id), reason)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent profile not found"
        )

    logger.info(f"Agent profile {profile_id} deactivated by {user_id}")
    return {"message": "Agent profile deactivated successfully", "profile_id": profile_id}


@router.post("/profiles/{profile_id}/reactivate", status_code=status.HTTP_200_OK)
async def reactivate_profile(
    profile_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db = Depends(get_database),
):
    """Reactivate agent profile"""
    success = await profile_repository.reactivate(db, UUID(profile_id))

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent profile not found"
        )

    logger.info(f"Agent profile {profile_id} reactivated")
    return {"message": "Agent profile reactivated successfully", "profile_id": profile_id}


# ============================================================================
# PRE-SUBMIT VALIDATION
# ============================================================================

@router.post("/validate", response_model=AgentValidateResponse)
async def validate_agent(
    data: AgentValidateRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
    _: None = Depends(permission_required("agent.create")),
):
    """
    Validate agent invitation data without creating.
    Returns errors (block submit) and warnings (show confirmation).
    """
    from app.modules.agents.services.agent_profile_service import agent_profile_service

    try:
        result = await agent_profile_service.validate_agent_data(data)
        return result
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Agent validation failed: {type(e).__name__}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Validation failed due to an internal error. Please try again.",
        )


# ============================================================================
# AGENT INVITATION FLOW (2-step: invite → activate)
# ============================================================================

@router.post("/invite", response_model=AgentInviteResponse, status_code=status.HTTP_201_CREATED)
async def invite_agent(
    data: AgentInviteRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db = Depends(get_database),
    _: None = Depends(permission_required("agent.create"))
):
    """
    Step 1: Invite agent.

    This endpoint:
    1. Validates the agent data
    2. Generates a verification code
    3. Stores the invitation in pending_registrations
    4. Sends an invitation email to the agent

    The agent must click the link in the email and set their password
    to complete registration (via POST /agents/activate).
    """
    from app.modules.agents.services.agent_profile_service import AgentProfileService

    user_id = current_user.id if hasattr(current_user, 'id') else current_user.get("sub")

    # Rate limit: 10 invitations per hour per admin (prevent email spam/quota exhaustion)
    is_allowed, _ = await check_rate_limit(
        identifier=str(user_id), endpoint="/agents/invite", max_requests=10, window_seconds=3600
    )
    if not is_allowed:
        raise HTTPException(status_code=429, detail="Too many invitations. Please wait before sending more.")

    try:
        service = AgentProfileService()
        result = await service.initiate_agent_invitation(data, UUID(user_id))

        logger.info(f"User {user_id} invited agent {data.user.email}")
        return AgentInviteResponse(**result)

    except ValueError as e:
        logger.warning(f"Agent invitation validation failed for {data.user.email}: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        logger.error(
            f"Agent invitation error for {data.user.email}: {type(e).__name__}: {e}\n"
            f"{traceback.format_exc()}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Invitation failed due to an internal error. Please try again or contact support."
        )


@router.post("/activate", response_model=AgentActivateResponse, status_code=status.HTTP_201_CREATED)
async def activate_agent(
    data: AgentActivateRequest,
    req: Request,
    db = Depends(get_database),
):
    """
    Step 2: Activate agent account.

    This endpoint (PUBLIC - no auth required):
    1. Verifies the code from the invitation email
    2. Creates the user account with the provided password
    3. Creates the agent profile
    4. Assigns RBAC permissions
    5. Creates workload record

    The agent can then log in with their email and password.
    """
    # Rate limit: 5 attempts per 15 min per IP (prevent distributed brute-force)
    ip = req.client.host if req.client else "unknown"
    is_allowed_ip, _ = await check_rate_limit(
        identifier=ip, endpoint="/agents/activate", max_requests=5, window_seconds=900
    )
    if not is_allowed_ip:
        raise HTTPException(status_code=429, detail="Too many activation attempts. Please wait.")

    # Rate limit: 10 attempts per hour per email (prevent targeted brute-force across IPs)
    is_allowed_email, _ = await check_rate_limit(
        identifier=data.email.lower(), endpoint="/agents/activate/email", max_requests=10, window_seconds=3600
    )
    if not is_allowed_email:
        raise HTTPException(status_code=429, detail="Too many activation attempts for this email. Please wait.")

    from app.modules.agents.services.agent_profile_service import AgentProfileService

    try:
        service = AgentProfileService()
        result = await service.finalize_agent_creation(
            db,
            email=data.email,
            verification_code=data.verification_code,
            password=data.password,
        )

        logger.info(f"Agent activated: {data.email}")
        return AgentActivateResponse(**result)

    except ValueError as e:
        logger.warning(f"Agent activation failed for {data.email}: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        logger.error(
            f"Agent activation error for {data.email}: {type(e).__name__}: {e}\n"
            f"{traceback.format_exc()}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Activation failed due to an internal error. Please try again or contact support."
        )


# Keep legacy endpoint for backward compatibility (deprecated)
@router.post("/complete", response_model=AgentCompleteResponse, status_code=status.HTTP_201_CREATED,
             deprecated=True, summary="[DEPRECATED] Use POST /invite instead")
async def create_agent_complete(
    data: AgentCompleteCreate,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db = Depends(get_database),
    _: None = Depends(permission_required("agent.create"))
):
    """
    [DEPRECATED] Create agent user + profile atomically.

    This endpoint is deprecated. Use the new invitation flow:
    1. POST /agents/invite - Send invitation email
    2. POST /agents/activate - Agent sets password and activates

    This old endpoint creates accounts with email_verified=False,
    which requires a separate email verification step.
    """
    from app.modules.agents.services.agent_profile_service import AgentProfileService

    user_id = current_user.id if hasattr(current_user, 'id') else current_user.get("sub")

    service = AgentProfileService()
    # Note: This uses the old flow, not the invitation flow
    # For backward compatibility only
    raise HTTPException(
        status_code=status.HTTP_410_GONE,
        detail="This endpoint is deprecated. Use POST /agents/invite and POST /agents/activate instead."
    )


# ============================================================================
# ADMIN INVITATION FLOW (2-step: invite → activate)
# ============================================================================

@router.post("/admin/invite", response_model=AdminInviteResponse, status_code=status.HTTP_201_CREATED)
async def invite_admin(
    data: AdminInviteRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db = Depends(get_database),
    _: None = Depends(permission_required("agent.create"))
):
    """
    Step 1: Invite admin.

    This endpoint:
    1. Validates the admin data
    2. Generates a verification code
    3. Stores the invitation in pending_registrations
    4. Sends an invitation email to the admin

    The admin must click the link and set their password
    to complete registration (via POST /agents/admin/activate).
    """
    from app.modules.agents.services.agent_profile_service import AgentProfileService

    user_id = current_user.id if hasattr(current_user, 'id') else current_user.get("sub")

    # Rate limit: 10 invitations per hour per admin (prevent email spam/quota exhaustion)
    is_allowed, _ = await check_rate_limit(
        identifier=str(user_id), endpoint="/agents/admin/invite", max_requests=10, window_seconds=3600
    )
    if not is_allowed:
        raise HTTPException(status_code=429, detail="Too many invitations. Please wait before sending more.")

    try:
        service = AgentProfileService()
        result = await service.initiate_admin_invitation(data, UUID(user_id))

        logger.info(f"User {user_id} invited admin {data.email}")
        return AdminInviteResponse(**result)

    except ValueError as e:
        logger.warning(f"Admin invitation failed for {data.email}: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        logger.error(
            f"Admin invitation error for {data.email}: {type(e).__name__}: {e}\n"
            f"{traceback.format_exc()}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Invitation failed due to an internal error. Please try again or contact support."
        )


@router.post("/admin/activate", response_model=AdminActivateResponse, status_code=status.HTTP_201_CREATED)
async def activate_admin(
    data: AdminActivateRequest,
    req: Request,
    db = Depends(get_database),
):
    """
    Step 2: Activate admin account.

    This endpoint (PUBLIC - no auth required):
    1. Verifies the code from the invitation email
    2. Creates the admin user with the provided password

    The admin can then log in with their email and password.
    """
    # Rate limit: 5 attempts per 15 min per IP (prevent distributed brute-force)
    ip = req.client.host if req.client else "unknown"
    is_allowed_ip, _ = await check_rate_limit(
        identifier=ip, endpoint="/agents/admin/activate", max_requests=5, window_seconds=900
    )
    if not is_allowed_ip:
        raise HTTPException(status_code=429, detail="Too many activation attempts. Please wait.")

    # Rate limit: 10 attempts per hour per email (prevent targeted brute-force across IPs)
    is_allowed_email, _ = await check_rate_limit(
        identifier=data.email.lower(), endpoint="/agents/admin/activate/email", max_requests=10, window_seconds=3600
    )
    if not is_allowed_email:
        raise HTTPException(status_code=429, detail="Too many activation attempts for this email. Please wait.")

    from app.modules.agents.services.agent_profile_service import AgentProfileService

    try:
        service = AgentProfileService()
        result = await service.finalize_admin_creation(
            db,
            email=data.email,
            verification_code=data.verification_code,
            password=data.password,
        )

        logger.info(f"Admin activated: {data.email}")
        return AdminActivateResponse(**result)

    except ValueError as e:
        logger.warning(f"Admin activation failed for {data.email}: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        logger.error(
            f"Admin activation error for {data.email}: {type(e).__name__}: {e}\n"
            f"{traceback.format_exc()}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Activation failed due to an internal error. Please try again or contact support."
        )


# Keep legacy endpoint for backward compatibility (deprecated)
@router.post("/admin", response_model=AdminCreateResponse, status_code=status.HTTP_201_CREATED,
             deprecated=True, summary="[DEPRECATED] Use POST /admin/invite instead")
async def create_admin(
    data: AdminCreateRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db = Depends(get_database),
    _: None = Depends(permission_required("agent.create"))
):
    """
    [DEPRECATED] Create admin user.

    This endpoint is deprecated. Use the new invitation flow:
    1. POST /agents/admin/invite - Send invitation email
    2. POST /agents/admin/activate - Admin sets password and activates
    """
    raise HTTPException(
        status_code=status.HTTP_410_GONE,
        detail="This endpoint is deprecated. Use POST /agents/admin/invite and POST /agents/admin/activate instead."
    )


# ============================================================================
# STATISTICS & LISTS
# ============================================================================

@router.get("/profiles/supervisors/list", response_model=List[AgentProfileWithDetails])
async def list_supervisors(
    ministry_id: Optional[int] = None,
    entity_id: Optional[str] = None,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db = Depends(get_database),
):
    """List supervisor agents"""
    filters = AgentListFilters(
        is_supervisor=True,
        ministry_id=ministry_id,
        entity_id=UUID(entity_id) if entity_id else None,
        is_active=True,
        limit=100,
    )

    profiles = await profile_repository.list_with_details(db, filters)
    return [AgentProfileWithDetails(**p) for p in profiles]


@router.get("/profiles/ministry/{ministry_id}/available", response_model=List[AgentProfileWithDetails])
async def list_available_by_ministry(
    ministry_id: int,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db = Depends(get_database),
):
    """List available agents for a ministry"""
    profiles = await profile_repository.list_available_by_ministry(db, ministry_id)
    return [AgentProfileWithDetails(**p) for p in profiles]


@router.get("/profiles/entity/{entity_id}/available", response_model=List[AgentProfileWithDetails])
async def list_available_by_entity(
    entity_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db = Depends(get_database),
):
    """List available agents for an entity"""
    profiles = await profile_repository.list_available_by_entity(db, UUID(entity_id))
    return [AgentProfileWithDetails(**p) for p in profiles]


# ============================================================================
# WORKLOAD & PERFORMANCE (for agent profiles)
# ============================================================================

from app.modules.agents.models.agent import AgentWorkload, AgentWorkloadUpdate, AgentPerformanceStats
from app.modules.agents.repositories.workload_repository import WorkloadRepository

workload_repository = WorkloadRepository()


@router.get("/profiles/{profile_id}/workload", response_model=AgentWorkload)
async def get_profile_workload(
    profile_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db = Depends(get_database),
):
    """Get agent workload by profile ID"""
    workload = await workload_repository.get_workload_by_profile_id(db, profile_id)

    if not workload:
        # Try to create workload record if it doesn't exist
        workload = await workload_repository.create_workload_for_profile(db, profile_id)

    if not workload:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workload not found for this agent profile"
        )

    return AgentWorkload(**workload)


@router.put("/profiles/{profile_id}/workload", response_model=AgentWorkload)
async def update_profile_workload(
    profile_id: str,
    update_data: AgentWorkloadUpdate,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db = Depends(get_database),
    _: None = Depends(permission_required("agent.manage_workload"))
):
    """Update agent workload by profile ID - Requires agents.manage_workload permission"""
    # First check if workload exists
    existing = await workload_repository.get_workload_by_profile_id(db, profile_id)
    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workload not found for this agent profile"
        )

    # Update workload using agent_profile_id (agent_id column is deprecated/NULL)
    updated = await workload_repository.update_workload(db, str(profile_id), update_data)
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Failed to update workload"
        )

    logger.info(f"Workload updated for agent profile {profile_id}")
    return AgentWorkload(**updated)


@router.get("/profiles/{profile_id}/performance", response_model=AgentPerformanceStats)
async def get_profile_performance(
    profile_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db = Depends(get_database),
):
    """Get agent performance statistics by profile ID.

    Uses the new get_performance_by_profile_id method that computes
    performance metrics from assignments table for the new architecture.
    """
    # Verify profile exists
    profile = await profile_repository.get_by_id(db, UUID(profile_id))
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent profile not found"
        )

    # Get computed performance stats using profile_id
    stats = await workload_repository.get_performance_by_profile_id(db, profile_id)

    if not stats:
        # Return empty performance stats if none exist
        return AgentPerformanceStats(
            agent_id=0,  # Legacy field, not used with new architecture
            ministry_id=profile.get('ministry_id') or 0,
            current_month_processed=0,
            current_month_approved=0,
            current_month_rejected=0,
            current_month_escalated=0,
            sla_respected_count=0,
            sla_missed_count=0,
            current_active_locks=0,
            max_concurrent_locks=0,
        )

    # Map computed stats to AgentPerformanceStats model
    return AgentPerformanceStats(
        agent_id=0,  # Legacy field
        ministry_id=profile.get('ministry_id') or 0,
        current_month_processed=stats.get('current_month_processed', 0),
        current_month_approved=stats.get('current_month_approved', 0),
        current_month_rejected=stats.get('current_month_rejected', 0),
        current_month_escalated=stats.get('current_month_escalated', 0),
        avg_processing_minutes=stats.get('avg_processing_minutes'),
        avg_lock_duration_minutes=stats.get('avg_lock_duration_minutes'),
        sla_respected_count=stats.get('sla_respected_count', 0),
        sla_missed_count=stats.get('sla_missed_count', 0),
        sla_respect_percentage=stats.get('sla_respect_percentage'),
        current_active_locks=stats.get('current_active_locks', 0),
        max_concurrent_locks=stats.get('max_concurrent_locks', 0),
        last_action_at=stats.get('last_action_at'),
        last_login_at=stats.get('last_login_at'),
        stats_period_start=stats.get('stats_period_start'),
        stats_period_end=stats.get('stats_period_end'),
    )


# ============================================================================
# ADMIN ALERTS DASHBOARD
# ============================================================================

from app.core.cache import get_cache


@router.get("/admin/alerts-dashboard")
async def get_alerts_dashboard(
    current_user: Dict[str, Any] = Depends(get_current_user),
    db = Depends(get_database),
    _: None = Depends(permission_required("agent.view"))
):
    """
    Aggregated alerts dashboard for admin agent management.

    Returns counts and details for:
    - Inactive agents (no activity >48h)
    - Overloaded agents (capacity >80%)
    - Stale locks (payments locked >4h)
    - SLA at risk (expiring within 24h)
    - Workload summary by entity
    - LLM briefing (async, cached 5min, graceful degradation)

    Cached for 60 seconds (real-time enough for admin monitoring).
    """
    cache = get_cache()
    cache_key = "admin:agents:alerts-dashboard"

    cached = await cache.get(cache_key)
    if cached:
        return cached

    result = await workload_repository.get_admin_alerts_dashboard(db)

    if not result:
        return {
            "inactive_count": 0,
            "overloaded_count": 0,
            "stale_locks_count": 0,
            "sla_at_risk_count": 0,
            "total_alerts": 0,
        }

    # Async LLM briefing (non-blocking, same TTL as dashboard to avoid stale analysis)
    from app.modules.agents.services.llm_briefing_service import llm_briefing_service

    briefing_key = "admin:agents:llm-briefing"
    briefing = await cache.get(briefing_key)
    if not briefing:
        try:
            briefing = await llm_briefing_service.generate_briefing(result)
            if briefing:
                # 5min TTL to reduce Gemini API calls and avoid 429 rate limits
                await cache.set(briefing_key, briefing, ttl=300)
        except Exception as e:
            logger.warning(f"LLM briefing failed (graceful): {e}")

    # Safely extract briefing fields (cache may return unexpected types)
    if isinstance(briefing, dict):
        result["llm_briefing"] = briefing.get("briefing")
        result["llm_priority"] = briefing.get("priority", "normal")
    else:
        result["llm_briefing"] = None
        result["llm_priority"] = "normal"

    await cache.set(cache_key, result, ttl=60)

    return result


# ============================================================================
# ADMIN ASSISTANT (LLM Q&A)
# ============================================================================

from pydantic import BaseModel as PydanticBaseModel, Field
import re


class AdminAssistantRequest(PydanticBaseModel):
    """Request for admin assistant Q&A."""
    question: str = Field(
        ...,
        min_length=3,
        max_length=500,
        description="Question en langage naturel (3-500 caractères)"
    )
    previous_context: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Contexte de la question précédente: {question: str, tools_used: list[str]}"
    )
    session_id: Optional[str] = Field(
        default=None,
        max_length=64,
        description="UUID de session pour la mémoire conversationnelle"
    )


class AdminAssistantResponse(PydanticBaseModel):
    """Response from admin assistant."""
    answer: str
    tools_used: List[str] = []
    data: Dict[str, Any] = {}


def _sanitize_question(question: str) -> str:
    """Sanitize user question to prevent prompt injection."""
    # Strip control characters and excessive whitespace
    cleaned = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', question)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    # Remove common injection patterns
    injection_patterns = [
        r'(?i)ignore\s+(previous|above|all)\s+(instructions?|prompts?)',
        r'(?i)you\s+are\s+now\s+',
        r'(?i)system\s*:\s*',
        r'(?i)INST\]',
        r'(?i)\[\/INST\]',
    ]
    for pattern in injection_patterns:
        cleaned = re.sub(pattern, '', cleaned)
    return cleaned.strip()


@router.post("/admin/assistant", response_model=AdminAssistantResponse)
async def admin_assistant_query(
    request: AdminAssistantRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db = Depends(get_database),
    _: None = Depends(permission_required("agent.view"))
):
    """
    LLM-powered admin assistant for agent management Q&A.

    Accepts natural language questions in Spanish about agents,
    workload, performance, SLA, and anomalies.

    Uses Gemini function calling — the LLM never generates SQL directly.
    It routes to predefined safe functions and formats the response.

    Rate limited: 10 requests per minute per user.
    """
    from app.core.cache import check_rate_limit
    from app.modules.agents.services.admin_assistant_service import admin_assistant_service

    # Rate limit: 10 requests/minute per user (Gemini costs money)
    user_id = current_user.id if hasattr(current_user, 'id') else current_user.get("sub")
    is_allowed, remaining = await check_rate_limit(
        str(user_id), "/agents/admin/assistant", max_requests=10, window_seconds=60
    )
    if not is_allowed:
        return AdminAssistantResponse(
            answer="Has alcanzado el límite de consultas (10/min). Espera un momento antes de intentar de nuevo.",
            tools_used=[],
            data={},
        )

    sanitized = _sanitize_question(request.question)
    if len(sanitized) < 3:
        return AdminAssistantResponse(
            answer="Pregunta demasiado corta o inválida. Escribe una pregunta clara.",
            tools_used=[],
            data={},
        )

    context: Dict[str, Any] = {}
    if request.previous_context:
        context["previous_context"] = request.previous_context

    result = await admin_assistant_service.process_question(db, sanitized, context=context)
    return AdminAssistantResponse(**result)
