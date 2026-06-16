"""SCIM 2.0 service — map SCIM Users onto local accounts (D4.13)."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import sessions as sessions_mod
from app.auth.models import FederatedIdentity
from app.config import get_settings
from app.identity import repository as identity_repo
from app.identity.models import Account

USER_SCHEMA = "urn:ietf:params:scim:schemas:core:2.0:User"
LIST_SCHEMA = "urn:ietf:params:scim:api:messages:2.0:ListResponse"


class ScimError(Exception):
    def __init__(self, status: int, detail: str):
        self.status = status
        self.detail = detail


def _username(data: dict) -> str | None:
    u = (data.get("userName") or "").strip().lower()
    if u:
        return u
    for e in data.get("emails", []):
        if e.get("value"):
            return e["value"].strip().lower()
    return None


def _display_name(data: dict) -> str | None:
    name = data.get("name") or {}
    full = " ".join(x for x in (name.get("givenName"), name.get("familyName")) if x)
    return data.get("displayName") or full or None


def to_scim(acc: Account) -> dict:
    return {
        "schemas": [USER_SCHEMA],
        "id": acc.id,
        "userName": acc.email or acc.account_number or acc.id,
        "active": acc.status not in ("deactivated", "suspended") and acc.is_active,
        "emails": [{"value": acc.email, "primary": True}] if acc.email else [],
        "displayName": acc.display_name,
        "meta": {"resourceType": "User"},
    }


async def list_users(session: AsyncSession, *, username: str | None = None,
                     start: int = 1, count: int = 50) -> tuple[list[Account], int]:
    stmt = select(Account)
    if username:
        stmt = stmt.where(Account.email == username.strip().lower())
    rows = list((await session.scalars(stmt)).all())
    total = len(rows)
    page = rows[max(start - 1, 0): max(start - 1, 0) + max(count, 0)]
    return page, total


async def create_user(session: AsyncSession, data: dict) -> Account:
    username = _username(data)
    if not username:
        raise ScimError(400, "userName or an email is required")
    if await identity_repo.get_by_email(session, username):
        raise ScimError(409, f"user '{username}' already exists")
    active = data.get("active", True)
    acc = Account(email=username, display_name=_display_name(data),
                  subject_type="agent",
                  status="active" if active else "deactivated")
    session.add(acc)
    await session.flush()
    # Link the IdP identity so a later OIDC login resolves to THIS account.
    ext = data.get("externalId")
    if ext:
        session.add(FederatedIdentity(account_id=acc.id,
                                      provider=get_settings().scim_provider,
                                      subject=str(ext)))
        await session.flush()
    return acc


async def set_active(session: AsyncSession, account_id: str, active: bool) -> Account:
    acc = await identity_repo.get_account(session, account_id)
    if acc is None:
        raise ScimError(404, "user not found")
    acc.status = "active" if active else "deactivated"
    if not active:  # instant deprovision: kill all sessions now
        await sessions_mod.revoke_all(session, account_id)
    await session.flush()
    return acc


async def replace_user(session: AsyncSession, account_id: str, data: dict) -> Account:
    acc = await identity_repo.get_account(session, account_id)
    if acc is None:
        raise ScimError(404, "user not found")
    dn = _display_name(data)
    if dn is not None:
        acc.display_name = dn
    acc.status = "active" if data.get("active", True) else "deactivated"
    if acc.status == "deactivated":
        await sessions_mod.revoke_all(session, account_id)
    await session.flush()
    return acc
