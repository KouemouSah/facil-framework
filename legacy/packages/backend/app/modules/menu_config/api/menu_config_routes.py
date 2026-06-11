"""
Menu Configuration API Routes

Provides endpoints for:
- GET /me: Get current agent's menu config (auto-generated or role-based)
- CRUD for workflow mappings (admin only)

Author: Claude Code Expert
Date: 2026-01-19
Updated: 2026-01-31 - Removed unused menu_templates endpoints
"""
from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, status
from loguru import logger
import asyncpg

from app.database.connection import get_database
from app.modules.auth.dependencies import get_current_user
from app.modules.users.models.user import UserResponse
from app.modules.permissions.services.permission_service import (
    get_permission_service,
    PermissionService,
)
from app.modules.menu_config.services.menu_config_service import (
    get_menu_config_service,
    MenuConfigService,
)
from app.modules.menu_config.repositories.workflow_mapping_repository import (
    WorkflowMappingRepository,
)
from app.core.cache import (
    invalidate_workflow_mappings_cache,
    invalidate_role_menu_cache,
)
from app.modules.menu_config.models.menu_config import (
    AgentMenuConfigResponse,
    WorkflowMenuMappingCreate,
    WorkflowMenuMappingUpdate,
    WorkflowMenuMappingResponse,
    WorkflowMenuMappingListResponse,
    WorkflowDisplayConfigCreate,
    WorkflowDisplayConfigUpdate,
    WorkflowDisplayConfigResponse,
    WorkflowDisplayConfigListResponse,
    AvailableColumn,
    AvailableColumnsResponse,
    WorkflowCodeResponse,
    WorkflowCodeListResponse,
    SampleRequestResponse,
)
from app.modules.menu_config.repositories.display_config_repository import (
    DisplayConfigRepository,
)


router = APIRouter(prefix="/menu-config", tags=["Menu Configuration"])


# =============================================================================
# HEALTH CHECK ENDPOINT
# =============================================================================

@router.get(
    "/health",
    summary="Menu config health check",
    description="Returns orphan counts: workflows without mappings, without display configs, and orphan mappings.",
)
async def get_menu_health(
    current_user: UserResponse = Depends(get_current_user),
    db: asyncpg.Connection = Depends(get_database),
    permission_service: PermissionService = Depends(get_permission_service),
):
    """Server-side orphan detection — replicates OrphanDetectionPanel logic."""
    await permission_service.check_permission(
        current_user.id, "menu.view_mappings", raise_exception=True
    )

    # 1. All workflow codes referenced by entities
    entity_rows = await db.fetch("""
        SELECT code, name, workflow_codes
        FROM entities
        WHERE is_active = true AND workflow_codes IS NOT NULL
    """)
    all_workflow_codes: set[str] = set()
    for row in entity_rows:
        wc = row["workflow_codes"]
        if isinstance(wc, list):
            all_workflow_codes.update(wc)
        elif isinstance(wc, str):
            import json as _json
            try:
                all_workflow_codes.update(_json.loads(wc))
            except (ValueError, TypeError):
                pass

    # 2. Active mappings
    mapping_rows = await db.fetch("""
        SELECT workflow_pattern FROM workflow_menu_mapping WHERE is_active = true
    """)
    patterns = [r["workflow_pattern"] for r in mapping_rows]

    # 3. Active display configs
    dc_rows = await db.fetch("""
        SELECT workflow_code FROM workflow_display_config WHERE is_active = true
    """)
    dc_codes = {r["workflow_code"] for r in dc_rows}

    # 4. Match workflows against patterns (SQL LIKE logic: % = wildcard)
    import re as _re

    def _like_to_regex(pattern: str) -> _re.Pattern:
        escaped = _re.escape(pattern).replace(r"\%", ".*").replace(r"\_", ".")
        return _re.compile(f"^{escaped}$", _re.IGNORECASE)

    compiled = [_like_to_regex(p) for p in patterns]

    workflows_without_mapping = []
    workflows_without_display = []
    for wc in sorted(all_workflow_codes):
        has_mapping = any(rx.match(wc) for rx in compiled)
        if not has_mapping:
            workflows_without_mapping.append(wc)
        if wc not in dc_codes:
            workflows_without_display.append(wc)

    # 5. Orphan mappings (patterns matching no entity workflow)
    orphan_mappings = []
    for pattern in patterns:
        rx = _like_to_regex(pattern)
        if not any(rx.match(wc) for wc in all_workflow_codes):
            orphan_mappings.append(pattern)

    total = len(workflows_without_mapping) + len(workflows_without_display) + len(orphan_mappings)

    return {
        "status": "healthy" if total == 0 else "degraded",
        "total_issues": total,
        "workflows_without_mapping": workflows_without_mapping,
        "workflows_without_display_config": workflows_without_display,
        "orphan_mappings": orphan_mappings,
        "entity_workflow_count": len(all_workflow_codes),
        "mapping_count": len(patterns),
        "display_config_count": len(dc_codes),
    }


