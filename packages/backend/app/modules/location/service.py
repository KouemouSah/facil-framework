"""Business rules for the location module.

Cross-module validation (a Site belongs to an Organization and optionally an
OrgUnit) lives here, plus code uniqueness, single-primary-per-org enforcement,
and a branch anti-cycle guard (ancestor walk on parent_site_id).
"""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.location import repository as repo
from app.modules.location.models import Site
from app.modules.location.schemas import SiteCreate, SiteUpdate
from app.modules.organization import repository as org_repo


class LocError(Exception):
    """Base domain error."""


class NotFound(LocError):
    pass


class Conflict(LocError):
    pass


class InvalidRef(LocError):
    pass


async def _address_exists(session: AsyncSession, address_id: str) -> bool:
    # Probe the sibling party module's `address` table by id without importing
    # its model (modular-monolith decoupling; the table name is a constant).
    res = await session.execute(
        text("SELECT 1 FROM address WHERE id = :id"), {"id": address_id})
    return res.first() is not None


async def _validate_refs(session: AsyncSession, org_id: str,
                         org_unit_id: str | None,
                         parent_site_id: str | None,
                         address_id: str | None = None) -> None:
    if org_unit_id:
        unit = await org_repo.get_unit(session, org_unit_id)
        if unit is None or unit.organization_id != org_id:
            raise InvalidRef(f"org_unit '{org_unit_id}' not found in this organization")
    if parent_site_id:
        parent = await repo.get_site(session, parent_site_id)
        if parent is None or parent.organization_id != org_id:
            raise InvalidRef(f"parent site '{parent_site_id}' not found in this organization")
    if address_id and not await _address_exists(session, address_id):
        raise InvalidRef(f"address '{address_id}' does not reference an existing address")


async def _would_cycle(session: AsyncSession, site_id: str,
                       new_parent_id: str | None) -> bool:
    cur, seen = new_parent_id, set()
    while cur:
        if cur == site_id:
            return True
        if cur in seen:
            break
        seen.add(cur)
        parent = await repo.get_site(session, cur)
        cur = parent.parent_site_id if parent else None
    return False


async def create_site(session: AsyncSession, data: SiteCreate) -> Site:
    if await org_repo.get_organization(session, data.organization_id) is None:
        raise NotFound(f"organization '{data.organization_id}' not found")
    if await repo.get_site_by_code(session, data.organization_id, data.code):
        raise Conflict(f"site code '{data.code}' already exists in this organization")
    await _validate_refs(session, data.organization_id, data.org_unit_id,
                         data.parent_site_id, data.address_id)
    payload = data.model_dump()
    meta = payload.pop("metadata")
    site = Site(meta=meta, **payload)
    session.add(site)
    await session.flush()
    if site.is_primary:
        await repo.clear_primary(session, site.organization_id, except_id=site.id)
    await session.flush()
    return site


async def update_site(session: AsyncSession, site_id: str, data: SiteUpdate) -> Site:
    site = await repo.get_site(session, site_id)
    if site is None:
        raise NotFound(f"site '{site_id}' not found")
    fields = data.model_dump(exclude_unset=True)
    new_unit = fields.get("org_unit_id") if "org_unit_id" in fields else site.org_unit_id
    new_parent = fields.get("parent_site_id") if "parent_site_id" in fields else site.parent_site_id
    new_address = fields.get("address_id") if "address_id" in fields else site.address_id
    if "org_unit_id" in fields or "parent_site_id" in fields or "address_id" in fields:
        await _validate_refs(session, site.organization_id, new_unit, new_parent, new_address)
    if "parent_site_id" in fields and await _would_cycle(session, site_id, new_parent):
        raise InvalidRef("cannot set a site under itself or one of its branches")
    if "metadata" in fields:
        site.meta = fields.pop("metadata")
    for field, value in fields.items():
        setattr(site, field, value)
    await session.flush()
    if site.is_primary:
        await repo.clear_primary(session, site.organization_id, except_id=site.id)
        await session.flush()
    return site
