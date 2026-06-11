"""
Assignment Routes - FastAPI Endpoints for Assignment Operations
Handles manual and automatic assignment of declarations to agents

Author: Claude Code
Date: 2025-11-16
Version: 1.0 - Initial implementation
"""

from typing import List, Optional, Dict, Any, Union
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel, Field, field_validator

from app.modules.auth.middleware.auth_middleware import get_current_user
from app.modules.users.models.user import UserResponse
from app.modules.assignment.models.assignment_history import (
    Assignment,
    AssignmentCreate,
    AssignmentUpdate,
    AssignmentStatus,
    ReassignmentCreate,
    ReassignmentReason
)
from app.modules.assignment.services.assignment_service import (
    AssignmentService,
    get_assignment_service
)
from app.modules.assignment.services.auto_assignment_service import (
    AutoAssignmentService,
    get_auto_assignment_service
)
from app.modules.assignment.repositories.assignment_repository import (
    AssignmentRepository,
    get_assignment_repository
)
from app.modules.assignment.repositories.workload_repository import (
    WorkloadRepository,
    get_workload_repository
)
from app.modules.assignment.repositories.rules_repository import (
    RulesRepository,
    get_rules_repository
)
from app.modules.assignment.services.rules_engine import get_rules_engine
from app.core.database import get_db_connection

# Permission middleware
from app.modules.permissions.middleware import require_permission
from app.modules.permissions.services.permission_service import (
    PermissionService,
    get_permission_service,
)

import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/assignments", tags=["assignments"])


# ============================================================================
# AGENT CONTEXT HELPER (Migration 048 - Unified agent role)
# ============================================================================

async def get_agent_context(user_id: str, db) -> Dict[str, Any]:
    """
    Get agent context from agent_profiles table.

    Returns:
        dict with keys:
        - is_supervisor: bool
        - agent_type: 'ministry_agent' or 'entity_agent'
        - ministry_id: int or None
        - entity_id: UUID or None
        - entity_type: 'ministry' or 'entity' (derived from agent_type)
    """
    query = """
        SELECT
            ap.is_supervisor,
            ap.agent_type,
            ap.ministry_id,
            ap.entity_id,
            ap.entity_location_id,
            el.is_main_office
        FROM agent_profiles ap
        LEFT JOIN entity_locations el ON el.id = ap.entity_location_id
        WHERE ap.user_id = $1 AND ap.is_active = true
    """
    result = await db.fetchrow(query, user_id)

    if not result:
        return {
            "is_supervisor": False,
            "agent_type": None,
            "ministry_id": None,
            "entity_id": None,
            "entity_type": None,
            "entity_location_id": None,
            "is_main_office": False,
        }

    agent_type = result.get("agent_type")
    entity_type = "ministry" if agent_type == "ministry_agent" else "entity"

    return {
        "is_supervisor": result.get("is_supervisor", False),
        "agent_type": agent_type,
        "ministry_id": result.get("ministry_id"),
        "entity_id": result.get("entity_id"),
        "entity_type": entity_type,
        "entity_location_id": result.get("entity_location_id"),
        "is_main_office": result.get("is_main_office", False),
    }


async def _get_agent_profile_id_for_user(user_id: str, db) -> Optional[UUID]:
    """
    Get agent_profile_id from user_id.

    Migration 054: agent_profile_id is the primary identifier, not user_id.
    This helper converts user_id to agent_profile_id for authorization checks.
    """
    query = """
        SELECT id FROM agent_profiles
        WHERE user_id = $1 AND is_active = true
    """
    result = await db.fetchrow(query, UUID(user_id))
    return result['id'] if result else None


# ============================================================================
# REQUEST/RESPONSE SCHEMAS
# ============================================================================

# Priority level mapping for backward compatibility
# Legacy frontend may send string values like "low", "medium", "high", "urgent"
PRIORITY_LEVEL_MAPPING = {
    "low": 2,
    "medium": 5,
    "normal": 5,
    "high": 7,
    "urgent": 9,
    "critical": 10,
}


def _convert_priority_level(value: Union[int, str]) -> int:
    """Convert legacy string priority to integer (1-10)

    Backward compatibility for Migration 053:
    - DB schema uses integer (1-10)
    - Legacy code may send strings ("low", "medium", "high", "urgent")
    """
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        # Try to parse as integer first
        try:
            return int(value)
        except ValueError:
            pass
        # Map legacy string values
        return PRIORITY_LEVEL_MAPPING.get(value.lower(), 5)
    return 5  # Default


class ManualAssignmentRequest(BaseModel):
    """Request to manually assign an item to an agent

    Migration 053: Uses item_id + item_type instead of declaration_id + declaration_type
    Migration 054: Uses agent_profile_id instead of agent_id
    """
    item_id: UUID = Field(..., description="UUID of the item (tax_declaration, service_request, etc.)")
    item_type: str = Field(..., description="Type: declaration type or workflow code")
    agent_profile_id: UUID = Field(..., description="Reference to agent_profiles.id")
    notes: Optional[str] = None
    priority_level: int = Field(default=5, ge=1, le=10, description="Priority 1-10")
    deadline_days: Optional[int] = Field(None, ge=1, le=90)

    @field_validator('priority_level', mode='before')
    @classmethod
    def convert_legacy_priority(cls, v):
        """Convert legacy string priority to integer for backward compatibility"""
        return _convert_priority_level(v)


class AutoAssignmentRequest(BaseModel):
    """Request for automatic assignment

    Migration 053: Uses item_id + item_type instead of declaration_id + declaration_type
    """
    item_id: UUID = Field(..., description="UUID of the item (tax_declaration, service_request, etc.)")
    item_type: str = Field(..., description="Type: declaration type or workflow code")
    item_data: dict = Field(..., description="Item data for rule evaluation")
    entity_type: str = Field(default="ministry", pattern="^(ministry|entity)$")
    entity_id: Optional[str] = None