# =============================================================================
# AGENT MENU CONFIG ENDPOINT
# =============================================================================

@router.get(
    "/me",
    response_model=AgentMenuConfigResponse,
    summary="Get current agent's menu configuration",
    description="""
    Returns the complete menu and dashboard configuration for the current agent.

    For workflow-based entities (CNEDOGE, DGT, etc.):
    - Menus are auto-generated from entity.workflow_codes using mapping rules

    For module-based entities (TESORO):
    - Menus come from the role's menu_config
    """
)
async def get_my_menu_config(
    current_user: UserResponse = Depends(get_current_user),
    db: asyncpg.Connection = Depends(get_database),
    menu_service: MenuConfigService = Depends(get_menu_config_service),
):
    """Get current agent's menu configuration"""

    # Get agent profile for current user
    agent_profile = await db.fetchrow("""
        SELECT id, user_id, entity_id
        FROM agent_profiles
        WHERE user_id = $1 AND is_active = true
    """, current_user.id)

    if not agent_profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent profile not found for current user"
        )

    try:
        menu_config = await menu_service.get_agent_menu_config(
            agent_profile_id=agent_profile['id'],
            user_id=UUID(current_user.id),
            db_connection=db
        )
        return menu_config
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error getting menu config: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get menu configuration"
        )


# =============================================================================
# WORKFLOW MAPPINGS CRUD ENDPOINTS (Admin only)
# =============================================================================

@router.get(
    "/workflow-mappings",
    response_model=WorkflowMenuMappingListResponse,
    summary="List workflow menu mappings",
    description="Get all workflow menu mappings with pagination. Requires menu.view_mappings permission."
)
async def list_workflow_mappings(
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    current_user: UserResponse = Depends(get_current_user),
    db: asyncpg.Connection = Depends(get_database),
    permission_service: PermissionService = Depends(get_permission_service),
):
    """List all workflow menu mappings with pagination"""

    # Check permission
    await permission_service.check_permission(
        current_user.id, "menu.view_mappings", raise_exception=True
    )

    repo = WorkflowMappingRepository(db)

    offset = (page - 1) * page_size
    mappings = await repo.get_all(
        is_active=is_active,
        limit=page_size,
        offset=offset
    )

    total = await repo.count(is_active=is_active)
    pages = (total + page_size - 1) // page_size

    return WorkflowMenuMappingListResponse(
        items=[WorkflowMenuMappingResponse(**m) for m in mappings],
        total=total,
        page=page,
        page_size=page_size,
        pages=pages
    )


@router.post(
    "/workflow-mappings",
    response_model=WorkflowMenuMappingResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create workflow mapping",
    description="Create a new workflow menu mapping. Requires menu.create_mapping permission."
)
async def create_workflow_mapping(
    mapping: WorkflowMenuMappingCreate,
    current_user: UserResponse = Depends(get_current_user),
    db: asyncpg.Connection = Depends(get_database),
    permission_service: PermissionService = Depends(get_permission_service),
):
    """Create a new workflow menu mapping"""

    # Check permission
    await permission_service.check_permission(
        current_user.id, "menu.create_mapping", raise_exception=True
    )

    repo = WorkflowMappingRepository(db)

    # Check if pattern already exists
    existing = await repo.get_by_pattern(mapping.workflow_pattern)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Mapping with pattern '{mapping.workflow_pattern}' already exists"
        )

    created = await repo.create(mapping)

    # Invalidate caches: mapping list + per-agent menus
    await invalidate_workflow_mappings_cache()
    await invalidate_role_menu_cache("_all_")

    return WorkflowMenuMappingResponse(**created)


@router.get(
    "/workflow-mappings/{mapping_id}",
    response_model=WorkflowMenuMappingResponse,
    summary="Get workflow mapping",
    description="Get a workflow mapping by ID. Requires menu.view_mappings permission."
)
async def get_workflow_mapping(
    mapping_id: int,
    current_user: UserResponse = Depends(get_current_user),
    db: asyncpg.Connection = Depends(get_database),
    permission_service: PermissionService = Depends(get_permission_service),
):
    """Get a workflow mapping by ID"""

    # Check permission
    await permission_service.check_permission(
        current_user.id, "menu.view_mappings", raise_exception=True
    )

    repo = WorkflowMappingRepository(db)
    mapping = await repo.get_by_id(mapping_id)

    if not mapping:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Mapping with id '{mapping_id}' not found"
        )

    return WorkflowMenuMappingResponse(**mapping)


