"""Generic CRUD router factory (backlog ERP — the "automated parity" mechanism).

`build_crud_router` generates the standardized ERP contract for a scoped resource
in one call — list (L1 contract: sort whitelist + substring search + total),
get (+etag), create, update (If-Match optimistic concurrency), delete — with RBAC
scope filtering/enforcement and audit baked in. New modules call this and get the
full surface consistently, so the org/site edit-form gap (a hand-written router
that simply forgot update) cannot recur.

See docs/ENGINEERING_STANDARDS.md §1/§8/§13bis. Service-rich modules with domain
logic (cycle guards, uniqueness, nested resources) may keep hand-written routers
that compose the same helpers (list_query, concurrency, visible_orgs, audit).
"""

from __future__ import annotations

from collections.abc import Sequence

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.concurrency import enforce_if_match, row_etag
from app.api.deps import get_session
from app.api.list_query import apply_sort, clamp_page, paginated
from app.auth import audit
from app.rbac import repository as rbac_repo
from app.security.auth_dep import require_auth
from app.security.permission_dep import enforce, visible_orgs


def build_crud_router(*, prefix: str, tags: list[str], model, resource: str,
                      create_schema: type[BaseModel], update_schema: type[BaseModel],
                      sortable: dict, default_sort: str,
                      search_fields: Sequence = (), scope_col=None) -> APIRouter:
    """Build a CRUD router for `model`.

    - `resource`: permission prefix (`<resource>.{read,create,update,delete}`).
    - `sortable`: {public field -> ORM column} whitelist; `default_sort` e.g. "-created_at".
    - `search_fields`: ORM columns matched by `q` (ILIKE substring).
    - `scope_col`: the org-scope column (e.g. Model.organization_id) for tenant
      isolation; None = global resource (no scope filter; perms checked globally).
    """
    router = APIRouter(prefix=prefix, tags=tags)

    def _base_select(q: str | None, org_ids: set[str] | None):
        stmt = select(model)
        if scope_col is not None and org_ids is not None:
            stmt = stmt.where(scope_col.in_(org_ids))
        if q and search_fields:
            like = f"%{q}%"
            stmt = stmt.where(or_(*[c.ilike(like) for c in search_fields]))
        return stmt

    @router.get("")
    async def list_(q: str | None = None, sort: str = default_sort,
                    limit: int = 50, offset: int = 0,
                    principal: dict = Depends(require_auth),
                    session: AsyncSession = Depends(get_session)) -> dict:
        org_ids = (await visible_orgs(session, principal, f"{resource}.read")
                   if scope_col is not None else None)
        limit, offset = clamp_page(limit, offset)
        stmt = apply_sort(_base_select(q, org_ids), sort, allowed=sortable,
                          default=default_sort)
        items, total = await paginated(session, stmt, limit=limit, offset=offset)
        return {"items": [i.as_dict() for i in items], "total": total,
                "limit": limit, "offset": offset}

    @router.get("/{item_id}")
    async def get_(item_id: str, principal: dict = Depends(require_auth),
                   session: AsyncSession = Depends(get_session)) -> dict:
        entity = await session.get(model, item_id)
        if entity is None:
            raise HTTPException(404, f"{resource} '{item_id}' not found")
        scope = await rbac_repo.resolve_scope(
            session, {"organization_id": getattr(entity, "organization_id", None)})
        await enforce(session, principal, f"{resource}.read", scope)
        return {**entity.as_dict(), "etag": row_etag(entity)}

    @router.post("", status_code=201)
    async def create_(body: create_schema, principal: dict = Depends(require_auth),
                      session: AsyncSession = Depends(get_session)) -> dict:
        data = body.model_dump()
        scope = await rbac_repo.resolve_scope(
            session, {"organization_id": data.get("organization_id")})
        await enforce(session, principal, f"{resource}.create", scope)
        entity = model(**data)
        session.add(entity)
        await session.flush()
        await audit.record(session, f"{resource}_created",
                           detail={"by": principal.get("sub"), "id": entity.id})
        await session.commit()
        return entity.as_dict()

    @router.put("/{item_id}")
    async def update_(item_id: str, body: update_schema, request: Request,
                      principal: dict = Depends(require_auth),
                      session: AsyncSession = Depends(get_session)) -> dict:
        entity = await session.get(model, item_id)
        if entity is None:
            raise HTTPException(404, f"{resource} '{item_id}' not found")
        scope = await rbac_repo.resolve_scope(
            session, {"organization_id": getattr(entity, "organization_id", None)})
        await enforce(session, principal, f"{resource}.update", scope)
        enforce_if_match(request, row_etag(entity))
        for k, v in body.model_dump(exclude_unset=True).items():
            setattr(entity, k, v)
        await audit.record(session, f"{resource}_updated",
                           detail={"by": principal.get("sub"), "id": item_id})
        await session.commit()
        return entity.as_dict()

    @router.delete("/{item_id}")
    async def delete_(item_id: str, principal: dict = Depends(require_auth),
                      session: AsyncSession = Depends(get_session)) -> dict:
        entity = await session.get(model, item_id)
        if entity is None:
            raise HTTPException(404, f"{resource} '{item_id}' not found")
        scope = await rbac_repo.resolve_scope(
            session, {"organization_id": getattr(entity, "organization_id", None)})
        await enforce(session, principal, f"{resource}.delete", scope)
        await session.delete(entity)
        await audit.record(session, f"{resource}_deleted",
                           detail={"by": principal.get("sub"), "id": item_id})
        await session.commit()
        return {"deleted": item_id}

    return router