class StartProcessingRequest(BaseModel):
    """Request to start processing an assignment"""
    pass  # No additional fields needed


class CompleteAssignmentRequest(BaseModel):
    """Request to complete an assignment"""
    validation_status: str = Field(..., pattern="^(approved|rejected)$")
    quality_score: Optional[float] = Field(None, ge=0.0, le=10.0)


class ReassignmentRequest(BaseModel):
    """Request to reassign item to new agent

    Migration 054: Uses agent_profile_id instead of agent_id
    """
    new_agent_profile_id: UUID = Field(..., description="Reference to agent_profiles.id")
    reason: ReassignmentReason
    notes: Optional[str] = None


class UpdatePriorityRequest(BaseModel):
    """Request to update assignment priority

    Migration 053: priority_level is int (1-10) not string
    """
    priority_level: int = Field(..., ge=1, le=10, description="Priority 1-10")

    @field_validator('priority_level', mode='before')
    @classmethod
    def convert_legacy_priority(cls, v):
        """Convert legacy string priority to integer for backward compatibility"""
        return _convert_priority_level(v)


class ExtendDeadlineRequest(BaseModel):
    """Request to extend assignment deadline"""
    additional_days: int = Field(..., ge=1, le=90)


class UpdateNotesRequest(BaseModel):
    """Request to update assignment notes"""
    notes: str = Field(..., min_length=0, max_length=5000, description="Notes content (max 5000 chars)")


# ============================================================================
# DEPENDENCY INJECTION
# ============================================================================

async def get_assignment_service_dep(
    db = Depends(get_db_connection)
) -> AssignmentService:
    """Dependency for AssignmentService"""
    assignment_repo = get_assignment_repository(db)
    workload_repo = get_workload_repository(db)
    return get_assignment_service(assignment_repo, workload_repo)


async def get_auto_assignment_service_dep(
    db = Depends(get_db_connection)
) -> AutoAssignmentService:
    """Dependency for AutoAssignmentService"""
    assignment_repo = get_assignment_repository(db)
    workload_repo = get_workload_repository(db)
    rules_repo = get_rules_repository(db)
    rules_engine = get_rules_engine()
    return get_auto_assignment_service(
        assignment_repo,
        workload_repo,
        rules_repo,
        rules_engine
    )


# ============================================================================
# ENDPOINTS - ASSIGNMENT OPERATIONS
# ============================================================================
# Note: Authorization is handled via @require_permission decorators
# Legacy check_*_permission functions have been removed (replaced by RBAC system)


