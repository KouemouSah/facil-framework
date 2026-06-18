"""Business rules for the organization module.

Keeps the data layer (repository) free of policy: code uniqueness, materialized
`path`/`depth` computation, and the anti-cycle guard on re-parenting (with a
subtree path rewrite) live here. Raises domain errors the API maps to HTTP.
"""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.organization import repository as repo
from app.modules.organization.models import OrgUnit, Organization
from app.modules.organization.schemas import (OrganizationCreate,
                                               OrganizationUpdate, OrgUnitCreate,
                                               OrgUnitUpdate)


class OrgError(Exception):
    """Base domain error."""


class NotFound(OrgError):
    pass


class Conflict(OrgError):
    pass


class InvalidParent(OrgError):
    pass


class InvalidReference(OrgError):
    """A company-link FK (party/address/currency) points to a missing row."""


# --- Company-link FK validation (F.3) ------------------------------------
# An Organization references master data in sibling modules (party / address /
# currency) plus a consolidation parent. We validate references explicitly here
# (clear 422 per field, and works on SQLite where FKs aren't enforced) rather
# than relying solely on the DB FK (which surfaces as an opaque 409). Existence
# is probed by parameterised SQL on a fixed table name to avoid importing other
# modules' models into this one (modular-monolith decoupling).
_LINK_TABLES = {"party_id": "party", "hq_address_id": "address",
                "currency_id": "currency"}


async def _ref_exists(session: AsyncSession, table: str, rid: str) -> bool:
    res = await session.execute(
        text(f"SELECT 1 FROM {table} WHERE id = :id"), {"id": rid})  # noqa: S608 (table is a constant)
    return res.first() is not None


async def _assert_no_parent_cycle(session: AsyncSession, org_id: str,
                                  parent_id: str) -> None:
    """Walk the parent chain up from `parent_id`; reject if it reaches `org_id`
    (A→B→A consolidation loop). Self-protects against any pre-existing cycle."""
    seen: set[str] = set()
    cur: str | None = parent_id
    while cur:
        if cur == org_id:
            raise InvalidParent("re-parenting would create a consolidation cycle")
        if cur in seen:
            break
        seen.add(cur)
        res = await session.execute(
            text("SELECT parent_id FROM organization WHERE id = :id"), {"id": cur})
        row = res.first()
        cur = row[0] if row else None


async def _validate_links(session: AsyncSession, org_id: str | None,
                          fields: dict) -> None:
    for key, table in _LINK_TABLES.items():
        rid = fields.get(key)
        if rid and not await _ref_exists(session, table, rid):
            raise InvalidReference(
                f"{key} '{rid}' does not reference an existing {table}")
    parent_id = fields.get("parent_id")
    if parent_id:
        if parent_id == org_id:
            raise InvalidParent(
                "an organization cannot be its own consolidation parent")
        if not await _ref_exists(session, "organization", parent_id):
            raise InvalidReference(
                f"parent_id '{parent_id}' does not reference an existing organization")
        if org_id is not None:
            await _assert_no_parent_cycle(session, org_id, parent_id)


# --- Organization --------------------------------------------------------

async def create_organization(session: AsyncSession,
                              data: OrganizationCreate) -> Organization:
    if await repo.get_organization_by_code(session, data.code):
        raise Conflict(f"organization code '{data.code}' already exists")
    fields = data.model_dump()
    await _validate_links(session, None, fields)
    org = Organization(**fields)
    session.add(org)
    await session.flush()
    return org


async def update_organization(session: AsyncSession, org_id: str,
                             data: OrganizationUpdate) -> Organization:
    org = await repo.get_organization(session, org_id)
    if org is None:
        raise NotFound(f"organization '{org_id}' not found")
    fields = data.model_dump(exclude_unset=True)
    await _validate_links(session, org_id, fields)
    for field, value in fields.items():
        setattr(org, field, value)
    await session.flush()
    return org


# --- OrgUnit -------------------------------------------------------------

def _child_path(parent: OrgUnit | None, unit_id: str) -> tuple[str, int]:
    base = parent.path if parent else "/"
    return f"{base}{unit_id}/", (parent.depth + 1 if parent else 0)


async def _resolve_parent(session: AsyncSession, org_id: str,
                          parent_id: str | None) -> OrgUnit | None:
    if not parent_id:
        return None
    parent = await repo.get_unit(session, parent_id)
    if parent is None or parent.organization_id != org_id:
        raise InvalidParent(f"parent unit '{parent_id}' not found in this organization")
    return parent


async def create_unit(session: AsyncSession, org_id: str,
                     data: OrgUnitCreate) -> OrgUnit:
    if await repo.get_organization(session, org_id) is None:
        raise NotFound(f"organization '{org_id}' not found")
    if await repo.get_unit_by_code(session, org_id, data.code):
        raise Conflict(f"unit code '{data.code}' already exists in this organization")
    parent = await _resolve_parent(session, org_id, data.parent_id)
    payload = data.model_dump()
    meta = payload.pop("metadata")
    unit = OrgUnit(organization_id=org_id, meta=meta, **payload)
    session.add(unit)
    await session.flush()  # assign id
    unit.path, unit.depth = _child_path(parent, unit.id)
    await session.flush()
    return unit


async def _reparent(session: AsyncSession, unit: OrgUnit,
                    new_parent: OrgUnit | None) -> None:
    if new_parent is not None:
        if new_parent.id == unit.id or new_parent.path.startswith(unit.path):
            raise InvalidParent("cannot move a unit under itself or its descendant")
        if new_parent.organization_id != unit.organization_id:
            raise InvalidParent("parent must belong to the same organization")
    old_prefix, old_depth = unit.path, unit.depth
    new_path, new_depth = _child_path(new_parent, unit.id)
    delta = new_depth - old_depth
    for node in await repo.subtree(session, unit):  # includes `unit` itself
        node.path = new_path + node.path[len(old_prefix):]
        node.depth = node.depth + delta
    unit.parent_id = new_parent.id if new_parent else None
    await session.flush()


async def update_unit(session: AsyncSession, unit_id: str,
                     data: OrgUnitUpdate) -> OrgUnit:
    unit = await repo.get_unit(session, unit_id)
    if unit is None:
        raise NotFound(f"unit '{unit_id}' not found")
    fields = data.model_dump(exclude_unset=True)
    if "parent_id" in data.model_fields_set:
        new_parent = await _resolve_parent(session, unit.organization_id,
                                           fields.pop("parent_id"))
        await _reparent(session, unit, new_parent)
    if "metadata" in fields:
        unit.meta = fields.pop("metadata")
    for field, value in fields.items():
        setattr(unit, field, value)
    await session.flush()
    return unit
