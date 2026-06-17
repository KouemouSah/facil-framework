"""Admin accounts API — list / create / status for accounts (agents & users).

Core always-on router (mounted like rbac). Reads require `account.read`, writes
require `account.manage` — both satisfied by the bootstrap admin-token break-glass
so the first operator can create agents before any grant exists. Account creation
reuses the auth registration service (account + password credential), so an
admin-created agent can log in immediately. Status changes mirror `is_active`,
which the auth/login path already enforces (suspension takes effect at once).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_session
from app.auth import service as auth_service
from app.identity import repository as repo
from app.identity import service as identity_service
from app.identity.models import ACCOUNT_STATUSES
from app.security.permission_dep import require_permission

router = APIRouter(prefix="/api/v1/admin/accounts", tags=["admin-accounts"])

_READ = Depends(require_permission("account.read"))
_MANAGE = Depends(require_permission("account.manage"))


class AccountIn(BaseModel):
    email: str
    password: str
    display_name: str | None = None
    organization_id: str | None = None


class StatusIn(BaseModel):
    status: str


@router.get("", dependencies=[_READ])
async def list_accounts(q: str | None = None, organization_id: str | None = None,
                        limit: int = 50, offset: int = 0,
                        session: AsyncSession = Depends(get_session)) -> list[dict]:
    limit = min(max(limit, 1), 200)
    offset = max(offset, 0)
    accounts = await repo.list_accounts(
        session, q=q, organization_id=organization_id, limit=limit, offset=offset)
    return [a.as_dict() for a in accounts]


@router.post("", status_code=201, dependencies=[_MANAGE])
async def create_account(body: AccountIn,
                         session: AsyncSession = Depends(get_session)) -> dict:
    try:
        account = await auth_service.register(
            session, password=body.password, email=body.email,
            display_name=body.display_name, organization_id=body.organization_id)
    except auth_service.WeakPassword as e:
        raise HTTPException(422, str(e)) from e
    except identity_service.EmailTaken as e:
        raise HTTPException(409, str(e)) from e
    await session.commit()
    return account.as_dict()


@router.patch("/{account_id}/status", dependencies=[_MANAGE])
async def set_status(account_id: str, body: StatusIn,
                     session: AsyncSession = Depends(get_session)) -> dict:
    try:
        account = await identity_service.set_status(session, account_id, body.status)
    except identity_service.InvalidStatus as e:
        raise HTTPException(422, str(e)) from e
    except identity_service.NotFound as e:
        raise HTTPException(404, str(e)) from e
    await session.commit()
    return account.as_dict()


@router.get("/statuses", dependencies=[_READ])
async def list_statuses() -> dict:
    """The status vocabulary, for admin UIs."""
    return {"statuses": list(ACCOUNT_STATUSES)}