@router.get("/assignable-items")
@require_permission("assignment.create")
async def get_assignable_items(
    tab: str = Query("unassigned", description="Tab: unassigned | escalated | active"),
    entity_code: Optional[str] = Query(None, description="Filter by entity_code (admin only)"),
    entity_location_id: Optional[str] = Query(None, description="Filter by site (entity_location_id)"),
    search: Optional[str] = Query(None, description="Search by reference"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: UserResponse = Depends(get_current_user),
    permission_service: PermissionService = Depends(get_permission_service),
    db=Depends(get_db_connection),
):
    """
    Get items available for assignment/reassignment.
    Scoped to supervisor's entity (non-admin users only see their entity's items).

    Tabs:
    - unassigned: SUBMITTED requests with no active assignment
    - escalated: Requests flagged escalated=true (pending or in_review)
    - active: Currently assigned requests (for reassignment)
    """
    try:
        offset = (page - 1) * page_size
        base_conditions = []
        params: list = []
        param_idx = 1

        # ── Entity scoping: supervisor sees only their entity's items ──
        is_admin = current_user.role == "admin"
        if not is_admin:
            agent_ctx = await get_agent_context(current_user.id, db)
            if agent_ctx.get("entity_id"):
                # Get entity code from entity_id
                ent_row = await db.fetchrow(
                    "SELECT code, workflow_codes FROM entities WHERE id = $1",
                    agent_ctx["entity_id"]
                )
                if ent_row:
                    supervisor_entity_code = ent_row["code"]
                    raw_wc = ent_row["workflow_codes"]
                    # JSONB may return as string in some asyncpg versions — normalize to list
                    if isinstance(raw_wc, str):
                        import json
                        try:
                            raw_wc = json.loads(raw_wc)
                        except (json.JSONDecodeError, TypeError):
                            raw_wc = []
                    workflow_codes = raw_wc if isinstance(raw_wc, list) and len(raw_wc) > 0 else []
                    if workflow_codes:
                        # Scope by workflow_codes (entity may handle multiple workflows)
                        base_conditions.append(f"sr.workflow_code = ANY(${param_idx}::text[])")
                        params.append(workflow_codes)
                        param_idx += 1
                    else:
                        # Entity without workflows (e.g. treasury) — scope by entity_code
                        base_conditions.append(f"sr.entity_code = ${param_idx}")
                        params.append(supervisor_entity_code)
                        param_idx += 1

                # ── Site scoping: non-main-office supervisors auto-scoped to their site ──
                sup_location_id = agent_ctx.get("entity_location_id")
                sup_is_main = agent_ctx.get("is_main_office", False)
                if sup_location_id and not sup_is_main:
                    # Site supervisor — force filter to their location
                    base_conditions.append(f"sr.entity_location_id = ${param_idx}::uuid")
                    params.append(str(sup_location_id))
                    param_idx += 1

        # ── Optional site filter (main-office supervisors or admin) ──
        if entity_location_id:
            base_conditions.append(f"sr.entity_location_id = ${param_idx}::uuid")
            params.append(entity_location_id)
            param_idx += 1
        elif entity_code and is_admin:
            # Admin-only entity_code filter (supervisors are already scoped)
            base_conditions.append(f"sr.entity_code = ${param_idx}")
            params.append(entity_code)
            param_idx += 1

        if search:
            base_conditions.append(
                f"(sr.reference ILIKE ${param_idx} OR u.full_name ILIKE ${param_idx})"
            )
            params.append(f"%{search}%")
            param_idx += 1

        where_extra = (" AND " + " AND ".join(base_conditions)) if base_conditions else ""

        if tab == "unassigned":
            query = f"""
                SELECT sr.id, sr.reference, sr.workflow_code, sr.entity_code,
                       sr.status::text, sr.created_at, u.full_name as citizen_name,
                       e.name as entity_name,
                       'unassigned' as assignment_state,
                       NULL::text as assigned_agent_name,
                       NULL::uuid as current_assignment_id,
                       NULL::uuid as current_agent_profile_id
                FROM service_requests sr
                LEFT JOIN users u ON u.id = sr.user_id
                LEFT JOIN entities e ON e.code = sr.entity_code
                WHERE sr.status IN ('SUBMITTED', 'UNDER_REVIEW', 'IN_PROGRESS', 'DOCUMENTS_REQUIRED')
                  AND sr.escalated = false
                  AND NOT EXISTS (
                      SELECT 1 FROM assignments a
                      WHERE a.item_id = sr.id
                        AND a.status IN ('assigned', 'in_progress', 'pending_review')
                  )
                  {where_extra}
                ORDER BY sr.created_at ASC
                LIMIT ${param_idx} OFFSET ${param_idx + 1}
            """
            count_query = f"""
                SELECT COUNT(*) FROM service_requests sr
                LEFT JOIN users u ON u.id = sr.user_id
                WHERE sr.status IN ('SUBMITTED', 'UNDER_REVIEW', 'IN_PROGRESS', 'DOCUMENTS_REQUIRED')
                  AND sr.escalated = false
                  AND NOT EXISTS (
                      SELECT 1 FROM assignments a
                      WHERE a.item_id = sr.id
                        AND a.status IN ('assigned', 'in_progress', 'pending_review')
                  )
                  {where_extra}
            """
        elif tab == "escalated":
            query = f"""
                SELECT sr.id, sr.reference, sr.workflow_code, sr.entity_code,
                       sr.status::text, sr.created_at, u.full_name as citizen_name,
                       e.name as entity_name,
                       CASE WHEN sr.assigned_to IS NULL THEN 'pending'
                            ELSE 'in_review' END as assignment_state,
                       assigned_user.full_name as assigned_agent_name,
                       NULL::uuid as current_assignment_id,
                       NULL::uuid as current_agent_profile_id
                FROM service_requests sr
                LEFT JOIN users u ON u.id = sr.user_id
                LEFT JOIN entities e ON e.code = sr.entity_code
                LEFT JOIN users assigned_user ON assigned_user.id = sr.assigned_to
                WHERE sr.escalated = true
                  {where_extra}
                ORDER BY sr.escalated_at DESC NULLS LAST, sr.created_at DESC
                LIMIT ${param_idx} OFFSET ${param_idx + 1}
            """
            count_query = f"""
                SELECT COUNT(*) FROM service_requests sr
                LEFT JOIN users u ON u.id = sr.user_id
                WHERE sr.escalated = true
                  {where_extra}
            """
        elif tab == "active":
            query = f"""
                SELECT sr.id, sr.reference, sr.workflow_code, sr.entity_code,
                       sr.status::text, sr.created_at, u.full_name as citizen_name,
                       e.name as entity_name,
                       a.status::text as assignment_state,
                       agent_user.full_name as assigned_agent_name,
                       a.id as current_assignment_id,
                       a.agent_profile_id as current_agent_profile_id
                FROM service_requests sr
                LEFT JOIN users u ON u.id = sr.user_id
                LEFT JOIN entities e ON e.code = sr.entity_code
                JOIN assignments a ON a.item_id = sr.id
                    AND a.status IN ('assigned', 'in_progress')
                LEFT JOIN agent_profiles ap ON ap.id = a.agent_profile_id
                LEFT JOIN users agent_user ON agent_user.id = ap.user_id
                WHERE 1=1
                  {where_extra}
                ORDER BY a.assigned_at DESC
                LIMIT ${param_idx} OFFSET ${param_idx + 1}
            """
            count_query = f"""
                SELECT COUNT(*) FROM service_requests sr
                LEFT JOIN users u ON u.id = sr.user_id
                JOIN assignments a ON a.item_id = sr.id
                    AND a.status IN ('assigned', 'in_progress')
                WHERE 1=1
                  {where_extra}
            """
        else:
            raise HTTPException(status_code=400, detail=f"Invalid tab: {tab}")

        params.extend([page_size, offset])
        count_params = params[:-2]  # without limit/offset

        rows = await db.fetch(query, *params)
        total_row = await db.fetchval(count_query, *count_params)
        total = total_row or 0

        items = []
        for row in rows:
            items.append({
                "id": str(row["id"]),
                "reference": row["reference"],
                "workflow_code": row["workflow_code"],
                "entity_code": row["entity_code"],
                "status": row["status"],
                "created_at": row["created_at"].isoformat() if row["created_at"] else None,
                "citizen_name": row["citizen_name"] or "—",
                "entity_name": row["entity_name"] or row["entity_code"] or "—",
                "assignment_state": row["assignment_state"],
                "assigned_agent_name": row["assigned_agent_name"],
                "current_assignment_id": str(row["current_assignment_id"]) if row["current_assignment_id"] else None,
                "current_agent_profile_id": str(row["current_agent_profile_id"]) if row["current_agent_profile_id"] else None,
            })

        return {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching assignable items: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al obtener elementos asignables"
        )


@router.get("/available-agents-for-item/{entity_code}")
@require_permission("assignment.create")
async def get_available_agents_for_item(
    entity_code: str,
    current_user: UserResponse = Depends(get_current_user),
    permission_service: PermissionService = Depends(get_permission_service),
    db=Depends(get_db_connection),
):
    """
    Get available agents for a specific entity_code.
    Returns agents with their workload info, sorted by recommendation score.
    Scoped: non-admin supervisors can only fetch agents for their own entity.
    """
    try:
        # Security: verify supervisor has access to this entity
        is_admin = current_user.role == "admin"
        if not is_admin:
            agent_ctx = await get_agent_context(current_user.id, db)
            if agent_ctx.get("entity_id"):
                sup_ent = await db.fetchval(
                    "SELECT code FROM entities WHERE id = $1",
                    agent_ctx["entity_id"]
                )
                if sup_ent and sup_ent != entity_code:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="No tiene permiso para ver agentes de otra entidad"
                    )
        query = """
            SELECT
                ap.id as agent_profile_id,
                u.full_name,
                u.email,
                ap.is_supervisor,
                aw.current_assignments,
                aw.max_concurrent_assignments,
                aw.workload_status::text,
                aw.availability::text,
                aw.success_rate,
                aw.avg_processing_time_hours
            FROM agent_profiles ap
            JOIN users u ON u.id = ap.user_id
            JOIN entities e ON e.id = ap.entity_id
            LEFT JOIN agent_workloads aw ON aw.agent_profile_id = ap.id
            WHERE e.code = $1
              AND ap.is_active = true
              AND (aw.availability IS NULL OR aw.availability = 'available')
            ORDER BY
                COALESCE(aw.current_assignments, 0) ASC,
                COALESCE(aw.success_rate, 100) DESC,
                COALESCE(aw.avg_processing_time_hours, 999) ASC
        """
        rows = await db.fetch(query, entity_code)

        agents = []
        for i, row in enumerate(rows):
            current = row["current_assignments"] or 0
            max_cap = row["max_concurrent_assignments"] or 10
            agents.append({
                "agent_profile_id": str(row["agent_profile_id"]),
                "full_name": row["full_name"] or row["email"] or "—",
                "email": row["email"],
                "is_supervisor": row["is_supervisor"],
                "current_assignments": current,
                "max_concurrent_assignments": max_cap,
                "workload_status": row["workload_status"] or "available",
                "availability": row["availability"] or "available",
                "success_rate": float(row["success_rate"]) if row["success_rate"] else None,
                "avg_processing_hours": float(row["avg_processing_time_hours"]) if row["avg_processing_time_hours"] else None,
                "capacity_percent": round(current / max_cap * 100) if max_cap > 0 else 0,
                "is_recommended": i == 0,  # First agent = best score
            })

        return {"agents": agents, "entity_code": entity_code}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching agents for entity {entity_code}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al obtener agentes disponibles"
        )