@router.put(
    "/workflow-mappings/{mapping_id}",
    response_model=WorkflowMenuMappingResponse,
    summary="Update workflow mapping",
    description="Update a workflow mapping. Requires menu.update_mapping permission."
)
async def update_workflow_mapping(
    mapping_id: int,
    mapping: WorkflowMenuMappingUpdate,
    current_user: UserResponse = Depends(get_current_user),
    db: asyncpg.Connection = Depends(get_database),
    permission_service: PermissionService = Depends(get_permission_service),
):
    """Update a workflow mapping"""

    # Check permission
    await permission_service.check_permission(
        current_user.id, "menu.update_mapping", raise_exception=True
    )

    repo = WorkflowMappingRepository(db)
    updated = await repo.update(mapping_id, mapping)

    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Mapping with id '{mapping_id}' not found"
        )

    # Invalidate caches: mapping list + per-agent menus
    await invalidate_workflow_mappings_cache()
    await invalidate_role_menu_cache("_all_")

    return WorkflowMenuMappingResponse(**updated)


@router.delete(
    "/workflow-mappings/{mapping_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete workflow mapping",
    description="Delete a workflow mapping. Requires menu.delete_mapping permission."
)
async def delete_workflow_mapping(
    mapping_id: int,
    current_user: UserResponse = Depends(get_current_user),
    db: asyncpg.Connection = Depends(get_database),
    permission_service: PermissionService = Depends(get_permission_service),
):
    """Delete a workflow mapping"""

    # Check permission
    await permission_service.check_permission(
        current_user.id, "menu.delete_mapping", raise_exception=True
    )

    repo = WorkflowMappingRepository(db)
    deleted = await repo.delete(mapping_id)

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Mapping with id '{mapping_id}' not found"
        )

    # Invalidate caches: mapping list + per-agent menus
    await invalidate_workflow_mappings_cache()
    await invalidate_role_menu_cache("_all_")


# =============================================================================
# WORKFLOW CODES ENDPOINT (for dropdown selection)
# =============================================================================

@router.get(
    "/workflows",
    response_model=WorkflowCodeListResponse,
    summary="List available workflow codes",
    description="Get all distinct workflow codes from workflows table for dropdown selection."
)
async def list_workflow_codes(
    current_user: UserResponse = Depends(get_current_user),
    db: asyncpg.Connection = Depends(get_database),
    permission_service: PermissionService = Depends(get_permission_service),
):
    """List all available workflow codes for dropdown selection."""
    # Check permission
    await permission_service.check_permission(
        current_user.id, "menu.view_mappings", raise_exception=True
    )

    # Query distinct workflows from workflows table
    query = """
        SELECT code, name_es, category
        FROM workflows
        WHERE is_active = true
        ORDER BY category NULLS LAST, code
    """
    rows = await db.fetch(query)

    items = [
        WorkflowCodeResponse(
            code=row["code"],
            name_es=row["name_es"],
            category=row.get("category")
        )
        for row in rows
    ]

    return WorkflowCodeListResponse(items=items, total=len(items))


# =============================================================================
# WORKFLOW DISPLAY CONFIG CRUD ENDPOINTS (Admin only)
# =============================================================================

@router.get(
    "/display-configs",
    response_model=WorkflowDisplayConfigListResponse,
    summary="List workflow display configurations",
    description="Get all workflow display configs with pagination. Requires menu.view_mappings permission."
)
async def list_display_configs(
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    current_user: UserResponse = Depends(get_current_user),
    db: asyncpg.Connection = Depends(get_database),
    permission_service: PermissionService = Depends(get_permission_service),
):
    """List all workflow display configurations with pagination"""

    # Check permission
    await permission_service.check_permission(
        current_user.id, "menu.view_mappings", raise_exception=True
    )

    repo = DisplayConfigRepository(db)

    offset = (page - 1) * page_size
    configs = await repo.get_all(
        is_active=is_active,
        limit=page_size,
        offset=offset
    )

    total = await repo.count(is_active=is_active)
    pages = (total + page_size - 1) // page_size

    return WorkflowDisplayConfigListResponse(
        items=[WorkflowDisplayConfigResponse(**c) for c in configs],
        total=total,
        page=page,
        page_size=page_size,
        pages=pages
    )


