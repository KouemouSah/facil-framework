"""Identity service — registration, gated NIU issuance, login-identifier resolution.

Lifecycle (validated 2026-06-16):
- register(): creates the Account (email + basics). Under policy `immediate` it
  also issues the NIU now; under `on_verified_document` it stays
  status=pending_identity with account_number=NULL until issue_number() is called
  by the identity-verification step (D4.1b) once a document is verified.
- issue_number(): mints the NIU for a category (prefix) + records subject_type +
  flips status to active. IMMUTABLE — never re-issues an existing NIU. Uniqueness
  is the DB UNIQUE constraint; a per-attempt SAVEPOINT lets us retry the (rare)
  random collision without losing the account.
- resolve_identifier(): email OR NIU; the NIU's check digit is verified before any
  DB hit; a uniform None (no oracle) is returned for typos / unknowns.
"""

from __future__ import annotations

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.identity import number as num
from app.identity import repository as repo
from app.identity.models import ACCOUNT_STATUSES, Account
from app.identity.number import NumberStrategy

ISSUANCE_POLICIES = ("immediate", "on_verified_document")
_MAX_MINT_RETRIES = 8


class IdentityError(Exception):
    pass


class EmailTaken(IdentityError):
    pass


class AlreadyIssued(IdentityError):
    pass


class NumberExhausted(IdentityError):
    pass


class NotFound(IdentityError):
    pass


class InvalidStatus(IdentityError):
    pass


async def register(session: AsyncSession, *, email: str | None = None,
                   organization_id: str | None = None,
                   display_name: str | None = None,
                   policy: str = "immediate", category: str | None = None,
                   strategy: NumberStrategy | None = None) -> Account:
    if policy not in ISSUANCE_POLICIES:
        raise IdentityError(f"policy must be one of {ISSUANCE_POLICIES}")
    if email is not None:
        email = email.strip().lower()
        if await repo.get_by_email(session, email):
            raise EmailTaken(f"email '{email}' already registered")
    account = Account(email=email, organization_id=organization_id,
                      display_name=display_name, status="pending_identity")
    session.add(account)
    await session.flush()
    if policy == "immediate":
        await issue_number(session, account, category=category, strategy=strategy)
    return account


async def set_status(session: AsyncSession, account_id: str, status: str) -> Account:
    """Admin status transition. `is_active` mirrors status so existing auth
    checks (which gate on is_active) honour suspension/deactivation."""
    if status not in ACCOUNT_STATUSES:
        raise InvalidStatus(f"status must be one of {ACCOUNT_STATUSES}")
    account = await repo.get_account(session, account_id)
    if account is None:
        raise NotFound(f"account '{account_id}' not found")
    account.status = status
    account.is_active = status in ("pending_identity", "active")
    await session.flush()
    return account


async def issue_number(session: AsyncSession, account: Account, *,
                      category: str | None = None, subject_type: str | None = None,
                      strategy: NumberStrategy | None = None) -> Account:
    """Mint + assign the NIU (once). Called at register (immediate) or by the
    identity-verification step (gated). Idempotent guard: never re-issues."""
    if account.account_number:
        raise AlreadyIssued(f"account {account.id} already has a NIU")
    strategy = strategy or NumberStrategy()
    for _ in range(_MAX_MINT_RETRIES):
        candidate = num.mint(strategy, category=category)
        if await repo.number_exists(session, candidate):
            continue
        account.account_number = candidate
        account.subject_type = subject_type or category
        account.status = "active"
        try:
            async with session.begin_nested():  # SAVEPOINT — survives a collision
                await session.flush()
            return account
        except IntegrityError:
            continue  # concurrent mint of the same number — try another
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