@router.post("/manual", response_model=Assignment, status_code=status.HTTP_201_CREATED)
@require_permission("assignment.create")
async def create_manual_assignment(
    request: ManualAssignmentRequest,
    current_user: UserResponse = Depends(get_current_user),
    permission_service: PermissionService = Depends(get_permission_service),
    service: AssignmentService = Depends(get_assignment_service_dep),
    db = Depends(get_db_connection)
):
    """
    **Manually assign a declaration to an agent (Supervisor only)**

    Permissions:
    - Requires: assignment.create

    Validates:
    - Agent availability
    - Agent capacity
    - Agent role matches declaration type

    Returns:
    - Created assignment with status 'assigned'
    """

    try:
        # Convert user_id to agent_profile_id (Migration 054)
        # assigned_by_profile_id must reference agent_profiles.id, not users.id
        supervisor_profile_id = await _get_agent_profile_id_for_user(current_user.id, db)
        if not supervisor_profile_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Supervisor agent profile not found. Only agents can create assignments."
            )

        assignment = await service.assign_to_agent(
            db=db,
            item_id=request.item_id,
            item_type=request.item_type,
            agent_profile_id=request.agent_profile_id,
            supervisor_id=supervisor_profile_id,
            notes=request.notes,
            priority_level=request.priority_level,
            deadline_days=request.deadline_days
        )

        logger.info(
            f"Manual assignment created by {current_user.email} - "
            f"Assignment {assignment.id}"
        )

        return assignment

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error creating manual assignment: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create manual assignment"
        )


@router.post("/auto", response_model=Assignment, status_code=status.HTTP_201_CREATED)
@require_permission("assignment.auto_assign")
async def create_auto_assignment(
    request: AutoAssignmentRequest,
    current_user: UserResponse = Depends(get_current_user),
    permission_service: PermissionService = Depends(get_permission_service),
    service: AutoAssignmentService = Depends(get_auto_assignment_service_dep)
):
    """
    **Automatically assign declaration to best agent using intelligent algorithm**

    Permissions:
    - Requires: assignment.auto_assign

    Algorithm:
    1. Apply assignment rules to find filters
    2. Get eligible agents based on filters
    3. Score agents using multi-criteria algorithm (6 criteria)
    4. Select best agent (highest score)
    5. Create assignment and update workload

    Scoring Criteria:
    - Workload (30%): Current assignments
    - Speed (20%): Avg processing time
    - Success Rate (25%): Validation success rate
    - Specialization (15%): Type match
    - Pending Duration (10%): Age of pending assignments

    Returns:
    - Created assignment with auto_assignment_score
    """

    try:
        assignment = await service.auto_assign_item(
            item_id=request.item_id,
            item_type=request.item_type,
            item_data=request.item_data,
            entity_type=request.entity_type,
            entity_id=request.entity_id
        )

        logger.info(
            f"Auto-assignment created - Assignment {assignment.id}"
        )

        return assignment

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error creating auto assignment: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create auto assignment"
        )


