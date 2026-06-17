"""Admin accounts API — list / create / status for accounts (agents & users).

Core always-on router (mounted like rbac). Scope-aware (D4.3): reads are
filtered to the caller's visible organizations; create/status are enforced
against the target account's organization. The bootstrap admin-token break-glass
authorizes everything (and sees all tenants). Account creation reuses the auth
registration service (account + password credential), so an admin-created agent
can log in immediately. Suspending/deactivating an account revokes its sessions
at once (instant kill), matching the SCIM deprovision guarantee.
"""

from __future__ import annotations

import re

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_session
from app.auth import audit
from app.auth import sessions as sessions_mod
from app.auth import service as auth_service
from app.identity import repository as repo
from app.identity import service as identity_service
from app.identity.models import ACCOUNT_STATUSES
from app.rbac import repository as rbac_repo
from app.rbac import service as rbac_service
from app.security.auth_dep import require_auth
from app.security.permission_dep import enforce, visible_orgs

router = APIRouter(prefix="/api/v1/admin/accounts", tags=["admin-accounts"])

_BLOCKING = ("suspended", "deactivated")
# Pragmatic email shape check (no email-validator dep, consistent with the rest
# of the codebase which keeps `email` a plain str). Real verification is the
# email-verification flow (D4.5), not this syntactic gate.
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class AccountIn(BaseModel):
    email: str = Field(max_length=255)
    password: str
    display_name: str | None = Field(default=None, max_length=255)
    organization_id: str | None = None

    @field_validator("email")
    @classmethod
    def _check_email(cls, v: str) -> str:
        v = v.strip()
        if not _EMAIL_RE.match(v):
            raise ValueError("invalid email address")
        return v


class StatusIn(BaseModel):
    status: str


class BulkStatusIn(BaseModel):
    account_ids: list[str]
    status: str


@router.get("")
async def list_accounts(q: str | None = None, organization_id: str | None = None,
                        limit: int = 50, offset: int = 0,
                        principal: dict = Depends(require_auth),
                        session: AsyncSession = Depends(get_session)) -> list[dict]:
    # Scope filter: None = global/break-glass (all), otherwise restrict to the
    # caller's visible orgs (empty set -> no rows).
    visible = await visible_orgs(session, principal, "account.read")
    limit = min(max(limit, 1), 200)
    offset = max(offset, 0)
    accounts = await repo.list_accounts(
        session, q=q, organization_id=organization_id, org_ids=visible,
        limit=limit, offset=offset)
    return [a.as_dict() for a in accounts]


@router.post("", status_code=201)
async def create_account(body: AccountIn,
                         principal: dict = Depends(require_auth),
                         session: AsyncSession = Depends(get_session)) -> dict:
    # Body-scoped: authorize against the target organization (None = global).
    scope = await rbac_repo.resolve_scope(
        session, {"organization_id": body.organization_id})
    await enforce(session, principal, "account.manage", scope)
    try:
        account = await auth_service.register(
            session, password=body.password, email=body.email,
            display_name=body.display_name, organization_id=body.organization_id)
    except auth_service.WeakPassword as e:
        raise HTTPException(422, str(e)) from e
    except identity_service.EmailTaken as e:
        raise HTTPException(409, str(e)) from e
    await audit.record(session, audit.ACCOUNT_CREATED, account_id=account.id,
                       detail={"by": principal.get("sub"), "email": account.email})
    await session.commit()
    return account.as_dict()


@router.patch("/{account_id}/status")
async def set_status(account_id: str, body: StatusIn,
                     principal: dict = Depends(require_auth),
                     session: AsyncSession = Depends(get_session)) -> dict:
    if body.status not in ACCOUNT_STATUSES:
        raise HTTPException(422, f"status must be one of {ACCOUNT_STATUSES}")
    existing = await repo.get_account(session, account_id)
    if existing is None:
        raise HTTPException(404, f"account '{account_id}' not found")
    # Authorize against the account's own organization scope.
    scope = await rbac_repo.resolve_scope(
        session, {"organization_id": existing.organization_id})
    await enforce(session, principal, "account.manage", scope)
    try:
        account = await identity_service.set_status(session, account_id, body.status)
    except identity_service.InvalidStatus as e:
        raise HTTPException(422, str(e)) from e
    except identity_service.NotFound as e:
        raise HTTPException(404, str(e)) from e
    # Instant kill: a suspended/deactivated account must lose its sessions now.
    if body.status in _BLOCKING:
        await sessions_mod.revoke_all(session, account_id)
    await audit.record(session, audit.ACCOUNT_STATUS_CHANGED, account_id=account_id,
                       detail={"by": principal.get("sub"), "status": body.status})
    await session.commit()
    return account.as_dict()


@router.post("/bulk-status")
async def bulk_set_status(body: BulkStatusIn,
                          principal: dict = Depends(require_auth),
                          session: AsyncSession = Depends(get_session)) -> dict:
    """Set the status of many accounts. Scope-enforced PER account (they may span
    organizations) — out-of-scope or missing ids are reported, not 403-ing the
    whole call. Blocking statuses revoke each account's sessions. Bounded at 500."""
    if body.status not in ACCOUNT_STATUSES:
        raise HTTPException(422, f"status must be one of {ACCOUNT_STATUSES}")
    ids = list(dict.fromkeys(body.account_ids))
    if not ids:
        raise HTTPException(422, "account_ids must not be empty")
    if len(ids) > 500:
        raise HTTPException(422, "too many accounts (max 500)")
    bg = bool(principal.get("break_glass"))
    updated: list[str] = []
    errors: list[dict] = []
    for aid in ids:
        acc = await repo.get_account(session, aid)
        if acc is None:
            errors.append({"account_id": aid, "detail": "not found"})
            continue
        scope = await rbac_repo.resolve_scope(
            session, {"organization_id": acc.organization_id})
        if not bg and not await rbac_service.has_permission(
                session, principal["sub"], "account.manage", scope):
            errors.append({"account_id": aid, "detail": "forbidden"})
            continue
        await identity_service.set_status(session, aid, body.status)
        if body.status in _BLOCKING:
            await sessions_mod.revoke_all(session, aid)
        await audit.record(session, audit.ACCOUNT_STATUS_CHANGED, account_id=aid,
                           detail={"by": principal.get("sub"), "status": body.status,
                                   "bulk": True})
        updated.append(aid)
    await session.commit()
    return {"updated": updated, "errors": errors}


@router.get("/statuses")
async def list_statuses(principal: dict = Depends(require_auth)) -> dict:
    """The status vocabulary, for admin UIs."""
    return {"statuses": list(ACCOUNT_STATUSES)}
