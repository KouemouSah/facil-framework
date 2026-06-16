"""Identity service — registration (mint a unique NIU) + login-identifier resolution.

Uniqueness of the account_number is guaranteed by the DB UNIQUE constraint; the
service mints a random candidate and retries on the (rare) collision. Login-
identifier resolution accepts an email OR a NIU, validating the NIU's check digit
BEFORE any DB hit (reject typos early; the auth layer returns a uniform error so
this is not an enumeration oracle).
"""

from __future__ import annotations

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.identity import number as num
from app.identity import repository as repo
from app.identity.models import Account
from app.identity.number import NumberStrategy

_MAX_MINT_RETRIES = 8


class IdentityError(Exception):
    pass


class EmailTaken(IdentityError):
    pass


class NumberExhausted(IdentityError):
    pass


async def register(session: AsyncSession, *, email: str | None = None,
                   organization_id: str | None = None,
                   display_name: str | None = None,
                   strategy: NumberStrategy | None = None) -> Account:
    strategy = strategy or NumberStrategy()
    if email is not None and await repo.get_by_email(session, email):
        raise EmailTaken(f"email '{email}' already registered")

    for _ in range(_MAX_MINT_RETRIES):
        candidate = num.mint(strategy)
        if await repo.number_exists(session, candidate):
            continue
        account = Account(account_number=candidate, email=email,
                          organization_id=organization_id, display_name=display_name)
        session.add(account)
        try:
            await session.flush()
        except IntegrityError:  # concurrent mint of the same number — retry
            await session.rollback()
            continue
        return account
    raise NumberExhausted("could not mint a unique account_number; widen body_length")


async def resolve_identifier(session: AsyncSession, identifier: str,
                            strategy: NumberStrategy | None = None) -> Account | None:
    """Resolve a login identifier (email OR NIU) to an account, or None."""
    strategy = strategy or NumberStrategy()
    if not identifier:
        return None
    if "@" in identifier:
        return await repo.get_by_email(session, identifier.strip().lower())
    normalized = num.normalize(identifier)
    if not num.validate(normalized, strategy):  # reject typos before DB hit
        return None
    return await repo.get_by_number(session, normalized)