@router.get("/{assignment_id}", response_model=Assignment)
@require_permission("assignment.view")
async def get_assignment(
    assignment_id: UUID,
    current_user: UserResponse = Depends(get_current_user),
    permission_service: PermissionService = Depends(get_permission_service),
    db = Depends(get_db_connection)
):
    """
    **Get assignment details by ID**

    Permissions:
    - Requires: assignment.view
    - Assigned agent can view own assignments
    - Supervisors can view all assignments under supervision
    - Admin can view all
    """

    repo = get_assignment_repository(db)
    assignment = await repo.get_by_id(db, assignment_id)

    if not assignment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Assignment {assignment_id} not found"
        )

    # Authorization check (Migration 048/054: uses agent_profiles)
    is_admin = current_user.role == "admin"

    # Get agent context for current user
    agent_ctx = await get_agent_context(current_user.id, db) if not is_admin else {}
    is_supervisor = is_admin or agent_ctx.get("is_supervisor", False)

    # Check if current user is the assigned agent (compare via agent_profile)
    user_agent_profile_id = await _get_agent_profile_id_for_user(current_user.id, db)
    is_assigned_agent = user_agent_profile_id and str(assignment.agent_profile_id) == str(user_agent_profile_id)

    if not (is_assigned_agent or is_supervisor):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only view your own assignments"
        )

    return assignment


@router.get("/", response_model=List[Assignment])
@require_permission("assignment.list")
async def list_assignments(
    agent_profile_id: Optional[UUID] = Query(None, description="Filter by agent_profile_id"),
    status_filter: Optional[AssignmentStatus] = Query(None, description="Filter by status"),
    item_id: Optional[UUID] = Query(None, description="Filter by item_id"),
    item_type: Optional[str] = Query(None, description="Filter by item_type"),
    limit: int = Query(50, ge=1, le=1000),  # Increased max to allow loading all data
    offset: int = Query(0, ge=0),
    current_user: UserResponse = Depends(get_current_user),
    permission_service: PermissionService = Depends(get_permission_service),
    db = Depends(get_db_connection)
):
    """
    **List assignments with filters**

    Permissions:
    - Requires: assignment.list
    - Agents can only list their own assignments
    - Supervisors can list all assignments under supervision
    - Admin can list all

    Query Parameters:
    - agent_profile_id: Filter by agent_profile.id (Migration 054)
    - status: Filter by status (assigned, in_progress, completed, etc.)
    - item_id: Get assignment for specific item (Migration 053)
    - item_type: Filter by item type
    - limit: Max results (default 50, max 200)
    - offset: Pagination offset

    Migration 053/054: Uses item_id/item_type and agent_profile_id
    """

    repo = get_assignment_repository(db)

    # Get agent context for authorization (Migration 048)
    is_admin = current_user.role == "admin"
    agent_ctx = await get_agent_context(current_user.id, db) if not is_admin else {}
    is_supervisor = is_admin or agent_ctx.get("is_supervisor", False)
    is_agent = current_user.role == "agent" and not is_supervisor

    # If regular agent (not supervisor), force filter to own assignments
    # Convert user_id to agent_profile_id
    if is_agent:
        user_agent_profile_id = await _get_agent_profile_id_for_user(current_user.id, db)
        if not user_agent_profile_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Agent profile not found for current user"
            )
        agent_profile_id = user_agent_profile_id

    # Entity-scoped filter: supervisors only see their entity's assignments
    entity_id = agent_ctx.get("entity_id") if (is_supervisor and not is_admin) else None

    try:
        # Use list_all with filters
        assignments = await repo.list_all(
            db=db,
            agent_profile_id=agent_profile_id,
            status=status_filter.value if status_filter else None,
            item_type=item_type,
            limit=limit,
            offset=offset,
            entity_id=entity_id,
        )
        return assignments

    except Exception as e:
        logger.error(f"Error listing assignments: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list assignments"
        )


@router.put("/{assignment_id}/start", response_model=Assignment)
@require_permission("assignment.start")
async def start_processing(
    assignment_id: UUID,
    request: StartProcessingRequest,
    current_user: UserResponse = Depends(get_current_user),
    permission_service: PermissionService = Depends(get_permission_service),
    service: AssignmentService = Depends(get_assignment_service_dep)
):
    """
    **Start processing an assignment (Agent action)**

    Permissions:
    - Requires: assignment.start
    - Assigned agent only

    State Transition:
    - assigned → in_progress
    - Sets started_at timestamp
    - Moves from pending_declarations to in_progress_declarations in workload
    """

    # Verify agent is assigned to this assignment
    db = service.assignment_repo.db
    repo = get_assignment_repository(db)
    assignment = await repo.get_by_id(db, assignment_id)

    if not assignment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Assignment {assignment_id} not found"
        )

    # Compare agent_profile_id (Migration 054)
    user_agent_profile_id = await _get_agent_profile_id_for_user(current_user.id, db)
    if not user_agent_profile_id or str(assignment.agent_profile_id) != str(user_agent_profile_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only start your own assignments"
        )

    try:
        updated = await service.start_processing(assignment_id)

        logger.info(
            f"Assignment {assignment_id} started by agent {current_user.email}"
        )

        return updated

    except Exception as e:
        logger.error(f"Error starting assignment: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to start assignment"
        )


