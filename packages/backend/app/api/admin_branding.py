"""Admin branding API (D5.4) — RBAC-gated live editing of `branding.*`.

The bootstrap admin-settings router is token-gated (break-glass, for the IdP/
operator), so logged-in admins edit branding through this RBAC-gated surface
instead. Writes upsert the `branding.*` config-store keys and refresh the
in-process resolver immediately, so the public theme endpoint reflects changes
on the next request (live). `branding.manage` (break-glass ok) authorizes both.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.concurrency import enforce_if_match, etag_for
from app.api.deps import get_session
from app.auth import audit
from app.branding import BRANDING_STRING_FIELDS, THEME_MODES, branding_snapshot
from app.config_store import repository as repo
from app.security.auth_dep import require_auth
from app.security.permission_dep import require_permission

router = APIRouter(prefix="/api/v1/admin/branding", tags=["admin-branding"])

_MANAGE = Depends(require_permission("branding.manage"))


_URL_FIELDS = ("logo_url", "logo_dark_url", "favicon_url",
               "login_background_url", "support_url")


class BrandingIn(BaseModel):
    """All optional — only provided (non-null) fields are written. URL fields accept
    http(s), a same-origin absolute path (`/api/v1/assets/<id>` from the binary asset
    pipeline), or empty — but never `javascript:`/`data:` (XSS) nor protocol-relative
    `//host` (would leave the origin). Strings are length-bounded (storage abuse)."""
    app_name: str | None = Field(default=None, max_length=120)
    tagline: str | None = Field(default=None, max_length=255)
    logo_url: str | None = Field(default=None, max_length=2048)
    logo_dark_url: str | None = Field(default=None, max_length=2048)
    favicon_url: str | None = Field(default=None, max_length=2048)
    login_background_url: str | None = Field(default=None, max_length=2048)
    primary_color: str | None = Field(default=None, max_length=7)
    secondary_color: str | None = Field(default=None, max_length=7)
    theme_mode: str | None = None
    default_locale: str | None = Field(default=None, max_length=10)
    support_email: str | None = Field(default=None, max_length=255)
    support_url: str | None = Field(default=None, max_length=2048)

    @field_validator(*_URL_FIELDS)
    @classmethod
    def _safe_url(cls, v: str | None) -> str | None:
        if not v:
            return v
        # Same-origin absolute path (e.g. /api/v1/assets/<id>) is safe in <img>/<link>;
        # reject protocol-relative //host, which would point off-origin.
        if v.startswith("/") and not v.startswith("//"):
            return v
        if v.startswith("http://") or v.startswith("https://"):
            return v
        raise ValueError("URL must be http(s):// or a same-origin path starting with /")


@router.get("", dependencies=[_MANAGE])
async def get_branding(request: Request) -> dict:
    snap = branding_snapshot(request.app.state.resolver)
    return {**snap, "etag": etag_for(snap)}  # etag for optimistic concurrency


@router.put("", dependencies=[_MANAGE])
async def put_branding(body: BrandingIn, request: Request,
                       principal: dict = Depends(require_auth),
                       session: AsyncSession = Depends(get_session)) -> dict:
    data = body.model_dump(exclude_none=True)
    if "theme_mode" in data and data["theme_mode"] not in THEME_MODES:
        raise HTTPException(422, f"theme_mode must be one of {THEME_MODES}")
    # Lost-update guard: reject if branding changed since the client loaded it.
    enforce_if_match(request, etag_for(branding_snapshot(request.app.state.resolver)))
    for field, value in data.items():
        if field not in BRANDING_STRING_FIELDS:  # defence in depth vs the schema
            raise HTTPException(422, f"unknown branding field '{field}'")
        await repo.upsert_setting(session, f"branding.{field}", value,
                                  value_type="string")
    await audit.record(session, audit.BRANDING_CHANGED,
                       account_id=principal.get("sub"),
                       detail={"fields": sorted(data.keys())})
    await session.commit()
    # Live refresh: rebuild the resolver's DB layer so reads see the new values.
    request.app.state.resolver.set_db(await repo.active_map(session))
    snap = branding_snapshot(request.app.state.resolver)
    return {**snap, "etag": etag_for(snap)}