@router.post(
    "/display-configs",
    response_model=WorkflowDisplayConfigResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create display configuration",
    description="Create a new workflow display configuration. Requires menu.create_mapping permission."
)
async def create_display_config(
    config: WorkflowDisplayConfigCreate,
    current_user: UserResponse = Depends(get_current_user),
    db: asyncpg.Connection = Depends(get_database),
    permission_service: PermissionService = Depends(get_permission_service),
):
    """Create a new workflow display configuration"""

    # Check permission
    await permission_service.check_permission(
        current_user.id, "menu.create_mapping", raise_exception=True
    )

    repo = DisplayConfigRepository(db)

    # Check if workflow_code already has a config
    existing = await repo.get_by_code(config.workflow_code)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Display config for workflow '{config.workflow_code}' already exists"
        )

    created = await repo.create(config)

    # Invalidate per-agent menus (display_configs are included in AgentMenuConfigResponse)
    await invalidate_role_menu_cache("_all_")

    return WorkflowDisplayConfigResponse(**created)


@router.get(
    "/display-configs/{config_id}",
    response_model=WorkflowDisplayConfigResponse,
    summary="Get display configuration",
    description="Get a display configuration by ID. Requires menu.view_mappings permission."
)
async def get_display_config(
    config_id: int,
    current_user: UserResponse = Depends(get_current_user),
    db: asyncpg.Connection = Depends(get_database),
    permission_service: PermissionService = Depends(get_permission_service),
):
    """Get a display configuration by ID"""

    # Check permission
    await permission_service.check_permission(
        current_user.id, "menu.view_mappings", raise_exception=True
    )

    repo = DisplayConfigRepository(db)
    config = await repo.get_by_id(config_id)

    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Display config with id '{config_id}' not found"
        )

    return WorkflowDisplayConfigResponse(**config)


@router.get(
    "/display-configs/by-workflow/{workflow_code}",
    response_model=WorkflowDisplayConfigResponse,
    summary="Get display config for workflow",
    description="Get display configuration for an exact workflow code."
)
async def get_display_config_for_workflow(
    workflow_code: str,
    current_user: UserResponse = Depends(get_current_user),
    db: asyncpg.Connection = Depends(get_database),
):
    """Get display configuration for a specific workflow code (exact match).
    Read-only endpoint — accessible to any authenticated user (agents need this for preview rendering).
    """

    repo = DisplayConfigRepository(db)
    config = await repo.find_config_for_workflow(workflow_code)

    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No display config found for workflow '{workflow_code}'"
        )

    return WorkflowDisplayConfigResponse(**config)


@router.put(
    "/display-configs/{config_id}",
    response_model=WorkflowDisplayConfigResponse,
    summary="Update display configuration",
    description="Update a display configuration. Requires menu.update_mapping permission."
)
async def update_display_config(
    config_id: int,
    config: WorkflowDisplayConfigUpdate,
    current_user: UserResponse = Depends(get_current_user),
    db: asyncpg.Connection = Depends(get_database),
    permission_service: PermissionService = Depends(get_permission_service),
):
    """Update a display configuration"""

    # Check permission
    await permission_service.check_permission(
        current_user.id, "menu.update_mapping", raise_exception=True
    )

    repo = DisplayConfigRepository(db)
    updated = await repo.update(config_id, config)

    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Display config with id '{config_id}' not found"
        )

    # Invalidate per-agent menus
    await invalidate_role_menu_cache("_all_")

    return WorkflowDisplayConfigResponse(**updated)


@router.delete(
    "/display-configs/{config_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete display configuration",
    description="Delete a display configuration. Requires menu.delete_mapping permission."
)
async def delete_display_config(
    config_id: int,
    current_user: UserResponse = Depends(get_current_user),
    db: asyncpg.Connection = Depends(get_database),
    permission_service: PermissionService = Depends(get_permission_service),
):
    """Delete a display configuration"""

    # Check permission
    await permission_service.check_permission(
        current_user.id, "menu.delete_mapping", raise_exception=True
    )

    repo = DisplayConfigRepository(db)
    deleted = await repo.delete(config_id)

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Display config with id '{config_id}' not found"
        )

    # Invalidate per-agent menus
    await invalidate_role_menu_cache("_all_")


# =============================================================================
# AVAILABLE COLUMNS DISCOVERY ENDPOINT
# =============================================================================