@router.put("/{assignment_id}/complete", response_model=Assignment)
@require_permission("assignment.complete")
async def complete_assignment(
    assignment_id: UUID,
    request: CompleteAssignmentRequest,
    current_user: UserResponse = Depends(get_current_user),
    permission_service: PermissionService = Depends(get_permission_service),
    service: AssignmentService = Depends(get_assignment_service_dep)
):
    """
    **Complete an assignment (Agent action)**

    Permissions:
    - Requires: assignment.complete
    - Assigned agent only

    State Transition:
    - in_progress → completed
    - Sets completed_at timestamp
    - Auto-calculates processing_duration_hours (trigger)
    - Decrements agent workload
    - Updates agent performance metrics

    Request Body:
    - validation_status: "approved" or "rejected"
    - quality_score: 0-10 (optional)
    """

    # Verify agent is assigned
    db = service.assignment_repo.db
    repo = get_assignment_repository(db)
    assignment = await repo.get_by_id(db, assignment_id)

    if not assignment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Assignment {assignment_id} not found"
        )

    # Compare agent_profile_id (Migration 054)
    user_agent_profile_id = await _get_agent_profile_id_for_user(current_user.id, db)
    if not user_agent_profile_id or str(assignment.agent_profile_id) != str(user_agent_profile_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only complete your own assignments"
        )

    try:
        updated = await service.complete_assignment(
            assignment_id,
            request.validation_status,
            request.quality_score
        )

        logger.info(
            f"Assignment {assignment_id} completed by agent {current_user.email} - "
            f"Status: {request.validation_status}"
        )

        return updated

    except Exception as e:
        logger.error(f"Error completing assignment: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to complete assignment"
        )


@router.put("/{assignment_id}/reassign", response_model=Assignment)
@require_permission("assignment.reassign")
async def reassign_assignment(
    assignment_id: UUID,
    request: ReassignmentRequest,
    current_user: UserResponse = Depends(get_current_user),
    permission_service: PermissionService = Depends(get_permission_service),
    service: AssignmentService = Depends(get_assignment_service_dep),
    db = Depends(get_db_connection)
):
    """
    **Reassign declaration to a new agent (Supervisor only)**

    Permissions:
    - Requires: assignment.reassign (critical permission)
    - For in-progress assignments: requires assignment.reassign_in_progress

    Workflow:
    1. Mark current assignment as 'reassigned'
    2. Validate new agent eligibility
    3. Create new assignment for new agent
    4. Update workloads (decrement old, increment new)
    5. Record reassignment reason

    Allowed Reasons:
    - workload_rebalance
    - agent_unavailable
    - specialization_mismatch
    - performance_issues
    - agent_request
    - deadline_risk
    - quality_concerns
    - other
    """

    # Additional permission check for in-progress assignments
    db = service.assignment_repo.db
    repo = get_assignment_repository(db)
    assignment = await repo.get_by_id(db, assignment_id)

    if assignment and assignment.status == "in_progress":
        # Requires critical permission for in-progress reassignment
        has_critical_perm = await permission_service.has_permission(
            current_user.id,
            "assignment.reassign_in_progress"
        )

        if not has_critical_perm:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    "Reasignar una tarea EN CURSO requiere permiso crítico: "
                    "'assignment.reassign_in_progress'. Contacte a su administrador."
                )
            )

    try:
        # Convert user_id to agent_profile_id (Migration 054)
        supervisor_profile_id = await _get_agent_profile_id_for_user(current_user.id, db)
        if not supervisor_profile_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Supervisor agent profile not found"
            )

        # Validate before reassigning (cooldown, same-agent, terminal status)
        validation = await service.validate_reassignment(
            db=db,
            assignment_id=assignment_id,
            new_agent_profile_id=request.new_agent_profile_id,
            reason=request.reason,
        )
        if not validation["is_valid"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="; ".join(validation["errors"])
            )

        new_assignment = await service.reassign_to_new_agent(
            db=db,
            assignment_id=assignment_id,
            new_agent_profile_id=request.new_agent_profile_id,
            reason=request.reason,
            supervisor_id=supervisor_profile_id,
            notes=request.notes
        )

        logger.info(
            f"Assignment {assignment_id} reassigned by {current_user.email} - "
            f"New assignment: {new_assignment.id} - Reason: {request.reason}"
        )

        return new_assignment

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error reassigning assignment: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to reassign assignment"
        )


@router.delete("/{assignment_id}", status_code=status.HTTP_204_NO_CONTENT)
@require_permission("assignment.cancel")
async def cancel_assignment(
    assignment_id: UUID,
    current_user: UserResponse = Depends(get_current_user),
    permission_service: PermissionService = Depends(get_permission_service),
    service: AssignmentService = Depends(get_assignment_service_dep)
):
    """
    **Cancel an assignment (Supervisor only)**

    Permissions:
    - Requires: assignment.cancel (critical permission)

    State Transition:
    - any → cancelled
    - Decrements agent workload
    - Declaration becomes unassigned (can be reassigned)
    """

    try:
        await service.cancel_assignment(assignment_id)

        logger.info(
            f"Assignment {assignment_id} cancelled by {current_user.email}"
        )

        return None

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error cancelling assignment: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to cancel assignment"
        )


