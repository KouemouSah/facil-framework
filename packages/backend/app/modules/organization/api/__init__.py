"""organization module API — Organization + OrgUnit CRUD (RBAC scope-aware).

Entrypoint consumed by the Module Loader (`router`). Enforced by RBAC (D4.3):
each route requires an `organization.{read,write,delete}` permission; the scope
is resolved from the path (org_id / unit_id), so a grant scoped to one org/unit
subtree cannot reach another. The bootstrap admin-token still works (break-glass).
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.concurrency import enforce_if_match, row_etag
from app.api.csv_export import EXPORT_CAP, export_response
from app.api.deps import get_session
from app.api.list_query import apply_sort, keyset_page, paginated, resolve_sort
from app.core.schema.merge import merge_blob
from app.core.schema.pydantic_gen import SchemaViolation, validate_blob
from app.modules.organization import repository as repo
from app.modules.organization import service
from app.modules.organization.models import Organization
from app.modules.organization.schemas import (OrganizationCreate,
                                               OrganizationUpdate, OrgUnitCreate,
                                               OrgUnitUpdate)
from app.security.auth_dep import require_auth
from app.security.permission_dep import require_permission, visible_orgs

_ORG_SORT = {"code": Organization.code, "legal_name": Organization.legal_name,
             "created_at": Organization.created_at}

_READ = Depends(require_permission("organization.read"))
_CREATE = Depends(require_permission("organization.create"))
_UPDATE = Depends(require_permission("organization.update"))
_DELETE = Depends(require_permission("organization.delete"))

router = APIRouter(
    prefix="/api/v1/modules/organization",
    tags=["organization"],
)

_STATUS = {service.NotFound: 404, service.Conflict: 409,
           service.InvalidParent: 422, service.InvalidReference: 422}


def _http(e: service.OrgError) -> HTTPException:
    return HTTPException(_STATUS.get(type(e), 400), str(e))


async def _commit(session: AsyncSession) -> None:
    """Commit, mapping a FK/uniqueness violation (e.g. a bad party/address/
    currency reference on an org) to 409 instead of a bare 500."""
    try:
        await session.commit()
    except IntegrityError as e:
        await session.rollback()
        raise HTTPException(409, "duplicate or invalid reference") from e


# --- Organizations -------------------------------------------------------

def _page(limit: int, offset: int) -> tuple[int, int]:
    return min(max(limit, 1), 200), max(offset, 0)


@router.get("/")
async def list_organizations(q: str | None = None, sort: str = "code",
                             limit: int = 50, cursor: str | None = None,
                             principal: dict = Depends(require_auth),
                             session: AsyncSession = Depends(get_session)) -> dict:
    # Scope + keyset pagination IN SQL (scale 1M+). Contract:
    # {items,next_cursor,count,capped}. `keyset_page` applies the whitelisted
    # order itself, so the select is passed unsorted.
    visible = await visible_orgs(session, principal, "organization.read")
    stmt = repo.organizations_select(org_ids=visible, q=q)
    sort_col, sort_desc = resolve_sort(sort, allowed=_ORG_SORT, default="code")
    items, next_cursor, count, capped = await keyset_page(
        session, stmt, sort_col=sort_col, sort_desc=sort_desc,
        cursor=cursor, limit=limit)
    return {"items": [o.as_dict() for o in items], "next_cursor": next_cursor,
            "count": count, "capped": capped}


_ORG_EXPORT_COLS = ("id", "code", "legal_name", "display_name", "email",
                    "city", "country_code", "is_active")


@router.get("/export")
async def export_organizations(q: str | None = None, sort: str = "code",
                               format: str = "csv",
                               principal: dict = Depends(require_auth),
                               session: AsyncSession = Depends(get_session)):
    visible = await visible_orgs(session, principal, "organization.read")
    stmt = repo.organizations_select(org_ids=visible, q=q)
    stmt = apply_sort(stmt, sort, allowed=_ORG_SORT, default="code")
    items, total = await paginated(session, stmt, limit=EXPORT_CAP, offset=0)
    return export_response(items, _ORG_EXPORT_COLS, "organizations", format, total=total)


logger = logging.getLogger(__name__)

_LABELS_CAP = 500


@router.get("/labels")
async def organization_labels(ids: str = "",
                              principal: dict = Depends(require_auth),
                              session: AsyncSession = Depends(get_session)) -> dict:
    """Resolve many org ids → display label in ONE call (kills the client-side
    N+1 when rendering role-assignment scopes). Scope-filtered like the list:
    ids the principal can't read are simply absent from the map (same graceful
    degradation as the per-id path). Literal route registered before `/{org_id}`.
    Contract: {id: label}. Bounded to _LABELS_CAP ids."""
    requested = {i for i in ids.split(",") if i}
    if not requested:
        return {}
    # Deterministic truncation if a caller ever exceeds the cap (a set's iteration
    # order is unspecified, so sort before slicing). Log it — a caller sending >cap
    # ids means some labels silently fall back to the id, so the cap must be visible
    # (no silent truncation) even though the UI never requests this many in practice.
    if len(requested) > _LABELS_CAP:
        logger.warning("organization_labels: %d ids requested, truncated to cap %d",
                       len(requested), _LABELS_CAP)
        requested = set(sorted(requested)[:_LABELS_CAP])
    visible = await visible_orgs(session, principal, "organization.read")
    org_ids = requested if visible is None else (requested & visible)
    if not org_ids:
        return {}
    stmt = repo.organizations_select(org_ids=org_ids)
    rows = (await session.execute(stmt)).scalars().all()
    return {o.id: (o.display_name or o.legal_name) for o in rows}


@router.post("/", status_code=201, dependencies=[_CREATE])
async def create_organization(body: OrganizationCreate, request: Request,
                              session: AsyncSession = Depends(get_session)) -> dict:
    # `document_identity` allowlist (Task 8) applies to create too — the
    # invariant ("the schema IS the allowlist") is unconditional, not PUT-only.
    # There is no existing blob to merge against on create, so validate
    # directly instead of `merge_blob`. An empty dict means "not configured
    # yet" (document identity is optional, filled in later) so it is skipped
    # rather than rejected for missing the required `legal_name` — only a
    # non-empty submission is validated (and must then satisfy `required`).
    if body.document_identity:
        specs = request.app.state.schema_registry.get("organization.document_identity")
        try:
            body.document_identity = validate_blob(specs, body.document_identity)
        except SchemaViolation as e:
            raise HTTPException(422, detail=e.errors) from e
    try:
        org = await service.create_organization(session, body)
    except service.OrgError as e:
        raise _http(e) from e
    await _commit(session)
    return org.as_dict()


# --- OrgUnits (literal routes before /{org_id} so they match first) ------

@router.get("/units/{unit_id}", dependencies=[_READ])
async def get_unit(unit_id: str, session: AsyncSession = Depends(get_session)) -> dict:
    unit = await repo.get_unit(session, unit_id)
    if unit is None:
        raise HTTPException(404, f"unit '{unit_id}' not found")
    return {**unit.as_dict(), "etag": row_etag(unit)}


@router.put("/units/{unit_id}", dependencies=[_UPDATE])
async def update_unit(unit_id: str, body: OrgUnitUpdate, request: Request,
                      session: AsyncSession = Depends(get_session)) -> dict:
    # Optimistic concurrency (parity with organization PUT): reject a stale write.
    existing = await repo.get_unit(session, unit_id)
    if existing is None:
        raise HTTPException(404, f"unit '{unit_id}' not found")
    enforce_if_match(request, row_etag(existing))
    try:
        unit = await service.update_unit(session, unit_id, body)
    except service.OrgError as e:
        raise _http(e) from e
    await session.commit()
    return {**unit.as_dict(), "etag": row_etag(unit)}


@router.delete("/units/{unit_id}", dependencies=[_DELETE])
async def delete_unit(unit_id: str,
                      session: AsyncSession = Depends(get_session)) -> dict:
    if await repo.get_unit(session, unit_id) is None:
        raise HTTPException(404, f"unit '{unit_id}' not found")
    # Refuse to delete a non-leaf (the self-FK has no cascade — a silent subtree
    # delete is dangerous). The admin deletes/reparents children first.
    if await repo.has_children(session, unit_id):
        raise HTTPException(409, "unit has child units; delete or reparent them first")
    await repo.delete_unit(session, unit_id)
    await session.commit()
    return {"deleted": unit_id}


# --- Organization by id + nested units -----------------------------------

@router.get("/{org_id}", dependencies=[_READ])
async def get_organization(org_id: str,
                           session: AsyncSession = Depends(get_session)) -> dict:
    org = await repo.get_organization(session, org_id)
    if org is None:
        raise HTTPException(404, f"organization '{org_id}' not found")
    return {**org.as_dict(), "etag": row_etag(org)}


@router.put("/{org_id}", dependencies=[_UPDATE])
async def update_organization(org_id: str, body: OrganizationUpdate, request: Request,
                              session: AsyncSession = Depends(get_session)) -> dict:
    # Optimistic concurrency: reject if the row changed since the client loaded it.
    existing = await repo.get_organization(session, org_id)
    if existing is None:
        raise HTTPException(404, f"organization '{org_id}' not found")
    enforce_if_match(request, row_etag(existing))
    # `document_identity` is now a schema-validated, merge-preserve blob (Task 8):
    # only declared keys can be written by the request (422 otherwise); a
    # pre-existing undeclared key (historic data) survives untouched.
    if body.document_identity is not None:
        specs = request.app.state.schema_registry.get("organization.document_identity")
        try:
            body.document_identity = merge_blob(
                existing.document_identity or {}, body.document_identity, specs)
        except SchemaViolation as e:
            raise HTTPException(422, detail=e.errors) from e
    try:
        org = await service.update_organization(session, org_id, body)
    except service.OrgError as e:
        raise _http(e) from e
    await _commit(session)
    # No etag here: updated_at is server-onupdate (expired after flush; reading it
    # would need async IO). The client refetches GET for the rotated etag.
    return org.as_dict()


@router.delete("/{org_id}", dependencies=[_DELETE])
async def delete_organization(org_id: str,
                              session: AsyncSession = Depends(get_session)) -> dict:
    if not await repo.delete_organization(session, org_id):
        raise HTTPException(404, f"organization '{org_id}' not found")
    await session.commit()
    return {"deleted": org_id}


@router.get("/{org_id}/units", dependencies=[_READ])
async def list_units(org_id: str, limit: int = 50, offset: int = 0,
                     session: AsyncSession = Depends(get_session)) -> list[dict]:
    if await repo.get_organization(session, org_id) is None:
        raise HTTPException(404, f"organization '{org_id}' not found")
    limit, offset = _page(limit, offset)
    units = await repo.list_units(session, org_id, limit=limit, offset=offset)
    return [{**u.as_dict(), "etag": row_etag(u)} for u in units]


_UNIT_EXPORT_COLS = ("id", "code", "name", "unit_type", "parent_id", "depth", "is_active")


@router.get("/{org_id}/units/export", dependencies=[_READ])
async def export_units(org_id: str, format: str = "csv",
                       session: AsyncSession = Depends(get_session)):
    """Export an organization's units (flat) — unblocks the deferred org-units export."""
    if await repo.get_organization(session, org_id) is None:
        raise HTTPException(404, f"organization '{org_id}' not found")
    units = await repo.list_units(session, org_id, limit=EXPORT_CAP, offset=0)
    return export_response(units, _UNIT_EXPORT_COLS, "org-units", format, total=len(units))


@router.post("/{org_id}/units", status_code=201, dependencies=[_CREATE])
async def create_unit(org_id: str, body: OrgUnitCreate,
                      session: AsyncSession = Depends(get_session)) -> dict:
    try:
        unit = await service.create_unit(session, org_id, body)
    except service.OrgError as e:
        raise _http(e) from e
    await session.commit()
    return unit.as_dict()
