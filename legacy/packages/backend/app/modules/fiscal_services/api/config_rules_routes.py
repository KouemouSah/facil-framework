"""Config Rules Routes — API endpoints for fiscal_config_rules.

Prefix: /api/v1/config-rules

7 endpoints:
  GET    /                 — List rules (paginated, filtered)
  GET    /resolve          — Preview resolution for a specific item
  POST   /recompute        — Force recompute effective configs
  GET    /{rule_id}        — Get single rule
  POST   /                 — Create rule
  PUT    /{rule_id}        — Update rule
  DELETE /{rule_id}        — Delete rule
"""

from fastapi import APIRouter, HTTPException, Depends, Query
from typing import Optional
from uuid import UUID
from loguru import logger

from app.database.connection import get_database
from app.modules.auth.middleware.auth_middleware import get_current_user
from app.modules.users.models.user import UserResponse
from app.modules.permissions.middleware.permission_middleware import permission_required
from app.modules.fiscal_services.models.config_rules import (
    ConfigRuleCreate,
    ConfigRuleUpdate,
    ConfigRuleResponse,
    ConfigRuleListResponse,
    RecomputeResult,
)
from app.modules.fiscal_services.services.config_rules_service import (
    ConfigRulesService,
)

router = APIRouter(prefix="/config-rules", tags=["Config Rules"])


# ============================================================
# Static paths MUST be before /{rule_id} to avoid UUID conflict
# ============================================================

@router.get("/", response_model=ConfigRuleListResponse)
async def list_config_rules(
    config_type: Optional[str] = Query(None, max_length=30),
    bundle_id: Optional[UUID] = Query(None),
    is_enabled: Optional[bool] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db=Depends(get_database),
    current_user: UserResponse = Depends(get_current_user),
    _: None = Depends(permission_required("fiscal_service.view_bundles")),
):
    """List config rules with filters and pagination."""
    rules, total = await ConfigRulesService.list_rules(
        db,
        config_type=config_type,
        bundle_id=bundle_id,
        is_enabled=is_enabled,
        page=page,
        page_size=page_size,
    )
    return ConfigRuleListResponse(
        items=[ConfigRuleResponse(**r) for r in rules],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/resolve")
async def resolve_effective_config(
    bundle_id: UUID = Query(...),
    fee_type: str = Query(..., max_length=20),
    item_id: UUID = Query(...),
    ministry_id: Optional[int] = Query(None),
    db=Depends(get_database),
    current_user: UserResponse = Depends(get_current_user),
    _: None = Depends(permission_required("fiscal_service.view_bundles")),
):
    """Preview which config rules win for a specific item.

    Debug/admin endpoint: shows the resolved penalty + deadline rules
    with their specificity, letting admins verify the config cascade.
    """
    result = await ConfigRulesService.resolve_for_item(
        db, bundle_id, fee_type, ministry_id, item_id,
    )
    return result


@router.post("/recompute", response_model=RecomputeResult)
async def recompute_effective_configs(
    bundle_id: Optional[UUID] = Query(None),
    db=Depends(get_database),
    current_user: UserResponse = Depends(get_current_user),
    _: None = Depends(permission_required("fiscal_service.manage_bundles")),
):
    """Force recompute of materialized effective configs on items.

    Normally auto-triggered by DB trigger on config_rules changes.
    This endpoint allows manual recompute (e.g., after timezone/date change).
    """
    affected = await ConfigRulesService.recompute(db, bundle_id)
    return RecomputeResult(affected_items=affected, bundle_id=bundle_id)


# ============================================================
# CRUD — /{rule_id} MUST be LAST
# ============================================================

@router.get("/{rule_id}", response_model=ConfigRuleResponse)
async def get_config_rule(
    rule_id: UUID,
    db=Depends(get_database),
    current_user: UserResponse = Depends(get_current_user),
    _: None = Depends(permission_required("fiscal_service.view_bundles")),
):
    """Get a single config rule by ID."""
    rule = await ConfigRulesService.get_rule(db, rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="Config rule not found")
    return ConfigRuleResponse(**rule)


@router.post("/", response_model=ConfigRuleResponse, status_code=201)
async def create_config_rule(
    data: ConfigRuleCreate,
    db=Depends(get_database),
    current_user: UserResponse = Depends(get_current_user),
    _: None = Depends(permission_required("fiscal_service.manage_bundles")),
):
    """Create a new config rule.

    Validates scope (item belongs to bundle, ministry exists)
    and config shape (penalty needs rate, deadline needs month+day, etc.).
    """
    try:
        rule = await ConfigRulesService.create_rule(
            db, data.model_dump(), user_id=UUID(current_user.id),
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error(f"Config rule creation failed: {e}")
        raise HTTPException(
            status_code=422,
            detail=f"Error al crear la regla: {type(e).__name__}",
        )
    return ConfigRuleResponse(**rule)


@router.put("/{rule_id}", response_model=ConfigRuleResponse)
async def update_config_rule(
    rule_id: UUID,
    data: ConfigRuleUpdate,
    db=Depends(get_database),
    current_user: UserResponse = Depends(get_current_user),
    _: None = Depends(permission_required("fiscal_service.manage_bundles")),
):
    """Update a config rule (partial update).

    Only updatable fields: effective_from, effective_to, is_enabled,
    config, name_es, description. Scope fields (bundle_id, fee_type,
    ministry_id, item_id) are immutable — delete and recreate instead.
    """
    try:
        rule = await ConfigRulesService.update_rule(
            db, rule_id, data.model_dump(exclude_unset=True),
            user_id=UUID(current_user.id),
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        # DB errors (trigger trg_auto_recompute_config failures,
        # constraint violations, etc.) must not bubble up as 500.
        logger.error(f"Config rule update failed for {rule_id}: {e}")
        raise HTTPException(
            status_code=422,
            detail=f"Error al actualizar la regla: {type(e).__name__}",
        )
    if not rule:
        raise HTTPException(status_code=404, detail="Config rule not found")
    return ConfigRuleResponse(**rule)


@router.delete("/{rule_id}", status_code=204)
async def delete_config_rule(
    rule_id: UUID,
    db=Depends(get_database),
    current_user: UserResponse = Depends(get_current_user),
    _: None = Depends(permission_required("fiscal_service.manage_bundles")),
):
    """Delete a config rule. Trigger auto-recomputes affected items."""
    success = await ConfigRulesService.delete_rule(db, rule_id)
    if not success:
        raise HTTPException(status_code=404, detail="Config rule not found")
