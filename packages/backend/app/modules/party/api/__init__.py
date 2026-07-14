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
from app.api.list_query import keyset_page, resolve_sort
from app.auth import audit
from app.core.schema import repository as schema_repo
from app.core.schema.merge import merge_blob
from app.core.schema.pydantic_gen import SchemaViolation, validate_blob
from app.core.schema.sanitize import clean_richtext_fields
from app.modules.party import repository as repo
from app.modules.party import schemas
from app.modules.party.models import Address, Party, PartyAddress, PartyRole
from app.security.auth_dep import require_auth
from app.security.permission_dep import require_permission, visible_orgs

router = APIRouter(prefix="/api/v1/modules/party", tags=["party"])

_READ = Depends(require_permission("party.read"))
_CREATE = Depends(require_permission("party.create"))
_UPDATE = Depends(require_permission("party.update"))
_DELETE = Depends(require_permission("party.delete"))

_PARTY_SORT = {"name": Party.name, "created_at": Party.created_at}
_ADDRESS_SORT = {"city": Address.city, "created_at": Address.created_at}


def _bool(v: int | None) -> bool | None:
    return None if v is None else bool(v)


async def _keyset(session, stmt, *, sort, allowed, default, limit, cursor) -> dict:
    sort_col, sort_desc = resolve_sort(sort, allowed=allowed, default=default)
    items, next_cursor, count, capped = await keyset_page(
        session, stmt, sort_col=sort_col, sort_desc=sort_desc, cursor=cursor, limit=limit)
    return {"items": [i.as_dict() for i in items], "next_cursor": next_cursor,
            "count": count, "capped": capped}


# --- Parties -------------------------------------------------------------

@router.get("/parties", dependencies=[_READ])
async def list_parties(q: str | None = None, party_type: str | None = None,
                       active: int | None = None, sort: str = "name",
                       limit: int = 50, cursor: str | None = None,
                       session: AsyncSession = Depends(get_session)) -> dict:
    stmt = repo.parties_select(q=q, party_type=party_type, active=_bool(active))
    return await _keyset(session, stmt, sort=sort, allowed=_PARTY_SORT,
                         default="name", limit=limit, cursor=cursor)


async def _party_specs(session: AsyncSession, principal: dict,
                       definitions_org_id: str | None) -> list[dict]:
    """Resolve which organisation's `party.custom_fields` definitions apply.

    A `Party` is GLOBAL directory data with no `organization_id` of its own
    (V1, "not tenant-scoped" — see this module's docstring), but a
    `FieldDefinition` is ALWAYS org-owned (`organization_id` NOT NULL — the
    formal statement of tenant isolation). So the caller must NAME the
    organisation whose definitions apply.

    The parameter is called `definitions_org_id`, NOT `organization_id`, and
    that is load-bearing: `rbac.scope.raw_scope_ids` harvests any query param
    named `org_id`/`organization_id` and feeds it to `require_permission` as
    the REQUEST SCOPE. Naming it `organization_id` would silently narrow the
    scope of every party write from global to that org — turning the
    router-level `party.create`/`party.update` check from "needs a GLOBAL
    grant" (correct for global directory data: `covers()` rejects an
    org-scoped grant against a global request) into "an org-scoped grant on
    ANY org you control is enough", letting a tenant admin mutate the shared
    directory. The name must stay invisible to `raw_scope_ids`.

    It is still authorization-checked in its own right: the caller must be
    able to SEE that organisation, or they could use the 422 "key not
    declared" vs. success signal as an oracle to enumerate another tenant's
    custom-field keys. 404, not 403 (same anti-enumeration rule as
    `GET /api/v1/schema`, whose gate this mirrors).
    """
    if not definitions_org_id:
        return []
    allowed = await visible_orgs(session, principal, "organization.read")
    if allowed is not None and definitions_org_id not in allowed:
        raise HTTPException(404, f"organization {definitions_org_id!r} not found")
    return [r.as_spec() for r in await schema_repo.definitions_for(
        session, "party.custom_fields", definitions_org_id)]


def _require_definitions_org(custom_fields: dict | None,
                             definitions_org_id: str | None) -> None:
    """`definitions_org_id` is required whenever `custom_fields` is present AT
    ALL — including `{}`. An empty dict is a CLEAR (per `validate_blob`'s
    documented sentinel: a declared key absent from the payload is removed from
    the stored blob), not a no-op. Accepting `{}` without an org would resolve
    zero specs, so `merge_blob` would preserve every existing key and the clear
    would be SILENTLY IGNORED while still returning 200 — exactly the silent
    failure the repo forbids. Demand the org so the clear is real."""
    if custom_fields is not None and not definitions_org_id:
        raise HTTPException(
            422, "definitions_org_id is required whenever custom_fields is sent on a "
                 "party (party.custom_fields definitions are organisation-scoped; "
                 "an empty object is a CLEAR, not a no-op)")


@router.post("/parties", status_code=201, dependencies=[_CREATE])
async def create_party(body: schemas.PartyIn, definitions_org_id: str | None = None,
                       principal: dict = Depends(require_auth),
                       session: AsyncSession = Depends(get_session)) -> dict:
    # `custom_fields` (Task 13) allowlist against `party.custom_fields` DB
    # definitions — unconditional, exactly like every other extensible target.
    # Omitting the key entirely means "not configured" and is skipped; sending
    # it (even as `{}`) requires `definitions_org_id` — see the two helpers.
    touched = bool(body.custom_fields)
    if touched:
        _require_definitions_org(body.custom_fields, definitions_org_id)
        specs = await _party_specs(session, principal, definitions_org_id)
        try:
            body.custom_fields = clean_richtext_fields(
                specs, validate_blob(specs, body.custom_fields))
        except SchemaViolation as e:
            raise HTTPException(422, detail=e.errors) from e
    row = Party(**body.model_dump())
    return await _save_new(session, row, principal=principal if touched else None,
                           entity="party")


@router.get("/parties/{pid}", dependencies=[_READ])
async def get_party(pid: str, session: AsyncSession = Depends(get_session)) -> dict:
    return _detail(await session.get(Party, pid), "party", pid)


@router.put("/parties/{pid}", dependencies=[_UPDATE])
async def update_party(pid: str, body: schemas.PartyUpdate, request: Request,
                       definitions_org_id: str | None = None,
                       principal: dict = Depends(require_auth),
                       session: AsyncSession = Depends(get_session)) -> dict:
    row = await session.get(Party, pid)
    if row is None:
        raise HTTPException(404, f"party '{pid}' not found")
    enforce_if_match(request, row_etag(row))
    # `custom_fields` (Task 13): same allowlist as create, merge-preserve like
    # organization/org_unit/site. `definitions_org_id` (NOT `organization_id`
    # — see `_party_specs`) is required whenever the key is present, including
    # for an empty-dict CLEAR.
    touched = body.custom_fields is not None
    if touched:
        _require_definitions_org(body.custom_fields, definitions_org_id)
        specs = await _party_specs(session, principal, definitions_org_id)
        try:
            body.custom_fields = clean_richtext_fields(specs, merge_blob(
                row.custom_fields or {}, body.custom_fields, specs))
        except SchemaViolation as e:
            raise HTTPException(422, detail=e.errors) from e
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(row, k, v)
    if touched:
        await audit.record(session, audit.CUSTOM_FIELDS_CHANGED,
                           account_id=principal.get("sub"),
                           detail={"entity": "party", "id": pid})
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
