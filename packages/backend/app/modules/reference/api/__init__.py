"""reference module API — Currency / Country / CountryRegion (master data).

Global admin master data (not org-scoped): reads require `reference.read`, writes
`reference.{create,update,delete}`. Lists use the keyset contract
{items,next_cursor,count,capped}; the `?active=1&q=` shape feeds the front-end
`<RefSelect>` dropdowns (no separate options endpoint — DRY). Optimistic
concurrency via ETag/If-Match on update, like organization/account.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.concurrency import enforce_if_match, row_etag
from app.api.deps import get_session
from app.api.list_query import keyset_page, resolve_sort
from app.modules.reference import repository as repo
from app.modules.reference import schemas
from app.modules.reference.models import Country, CountryRegion, Currency
from app.security.auth_dep import require_auth
from app.security.permission_dep import require_permission

router = APIRouter(prefix="/api/v1/modules/reference", tags=["reference"])

_READ = Depends(require_permission("reference.read"))
_CREATE = Depends(require_permission("reference.create"))
_UPDATE = Depends(require_permission("reference.update"))
_DELETE = Depends(require_permission("reference.delete"))

_CURRENCY_SORT = {"code": Currency.code, "name": Currency.name}
_COUNTRY_SORT = {"code": Country.code, "name": Country.name}
_REGION_SORT = {"code": CountryRegion.code, "name": CountryRegion.name}


def _bool(v: int | None) -> bool | None:
    return None if v is None else bool(v)


async def _keyset(session, stmt, *, sort, allowed, default, limit, cursor) -> dict:
    sort_col, sort_desc = resolve_sort(sort, allowed=allowed, default=default)
    items, next_cursor, count, capped = await keyset_page(
        session, stmt, sort_col=sort_col, sort_desc=sort_desc, cursor=cursor, limit=limit)
    return {"items": [i.as_dict() for i in items], "next_cursor": next_cursor,
            "count": count, "capped": capped}


# --- Currencies ----------------------------------------------------------

@router.get("/currencies", dependencies=[_READ])
async def list_currencies(q: str | None = None, active: int | None = None,
                          sort: str = "code", limit: int = 50, cursor: str | None = None,
                          session: AsyncSession = Depends(get_session)) -> dict:
    return await _keyset(session, repo.currencies_select(q=q, active=_bool(active)),
                         sort=sort, allowed=_CURRENCY_SORT, default="code",
                         limit=limit, cursor=cursor)


@router.post("/currencies", status_code=201, dependencies=[_CREATE])
async def create_currency(body: schemas.CurrencyIn,
                          session: AsyncSession = Depends(get_session)) -> dict:
    row = Currency(**body.model_dump())
    return await _save_new(session, row)


@router.get("/currencies/{cid}", dependencies=[_READ])
async def get_currency(cid: str, session: AsyncSession = Depends(get_session)) -> dict:
    return _detail(await session.get(Currency, cid), "currency", cid)


@router.put("/currencies/{cid}", dependencies=[_UPDATE])
async def update_currency(cid: str, body: schemas.CurrencyUpdate, request: Request,
                          session: AsyncSession = Depends(get_session)) -> dict:
    return await _apply_update(session, Currency, cid, body, request, "currency")


@router.delete("/currencies/{cid}", dependencies=[_DELETE])
async def delete_currency(cid: str, session: AsyncSession = Depends(get_session)) -> dict:
    return await _delete(session, Currency, cid, "currency")


# --- Countries -----------------------------------------------------------

@router.get("/countries", dependencies=[_READ])
async def list_countries(q: str | None = None, active: int | None = None,
                         sort: str = "name", limit: int = 50, cursor: str | None = None,
                         session: AsyncSession = Depends(get_session)) -> dict:
    return await _keyset(session, repo.countries_select(q=q, active=_bool(active)),
                         sort=sort, allowed=_COUNTRY_SORT, default="name",
                         limit=limit, cursor=cursor)


@router.post("/countries", status_code=201, dependencies=[_CREATE])
async def create_country(body: schemas.CountryIn,
                         session: AsyncSession = Depends(get_session)) -> dict:
    return await _save_new(session, Country(**body.model_dump()))


@router.get("/countries/{cid}", dependencies=[_READ])
async def get_country(cid: str, session: AsyncSession = Depends(get_session)) -> dict:
    return _detail(await session.get(Country, cid), "country", cid)


@router.put("/countries/{cid}", dependencies=[_UPDATE])
async def update_country(cid: str, body: schemas.CountryUpdate, request: Request,
                         session: AsyncSession = Depends(get_session)) -> dict:
    return await _apply_update(session, Country, cid, body, request, "country")


@router.delete("/countries/{cid}", dependencies=[_DELETE])
async def delete_country(cid: str, session: AsyncSession = Depends(get_session)) -> dict:
    return await _delete(session, Country, cid, "country")


# --- Regions (subdivisions) ---------------------------------------------

@router.get("/regions", dependencies=[_READ])
async def list_regions(country_id: str | None = None, q: str | None = None,
                       active: int | None = None, sort: str = "name",
                       limit: int = 50, cursor: str | None = None,
                       session: AsyncSession = Depends(get_session)) -> dict:
    stmt = repo.regions_select(country_id=country_id, q=q, active=_bool(active))
    return await _keyset(session, stmt, sort=sort, allowed=_REGION_SORT,
                         default="name", limit=limit, cursor=cursor)


@router.post("/regions", status_code=201, dependencies=[_CREATE])
async def create_region(body: schemas.RegionIn,
                        session: AsyncSession = Depends(get_session)) -> dict:
    if await session.get(Country, body.country_id) is None:
        raise HTTPException(422, f"country '{body.country_id}' not found")
    return await _save_new(session, CountryRegion(**body.model_dump()))


@router.get("/regions/{rid}", dependencies=[_READ])
async def get_region(rid: str, session: AsyncSession = Depends(get_session)) -> dict:
    return _detail(await session.get(CountryRegion, rid), "region", rid)


@router.put("/regions/{rid}", dependencies=[_UPDATE])
async def update_region(rid: str, body: schemas.RegionUpdate, request: Request,
                        session: AsyncSession = Depends(get_session)) -> dict:
    return await _apply_update(session, CountryRegion, rid, body, request, "region")


@router.delete("/regions/{rid}", dependencies=[_DELETE])
async def delete_region(rid: str, session: AsyncSession = Depends(get_session)) -> dict:
    return await _delete(session, CountryRegion, rid, "region")


# --- Bulk import (mass create; per-row SAVEPOINT, no silent drop) --------

_IMPORTABLE = {
    "currencies": (schemas.CurrencyIn, Currency),
    "countries": (schemas.CountryIn, Country),
    "regions": (schemas.RegionIn, CountryRegion),
}


class ImportIn(BaseModel):
    rows: list[dict]


@router.post("/{entity}/import", dependencies=[_CREATE])
async def import_entity(entity: str, body: ImportIn,
                        session: AsyncSession = Depends(get_session)) -> dict:
    """Mass-create reference rows (CSV parsed client-side -> rows). Each row is
    validated via the entity schema and inserted in its OWN savepoint, so a bad/
    duplicate row is reported (row index + reason) without aborting the batch and
    without silent drops. Bounded at 1000 rows."""
    if entity not in _IMPORTABLE:
        raise HTTPException(404, f"unknown entity '{entity}'")
    schema_in, model = _IMPORTABLE[entity]
    if len(body.rows) > 1000:
        raise HTTPException(422, "too many rows (max 1000)")
    created, errors = 0, []
    for i, row in enumerate(body.rows, start=1):
        clean = {k: v for k, v in row.items() if v not in ("", None)}
        try:
            data = schema_in(**clean).model_dump()
            async with session.begin_nested():
                session.add(model(**data))
            created += 1
        except Exception as e:  # noqa: BLE001 — collected per row, never silent
            errors.append({"row": i, "detail": str(e)[:300]})
    await session.commit()
    return {"created": created, "errors": errors, "total": len(body.rows)}


# --- Shared CRUD helpers -------------------------------------------------

async def _save_new(session: AsyncSession, row) -> dict:
    session.add(row)
    try:
        await session.commit()
    except IntegrityError as e:
        await session.rollback()
        raise HTTPException(409, "duplicate or invalid reference (unique code?)") from e
    return row.as_dict()


def _detail(row, label: str, rid: str) -> dict:
    if row is None:
        raise HTTPException(404, f"{label} '{rid}' not found")
    return {**row.as_dict(), "etag": row_etag(row)}


async def _apply_update(session, model, rid: str, body, request: Request, label: str) -> dict:
    row = await session.get(model, rid)
    if row is None:
        raise HTTPException(404, f"{label} '{rid}' not found")
    enforce_if_match(request, row_etag(row))
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(row, k, v)
    try:
        await session.commit()
    except IntegrityError as e:
        await session.rollback()
        raise HTTPException(409, "duplicate or invalid reference (unique code?)") from e
    return row.as_dict()


async def _delete(session, model, rid: str, label: str) -> dict:
    row = await session.get(model, rid)
    if row is None:
        raise HTTPException(404, f"{label} '{rid}' not found")
    await session.delete(row)
    await session.commit()
    return {"deleted": rid}
