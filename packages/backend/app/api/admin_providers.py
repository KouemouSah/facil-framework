"""Admin providers API — CRUD on the provider registry (token-gated)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.concurrency import enforce_if_match, row_etag
from app.api.deps import get_session
from app.core.providers import repository as repo
from app.models.provider import CAPABILITIES, public_config, secret_keys_in
from app.security.permission_dep import require_permission

_MANAGE = Depends(require_permission("provider.manage"))

router = APIRouter(
    prefix="/api/v1/admin/providers",
    tags=["admin-providers"],
    dependencies=[Depends(require_permission("provider.read"))],
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


def _public(obj) -> dict:
    """Row → API dict: config stripped of any secret-bearing key + etag."""
    return {**obj.as_dict(), "config": public_config(obj.config), "etag": row_etag(obj)}


@router.get("/registered")
async def list_registered(request: Request) -> list[dict]:
    """What the running registry can instantiate (capability/code pairs) plus each
    type's declarative, non-secret `config_schema` — drives the admin form."""
    return request.app.state.registry.registered_detailed


@router.get("/llm/routing")
async def get_llm_routing(request: Request) -> dict:
    """Resolved role->provider routing + named providers (W6 ai.routing /
    ai.providers, with the sovereign split defaults when unset)."""
    router_ = request.app.state.llm_router
    return {"routing": router_.routing(), "providers": router_.providers()}


@router.post("/llm/routing/check")
async def check_llm_routing(request: Request,
                            session: AsyncSession = Depends(get_session)) -> dict:
    """Resolve every routed role to its concrete provider and probe it (real
    healthcheck, no mutation) — live validation of the routing layer."""
    return await request.app.state.llm_router.healthcheck(session)


@router.get("/")
async def list_providers(capability: str | None = None,
                         session: AsyncSession = Depends(get_session)) -> list[dict]:
    return [_public(p) for p in await repo.list_providers(session, capability)]


@router.get("/{capability}/{code}")
async def get_provider(capability: str, code: str,
                       session: AsyncSession = Depends(get_session)) -> dict:
    obj = await repo.get_provider(session, capability, code)
    if obj is None:
        raise HTTPException(404, f"provider {capability}/{code} not found")
    return _public(obj)


@router.put("/{capability}/{code}", dependencies=[_MANAGE])
async def put_provider(capability: str, code: str, body: ProviderIn, request: Request,
                       session: AsyncSession = Depends(get_session)) -> dict:
    _check_capability(capability)
    # Secrets discipline enforced at the authority (not just the UI): credentials
    # must never be stored in plaintext `config` — they travel via secret_ref/env.
    leaked = secret_keys_in(body.config)
    if leaked:
        raise HTTPException(
            422, f"config must not contain secret keys {sorted(leaked)}; use secret_ref")
    # Optimistic concurrency: if the client sent If-Match, reject a stale write
    # (409). Absent header = no check (create path / API clients).
    existing = await repo.get_provider(session, capability, code)
    if existing is not None:
        enforce_if_match(request, row_etag(existing))
    obj = await repo.upsert_provider(
        session, capability, code, config=body.config, secret_ref=body.secret_ref,
        is_active=body.is_active, updated_by=body.updated_by,
        rate_limit_per_minute=body.rate_limit_per_minute,
        retry_attempts=body.retry_attempts, timeout_seconds=body.timeout_seconds)
    await session.commit()
    return _public(obj)


@router.post("/{capability}/{code}/check")
async def check_provider(capability: str, code: str, request: Request,
                         session: AsyncSession = Depends(get_session)) -> dict:
    """Instantiate the provider (with its DB config if any) and run its
    connectivity healthcheck — real, no mutation."""
    registry = request.app.state.registry
    if not registry.is_registered(capability, code):
        raise HTTPException(404, f"provider {capability}/{code} is not registered")
    row = await repo.get_provider(session, capability, code)
    provider = registry.build(capability, code, row.config if row else {})
    result = await provider.healthcheck()
    return {"capability": capability, "provider_code": code, **result}


@router.post("/{capability}/{code}/default", dependencies=[_MANAGE])
async def set_default(capability: str, code: str,
                      session: AsyncSession = Depends(get_session)) -> dict:
    ok = await repo.set_default(session, capability, code)
    await session.commit()
    if not ok:
        raise HTTPException(404, f"provider {capability}/{code} not found")
    return {"capability": capability, "default": code}


@router.delete("/{capability}/{code}", dependencies=[_MANAGE])
async def delete_provider(capability: str, code: str,
                          session: AsyncSession = Depends(get_session)) -> dict:
    ok = await repo.delete_provider(session, capability, code)
    await session.commit()
    if not ok:
        raise HTTPException(404, f"provider {capability}/{code} not found")
    return {"deleted": f"{capability}/{code}"}
