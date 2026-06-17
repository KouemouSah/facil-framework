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
from app.api.list_query import keyset_page, resolve_sort
from app.auth.models import FederatedIdentity
from app.config import get_settings
from app.identity.models import Account
from app.security.auth_dep import require_auth
from app.security.permission_dep import require_permission, visible_orgs

_FED_SORT = {"provider": FederatedIdentity.provider,
             "subject": FederatedIdentity.subject,
             "created_at": FederatedIdentity.created_at}

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
async def identities(q: str | None = None, sort: str = "-created_at",
                     limit: int = 50, cursor: str | None = None,
                     principal: dict = Depends(require_auth),
                     session: AsyncSession = Depends(get_session)) -> dict:
    # Scope filter (tenant isolation): restrict to the caller's visible orgs
    # (None = global/break-glass). Keyset pagination (scale 1M+); contract
    # {items,next_cursor,count,capped}. The join to Account is for filtering
    # (scope + search) only — keyset runs over FederatedIdentity (its whitelisted
    # sort cols + id tiebreaker); the page's accounts are then batch-loaded by id
    # for display, keeping the generic keyset_page (scalar) helper unchanged.
    visible = await visible_orgs(session, principal, "account.read")
    base = select(FederatedIdentity).join(
        Account, Account.id == FederatedIdentity.account_id)
    if visible is not None:
        base = base.where(Account.organization_id.in_(visible))
    if q:
        like = f"%{q}%"
        base = base.where(or_(
            FederatedIdentity.subject.ilike(like),
            FederatedIdentity.provider.ilike(like),
            Account.email.ilike(like)))
    sort_col, sort_desc = resolve_sort(sort, allowed=_FED_SORT, default="-created_at")
    fids, next_cursor, count, capped = await keyset_page(
        session, base, sort_col=sort_col, sort_desc=sort_desc,
        cursor=cursor, limit=limit)
    accounts = {a.id: a for a in (await session.scalars(
        select(Account).where(
            Account.id.in_([f.account_id for f in fids])))).all()}
    items = []
    for fi in fids:
        acc = accounts.get(fi.account_id)
        items.append({
            "id": fi.id, "provider": fi.provider, "subject": fi.subject,
            "account_id": fi.account_id,
            "email": acc.email if acc else None,
            "display_name": acc.display_name if acc else None,
            "status": acc.status if acc else None,
            "linked_at": fi.created_at.isoformat() if fi.created_at else None,
        })
    return {"items": items, "next_cursor": next_cursor,
            "count": count, "capped": capped}