@router.patch("/{assignment_id}/priority", response_model=Assignment)
@require_permission("assignment.update_priority")
async def update_priority(
    assignment_id: UUID,
    request: UpdatePriorityRequest,
    current_user: UserResponse = Depends(get_current_user),
    permission_service: PermissionService = Depends(get_permission_service),
    service: AssignmentService = Depends(get_assignment_service_dep)
):
    """
    **Update assignment priority (Supervisor only)**

    Permissions:
    - Requires: assignment.update_priority

    Priority Levels (Migration 053):
    - 1-3: Low priority
    - 4-6: Medium priority (default: 5)
    - 7-8: High priority
    - 9-10: Urgent
    """

    try:
        updated = await service.update_priority(
            assignment_id,
            request.priority_level
        )

        if not updated:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Assignment {assignment_id} not found"
            )

        logger.info(
            f"Assignment {assignment_id} priority updated to {request.priority_level} "
            f"by {current_user.email}"
        )

        return updated

    except Exception as e:
        logger.error(f"Error updating priority: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update priority"
        )


@router.patch("/{assignment_id}/deadline", response_model=Assignment)
@require_permission("assignment.extend_deadline")
async def extend_deadline(
    assignment_id: UUID,
    request: ExtendDeadlineRequest,
    current_user: UserResponse = Depends(get_current_user),
    permission_service: PermissionService = Depends(get_permission_service),
    service: AssignmentService = Depends(get_assignment_service_dep)
):
    """
    **Extend assignment deadline (Supervisor only)**

    Permissions:
    - Requires: assignment.extend_deadline

    Parameters:
    - additional_days: Number of days to add (1-90)
    """

    try:
        updated = await service.extend_deadline(
            assignment_id,
            request.additional_days
        )

        if not updated:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Assignment {assignment_id} not found"
            )

        logger.info(
            f"Assignment {assignment_id} deadline extended by {request.additional_days} days "
            f"by {current_user.email}"
        )

        return updated

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error extending deadline: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to extend deadline"
        )


@router.patch("/{assignment_id}/notes", response_model=Assignment)
@require_permission("assignment.update_notes")
async def update_notes(
    assignment_id: UUID,
    request: UpdateNotesRequest,
    current_user: UserResponse = Depends(get_current_user),
    permission_service: PermissionService = Depends(get_permission_service),
    service: AssignmentService = Depends(get_assignment_service_dep),
    db = Depends(get_db_connection)
):
    """
    **Update assignment notes (Agent/Supervisor)**

    Permissions:
    - Requires: assignment.update_notes

    Notes can be updated by the assigned agent or a supervisor.
    Maximum length: 5000 characters.
    """

    try:
        updated = await service.update_notes(
            db=db,
            assignment_id=assignment_id,
            notes=request.notes
        )

        if not updated:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Assignment {assignment_id} not found"
            )

        logger.info(
            f"Assignment {assignment_id} notes updated by {current_user.email}"
        )

        return updated

    except Exception as e:
        logger.error(f"Error updating notes: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update notes"
        )


# ============================================================================
# ENDPOINTS - BULK OPERATIONS
# ============================================================================

class BulkReassignRequest(BaseModel):
    """Request to bulk reassign multiple assignments

    Migration 054: Uses agent_profile_id
    """
    assignment_ids: List[UUID] = Field(..., min_length=1, max_length=50)
    new_agent_profile_id: UUID = Field(..., description="Reference to agent_profiles.id")
    reason: ReassignmentReason
    notes: Optional[str] = None


class BulkReassignResult(BaseModel):
    """Result of bulk reassignment operation"""
    successful: List[str] = []
    failed: List[Dict[str, str]] = []
    total_processed: int = 0
    success_count: int = 0
    failure_count: int = 0


@router.post("/bulk/reassign", response_model=BulkReassignResult)
@require_permission("assignment.reassign")
async def bulk_reassign(
    request: BulkReassignRequest,
    current_user: UserResponse = Depends(get_current_user),
    permission_service: PermissionService = Depends(get_permission_service),
    service: AssignmentService = Depends(get_assignment_service_dep),
    db = Depends(get_db_connection)
):
    """
    **Bulk reassign multiple assignments to a new agent (Supervisor only)**

    Permissions:
    - Requires: assignment.reassign

    Request Body:
    - assignment_ids: List of assignment UUIDs (max 50)
    - new_agent_profile_id: Target agent
    - reason: Reassignment reason (from reassignment_reason_enum)
    - notes: Optional notes

    Returns:
    - successful: List of successfully reassigned assignment IDs
    - failed: List of failed assignments with error messages
    - total_processed, success_count, failure_count
    """
    # Get supervisor profile id
    supervisor_profile_id = await _get_agent_profile_id_for_user(current_user.id, db)
    if not supervisor_profile_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Supervisor agent profile not found"
        )

    result = BulkReassignResult(total_processed=len(request.assignment_ids))
    successful = []
    failed = []

    for assignment_id in request.assignment_ids:
        try:
            # Validate before reassigning
            validation = await service.validate_reassignment(
                db=db,
                assignment_id=assignment_id,
                new_agent_profile_id=request.new_agent_profile_id,
                reason=request.reason,
            )
            if not validation["is_valid"]:
                failed.append({
                    "assignment_id": str(assignment_id),
                    "error": "; ".join(validation["errors"])
                })
                continue

            await service.reassign_to_new_agent(
                db=db,
                assignment_id=assignment_id,
                new_agent_profile_id=request.new_agent_profile_id,
                reason=request.reason,
                supervisor_id=supervisor_profile_id,
                notes=request.notes
            )
            successful.append(str(assignment_id))
        except Exception as e:
            failed.append({
                "assignment_id": str(assignment_id),
                "error": str(e)
            })

    result.successful = successful
    result.failed = failed
    result.success_count = len(successful)
    result.failure_count = len(failed)

    logger.info(
        f"Bulk reassignment by {current_user.email}: "
        f"{result.success_count} successful, {result.failure_count} failed"
    )

    return result


