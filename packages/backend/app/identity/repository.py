"""Data access for accounts (identity)."""

from __future__ import annotations

from sqlalchemy import Select, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.identity.models import Account


async def get_account(session: AsyncSession, account_id: str) -> Account | None:
    return await session.get(Account, account_id)


def accounts_select(*, q: str | None = None, organization_id: str | None = None,
                    org_ids: set[str] | None = None,
                    status: str | None = None) -> Select:
    """Base SELECT for account listing: substring search (email / account_number /
    display_name), optional org/status filters, and the RBAC scope filter. Returns
    the (unsorted, unpaginated) statement so the caller applies sort + pagination
    via `app.api.list_query` (one place owns sort/total).

    `org_ids` = scope: None = unrestricted (global/break-glass); a set restricts
    to those orgs (empty set -> no rows)."""
    stmt = select(Account)
    if org_ids is not None:
        stmt = stmt.where(Account.organization_id.in_(org_ids))
    if organization_id:
        stmt = stmt.where(Account.organization_id == organization_id)
    if status:
        stmt = stmt.where(Account.status == status)
    if q:
        like = f"%{q}%"
        stmt = stmt.where(or_(
            Account.email.ilike(like),
            Account.account_number.ilike(like),
            Account.display_name.ilike(like)))
    return stmt


async def get_by_email(session: AsyncSession, email: str) -> Account | None:
    return await session.scalar(select(Account).where(Account.email == email))


async def get_by_number(session: AsyncSession, account_number: str) -> Account | None:
    return await session.scalar(
        select(Account).where(Account.account_number == account_number))


async def number_exists(session: AsyncSession, account_number: str) -> bool:
    return await session.scalar(
        select(Account.id).where(Account.account_number == account_number)) is not None
