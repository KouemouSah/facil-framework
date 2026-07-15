"""party module API — Party / PartyRole / Address / PartyAddress (the directory).

Global admin master data (V1, not tenant-scoped): reads require `party.read`,
writes `party.{create,update,delete}`. Lists use the keyset contract; ETag/If-Match
on update like the rest. A Party exposes nested roles and linked addresses.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.concurrency import enforce_if_match, row_etag
from app.api.deps import get_session
from app.api.list_query import keyset_page, resolve_entity_sort
from app.auth import audit
from app.modules.party import repository as repo
from app.modules.party import schemas
from app.modules.party.models import Address, Party, PartyAddress, PartyRole
from app.security.auth_dep import require_auth
from app.security.permission_dep import require_permission

router = APIRouter(prefix="/api/v1/modules/party", tags=["party"])

_READ = Depends(require_permission("party.read"))
_CREATE = Depends(require_permission("party.create"))
_UPDATE = Depends(require_permission("party.update"))
_DELETE = Depends(require_permission("party.delete"))

_PARTY_SORT = {"name": Party.name, "created_at": Party.created_at}
_ADDRESS_SORT = {"city": Address.city, "created_at": Address.created_at}


def _bool(v: int | None) -> bool | None:
    return None if v is None else bool(v)


async def _keyset(session, stmt, *, sort, allowed, default, limit, cursor,
                  id_col=None, specs=None) -> dict:
    sort_col, sort_desc, id_col, value_of = resolve_entity_sort(
        sort, allowed=allowed, default=default, id_col=id_col, specs=specs)
    items, next_cursor, count, capped = await keyset_page(
        session, stmt, sort_col=sort_col, sort_desc=sort_desc, cursor=cursor,
        limit=limit, id_col=id_col, value_of=value_of)
    return {"items": [i.as_dict() for i in items], "next_cursor": next_cursor,
            "count": count, "capped": capped}


# --- Parties -------------------------------------------------------------

@router.get("/parties", dependencies=[_READ])
async def list_parties(q: str | None = None, party_type: str | None = None,
                       active: int | None = None, sort: str = "name",
                       limit: int = 50, cursor: str | None = None,
                       session: AsyncSession = Depends(get_session)) -> dict:
    # `party.custom_fields` is not an extensible target (see
    # `registry.EXTENSIBLE_TARGETS`'s docstring — Party is a global directory
    # with no organisation to resolve definitions against), so `specs=None`
    # unconditionally: `resolve_entity_sort` already turns a
    # `sort=custom_fields.<key>` request into a 422 whenever `specs` is None.
    stmt = repo.parties_select(q=q, party_type=party_type, active=_bool(active))
    return await _keyset(session, stmt, sort=sort, allowed=_PARTY_SORT,
                         default="name", limit=limit, cursor=cursor,
                         id_col=Party.id, specs=None)


def _reject_custom_fields(custom_fields: dict | None) -> None:
    """`party.custom_fields` is NOT an extensible target (removed from
    `registry.EXTENSIBLE_TARGETS` — see its docstring for why: Party is a
    global directory with no organisation to own a definition set). The
    `custom_fields` COLUMN still exists on the model (pre-dates SP1; dropping
    it would be destructive to historic data), so it must be actively guarded
    rather than left reachable: without this, removing the old allowlist
    wiring would let a caller write ARBITRARY free-form JSON into it. Any
    attempt to write the key at all (present in the payload, including an
    empty `{}`) is refused — there is no organisation whose schema could ever
    validate it."""
    if custom_fields is not None:
        raise HTTPException(422, "party is not an extensible target")


@router.post("/parties", status_code=201, dependencies=[_CREATE])
async def create_party(body: schemas.PartyIn,
                       session: AsyncSession = Depends(get_session)) -> dict:
    # On CREATE, PartyIn.custom_fields defaults to {} (empty dict via default_factory).
    # An empty dict is falsy and carries no keys — there is no free-form JSON to leak.
    # Changing this guard to `is not None` would reject every ordinary party creation
    # that omits custom_fields (because {} is not None). This asymmetry with UPDATE is
    # deliberate: UPDATE's PartyUpdate.custom_fields defaults to None (omitted), so
    # _reject_custom_fields(None) correctly does nothing there. Pin with tests.
    if body.custom_fields:
        _reject_custom_fields(body.custom_fields)
    row = Party(**body.model_dump())
    # MINORS fix (final fix wave): `entity="party"` was dead — `_save_new`
    # only ever reads `entity` inside its `if principal is not None:` branch
    # (for the audit-record `detail`), and this call site never passes
    # `principal` (defaults to `None`), so the value never had any effect.
    return await _save_new(session, row)


@router.get("/parties/{pid}", dependencies=[_READ])
async def get_party(pid: str, session: AsyncSession = Depends(get_session)) -> dict:
    return _detail(await session.get(Party, pid), "party", pid)


@router.put("/parties/{pid}", dependencies=[_UPDATE])
async def update_party(pid: str, body: schemas.PartyUpdate, request: Request,
                       session: AsyncSession = Depends(get_session)) -> dict:
    row = await session.get(Party, pid)
    if row is None:
        raise HTTPException(404, f"party '{pid}' not found")
    enforce_if_match(request, row_etag(row))
    _reject_custom_fields(body.custom_fields)
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(row, k, v)
    try:
        await session.commit()
    except IntegrityError as e:
        await session.rollback()
        raise HTTPException(409, "duplicate or invalid reference") from e
    return row.as_dict()


@router.delete("/parties/{pid}", dependencies=[_DELETE])
async def delete_party(pid: str, session: AsyncSession = Depends(get_session)) -> dict:
    return await _delete(session, Party, pid, "party")


# --- Party roles (nested) ------------------------------------------------

@router.get("/parties/{pid}/roles", dependencies=[_READ])
async def list_party_roles(pid: str, session: AsyncSession = Depends(get_session)) -> list[dict]:
    rows = (await session.scalars(
        select(PartyRole).where(PartyRole.party_id == pid).order_by(PartyRole.role))).all()
    return [r.as_dict() for r in rows]


@router.post("/parties/{pid}/roles", status_code=201, dependencies=[_CREATE])
async def add_party_role(pid: str, body: schemas.PartyRoleIn,
                         session: AsyncSession = Depends(get_session)) -> dict:
    if await session.get(Party, pid) is None:
        raise HTTPException(404, f"party '{pid}' not found")
    return await _save_new(session, PartyRole(party_id=pid, role=body.role))


@router.delete("/parties/{pid}/roles/{role_id}", dependencies=[_DELETE])
async def remove_party_role(pid: str, role_id: str,
                            session: AsyncSession = Depends(get_session)) -> dict:
    row = await session.get(PartyRole, role_id)
    if row is None or row.party_id != pid:
        raise HTTPException(404, f"role '{role_id}' not found")
    await session.delete(row)
    await session.commit()
    return {"deleted": role_id}


# --- Party addresses (link to reusable Address) --------------------------

@router.get("/parties/{pid}/addresses", dependencies=[_READ])
async def list_party_addresses(pid: str, session: AsyncSession = Depends(get_session)) -> list[dict]:
    rows = (await session.scalars(
        select(PartyAddress).where(PartyAddress.party_id == pid))).all()
    return [r.as_dict() for r in rows]


@router.post("/parties/{pid}/addresses", status_code=201, dependencies=[_CREATE])
async def link_party_address(pid: str, body: schemas.PartyAddressIn,
                             session: AsyncSession = Depends(get_session)) -> dict:
    if await session.get(Party, pid) is None:
        raise HTTPException(404, f"party '{pid}' not found")
    if await session.get(Address, body.address_id) is None:
        raise HTTPException(422, f"address '{body.address_id}' not found")
    return await _save_new(session, PartyAddress(party_id=pid, **body.model_dump()))


@router.delete("/parties/{pid}/addresses/{link_id}", dependencies=[_DELETE])
async def unlink_party_address(pid: str, link_id: str,
                               session: AsyncSession = Depends(get_session)) -> dict:
    row = await session.get(PartyAddress, link_id)
    if row is None or row.party_id != pid:
        raise HTTPException(404, f"link '{link_id}' not found")
    await session.delete(row)
    await session.commit()
    return {"deleted": link_id}


# --- Addresses -----------------------------------------------------------

@router.get("/addresses", dependencies=[_READ])
async def list_addresses(q: str | None = None, country_id: str | None = None,
                         active: int | None = None, sort: str = "-created_at",
                         limit: int = 50, cursor: str | None = None,
                         session: AsyncSession = Depends(get_session)) -> dict:
    stmt = repo.addresses_select(q=q, country_id=country_id, active=_bool(active))
    return await _keyset(session, stmt, sort=sort, allowed=_ADDRESS_SORT,
                         default="-created_at", limit=limit, cursor=cursor)


@router.post("/addresses", status_code=201, dependencies=[_CREATE])
async def create_address(body: schemas.AddressIn,
                         session: AsyncSession = Depends(get_session)) -> dict:
    return await _save_new(session, Address(**body.model_dump()))


@router.get("/addresses/{aid}", dependencies=[_READ])
async def get_address(aid: str, session: AsyncSession = Depends(get_session)) -> dict:
    return _detail(await session.get(Address, aid), "address", aid)


@router.put("/addresses/{aid}", dependencies=[_UPDATE])
async def update_address(aid: str, body: schemas.AddressUpdate, request: Request,
                         session: AsyncSession = Depends(get_session)) -> dict:
    return await _apply_update(session, Address, aid, body, request, "address")


@router.delete("/addresses/{aid}", dependencies=[_DELETE])
async def delete_address(aid: str, session: AsyncSession = Depends(get_session)) -> dict:
    return await _delete(session, Address, aid, "address")


# --- Shared CRUD helpers -------------------------------------------------

async def _save_new(session: AsyncSession, row, *, principal: dict | None = None,
                    entity: str = "") -> dict:
    session.add(row)
    if principal is not None:
        # Flush BEFORE the audit: `audit.record` flushes and swallows every
        # exception by design, so if the new row's FIRST flush happened inside
        # it, an IntegrityError would be silently absorbed there, poisoning the
        # transaction, and the commit below would raise PendingRollbackError as
        # an unhandled 500 instead of this 409.
        try:
            await session.flush()
        except IntegrityError as e:
            await session.rollback()
            raise HTTPException(409, "duplicate or invalid reference") from e
        await audit.record(session, audit.CUSTOM_FIELDS_CHANGED,
                           account_id=principal.get("sub"),
                           detail={"entity": entity, "id": row.id})
    try:
        await session.commit()
    except IntegrityError as e:
        await session.rollback()
        raise HTTPException(409, "duplicate or invalid reference") from e
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
        raise HTTPException(409, "duplicate or invalid reference") from e
    return row.as_dict()


async def _delete(session, model, rid: str, label: str) -> dict:
    row = await session.get(model, rid)
    if row is None:
        raise HTTPException(404, f"{label} '{rid}' not found")
    await session.delete(row)
    await session.commit()
    return {"deleted": rid}
