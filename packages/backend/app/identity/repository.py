"""Data access for accounts (identity)."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.identity.models import Account


async def get_account(session: AsyncSession, account_id: str) -> Account | None:
    return await session.get(Account, account_id)


async def get_by_email(session: AsyncSession, email: str) -> Account | None:
    return await session.scalar(select(Account).where(Account.email == email))


async def get_by_number(session: AsyncSession, account_number: str) -> Account | None:
    return await session.scalar(
        select(Account).where(Account.account_number == account_number))


async def number_exists(session: AsyncSession, account_number: str) -> bool:
    return await session.scalar(
        select(Account.id).where(Account.account_number == account_number)) is not None
