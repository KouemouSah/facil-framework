"""Admin providers API — CRUD on the provider registry (token-gated)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_session
from app.core.providers import repository as repo
from app.models.provider import CAPABILITIES
from app.security.admin_token import require_admin_token

router = APIRouter(
    prefix="/api/v1/admin/providers",
    tags=["admin-providers"],
    dependencies=[Depends(require_admin_token)],
)


class ProviderIn(BaseModel):
    config: dict[str, Any] = {}
    secret_ref: str = ""
    is_active: bool = True
    rate_limit_per_minute: int | None = None
    retry_attempts: int | None = None
    timeout_seconds: int | None = None
    updated_by: str | None = None


def _check_capability(capability: str) -> None:
    if capability not in CAPABILITIES:
        raise HTTPException(422, f"capability must be one of {CAPABILITIES}")


@router.get("/registered")
async def list_registered(request: Request) -> list[dict]:
    """What the running registry can instantiate (capability/code pairs)."""
    return [{"capability": c, "provider_code": k}
            for c, k in request.app.state.registry.registered]


@router.get("/")
async def list_providers(capability: str | None = None,
                         session: AsyncSession = Depends(get_session)) -> list[dict]:
    return [p.as_dict() for p in await repo.list_providers(session, capability)]


@router.get("/{capability}/{code}")
async def get_provider(capability: str, code: str,
                       session: AsyncSession = Depends(get_session)) -> dict:
    obj = await repo.get_provider(session, capability, code)
    if obj is None:
        raise HTTPException(404, f"provider {capability}/{code} not found")
    return obj.as_dict()


@router.put("/{capability}/{code}")
async def put_provider(capability: str, code: str, body: ProviderIn,
                       session: AsyncSession = Depends(get_session)) -> dict:
    _check_capability(capability)
    obj = await repo.upsert_provider(
        session, capability, code, config=body.config, secret_ref=body.secret_ref,
        is_active=body.is_active, updated_by=body.updated_by,
        rate_limit_per_minute=body.rate_limit_per_minute,
        retry_attempts=body.retry_attempts, timeout_seconds=body.timeout_seconds)
    await session.commit()
    return obj.as_dict()


@router.post("/{capability}/{code}/default")
async def set_default(capability: str, code: str,
                      session: AsyncSession = Depends(get_session)) -> dict:
    ok = await repo.set_default(session, capability, code)
    await session.commit()
    if not ok:
        raise HTTPException(404, f"provider {capability}/{code} not found")
    return {"capability": capability, "default": code}


@router.delete("/{capability}/{code}")
async def delete_provider(capability: str, code: str,
                          session: AsyncSession = Depends(get_session)) -> dict:
    ok = await repo.delete_provider(session, capability, code)
    await session.commit()
    if not ok:
        raise HTTPException(404, f"provider {capability}/{code} not found")
    return {"deleted": f"{capability}/{code}"}
