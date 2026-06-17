"""Data access for the location module (Site)."""

from __future__ import annotations

from sqlalchemy import Select, delete, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.location.models import Site


def sites_select(*, organization_id: str | None = None,
                 org_unit_id: str | None = None, parent_site_id: str | None = None,
                 org_ids: set[str] | None = None, q: str | None = None) -> Select:
    """Base SELECT for sites: org/unit/parent filters + RBAC scope + optional
    substring search (code / name / city). Unsorted/unpaginated — caller applies
    sort + pagination via app.api.list_query."""
    stmt = select(Site)
    if organization_id is not None:
        stmt = stmt.where(Site.organization_id == organization_id)
    if org_unit_id is not None:
        stmt = stmt.where(Site.org_unit_id == org_unit_id)
    if parent_site_id is not None:
        stmt = stmt.where(Site.parent_site_id == parent_site_id)
    if org_ids is not None:  # None = all; empty set -> no rows
        stmt = stmt.where(Site.organization_id.in_(org_ids))
    if q:
        like = f"%{q}%"
        stmt = stmt.where(or_(
            Site.code.ilike(like), Site.name.ilike(like), Site.city.ilike(like)))
    return stmt


async def list_sites(session: AsyncSession, *, organization_id: str | None = None,
                     org_unit_id: str | None = None,
                     parent_site_id: str | None = None,
                     org_ids: set[str] | None = None,
                     limit: int = 50, offset: int = 0) -> list[Site]:
    """Scope query: filter sites by org / unit / parent + an optional visible-org
    set (RBAC scope, applied in SQL) + pagination."""
    stmt = select(Site).order_by(Site.organization_id, Site.code)
    if organization_id is not None:
        stmt = stmt.where(Site.organization_id == organization_id)
    if org_unit_id is not None:
        stmt = stmt.where(Site.org_unit_id == org_unit_id)
    if parent_site_id is not None:
        stmt = stmt.where(Site.parent_site_id == parent_site_id)
    if org_ids is not None:
        if not org_ids:
            return []
        stmt = stmt.where(Site.organization_id.in_(org_ids))
    stmt = stmt.limit(limit).offset(offset)
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
