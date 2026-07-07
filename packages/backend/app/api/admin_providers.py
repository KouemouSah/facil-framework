"""Admin providers API — CRUD on the provider registry (token-gated)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.concurrency import enforce_if_match, row_etag
from app.api.deps import get_session
from app.auth import audit
from app.core.providers import repository as repo
from app.models.provider import (
    CAPABILITIES, public_config, public_provider_map, secret_keys_in,
)
from app.security.auth_dep import require_auth
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


def _public(obj, registry) -> dict:
    """Row → API dict: `config` restricted to the provider's DECLARED schema keys
    (SEC-F2 allowlist) — or denylist-stripped if the type isn't registered — + etag.
    Never returns `as_dict_raw()` (which carries raw config) to a client."""
    allowed = registry.schema_keys(obj.capability, obj.provider_code)
    cfg = ({k: v for k, v in (obj.config or {}).items() if k in allowed}
           if allowed is not None else public_config(obj.config))
    return {**obj.as_dict_raw(), "config": cfg, "etag": row_etag(obj)}


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
    # Strip any secret-bearing key from the provider map: /llm/routing is only
    # `provider.read`-gated (lower than settings.read), so it must not echo a
    # plaintext credential a legacy `ai.providers` row might carry (SEC-001).
    return {"routing": router_.routing(),
            "providers": public_provider_map(router_.providers())}


@router.post("/llm/routing/check")
async def check_llm_routing(request: Request,
                            session: AsyncSession = Depends(get_session)) -> dict:
    """Resolve every routed role to its concrete provider and probe it (real
    healthcheck, no mutation) — live validation of the routing layer."""
    return await request.app.state.llm_router.healthcheck(session)


@router.get("/")
async def list_providers(request: Request, capability: str | None = None,
                         session: AsyncSession = Depends(get_session)) -> list[dict]:
    registry = request.app.state.registry
    return [_public(p, registry) for p in await repo.list_providers(session, capability)]


@router.get("/{capability}/{code}")
async def get_provider(capability: str, code: str, request: Request,
                       session: AsyncSession = Depends(get_session)) -> dict:
    obj = await repo.get_provider(session, capability, code)
    if obj is None:
        raise HTTPException(404, f"provider {capability}/{code} not found")
    return _public(obj, request.app.state.registry)


@router.put("/{capability}/{code}", dependencies=[_MANAGE])
async def put_provider(capability: str, code: str, body: ProviderIn, request: Request,
                       principal: dict = Depends(require_auth),
                       session: AsyncSession = Depends(get_session)) -> dict:
    _check_capability(capability)
    # Secrets discipline enforced at the authority (SEC-F2 durable fix): a registered
    # provider's `config` is ALLOWLISTED to its declared schema keys — any other key
    # (a credential, a case/variant, a nested blob) is rejected. Unregistered code →
    # denylist fallback. Credentials always travel via secret_ref / env.
    registry = request.app.state.registry
    allowed = registry.schema_keys(capability, code)
    if allowed is not None:
        extra = sorted(set(body.config) - allowed)
        if extra:
            raise HTTPException(
                422, f"config keys not allowed for {capability}/{code}: {extra} "
                     f"(declared: {sorted(allowed)}); credentials go via secret_ref")
    else:
        leaked = secret_keys_in(body.config)
        if leaked:
            raise HTTPException(
                422, f"config must not contain secret keys {sorted(leaked)}; use secret_ref")
    # Optimistic concurrency: if the client sent If-Match, reject a stale write
    # (409). Absent header = no check (create path / API clients).
    existing = await repo.get_provider(session, capability, code)
    if existing is not None:
        enforce_if_match(request, row_etag(existing))
    # Actor is server-derived (authenticated principal), never trusted from the body.
    actor = principal.get("sub")
    obj = await repo.upsert_provider(
        session, capability, code, config=body.config, secret_ref=body.secret_ref,
        is_active=body.is_active, updated_by=actor,
        rate_limit_per_minute=body.rate_limit_per_minute,
        retry_attempts=body.retry_attempts, timeout_seconds=body.timeout_seconds)
    await audit.record(session, audit.PROVIDER_CHANGED, account_id=actor,
                       detail={"capability": capability, "code": code})
    await session.commit()
    return _public(obj, registry)


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
                      principal: dict = Depends(require_auth),
                      session: AsyncSession = Depends(get_session)) -> dict:
    ok = await repo.set_default(session, capability, code)
    if not ok:
        raise HTTPException(404, f"provider {capability}/{code} not found")
    await audit.record(session, audit.PROVIDER_DEFAULT_SET,
                       account_id=principal.get("sub"),
                       detail={"capability": capability, "code": code})
    await session.commit()
    return {"capability": capability, "default": code}


@router.delete("/{capability}/{code}", dependencies=[_MANAGE])
async def delete_provider(capability: str, code: str,
                          principal: dict = Depends(require_auth),
                          session: AsyncSession = Depends(get_session)) -> dict:
    ok = await repo.delete_provider(session, capability, code)
    if not ok:
        raise HTTPException(404, f"provider {capability}/{code} not found")
    await audit.record(session, audit.PROVIDER_DELETED,
                       account_id=principal.get("sub"),
                       detail={"capability": capability, "code": code})
    await session.commit()
    return {"deleted": f"{capability}/{code}"}
