"""Data access for `provider_settings` (async SQLAlchemy)."""

from __future__ import annotations

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.provider import ProviderSetting


async def list_providers(session: AsyncSession, capability: str | None = None):
    stmt = select(ProviderSetting).order_by(
        ProviderSetting.capability, ProviderSetting.provider_code)
    if capability:
        stmt = stmt.where(ProviderSetting.capability == capability)
    return list((await session.scalars(stmt)).all())


async def get_provider(session: AsyncSession, capability: str, code: str):
    return await session.scalar(select(ProviderSetting).where(
        ProviderSetting.capability == capability,
        ProviderSetting.provider_code == code))


async def get_default(session: AsyncSession, capability: str):
    return await session.scalar(select(ProviderSetting).where(
        ProviderSetting.capability == capability,
        ProviderSetting.is_default.is_(True),
        ProviderSetting.is_active.is_(True)))


async def upsert_provider(session: AsyncSession, capability: str, code: str, *,
                          config: dict | None = None, secret_ref: str = "",
                          is_active: bool = True, updated_by: str | None = None,
                          **extra) -> ProviderSetting:
    obj = await get_provider(session, capability, code)
    if obj is None:
        obj = ProviderSetting(capability=capability, provider_code=code)
        session.add(obj)
    obj.config = config or {}
    obj.secret_ref = secret_ref
    obj.is_active = is_active
    obj.updated_by = updated_by
    for k in ("rate_limit_per_minute", "retry_attempts", "timeout_seconds"):
        if extra.get(k) is not None:
            setattr(obj, k, extra[k])
    await session.flush()
    return obj


async def set_default(session: AsyncSession, capability: str, code: str) -> bool:
    """Make (capability, code) the single default. Returns False if it doesn't exist."""
    target = await get_provider(session, capability, code)
    if target is None:
        return False
    await session.execute(update(ProviderSetting)
                          .where(ProviderSetting.capability == capability)
                          .values(is_default=False))
    target.is_default = True
    target.is_active = True
    await session.flush()
    return True


async def delete_provider(session: AsyncSession, capability: str, code: str) -> bool:
    res = await session.execute(delete(ProviderSetting).where(
        ProviderSetting.capability == capability,
        ProviderSetting.provider_code == code))
    return res.rowcount > 0
