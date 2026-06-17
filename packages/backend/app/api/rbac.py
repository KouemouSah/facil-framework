"""RBAC management API — roles, grants, account assignments, reseed (D4.3).

Always-on core router (mounted in main.py, like the auth router). Reads require
`rbac.read`, writes require `rbac.manage` — both satisfied by the bootstrap
admin-token break-glass so the first operator can set up roles before any grant
exists. Role management is a global action (scope = empty), so a non-global
rbac.manage grant does not authorize it.
"""

from __future__ import annotations

import datetime as _dt

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_session
from app.auth import audit
from app.rbac import repository as repo
from app.rbac import seed as seed_mod
from app.rbac import service
from app.security.permission_dep import require_permission

router = APIRouter(prefix="/api/v1/rbac", tags=["rbac"])

_READ = Depends(require_permission("rbac.read"))
_MANAGE = Depends(require_permission("rbac.manage"))


class RoleIn(BaseModel):
    code: str
    name: str
    description: str | None = None
    organization_id: str | None = None
    is_system: bool = False
    parent_id: str | None = None
    grants: list[str] | None = None


class GrantsIn(BaseModel):
    codes: list[str]


class AssignIn(BaseModel):
    role_id: str
    organization_id: str | None = None
    org_unit_id: str | None = None
    site_id: str | None = None
    expires_at: _dt.datetime | None = None


class BulkAssignIn(BaseModel):
    account_ids: list[str]
    role_id: str
    organization_id: str | None = None
    org_unit_id: str | None = None
    site_id: str | None = None
    expires_at: _dt.datetime | None = None


# --- Catalog + roles -----------------------------------------------------

@router.get("/permissions", dependencies=[_READ])
async def list_permissions(session: AsyncSession = Depends(get_session)) -> list[dict]:
    return [p.as_dict() for p in await repo.list_permissions(session)]


@router.get("/roles", dependencies=[_READ])
async def list_roles(organization_id: str | None = None,
                     session: AsyncSession = Depends(get_session)) -> list[dict]:
    roles = await repo.list_roles(session, organization_id=organization_id)
    return [r.as_dict() for r in roles]


@router.post("/roles", status_code=201)
async def create_role(body: RoleIn, principal: dict = _MANAGE,
                      session: AsyncSession = Depends(get_session)) -> dict:
    try:
        role = await service.create_role(
            session, code=body.code, name=body.name, description=body.description,
            organization_id=body.organization_id,
            is_system=False,  # only the profile seeder mints system roles
            parent_id=body.parent_id, grants=body.grants,
            created_by=principal.get("sub"))
    except service.RoleExists as e:
        raise HTTPException(409, str(e)) from e
    except service.InvalidGrant as e:
        raise HTTPException(422, str(e)) from e
    await session.commit()
    return role.as_dict()


@router.get("/roles/{role_id}/permissions", dependencies=[_READ])
async def get_role_permissions(role_id: str,
                               session: AsyncSession = Depends(get_session)) -> dict:
    """A role's directly-granted permission codes (read companion to PUT)."""
    if await repo.get_role(session, role_id) is None:
        raise HTTPException(404, f"role '{role_id}' not found")
    codes = await repo.role_codes(session, [role_id])
    return {"role_id": role_id, "codes": sorted(codes)}


@router.put("/roles/{role_id}/permissions", dependencies=[_MANAGE])
async def set_role_permissions(role_id: str, body: GrantsIn,
                               session: AsyncSession = Depends(get_session)) -> dict:
    try:
        role = await service.set_grants(session, role_id, body.codes)
    except service.RoleNotFound as e:
        raise HTTPException(404, str(e)) from e
    except service.SystemRoleProtected as e:
        raise HTTPException(409, str(e)) from e
    except service.InvalidGrant as e:
        raise HTTPException(422, str(e)) from e
    await session.commit()
    return {"role_id": role.id, "codes": body.codes}


