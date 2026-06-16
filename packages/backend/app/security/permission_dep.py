"""require_permission — scope-aware RBAC enforcement dependency (D4.3).

`require_permission(perm)` is a FastAPI dependency factory: it authenticates
(JWT or admin-token break-glass via require_auth), resolves the request's scope
from the path/query params, and authorizes `perm` at that scope — fail-closed.

The bootstrap admin token (`break_glass`) bypasses RBAC: it is the migration
bridge that lets the first operator create orgs/accounts and assign roles before
any grant exists. `enforce()` is the in-handler variant for body-scoped routes
(e.g. create-site, where the org comes from the request body, not the path).
"""

from __future__ import annotations

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_session
from app.rbac import repository as repo
from app.rbac import service
from app.rbac.scope import Scope, raw_scope_ids
from app.security.auth_dep import require_auth


def require_permission(perm: str):
    async def dep(request: Request, principal: dict = Depends(require_auth),
                  session: AsyncSession = Depends(get_session)) -> dict:
        if principal.get("break_glass"):
            return principal
        scope = await repo.resolve_scope(session, raw_scope_ids(request))
        if not await service.has_permission(session, principal["sub"], perm, scope):
            raise HTTPException(status.HTTP_403_FORBIDDEN,
                                f"permission denied: {perm}")
        return principal
    return dep


async def enforce(session: AsyncSession, principal: dict, perm: str,
                  scope: Scope) -> None:
    """In-handler check for body-scoped routes. Raises 403 unless authorized."""
    if principal.get("break_glass"):
        return
    if not await service.has_permission(session, principal["sub"], perm, scope):
        raise HTTPException(status.HTTP_403_FORBIDDEN, f"permission denied: {perm}")
