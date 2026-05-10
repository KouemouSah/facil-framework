"""Mission Routes — API endpoints for field mission planning.

Prefix: /api/v1/inspections/missions

9 endpoints for supervisor mission planning + agent availability.
"""

import logging
from typing import Optional
from uuid import UUID
from datetime import date

from fastapi import APIRouter, HTTPException, Depends, Query
from fastapi.responses import StreamingResponse

from app.database.connection import get_database
from app.modules.auth.middleware.auth_middleware import get_current_user
from app.modules.users.models.user import UserResponse
from app.modules.permissions.middleware.permission_middleware import (
    permission_required,
)
from app.modules.inspections.models.mission import (
    MissionCreate,
    MissionUpdate,
    MissionAgentBatchAssign,
    MissionCompleteRequest,
    AgentStatusUpdate,
    MissionResponse,
    MissionListResponse,
    MissionListItem,
    ZoneSuggestion,
    AgentAvailability,
)
from app.modules.inspections.services.mission_service import (
    MissionService,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/inspections/missions", tags=["Inspection Missions"])


# ============================================================
# Static paths BEFORE /{id}
# ============================================================


@router.post("/", status_code=201)
async def create_mission(
    data: MissionCreate,
    db=Depends(get_database),
    current_user: UserResponse = Depends(get_current_user),
    _: None = Depends(permission_required("inspection.manage_missions")),
):
    """Create a new field mission."""
    try:
        async with db.transaction():
            result = await MissionService.create_mission(
                db, UUID(current_user.id), data.model_dump(),
            )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return result


@router.get("/")
async def list_missions(
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    status: Optional[str] = Query(None),
    entity_location_id: Optional[UUID] = Query(None, description="Filter by site (main-office supervisors)"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db=Depends(get_database),
    current_user: UserResponse = Depends(get_current_user),
    _: None = Depends(permission_required("inspection.view_entity")),
):
    """List missions. Supervisors see entity-wide, agents see assigned."""
    try:
        items, total = await MissionService.list_missions(
            db, UUID(current_user.id),
            date_from=date_from, date_to=date_to,
            status=status, page=page, page_size=page_size,
            entity_location_id=entity_location_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return MissionListResponse(
        items=[MissionListItem(**i) for i in items],
        total=total,
    )


@router.get("/suggest-zones")
async def suggest_zones(
    db=Depends(get_database),
    current_user: UserResponse = Depends(get_current_user),
    _: None = Depends(permission_required("inspection.manage_missions")),
):
    """Auto-suggest priority zones for mission planning."""
    try:
        zones = await MissionService.suggest_zones(
            db, UUID(current_user.id),
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return [ZoneSuggestion(**z) for z in zones]


@router.get("/agents/availability")
async def get_agents_availability(
    mission_date: date = Query(...),
    entity_location_id: Optional[UUID] = Query(None, description="Filter agents by location (prevents cross-site assignment)"),
    db=Depends(get_database),
    current_user: UserResponse = Depends(get_current_user),
    _: None = Depends(permission_required("inspection.manage_missions")),
):
    """Get agent availability for a specific date.

    Pass entity_location_id to filter agents to a specific site.
    Without it, returns all agents across all locations of the entity.
    """
    try:
        agents = await MissionService.get_agents_availability(
            db, UUID(current_user.id), mission_date,
            entity_location_id=entity_location_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return [AgentAvailability(**a) for a in agents]


# ============================================================
# Templates (recurring missions)
# ============================================================


@router.get("/templates")
async def list_templates(
    db=Depends(get_database),
    current_user: UserResponse = Depends(get_current_user),
    _: None = Depends(permission_required("inspection.manage_missions")),
):
    """List recurring mission templates for the supervisor's entity."""
    from app.modules.inspections.services.inspection_service import InspectionService
    ctx = await InspectionService.resolve_inspector_context(db, UUID(current_user.id))
    rows = await db.fetch("""
        SELECT mt.*, u.first_name || ' ' || u.last_name AS created_by_name
        FROM mission_templates mt
        JOIN users u ON u.id = mt.created_by
        WHERE mt.entity_id = $1
        ORDER BY mt.is_active DESC, mt.name
    """, ctx["entity_id"])
    return [dict(r) for r in rows]


@router.post("/templates", status_code=201)
async def create_template(
    data: dict,
    db=Depends(get_database),
    current_user: UserResponse = Depends(get_current_user),
    _: None = Depends(permission_required("inspection.manage_missions")),
):
    """Create a recurring mission template."""
    from app.modules.inspections.services.inspection_service import InspectionService
    ctx = await InspectionService.resolve_inspector_context(db, UUID(current_user.id))

    recurrence = data.get("recurrence")
    if recurrence not in ("daily", "weekly", "biweekly", "monthly"):
        raise HTTPException(status_code=422, detail="Invalid recurrence type")

    if recurrence in ("weekly", "biweekly") and data.get("day_of_week") is None:
        raise HTTPException(status_code=422, detail="day_of_week required for weekly/biweekly")

    if recurrence == "monthly" and data.get("day_of_month") is None:
        raise HTTPException(status_code=422, detail="day_of_month required for monthly")

    # Resolve entity_location_id — always use supervisor's own location
    # Never allow cross-entity location injection (OWASP A01)
    location_id = ctx.get("entity_location_id")
    if not location_id:
        raise HTTPException(
            status_code=422,
            detail="Cannot create template: supervisor has no entity_location_id"
        )

    row = await db.fetchrow("""
        INSERT INTO mission_templates (
            entity_id, entity_location_id, created_by,
            name, recurrence, day_of_week, day_of_month,
            zone_ids, default_agent_ids, target_inspections_per_agent, notes
        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
        RETURNING *
    """,
        ctx["entity_id"],
        location_id,
        UUID(current_user.id),
        data["name"],
        recurrence,
        data.get("day_of_week"),
        data.get("day_of_month"),
        data.get("zone_ids"),
        data.get("default_agent_ids"),
        data.get("target_inspections_per_agent", 10),
        data.get("notes"),
    )
    return dict(row)


@router.put("/templates/{template_id}")
async def update_template(
    template_id: UUID,
    data: dict,
    db=Depends(get_database),
    current_user: UserResponse = Depends(get_current_user),
    _: None = Depends(permission_required("inspection.manage_missions")),
):
    """Update a mission template (toggle active, change config)."""
    from app.modules.inspections.services.inspection_service import InspectionService
    ctx = await InspectionService.resolve_inspector_context(db, UUID(current_user.id))

    template = await db.fetchrow(
        "SELECT entity_id FROM mission_templates WHERE id = $1", template_id,
    )
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    if template["entity_id"] != ctx["entity_id"]:
        raise HTTPException(status_code=403, detail="Cannot modify another entity's template")

    # Whitelist of updatable columns — prevents SQL injection via column names
    ALLOWED_COLUMNS = frozenset({
        "name", "recurrence", "day_of_week", "day_of_month", "zone_ids",
        "default_agent_ids", "target_inspections_per_agent", "notes", "is_active",
    })
    updates = {k: v for k, v in data.items() if k in ALLOWED_COLUMNS}
    if not updates:
        raise HTTPException(status_code=422, detail="No valid fields to update")

    # Build parameterized SET clause (column names from frozenset, not user input)
    cols = list(updates.keys())
    set_parts = [f"{col} = ${i+2}" for i, col in enumerate(cols)]
    vals = [updates[col] for col in cols]
    row = await db.fetchrow(
        f"UPDATE mission_templates SET {', '.join(set_parts)} WHERE id = $1 RETURNING *",
        template_id, *vals,
    )
    return dict(row) if row else {}


@router.delete("/templates/{template_id}", status_code=204)
async def delete_template(
    template_id: UUID,
    db=Depends(get_database),
    current_user: UserResponse = Depends(get_current_user),
    _: None = Depends(permission_required("inspection.manage_missions")),
):
    """Delete a mission template."""
    from app.modules.inspections.services.inspection_service import InspectionService
    ctx = await InspectionService.resolve_inspector_context(db, UUID(current_user.id))

    template = await db.fetchrow(
        "SELECT entity_id FROM mission_templates WHERE id = $1", template_id,
    )
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    if template["entity_id"] != ctx["entity_id"]:
        raise HTTPException(status_code=403, detail="Cannot delete another entity's template")

    await db.execute("DELETE FROM mission_templates WHERE id = $1", template_id)


@router.post("/templates/{template_id}/run")
async def run_template(
    template_id: UUID,
    data: dict = {},
    db=Depends(get_database),
    current_user: UserResponse = Depends(get_current_user),
    _: None = Depends(permission_required("inspection.manage_missions")),
):
    """Manually run a template to create a mission for a specific date."""
    from datetime import datetime as dt
    from app.modules.inspections.services.inspection_service import InspectionService

    ctx = await InspectionService.resolve_inspector_context(db, UUID(current_user.id))

    tpl = await db.fetchrow("SELECT * FROM mission_templates WHERE id = $1", template_id)
    if not tpl:
        raise HTTPException(status_code=404, detail="Template not found")
    if tpl["entity_id"] != ctx["entity_id"]:
        raise HTTPException(status_code=403, detail="Cannot run another entity's template")
    if not tpl["is_active"]:
        raise HTTPException(status_code=422, detail="Template is inactive")

    # Target date: provided or tomorrow
    mission_date_str = data.get("mission_date")
    if mission_date_str:
        try:
            mission_date = date.fromisoformat(mission_date_str) if isinstance(mission_date_str, str) else mission_date_str
        except ValueError:
            raise HTTPException(status_code=422, detail="Invalid date format (YYYY-MM-DD)")
    else:
        from datetime import timedelta as td
        mission_date = date.today() + td(days=1)

    if mission_date < date.today():
        raise HTTPException(status_code=422, detail="Cannot create mission in the past")

    # Check UNIQUE
    existing = await db.fetchval("""
        SELECT id FROM field_missions
        WHERE entity_id = $1 AND entity_location_id = $2 AND mission_date = $3
    """, tpl["entity_id"], tpl["entity_location_id"], mission_date)
    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"Mission already exists for this location on {mission_date}"
        )

    try:
        async with db.transaction():
            mission = await db.fetchrow("""
                INSERT INTO field_missions (
                    entity_id, entity_location_id, supervisor_id,
                    mission_date, title, notes, zone_ids, status
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, 'planned')
                RETURNING *
            """,
                tpl["entity_id"], tpl["entity_location_id"],
                UUID(current_user.id), mission_date,
                f"{tpl['name']} ({mission_date.isoformat()})",
                tpl["notes"], tpl["zone_ids"],
            )

            # Auto-assign default agents
            assigned = 0
            for agent_id in (tpl["default_agent_ids"] or []):
                profile = await db.fetchrow("""
                    SELECT id FROM agent_profiles
                    WHERE user_id = $1 AND entity_id = $2 AND is_active = true AND is_supervisor = false
                """, agent_id, tpl["entity_id"])
                if not profile:
                    continue

                conflict = await db.fetchval("""
                    SELECT 1 FROM field_mission_agents fma
                    JOIN field_missions fm ON fm.id = fma.mission_id
                    WHERE fma.agent_id = $1 AND fm.mission_date = $2
                      AND fm.status IN ('planned', 'in_progress')
                """, agent_id, mission_date)
                if conflict:
                    continue

                await db.execute("""
                    INSERT INTO field_mission_agents (
                        mission_id, agent_id, agent_profile_id,
                        target_inspections, status
                    ) VALUES ($1, $2, $3, $4, 'assigned')
                """, mission["id"], agent_id, profile["id"],
                    tpl["target_inspections_per_agent"])
                assigned += 1

            # Update template tracking
            await db.execute("""
                UPDATE mission_templates
                SET last_created_at = NOW(), last_created_mission_id = $1
                WHERE id = $2
            """, mission["id"], template_id)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create mission: {e}")

    return {
        "mission_id": str(mission["id"]),
        "mission_date": str(mission_date),
        "agents_assigned": assigned,
        "template_name": tpl["name"],
    }


@router.post("/{mission_id}/auto-assign")
async def auto_assign_agents(
    mission_id: UUID,
    target_total: int = Query(50, ge=10, le=200, description="Total inspections target"),
    db=Depends(get_database),
    current_user: UserResponse = Depends(get_current_user),
    _: None = Depends(permission_required("inspection.manage_missions")),
):
    """Propose optimal agent assignments for a mission using scoring algorithm.

    Returns ranked list of agents with scores. Supervisor reviews and confirms
    via POST /missions/{id}/agents to finalize the assignment.
    """
    from app.modules.inspections.services.mission_auto_assigner import MissionAutoAssigner

    try:
        mission = await MissionService.get_mission(
            db, UUID(current_user.id), mission_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    if mission["status"] not in ("planned", "in_progress"):
        raise HTTPException(
            status_code=422,
            detail=f"Cannot auto-assign to mission in status '{mission['status']}'"
        )

    proposed = await MissionAutoAssigner.propose_assignments(
        db,
        mission_id=mission_id,
        entity_id=mission["entity_id"],
        entity_location_id=mission["entity_location_id"],
        zone_ids=mission.get("zone_ids"),
        target_total=target_total,
    )

    return {
        "mission_id": str(mission_id),
        "target_total": target_total,
        "agents_proposed": len(proposed),
        "proposals": proposed,
    }


# ============================================================
# Dynamic paths — /{mission_id}
# ============================================================


@router.get("/{mission_id}")
async def get_mission(
    mission_id: UUID,
    db=Depends(get_database),
    current_user: UserResponse = Depends(get_current_user),
    _: None = Depends(permission_required("inspection.view_entity")),
):
    """Get mission detail — IDOR-protected via service layer."""
    try:
        result = await MissionService.get_mission(
            db, UUID(current_user.id), mission_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return MissionResponse(**result)


@router.put("/{mission_id}")
async def update_mission(
    mission_id: UUID,
    data: MissionUpdate,
    db=Depends(get_database),
    current_user: UserResponse = Depends(get_current_user),
    _: None = Depends(permission_required("inspection.manage_missions")),
):
    """Update mission details (title, notes, zones, status)."""
    try:
        async with db.transaction():
            result = await MissionService.update_mission(
                db, UUID(current_user.id), mission_id,
                data.model_dump(exclude_unset=True),
            )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return result


@router.post("/{mission_id}/agents", status_code=201)
async def assign_agents(
    mission_id: UUID,
    data: MissionAgentBatchAssign,
    db=Depends(get_database),
    current_user: UserResponse = Depends(get_current_user),
    _: None = Depends(permission_required("inspection.manage_missions")),
):
    """Batch assign agents to a mission."""
    try:
        async with db.transaction():
            agents = await MissionService.assign_agents(
                db, UUID(current_user.id), mission_id,
                [a.model_dump() for a in data.agents],
            )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return agents


@router.delete("/{mission_id}/agents/{agent_id}", status_code=204)
async def remove_agent(
    mission_id: UUID,
    agent_id: UUID,
    db=Depends(get_database),
    current_user: UserResponse = Depends(get_current_user),
    _: None = Depends(permission_required("inspection.manage_missions")),
):
    """Remove an agent from a mission."""
    try:
        async with db.transaction():
            success = await MissionService.remove_agent(
                db, UUID(current_user.id), mission_id, agent_id,
            )
        if not success:
            raise HTTPException(status_code=404, detail="Agent not found in mission")
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.post("/{mission_id}/complete")
async def complete_mission(
    mission_id: UUID,
    data: MissionCompleteRequest,
    db=Depends(get_database),
    current_user: UserResponse = Depends(get_current_user),
    _: None = Depends(permission_required("inspection.manage_missions")),
):
    """Complete a mission with optional notes."""
    try:
        async with db.transaction():
            result = await MissionService.complete_mission(
                db, UUID(current_user.id), mission_id,
                notes=data.notes,
            )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return result


@router.put("/{mission_id}/agents/{agent_id}/status")
async def update_agent_mission_status(
    mission_id: UUID,
    agent_id: UUID,
    data: AgentStatusUpdate,
    db=Depends(get_database),
    current_user: UserResponse = Depends(get_current_user),
    _: None = Depends(permission_required("inspection.manage_missions")),
):
    """Update an agent's status within a mission (absent, active, etc.)."""
    try:
        async with db.transaction():
            result = await MissionService.update_agent_status(
                db, UUID(current_user.id), mission_id, agent_id,
                new_status=data.status.value,
                reason=data.reason,
            )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return result


@router.get("/{mission_id}/report")
async def download_mission_report(
    mission_id: UUID,
    db=Depends(get_database),
    current_user: UserResponse = Depends(get_current_user),
    _: None = Depends(permission_required("inspection.view_reports")),
):
    """Download mission completion report as PDF."""
    from app.modules.inspections.services.inspection_pdf_service import (
        inspection_pdf_service,
    )

    try:
        mission = await MissionService.get_mission(
            db, UUID(current_user.id), mission_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    if mission["status"] != "completed":
        raise HTTPException(
            status_code=422,
            detail="Report only available for completed missions",
        )

    lang = getattr(current_user, "preferred_language", "es") or "es"
    pdf_bytes = await inspection_pdf_service.generate_mission_report(
        db, str(mission_id), language=lang,
    )

    filename = f"mission_report_{mission['mission_date']}_{str(mission_id)[:8]}.pdf"
    return StreamingResponse(
        iter([pdf_bytes]),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
