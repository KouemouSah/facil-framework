"""Data access for the organization module (Organization + OrgUnit)."""

from __future__ import annotations

from sqlalchemy import Select, delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.organization.models import OrgUnit, Organization


# --- Organization --------------------------------------------------------

def organizations_select(*, org_ids: set[str] | None = None,
                         q: str | None = None) -> Select:
    """Base SELECT for organizations: RBAC scope filter + optional substring
    search (code / legal_name / display_name). Unsorted/unpaginated — the caller
    applies sort + pagination via app.api.list_query."""
    stmt = select(Organization)
    if org_ids is not None:  # None = all / global reader; empty set -> no rows
        stmt = stmt.where(Organization.id.in_(org_ids))
    if q:
        like = f"%{q}%"
        stmt = stmt.where(or_(
            Organization.code.ilike(like),
            Organization.legal_name.ilike(like),
            Organization.display_name.ilike(like)))
    return stmt


async def get_organization(session: AsyncSession, org_id: str) -> Organization | None:
    return await session.get(Organization, org_id)


async def get_organization_by_code(session: AsyncSession, code: str) -> Organization | None:
    return await session.scalar(select(Organization).where(Organization.code == code))


async def delete_organization(session: AsyncSession, org_id: str) -> bool:
    res = await session.execute(delete(Organization).where(Organization.id == org_id))
    return res.rowcount > 0


# --- OrgUnit -------------------------------------------------------------

async def list_units(session: AsyncSession, org_id: str, *,
                     limit: int = 50, offset: int = 0) -> list[OrgUnit]:
    return list((await session.scalars(
        select(OrgUnit).where(OrgUnit.organization_id == org_id)
        .order_by(OrgUnit.path, OrgUnit.code).limit(limit).offset(offset))).all())


async def get_unit(session: AsyncSession, unit_id: str) -> OrgUnit | None:
    return await session.get(OrgUnit, unit_id)


async def get_unit_by_code(session: AsyncSession, org_id: str, code: str) -> OrgUnit | None:
    return await session.scalar(select(OrgUnit).where(
        OrgUnit.organization_id == org_id, OrgUnit.code == code))


async def subtree(session: AsyncSession, unit: OrgUnit) -> list[OrgUnit]:
    """All units at or below `unit` (inclusive), via the materialized path."""
    return list((await session.scalars(
        select(OrgUnit).where(OrgUnit.organization_id == unit.organization_id,
                              OrgUnit.path.like(f"{unit.path}%"))
        .order_by(OrgUnit.path))).all())


async def delete_unit(session: AsyncSession, unit_id: str) -> bool:
    res = await session.execute(delete(OrgUnit).where(OrgUnit.id == unit_id))
    return res.rowcount > 0