# System columns always available (from service_requests table + joins)
SYSTEM_COLUMNS = [
    AvailableColumn(
        id="reference",
        label_key="columns.reference",
        source="system",
        data_type="string",
        sample_count=0
    ),
    AvailableColumn(
        id="fullName",
        label_key="columns.fullName",
        source="system",
        data_type="string",
        sample_count=0
    ),
    AvailableColumn(
        id="solicitudType",
        label_key="columns.solicitudType",
        source="system",
        data_type="string",
        sample_count=0
    ),
    AvailableColumn(
        id="createdAt",
        label_key="columns.createdAt",
        source="system",
        data_type="date",
        sample_count=0
    ),
    AvailableColumn(
        id="priority",
        label_key="columns.priority",
        source="system",
        data_type="string",
        sample_count=0
    ),
    AvailableColumn(
        id="status",
        label_key="columns.status",
        source="system",
        data_type="string",
        sample_count=0
    ),
    AvailableColumn(
        id="totalAmount",
        label_key="columns.totalAmount",
        source="system",
        data_type="number",
        sample_count=0
    ),
    AvailableColumn(
        id="paymentStatus",
        label_key="columns.paymentStatus",
        source="system",
        data_type="string",
        sample_count=0
    ),
    AvailableColumn(
        id="assignedAgent",
        label_key="columns.assignedAgent",
        source="system",
        data_type="string",
        sample_count=0
    ),
]

@router.get(
    "/display-configs/available-columns/{workflow_code:path}",
    response_model=AvailableColumnsResponse,
    summary="Discover available columns for a workflow",
    description="""
    Discovers available columns for a workflow code from the workflow's
    document requirements and JSON extraction schemas.

    Source of truth: each workflow class defines its document requirements
    (with condition_type and schema_key). No longer depends on existing
    service_requests data.

    Supports filtering:
    - is_minor: Filter by minor status (true/false)

    Returns:
    - system_columns: Fixed columns from the service_requests table
    - extracted_columns: Columns from document extraction schemas
    - available_filters: Possible filter values for this workflow
    - filters_applied: Currently active filters
    - document_count: Number of documents with extraction schemas

    Requires menu.view_mappings permission.
    """
)
async def get_available_columns(
    workflow_code: str,
    is_minor: Optional[bool] = Query(None, description="Filter by minor status"),
    current_user: UserResponse = Depends(get_current_user),
    db: asyncpg.Connection = Depends(get_database),
    permission_service: PermissionService = Depends(get_permission_service),
):
    """Discover available columns for a workflow from document requirements + schemas"""

    # Check permission
    await permission_service.check_permission(
        current_user.id, "menu.view_mappings", raise_exception=True
    )

    repo = DisplayConfigRepository(db)

    try:
        result = await repo.get_available_columns_for_workflow(
            workflow_code,
            is_minor=is_minor,
        )

        # Build extracted columns list with new fields
        extracted_columns = [
            AvailableColumn(
                id=col["id"],
                label_key=col["label_key"],
                label=col.get("label", ""),
                source="extracted",
                data_type=col["data_type"],
                sample_count=col.get("sample_count", 0),
                document_code=col.get("document_code"),
                document_name_es=col.get("document_name_es"),
            )
            for col in result["extracted_columns"]
        ]

        return AvailableColumnsResponse(
            workflow_code=workflow_code,
            total_requests=result.get("total_requests", 0),
            system_columns=SYSTEM_COLUMNS,
            extracted_columns=extracted_columns,
            filters_applied=result.get("filters_applied"),
            available_filters=result.get("available_filters"),
            suggested_columns=result.get("suggested_columns", []),
            document_count=result.get("document_count", 0),
        )

    except Exception as e:
        logger.error(f"Error discovering columns for {workflow_code}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to discover columns: {str(e)}"
        )


@router.get(
    "/display-configs/sample-request/{workflow_code}",
    response_model=Optional[SampleRequestResponse],
    summary="Get sample request for preview",
    description="Get a sample service request for a workflow to preview real data."
)
async def get_sample_request(
    workflow_code: str,
    current_user: UserResponse = Depends(get_current_user),
    db: asyncpg.Connection = Depends(get_database),
    permission_service: PermissionService = Depends(get_permission_service),
):
    """Get a sample service request for preview purposes"""

    # Check permission
    await permission_service.check_permission(
        current_user.id, "menu.view_mappings", raise_exception=True
    )

    repo = DisplayConfigRepository(db)
    sample = await repo.get_sample_request(workflow_code)

    if not sample:
        return None

    return SampleRequestResponse(**sample)