"""Admin federation/SCIM read view (D5.2) — RBAC-gated, read-only.

Surfaces external-identity state for operators WITHOUT exposing the SCIM bearer
token: the `/scim/v2` surface is gated by `SCIM_TOKEN` (for the IdP/IGA, not the
browser), so the admin UI reads this RBAC-gated companion instead.
- status: whether SCIM provisioning is enabled + the federation provider + a
  count of linked identities and the distinct IdPs seen.
- identities: local accounts linked to an external IdP subject (provider, subject).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_session
from app.auth.models import FederatedIdentity
from app.config import get_settings
from app.identity.models import Account
from app.security.auth_dep import require_auth
from app.security.permission_dep import require_permission, visible_orgs

router = APIRouter(prefix="/api/v1/admin/federation", tags=["admin-federation"])

_READ = Depends(require_permission("account.read"))


@router.get("/status", dependencies=[_READ])
async def status(session: AsyncSession = Depends(get_session)) -> dict:
    s = get_settings()
    total = await session.scalar(
        select(func.count()).select_from(FederatedIdentity)) or 0
    providers = list(
        (await session.scalars(select(FederatedIdentity.provider).distinct())).all())
    return {
        # `enabled` reflects only whether a token is configured — never the value.
        "scim": {"enabled": bool(s.scim_token), "provider": s.scim_provider},
        "federation": {"linked_identities": total, "providers": providers},
    }


@router.get("/identities")
async def identities(q: str | None = None, limit: int = 50, offset: int = 0,
                     principal: dict = Depends(require_auth),
                     session: AsyncSession = Depends(get_session)) -> list[dict]:
    # Scope filter (tenant isolation): restrict linked identities to the caller's
    # visible organizations (None = global/break-glass sees all).
    visible = await visible_orgs(session, principal, "account.read")
    limit = min(max(limit, 1), 200)
    offset = max(offset, 0)
    stmt = (select(FederatedIdentity, Account)
            .join(Account, Account.id == FederatedIdentity.account_id)
            .order_by(FederatedIdentity.created_at.desc())
            .limit(limit).offset(offset))
    if visible is not None:
        stmt = stmt.where(Account.organization_id.in_(visible))
    if q:
        like = f"%{q}%"
        stmt = stmt.where(or_(
            FederatedIdentity.subject.ilike(like),
            FederatedIdentity.provider.ilike(like),
            Account.email.ilike(like)))
    rows = (await session.execute(stmt)).all()
    return [{
        "id": fi.id, "provider": fi.provider, "subject": fi.subject,
        "account_id": fi.account_id, "email": acc.email,
        "display_name": acc.display_name, "status": acc.status,
        "linked_at": fi.created_at.isoformat() if fi.created_at else None,
    } for fi, acc in rows]
