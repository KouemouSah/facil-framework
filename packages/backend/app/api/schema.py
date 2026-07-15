"""Schema API — the one endpoint every schema-driven form reads.

Product schemas (code) + custom-field definitions (DB, org-scoped) merged and
ordered. The frontend maps the result straight onto `FieldDef[]` — the backend
is the single source of truth, no client drift.
"""

from __future__ import annotations

import hashlib
import json

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_session
from app.core.schema import cache as schema_cache
from app.core.schema import repository as schema_repo
from app.core.schema.registry import EXTENSIBLE_TARGETS
from app.core.schema.resolver import resolve
from app.security.auth_dep import require_auth
from app.security.permission_dep import visible_orgs

router = APIRouter(prefix="/api/v1/schema", tags=["schema"],
                   dependencies=[Depends(require_auth)])


@router.get("/{target}")
async def get_schema(target: str, request: Request, organization_id: str | None = None,
                     principal: dict = Depends(require_auth),
                     session: AsyncSession = Depends(get_session)) -> dict:
    registry = request.app.state.schema_registry
    if not registry.is_registered(target) and target not in EXTENSIBLE_TARGETS:
        # 404 rather than an empty list: an empty list would let a typo'd target
        # render an empty form, and nobody would notice until data went missing.
        raise HTTPException(404, f"unknown schema target {target!r}")

    db_specs = None
    if target in EXTENSIBLE_TARGETS and organization_id:
        # Scope check BEFORE reading: the caller may only read schemas for an
        # organisation they can see. 404 (not 403) — do not leak the existence
        # of another tenant's organisation.
        allowed = await visible_orgs(session, principal, "organization.read")
        if allowed is not None and organization_id not in allowed:
            raise HTTPException(404, f"organization {organization_id!r} not found")

        # Cache of the RESOLVED schema (D2, spec §7's promised cache) — one
        # DB round trip per (organization_id, target) instead of one per
        # request. Keyed STRICTLY by (organization_id, target); see
        # `core.schema.cache`'s module docstring for why that is the one
        # thing that must never change. `getattr(..., None)` mirrors
        # `security/rate_limit.py`'s convention: no cache configured on
        # `app.state` -> transparently fall back to resolving from the DB.
        cache = getattr(request.app.state, "cache", None)
        db_specs = await schema_cache.get(cache, organization_id, target)
        if db_specs is None:
            rows = await schema_repo.definitions_for(session, target, organization_id)
            db_specs = [r.as_spec() for r in rows]
            await schema_cache.set(cache, organization_id, target, db_specs)

    try:
        fields = resolve(registry, target, db_specs=db_specs)
    except ValueError as e:
        # A tenant field shadows a product field — a bad definition, not a
        # server fault. Surfacing this as a bare 500 would hide a real
        # configuration error behind a generic error page.
        raise HTTPException(422, str(e)) from e

    etag = hashlib.sha256(
        json.dumps(fields, sort_keys=True, default=str).encode()).hexdigest()[:16]
    return {"target": target, "fields": fields, "etag": etag}
