"""organization module API — Organization + OrgUnit CRUD (token-gated).

Entrypoint consumed by the Module Loader (`router`). Admin-token gated until D4
brings real RBAC; the routes already carry organization/unit scope so the D4
enforcement is a wiring change, not a redesign.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_session
from app.modules.organization import repository as repo
from app.modules.organization import service
from app.modules.organization.schemas import (OrganizationCreate,
                                               OrganizationUpdate, OrgUnitCreate,
                                               OrgUnitUpdate)
from app.security.admin_token import require_admin_token

router = APIRouter(
    prefix="/api/v1/modules/organization",
    tags=["organization"],
    dependencies=[Depends(require_admin_token)],
)

_STATUS = {service.NotFound: 404, service.Conflict: 409, service.InvalidParent: 422}


def _http(e: service.OrgError) -> HTTPException:
    return HTTPException(_STATUS.get(type(e), 400), str(e))


# --- Organizations -------------------------------------------------------

@router.get("/")
async def list_organizations(session: AsyncSession = Depends(get_session)) -> list[dict]:
    return [o.as_dict() for o in await repo.list_organizations(session)]


@router.post("/", status_code=201)
async def create_organization(body: OrganizationCreate,
                              session: AsyncSession = Depends(get_session)) -> dict:
    try:
        org = await service.create_organization(session, body)
    except service.OrgError as e:
        raise _http(e) from e
    await session.commit()
    return org.as_dict()


# --- OrgUnits (literal routes before /{org_id} so they match first) ------

@router.get("/units/{unit_id}")
async def get_unit(unit_id: str, session: AsyncSession = Depends(get_session)) -> dict:
    unit = await repo.get_unit(session, unit_id)
    if unit is None:
        raise HTTPException(404, f"unit '{unit_id}' not found")
    return unit.as_dict()


@router.put("/units/{unit_id}")
async def update_unit(unit_id: str, body: OrgUnitUpdate,
                      session: AsyncSession = Depends(get_session)) -> dict:
    try:
        unit = await service.update_unit(session, unit_id, body)
    except service.OrgError as e:
        raise _http(e) from e
    await session.commit()
    return unit.as_dict()


@router.delete("/units/{unit_id}")
async def delete_unit(unit_id: str,
                      session: AsyncSession = Depends(get_session)) -> dict:
    if not await repo.delete_unit(session, unit_id):
        raise HTTPException(404, f"unit '{unit_id}' not found")
    await session.commit()
    return {"deleted": unit_id}


# --- Organization by id + nested units -----------------------------------

@router.get("/{org_id}")
async def get_organization(org_id: str,
                           session: AsyncSession = Depends(get_session)) -> dict:
    org = await repo.get_organization(session, org_id)
    if org is None:
        raise HTTPException(404, f"organization '{org_id}' not found")
    return org.as_dict()


@router.put("/{org_id}")
async def update_organization(org_id: str, body: OrganizationUpdate,
                              session: AsyncSession = Depends(get_session)) -> dict:
    try:
        org = await service.update_organization(session, org_id, body)
    except service.OrgError as e:
        raise _http(e) from e
    await session.commit()
    return org.as_dict()


@router.delete("/{org_id}")
async def delete_organization(org_id: str,
                              session: AsyncSession = Depends(get_session)) -> dict:
    if not await repo.delete_organization(session, org_id):
        raise HTTPException(404, f"organization '{org_id}' not found")
    await session.commit()
    return {"deleted": org_id}


@router.get("/{org_id}/units")
async def list_units(org_id: str,
                     session: AsyncSession = Depends(get_session)) -> list[dict]:
    if await repo.get_organization(session, org_id) is None:
        raise HTTPException(404, f"organization '{org_id}' not found")
    return [u.as_dict() for u in await repo.list_units(session, org_id)]


@router.post("/{org_id}/units", status_code=201)
async def create_unit(org_id: str, body: OrgUnitCreate,
                      session: AsyncSession = Depends(get_session)) -> dict:
    try:
        unit = await service.create_unit(session, org_id, body)
    except service.OrgError as e:
        raise _http(e) from e
    await session.commit()
    return unit.as_dict()
