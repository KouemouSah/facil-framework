"""Data access for the organization module (Organization + OrgUnit)."""

from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.organization.models import OrgUnit, Organization


# --- Organization --------------------------------------------------------

async def list_organizations(session: AsyncSession) -> list[Organization]:
    return list((await session.scalars(
        select(Organization).order_by(Organization.code))).all())


async def get_organization(session: AsyncSession, org_id: str) -> Organization | None:
    return await session.get(Organization, org_id)


async def get_organization_by_code(session: AsyncSession, code: str) -> Organization | None:
    return await session.scalar(select(Organization).where(Organization.code == code))


async def delete_organization(session: AsyncSession, org_id: str) -> bool:
    res = await session.execute(delete(Organization).where(Organization.id == org_id))
    return res.rowcount > 0


# --- OrgUnit -------------------------------------------------------------

async def list_units(session: AsyncSession, org_id: str) -> list[OrgUnit]:
    return list((await session.scalars(
        select(OrgUnit).where(OrgUnit.organization_id == org_id)
        .order_by(OrgUnit.path, OrgUnit.code))).all())


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
