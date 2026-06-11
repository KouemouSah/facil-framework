"""Admin settings API — CRUD on the config-store (token-gated).

PUT/DELETE refresh the resolver's DB layer in-process (D1 invalidation).
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_session
from app.config_store import repository as repo
from app.models.setting import VALUE_TYPES
from app.security.admin_token import require_admin_token

router = APIRouter(
    prefix="/api/v1/admin/settings",
    tags=["admin-settings"],
    dependencies=[Depends(require_admin_token)],
)


class SettingIn(BaseModel):
    value: Any = None
    value_type: str = "string"
    scope: str = "global"
    secret_ref: str = ""
    name_es: str | None = None
    name_fr: str | None = None
    name_en: str | None = None
    description: str | None = None
    is_active: bool = True
    updated_by: str | None = None


async def _refresh_resolver(request: Request, session: AsyncSession) -> None:
    request.app.state.resolver.set_db(await repo.active_map(session))


@router.get("/")
async def list_settings(scope: str | None = None,
                        session: AsyncSession = Depends(get_session)) -> list[dict]:
    return [s.as_dict() for s in await repo.list_settings(session, scope)]


@router.get("/{key}")
async def get_setting(key: str, session: AsyncSession = Depends(get_session)) -> dict:
    obj = await repo.get_setting(session, key)
    if obj is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"setting '{key}' not found")
    return obj.as_dict()


@router.put("/{key}")
async def put_setting(key: str, body: SettingIn, request: Request,
                      session: AsyncSession = Depends(get_session)) -> dict:
    if body.value_type not in VALUE_TYPES:
        raise HTTPException(422, f"value_type must be one of {VALUE_TYPES}")
    obj = await repo.upsert_setting(
        session, key, body.value, value_type=body.value_type, scope=body.scope,
        secret_ref=body.secret_ref, updated_by=body.updated_by,
        name_es=body.name_es, name_fr=body.name_fr, name_en=body.name_en,
        description=body.description, is_active=body.is_active)
    await session.commit()
    await _refresh_resolver(request, session)
    return obj.as_dict()


@router.delete("/{key}")
async def delete_setting(key: str, request: Request,
                         session: AsyncSession = Depends(get_session)) -> dict:
    ok = await repo.delete_setting(session, key)
    await session.commit()
    await _refresh_resolver(request, session)
    if not ok:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"setting '{key}' not found")
    return {"deleted": key}
