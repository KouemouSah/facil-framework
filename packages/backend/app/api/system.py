"""System / first-run API (D5.3) — install status for the web installer.

Public, unauthenticated: the web app calls this on boot to decide whether to show
the first-run installer (no super-admin yet) or the normal login. "Installed" is
DERIVED (a super-admin account exists), not a spoofable flag.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_session
from app.rbac.models import AccountRole, RolePermission

router = APIRouter(prefix="/api/v1/system", tags=["system"])


@router.get("/install-status")
async def install_status(request: Request,
                         session: AsyncSession = Depends(get_session)) -> dict:
    # Installed once at least one account holds a role that grants `*` (the
    # super-admin created by the installer). Derived from RBAC, not a flag.
    star_roles = select(RolePermission.role_id).where(
        RolePermission.permission_code == "*")
    count = await session.scalar(
        select(func.count()).select_from(AccountRole).where(
            AccountRole.role_id.in_(star_roles)))
    resolver = request.app.state.resolver
    return {
        "installed": bool(count),
        "app_name": resolver.resolve("branding.app_name", "Facil"),
        "default_locale": resolver.resolve("branding.default_locale", "en"),
    }