# ============================================================================
# ENDPOINTS - STATISTICS
# ============================================================================

class AssignmentStatsResponse(BaseModel):
    """Assignment statistics response

    Provides aggregate statistics for assignments.
    """
    total_assigned: int = 0
    total_in_progress: int = 0
    total_pending_review: int = 0
    total_completed: int = 0
    total_cancelled: int = 0
    total_reassigned: int = 0
    total_rejected: int = 0
    average_processing_time_hours: Optional[float] = None
    on_time_completion_rate: Optional[float] = None
    by_item_type: Dict[str, int] = {}
    by_assignment_method: Dict[str, int] = {}


@router.get("/stats/summary", response_model=AssignmentStatsResponse)
@require_permission("assignment.view_stats")
async def get_assignment_stats(
    agent_profile_id: Optional[UUID] = Query(None, description="Filter by agent"),
    item_type: Optional[str] = Query(None, description="Filter by item type"),
    days: int = Query(30, ge=1, le=365, description="Period in days"),
    current_user: UserResponse = Depends(get_current_user),
    permission_service: PermissionService = Depends(get_permission_service),
    db = Depends(get_db_connection)
):
    """
    **Get assignment statistics summary**

    Permissions:
    - Requires: assignment.view_stats

    Query Parameters:
    - agent_profile_id: Filter by specific agent (optional)
    - item_type: Filter by item type (optional)
    - days: Period in days (default: 30, max: 365)

    Returns:
    - Counts by status
    - Average processing time
    - On-time completion rate
    - Breakdown by item_type
    - Breakdown by assignment_method
    """
    from datetime import datetime, timedelta, timezone

    # Build base query
    date_threshold = datetime.now(timezone.utc) - timedelta(days=days)

    # Entity scoping for supervisors (not admin)
    is_admin = current_user.role == "admin"
    agent_ctx = await get_agent_context(current_user.id, db) if not is_admin else {}
    supervisor_entity_id = agent_ctx.get("entity_id") if (not is_admin and agent_ctx.get("is_supervisor")) else None

    # Build filters — use alias 'a' since we may JOIN agent_profiles
    filters = ["a.created_at >= $1"]
    params: List[Any] = [date_threshold]
    param_idx = 2

    if agent_profile_id:
        filters.append(f"a.agent_profile_id = ${param_idx}")
        params.append(agent_profile_id)
        param_idx += 1

    if item_type:
        filters.append(f"a.item_type = ${param_idx}")
        params.append(item_type)
        param_idx += 1

    # Supervisor entity scoping via JOIN
    entity_join = ""
    if supervisor_entity_id:
        entity_join = "JOIN agent_profiles ap_s ON ap_s.id = a.agent_profile_id"
        filters.append(f"ap_s.entity_id = ${param_idx}")
        params.append(supervisor_entity_id)
        param_idx += 1

    where_clause = " AND ".join(filters)

    # Get counts by status
    status_query = f"""
        SELECT
            COUNT(*) FILTER (WHERE a.status = 'assigned') as assigned,
            COUNT(*) FILTER (WHERE a.status = 'in_progress') as in_progress,
            COUNT(*) FILTER (WHERE a.status = 'pending_review') as pending_review,
            COUNT(*) FILTER (WHERE a.status = 'completed') as completed,
            COUNT(*) FILTER (WHERE a.status = 'cancelled') as cancelled,
            COUNT(*) FILTER (WHERE a.status = 'reassigned') as reassigned,
            COUNT(*) FILTER (WHERE a.status = 'rejected') as rejected,
            AVG(a.processing_duration_hours) FILTER (WHERE a.status = 'completed') as avg_processing_time,
            AVG(CASE WHEN a.deadline_met = true THEN 1.0 ELSE 0.0 END)
                FILTER (WHERE a.status = 'completed' AND a.deadline IS NOT NULL) as on_time_rate
        FROM assignments a
        {entity_join}
        WHERE {where_clause}
    """

    status_row = await db.fetchrow(status_query, *params)

    # Get breakdown by item_type
    type_query = f"""
        SELECT a.item_type, COUNT(*) as count
        FROM assignments a
        {entity_join}
        WHERE {where_clause}
        GROUP BY a.item_type
    """
    type_rows = await db.fetch(type_query, *params)
    by_item_type = {row['item_type']: row['count'] for row in type_rows}

    # Get breakdown by assignment_method
    method_query = f"""
        SELECT a.assignment_method, COUNT(*) as count
        FROM assignments a
        {entity_join}
        WHERE {where_clause}
        GROUP BY a.assignment_method
    """
    method_rows = await db.fetch(method_query, *params)
    by_assignment_method = {row['assignment_method']: row['count'] for row in method_rows}

    response = AssignmentStatsResponse(
        total_assigned=status_row['assigned'] or 0,
        total_in_progress=status_row['in_progress'] or 0,
        total_pending_review=status_row['pending_review'] or 0,
        total_completed=status_row['completed'] or 0,
        total_cancelled=status_row['cancelled'] or 0,
        total_reassigned=status_row['reassigned'] or 0,
        total_rejected=status_row['rejected'] or 0,
        average_processing_time_hours=float(status_row['avg_processing_time']) if status_row['avg_processing_time'] else None,
        on_time_completion_rate=float(status_row['on_time_rate']) if status_row['on_time_rate'] else None,
        by_item_type=by_item_type,
        by_assignment_method=by_assignment_method
    )

    logger.info(f"Assignment stats retrieved by {current_user.email} for period: {days} days")

    return response
