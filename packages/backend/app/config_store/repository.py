"""Data access for the `settings` table (async SQLAlchemy)."""

from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.setting import Setting


async def list_settings(session: AsyncSession, scope: str | None = None) -> list[Setting]:
    stmt = select(Setting).order_by(Setting.key)
    if scope:
        stmt = stmt.where(Setting.scope == scope)
    return list((await session.scalars(stmt)).all())


async def get_setting(session: AsyncSession, key: str) -> Setting | None:
    return await session.scalar(select(Setting).where(Setting.key == key))


async def upsert_setting(session: AsyncSession, key: str, value, *,
                         value_type: str = "string", scope: str = "global",
                         secret_ref: str = "", updated_by: str | None = None,
                         **names) -> Setting:
    obj = await get_setting(session, key)
    if obj is None:
        obj = Setting(key=key)
        session.add(obj)
    obj.value = value
    obj.value_type = value_type
    obj.scope = scope
    obj.secret_ref = secret_ref
    obj.updated_by = updated_by
    for k in ("name_es", "name_fr", "name_en", "description", "is_active"):
        if k in names and names[k] is not None:
            setattr(obj, k, names[k])
    await session.flush()
    return obj


async def delete_setting(session: AsyncSession, key: str) -> bool:
    res = await session.execute(delete(Setting).where(Setting.key == key))
    return res.rowcount > 0


async def active_map(session: AsyncSession) -> dict[str, object]:
    """{key: value} of active settings — the DB layer for the resolver."""
    rows = await session.scalars(select(Setting).where(Setting.is_active.is_(True)))
    return {s.key: s.value for s in rows}
