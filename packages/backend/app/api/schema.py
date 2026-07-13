"""Schema API — the one endpoint every schema-driven form reads.

Product schemas (code) + custom-field definitions (DB, org-scoped) merged and
ordered. The frontend maps the result straight onto `FieldDef[]` — the backend
is the single source of truth, no client drift.
"""

from __future__ import annotations

import hashlib
import json

from fastapi import APIRouter, Depends, HTTPException, Request

from app.core.schema.registry import EXTENSIBLE_TARGETS
from app.core.schema.resolver import resolve
from app.security.auth_dep import require_auth

router = APIRouter(prefix="/api/v1/schema", tags=["schema"],
                   dependencies=[Depends(require_auth)])


@router.get("/{target}")
async def get_schema(target: str, request: Request,
                     organization_id: str | None = None) -> dict:
    registry = request.app.state.schema_registry
    if not registry.is_registered(target) and target not in EXTENSIBLE_TARGETS:
        # 404 rather than an empty list: an empty list would let a typo'd target
        # render an empty form, and nobody would notice until data went missing.
        raise HTTPException(404, f"unknown schema target {target!r}")

    # M0: code schemas only. Task 12 wires the org-scoped DB half in here.
    fields = resolve(registry, target, db_specs=None)
    etag = hashlib.sha256(
        json.dumps(fields, sort_keys=True, default=str).encode()).hexdigest()[:16]
    return {"target": target, "fields": fields, "etag": etag}
