"""Admin settings API — CRUD on the config-store (RBAC-gated, D4.3/A2).

Reads require `settings.read`, writes `settings.manage` (manage implies read by
convention). The bootstrap admin-token break-glass satisfies both, so the first
operator works before any grant exists; a logged-in admin uses RBAC via the BFF.
PUT/DELETE refresh the resolver's DB layer in-process (D1 invalidation).
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.concurrency import enforce_if_match, row_etag
from app.api.deps import get_session
from app.auth import audit
from app.config_store import repository as repo
from app.models.provider import provider_map_unknown_keys, public_provider_map
from app.models.setting import VALUE_TYPES
from app.security.auth_dep import require_auth
from app.security.permission_dep import require_permission

_MANAGE = Depends(require_permission("settings.manage"))

# The LLM-routing provider map (name -> {kind, endpoint, model, api_key_secret}).
# Credentials must be REFERENCES (api_key_secret), never plaintext — enforced here
# on write (422) and stripped on read, mirroring the provider_settings discipline.
_PROVIDER_MAP_KEY = "ai.providers"


def _public_setting(obj) -> dict:
    """Setting row → API dict (+etag), with the ai.providers map stripped of any
    secret-bearing key (defence in depth for legacy rows)."""
    d = {**obj.as_dict(), "etag": row_etag(obj)}
    if obj.key == _PROVIDER_MAP_KEY:
        d["value"] = public_provider_map(d.get("value"))
    return d

router = APIRouter(
    prefix="/api/v1/admin/settings",
    tags=["admin-settings"],
    dependencies=[Depends(require_permission("settings.read"))],
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
    # Refreshes the resolver's DB layer in-process. NOTE (SEC-010): the OIDC
    # verifier chain (app.state.auth_verifiers) is built once at boot from
    # auth.methods/auth.oidc.*; changing those keys here updates the resolver but a
    # **restart is required** for the verifier chain to pick them up. Tracked as a
    # follow-up (rebuild verifiers on auth.* change) in the go/no-go plan.
    request.app.state.resolver.set_db(await repo.active_map(session))


@router.get("/")
async def list_settings(scope: str | None = None,
                        session: AsyncSession = Depends(get_session)) -> list[dict]:
    return [_public_setting(s) for s in await repo.list_settings(session, scope)]


@router.get("/{key}")
async def get_setting(key: str, session: AsyncSession = Depends(get_session)) -> dict:
    obj = await repo.get_setting(session, key)
    if obj is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"setting '{key}' not found")
    return _public_setting(obj)


@router.put("/{key}", dependencies=[_MANAGE])
async def put_setting(key: str, body: SettingIn, request: Request,
                      principal: dict = Depends(require_auth),
                      session: AsyncSession = Depends(get_session)) -> dict:
    if body.value_type not in VALUE_TYPES:
        raise HTTPException(422, f"value_type must be one of {VALUE_TYPES}")
    # Secrets discipline on the LLM-routing map (SEC-001 / SEC-F2, authority-
    # enforced): each `ai.providers` entry is ALLOWLISTED to kind/endpoint/model/
    # api_key_secret — any other key (a raw credential, a case/variant) is rejected
    # before it is persisted / leaked. Credentials travel via api_key_secret (a name).
    if key == _PROVIDER_MAP_KEY:
        bad = provider_map_unknown_keys(body.value)
        if bad:
            raise HTTPException(
                422, "ai.providers entries only allow kind/endpoint/model/api_key_secret; "
                     f"unexpected keys {sorted(bad)}")
    # Optimistic concurrency (routing edits ai.routing/ai.providers): reject a
    # stale write if If-Match is sent. Absent header = no check (backwards compat).
    existing = await repo.get_setting(session, key)
    if existing is not None:
        enforce_if_match(request, row_etag(existing))
    # Actor is server-derived (the authenticated principal), never trusted from
    # the body — the audit trail must not be spoofable.
    actor = principal.get("sub")
    obj = await repo.upsert_setting(
        session, key, body.value, value_type=body.value_type, scope=body.scope,
        secret_ref=body.secret_ref, updated_by=actor,
        name_es=body.name_es, name_fr=body.name_fr, name_en=body.name_en,
        description=body.description, is_active=body.is_active)
    await audit.record(session, audit.SETTING_CHANGED, account_id=actor,
                       detail={"key": key})
    await session.commit()
    await _refresh_resolver(request, session)
    return _public_setting(obj)


@router.delete("/{key}", dependencies=[_MANAGE])
async def delete_setting(key: str, request: Request,
                         principal: dict = Depends(require_auth),
                         session: AsyncSession = Depends(get_session)) -> dict:
    ok = await repo.delete_setting(session, key)
    if ok:
        await audit.record(session, audit.SETTING_DELETED,
                           account_id=principal.get("sub"), detail={"key": key})
    await session.commit()
    await _refresh_resolver(request, session)
    if not ok:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"setting '{key}' not found")
    return {"deleted": key}
