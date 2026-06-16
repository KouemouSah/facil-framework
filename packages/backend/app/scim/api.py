"""SCIM 2.0 API — /scim/v2/Users + ServiceProviderConfig (D4.13).

Bearer-token gated (SCIM_TOKEN). Minimal but spec-shaped: list (filter
`userName eq "x"` + startIndex/count), get, create, replace (PUT), and PATCH for
the deprovision path (`active: false`).
"""

from __future__ import annotations

import re

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_session
from app.config import get_settings
from app.scim import service

router = APIRouter(prefix="/scim/v2", tags=["scim"])

_FILTER = re.compile(r'userName eq "([^"]+)"', re.IGNORECASE)


async def require_scim_token(authorization: str | None = Header(default=None)) -> None:
    token = get_settings().scim_token
    if not token:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE,
                            "SCIM locked: SCIM_TOKEN not configured")
    if not authorization or authorization.removeprefix("Bearer ").strip() != token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid SCIM token")


_GATE = Depends(require_scim_token)


class _Body(BaseModel):
    model_config = {"extra": "allow"}


def _err(e: service.ScimError) -> HTTPException:
    return HTTPException(e.status, e.detail)


@router.get("/ServiceProviderConfig", dependencies=[_GATE])
async def service_provider_config() -> dict:
    return {"schemas": ["urn:ietf:params:scim:schemas:core:2.0:ServiceProviderConfig"],
            "patch": {"supported": True}, "filter": {"supported": True, "maxResults": 200},
            "bulk": {"supported": False}, "changePassword": {"supported": False},
            "sort": {"supported": False}, "etag": {"supported": False}}


@router.get("/Users", dependencies=[_GATE])
async def list_users(filter: str | None = None, startIndex: int = 1,
                     count: int = 50,
                     session: AsyncSession = Depends(get_session)) -> dict:
    username = None
    if filter:
        m = _FILTER.search(filter)
        username = m.group(1) if m else "\x00no-match"  # unknown filter -> empty
    rows, total = await service.list_users(
        session, username=username, start=startIndex, count=min(count, 200))
    return {"schemas": [service.LIST_SCHEMA], "totalResults": total,
            "startIndex": startIndex, "itemsPerPage": len(rows),
            "Resources": [service.to_scim(a) for a in rows]}


@router.get("/Users/{user_id}", dependencies=[_GATE])
async def get_user(user_id: str,
                   session: AsyncSession = Depends(get_session)) -> dict:
    from app.identity import repository as identity_repo
    acc = await identity_repo.get_account(session, user_id)
    if acc is None:
        raise HTTPException(404, "user not found")
    return service.to_scim(acc)


@router.post("/Users", status_code=201, dependencies=[_GATE])
async def create_user(body: _Body,
                      session: AsyncSession = Depends(get_session)) -> dict:
    try:
        acc = await service.create_user(session, body.model_dump())
    except service.ScimError as e:
        raise _err(e) from e
    await session.commit()
    return service.to_scim(acc)


@router.put("/Users/{user_id}", dependencies=[_GATE])
async def replace_user(user_id: str, body: _Body,
                       session: AsyncSession = Depends(get_session)) -> dict:
    try:
        acc = await service.replace_user(session, user_id, body.model_dump())
    except service.ScimError as e:
        raise _err(e) from e
    await session.commit()
    return service.to_scim(acc)


@router.patch("/Users/{user_id}", dependencies=[_GATE])
async def patch_user(user_id: str, body: _Body, request: Request,
                     session: AsyncSession = Depends(get_session)) -> dict:
    # Minimal PATCH: honour the `active` operation (the deprovision path).
    data = body.model_dump()
    active = None
    for op in data.get("Operations", []):
        path = (op.get("path") or "").lower()
        val = op.get("value")
        if path == "active":
            active = val if isinstance(val, bool) else str(val).lower() == "true"
        elif isinstance(val, dict) and "active" in val:
            active = bool(val["active"])
    if active is None:
        raise HTTPException(400, "unsupported PATCH (only `active` is handled)")
    try:
        acc = await service.set_active(session, user_id, active)
    except service.ScimError as e:
        raise _err(e) from e
    await session.commit()
    return service.to_scim(acc)
