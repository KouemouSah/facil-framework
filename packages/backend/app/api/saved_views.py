"""Saved views API (backlog ERP item 4) — the caller's own list-view presets.

Per-user (no extra permission): a principal manages only its own views. Used by
the DataGrid "Views" menu to save/apply/delete table query presets.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_session
from app.models.saved_view import SavedView
from app.security.auth_dep import require_auth

router = APIRouter(prefix="/api/v1/me/views", tags=["saved-views"])


def _owner(principal: dict) -> str:
    return principal.get("sub") or "break-glass"


class ViewIn(BaseModel):
    resource: str = Field(max_length=60)
    name: str = Field(min_length=1, max_length=120)
    config: dict = Field(default_factory=dict)


@router.get("")
async def list_views(resource: str | None = None,
                     principal: dict = Depends(require_auth),
                     session: AsyncSession = Depends(get_session)) -> list[dict]:
    stmt = select(SavedView).where(SavedView.account_id == _owner(principal))
    if resource:
        stmt = stmt.where(SavedView.resource == resource)
    stmt = stmt.order_by(SavedView.name)
    return [v.as_dict() for v in (await session.scalars(stmt)).all()]


@router.post("", status_code=201)
async def save_view(body: ViewIn, principal: dict = Depends(require_auth),
                    session: AsyncSession = Depends(get_session)) -> dict:
    owner = _owner(principal)
    # Upsert by (owner, resource, name) so re-saving a name overwrites its config.
    existing = await session.scalar(select(SavedView).where(
        SavedView.account_id == owner, SavedView.resource == body.resource,
        SavedView.name == body.name))
    if existing is not None:
        existing.config = body.config
        view = existing
    else:
        view = SavedView(account_id=owner, resource=body.resource,
                         name=body.name, config=body.config)
        session.add(view)
    await session.commit()
    return view.as_dict()


@router.delete("/{view_id}")
async def delete_view(view_id: str, principal: dict = Depends(require_auth),
                      session: AsyncSession = Depends(get_session)) -> dict:
    view = await session.get(SavedView, view_id)
    if view is None or view.account_id != _owner(principal):
        raise HTTPException(404, f"view '{view_id}' not found")
    await session.delete(view)
    await session.commit()
    return {"deleted": view_id}