@router.delete("/roles/{role_id}", dependencies=[_MANAGE])
async def delete_role(role_id: str,
                      session: AsyncSession = Depends(get_session)) -> dict:
    try:
        deleted = await service.delete_role(session, role_id)
    except service.SystemRoleProtected as e:
        raise HTTPException(409, str(e)) from e
    if not deleted:
        raise HTTPException(404, f"role '{role_id}' not found")
    await session.commit()
    return {"deleted": role_id}


# --- Account assignments -------------------------------------------------

@router.get("/accounts/{account_id}/roles", dependencies=[_READ])
async def list_assignments(account_id: str,
                           session: AsyncSession = Depends(get_session)) -> list[dict]:
    return [a.as_dict() for a in await repo.list_account_roles(session, account_id)]


@router.post("/accounts/{account_id}/roles", status_code=201)
async def assign_role(account_id: str, body: AssignIn, principal: dict = _MANAGE,
                      session: AsyncSession = Depends(get_session)) -> dict:
    try:
        assignment = await service.assign_role(
            session, account_id=account_id, role_id=body.role_id,
            organization_id=body.organization_id, org_unit_id=body.org_unit_id,
            site_id=body.site_id, expires_at=body.expires_at,
            created_by=principal.get("sub"))
    except service.RoleNotFound as e:
        raise HTTPException(404, str(e)) from e
    await audit.record(session, audit.ROLE_ASSIGNED, account_id=account_id,
                       detail={"by": principal.get("sub"), "role_id": body.role_id,
                               "organization_id": body.organization_id})
    await session.commit()
    return assignment.as_dict()


@router.post("/accounts/bulk-roles", status_code=201)
async def bulk_assign_role(body: BulkAssignIn, principal: dict = _MANAGE,
                           session: AsyncSession = Depends(get_session)) -> dict:
    """Assign one role to many accounts at the same scope (one transaction).
    The role must exist (else the whole call fails); per-account failures are
    reported. Bounded at 500 to stay a single, predictable unit of work."""
    ids = list(dict.fromkeys(body.account_ids))  # de-dupe, keep order
    if not ids:
        raise HTTPException(422, "account_ids must not be empty")
    if len(ids) > 500:
        raise HTTPException(422, "too many accounts (max 500)")
    assigned: list[str] = []
    errors: list[dict] = []
    for aid in ids:
        try:
            await service.assign_role(
                session, account_id=aid, role_id=body.role_id,
                organization_id=body.organization_id, org_unit_id=body.org_unit_id,
                site_id=body.site_id, expires_at=body.expires_at,
                created_by=principal.get("sub"))
        except service.RoleNotFound as e:
            raise HTTPException(404, str(e)) from e  # role missing -> abort all
        except Exception as e:  # noqa: BLE001 (per-item failure, keep going)
            errors.append({"account_id": aid, "detail": str(e)})
            continue
        await audit.record(session, audit.ROLE_ASSIGNED, account_id=aid,
                           detail={"by": principal.get("sub"), "role_id": body.role_id,
                                   "organization_id": body.organization_id, "bulk": True})
        assigned.append(aid)
    await session.commit()
    return {"assigned": assigned, "errors": errors}


@router.delete("/accounts/{account_id}/roles/{assignment_id}")
async def revoke_role(account_id: str, assignment_id: str, principal: dict = _MANAGE,
                      session: AsyncSession = Depends(get_session)) -> dict:
    if not await repo.delete_account_role(session, assignment_id):
        raise HTTPException(404, f"assignment '{assignment_id}' not found")
    await audit.record(session, audit.ROLE_REVOKED, account_id=account_id,
                       detail={"by": principal.get("sub"), "assignment_id": assignment_id})
    await session.commit()
    return {"deleted": assignment_id}


# --- Reseed --------------------------------------------------------------

@router.post("/admin/reseed", dependencies=[_MANAGE])
async def reseed(request: Request, profile: str | None = None,
                 session: AsyncSession = Depends(get_session)) -> dict:
    active = profile or request.app.state.resolver.resolve("profile", "empty")
    result = await seed_mod.seed_roles(session, profile=active)
    await session.commit()
    return result
