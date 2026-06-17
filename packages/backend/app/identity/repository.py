"""Data access for accounts (identity)."""

from __future__ import annotations

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.identity.models import Account


async def get_account(session: AsyncSession, account_id: str) -> Account | None:
    return await session.get(Account, account_id)


async def list_accounts(session: AsyncSession, *, q: str | None = None,
                        organization_id: str | None = None,
                        limit: int = 50, offset: int = 0) -> list[Account]:
    """Paginated account listing with an optional substring search (email /
    account_number / display_name) and org filter. Newest first."""
    stmt = select(Account)
    if organization_id:
        stmt = stmt.where(Account.organization_id == organization_id)
    if q:
        like = f"%{q}%"
        stmt = stmt.where(or_(
            Account.email.ilike(like),
            Account.account_number.ilike(like),
            Account.display_name.ilike(like)))
    stmt = stmt.order_by(Account.created_at.desc()).limit(limit).offset(offset)
    return list((await session.scalars(stmt)).all())


async def get_by_email(session: AsyncSession, email: str) -> Account | None:
    return await session.scalar(select(Account).where(Account.email == email))


async def get_by_number(session: AsyncSession, account_number: str) -> Account | None:
    return await session.scalar(
        select(Account).where(Account.account_number == account_number))


async def number_exists(session: AsyncSession, account_number: str) -> bool:
    return await session.scalar(
        select(Account.id).where(Account.account_number == account_number)) is not None
