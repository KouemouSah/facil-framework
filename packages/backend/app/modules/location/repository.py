"""Data access for the location module (Site)."""

from __future__ import annotations

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.location.models import Site


async def list_sites(session: AsyncSession, *, organization_id: str | None = None,
                     org_unit_id: str | None = None,
                     parent_site_id: str | None = None) -> list[Site]:
    """Scope query: filter sites by org / unit / parent (the scope primitive
    D4 will bind to the authenticated user)."""
    stmt = select(Site).order_by(Site.organization_id, Site.code)
    if organization_id is not None:
        stmt = stmt.where(Site.organization_id == organization_id)
    if org_unit_id is not None:
        stmt = stmt.where(Site.org_unit_id == org_unit_id)
    if parent_site_id is not None:
        stmt = stmt.where(Site.parent_site_id == parent_site_id)
    return list((await session.scalars(stmt)).all())


async def get_site(session: AsyncSession, site_id: str) -> Site | None:
    return await session.get(Site, site_id)


async def get_site_by_code(session: AsyncSession, org_id: str, code: str) -> Site | None:
    return await session.scalar(select(Site).where(
        Site.organization_id == org_id, Site.code == code))


async def clear_primary(session: AsyncSession, org_id: str, *, except_id: str) -> None:
    """Unset is_primary on every other site of the org (single HQ per org)."""
    await session.execute(update(Site)
                          .where(Site.organization_id == org_id, Site.id != except_id)
                          .values(is_primary=False))


async def delete_site(session: AsyncSession, site_id: str) -> bool:
    res = await session.execute(delete(Site).where(Site.id == site_id))
    return res.rowcount > 0
