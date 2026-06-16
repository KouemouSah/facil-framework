"""location module API — Site CRUD + branch listing (token-gated).

Entrypoint consumed by the Module Loader (`router`). Sites carry org/unit scope
so the D4 RBAC enforcement is a wiring change, not a redesign.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_session
from app.modules.location import repository as repo
from app.modules.location import service
from app.modules.location.schemas import SiteCreate, SiteUpdate
from app.security.admin_token import require_admin_token

router = APIRouter(
    prefix="/api/v1/modules/location",
    tags=["location"],
    dependencies=[Depends(require_admin_token)],
)

_STATUS = {service.NotFound: 404, service.Conflict: 409, service.InvalidRef: 422}


def _http(e: service.LocError) -> HTTPException:
    return HTTPException(_STATUS.get(type(e), 400), str(e))


@router.get("/sites")
async def list_sites(organization_id: str | None = None,
                     org_unit_id: str | None = None,
                     parent_site_id: str | None = None,
                     session: AsyncSession = Depends(get_session)) -> list[dict]:
    sites = await repo.list_sites(session, organization_id=organization_id,
                                  org_unit_id=org_unit_id, parent_site_id=parent_site_id)
    return [s.as_dict() for s in sites]


@router.post("/sites", status_code=201)
async def create_site(body: SiteCreate,
                      session: AsyncSession = Depends(get_session)) -> dict:
    try:
        site = await service.create_site(session, body)
    except service.LocError as e:
        raise _http(e) from e
    await session.commit()
    return site.as_dict()


@router.get("/sites/{site_id}")
async def get_site(site_id: str, session: AsyncSession = Depends(get_session)) -> dict:
    site = await repo.get_site(session, site_id)
    if site is None:
        raise HTTPException(404, f"site '{site_id}' not found")
    return site.as_dict()


@router.put("/sites/{site_id}")
async def update_site(site_id: str, body: SiteUpdate,
                      session: AsyncSession = Depends(get_session)) -> dict:
    try:
        site = await service.update_site(session, site_id, body)
    except service.LocError as e:
        raise _http(e) from e
    await session.commit()
    return site.as_dict()


@router.delete("/sites/{site_id}")
async def delete_site(site_id: str,
                      session: AsyncSession = Depends(get_session)) -> dict:
    if not await repo.delete_site(session, site_id):
        raise HTTPException(404, f"site '{site_id}' not found")
    await session.commit()
    return {"deleted": site_id}


@router.get("/sites/{site_id}/branches")
async def list_branches(site_id: str,
                        session: AsyncSession = Depends(get_session)) -> list[dict]:
    if await repo.get_site(session, site_id) is None:
        raise HTTPException(404, f"site '{site_id}' not found")
    return [s.as_dict() for s in await repo.list_sites(session, parent_site_id=site_id)]
