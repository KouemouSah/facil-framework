"""location module API — Site CRUD + branch listing (RBAC scope-aware).

Entrypoint consumed by the Module Loader (`router`). Enforced by RBAC (D4.3):
`location.{read,write,delete}` permissions, scoped from the request. Read/by-id
routes resolve scope from path/query; create-site is body-scoped, so it resolves
the scope from the body and enforces in-handler. Bootstrap admin-token = break-glass.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.concurrency import enforce_if_match, row_etag
from app.api.csv_export import EXPORT_CAP, export_response
from app.api.deps import get_session
from app.api.list_query import apply_sort, keyset_page, paginated, resolve_sort
from app.modules.location import repository as repo
from app.modules.location import service
from app.modules.location.models import Site
from app.modules.location.schemas import SiteCreate, SiteUpdate
from app.rbac import repository as rbac_repo
from app.security.auth_dep import require_auth
from app.security.permission_dep import enforce, require_permission, visible_orgs

_SITE_SORT = {"code": Site.code, "name": Site.name, "site_type": Site.site_type,
              "city": Site.city, "created_at": Site.created_at}

_READ = Depends(require_permission("location.read"))
_DELETE = Depends(require_permission("location.delete"))

router = APIRouter(
    prefix="/api/v1/modules/location",
    tags=["location"],
)

_STATUS = {service.NotFound: 404, service.Conflict: 409, service.InvalidRef: 422}


def _http(e: service.LocError) -> HTTPException:
    return HTTPException(_STATUS.get(type(e), 400), str(e))


async def _commit(session: AsyncSession) -> None:
    """Commit, mapping a FK/uniqueness violation (e.g. a bad address reference)
    to 409 rather than a bare 500."""
    try:
        await session.commit()
    except IntegrityError as e:
        await session.rollback()
        raise HTTPException(409, "duplicate or invalid reference") from e


@router.get("/sites")
async def list_sites(organization_id: str | None = None,
                     org_unit_id: str | None = None,
                     parent_site_id: str | None = None,
                     q: str | None = None, sort: str = "code",
                     limit: int = 50, cursor: str | None = None,
                     principal: dict = Depends(require_auth),
                     session: AsyncSession = Depends(get_session)) -> dict:
    # Scope + keyset pagination IN SQL (scale 1M+). Contract:
    # {items,next_cursor,count,capped}. NULL-safe (city is nullable).
    visible = await visible_orgs(session, principal, "location.read")
    stmt = repo.sites_select(organization_id=organization_id, org_unit_id=org_unit_id,
                             parent_site_id=parent_site_id, org_ids=visible, q=q)
    sort_col, sort_desc = resolve_sort(sort, allowed=_SITE_SORT, default="code")
    items, next_cursor, count, capped = await keyset_page(
        session, stmt, sort_col=sort_col, sort_desc=sort_desc,
        cursor=cursor, limit=limit)
    return {"items": [s.as_dict() for s in items], "next_cursor": next_cursor,
            "count": count, "capped": capped}


_SITE_EXPORT_COLS = ("id", "code", "name", "site_type", "organization_id",
                     "city", "country_code", "is_primary", "is_active")


@router.get("/sites/export")
async def export_sites(organization_id: str | None = None, q: str | None = None,
                       sort: str = "code", format: str = "csv",
                       principal: dict = Depends(require_auth),
                       session: AsyncSession = Depends(get_session)):
    visible = await visible_orgs(session, principal, "location.read")
    stmt = repo.sites_select(organization_id=organization_id, org_ids=visible, q=q)
    stmt = apply_sort(stmt, sort, allowed=_SITE_SORT, default="code")
    items, total = await paginated(session, stmt, limit=EXPORT_CAP, offset=0)
    return export_response(items, _SITE_EXPORT_COLS, "sites", format, total=total)


@router.post("/sites", status_code=201)
async def create_site(body: SiteCreate, request: Request,
                      principal: dict = Depends(require_auth),
                      session: AsyncSession = Depends(get_session)) -> dict:
    # Body-scoped: the target org/unit comes from the payload, not the path.
    scope = await rbac_repo.resolve_scope(
        session, {"organization_id": body.organization_id,
                  "org_unit_id": body.org_unit_id, "site_id": None})
    await enforce(session, principal, "location.create", scope)
    try:
        site = await service.create_site(session, body)
    except service.LocError as e:
        raise _http(e) from e
    await _commit(session)
    return site.as_dict()


@router.get("/sites/{site_id}", dependencies=[_READ])
async def get_site(site_id: str, session: AsyncSession = Depends(get_session)) -> dict:
    site = await repo.get_site(session, site_id)
    if site is None:
        raise HTTPException(404, f"site '{site_id}' not found")
    return {**site.as_dict(), "etag": row_etag(site)}


@router.put("/sites/{site_id}", dependencies=[Depends(require_permission("location.update"))])
async def update_site(site_id: str, body: SiteUpdate, request: Request,
                      session: AsyncSession = Depends(get_session)) -> dict:
    # Optimistic concurrency: reject if the row changed since the client loaded it.
    existing = await repo.get_site(session, site_id)
    if existing is None:
        raise HTTPException(404, f"site '{site_id}' not found")
    enforce_if_match(request, row_etag(existing))
    try:
        site = await service.update_site(session, site_id, body)
    except service.LocError as e:
        raise _http(e) from e
    await _commit(session)
    # No etag here (updated_at is server-onupdate; expired after flush). The client
    # refetches GET for the rotated etag.
    return site.as_dict()


@router.delete("/sites/{site_id}", dependencies=[_DELETE])
async def delete_site(site_id: str,
                      session: AsyncSession = Depends(get_session)) -> dict:
    if not await repo.delete_site(session, site_id):
        raise HTTPException(404, f"site '{site_id}' not found")
    await session.commit()
    return {"deleted": site_id}


@router.get("/sites/{site_id}/branches", dependencies=[_READ])
async def list_branches(site_id: str,
                        session: AsyncSession = Depends(get_session)) -> list[dict]:
    if await repo.get_site(session, site_id) is None:
        raise HTTPException(404, f"site '{site_id}' not found")
    return [s.as_dict() for s in await repo.list_sites(session, parent_site_id=site_id)]
