"""RBAC service — authorization decisions + role/assignment management (D4.3).

`has_permission` is the heart: for an account, find any active, non-expired role
assignment whose effective permissions (role + inherited ancestors) match the
requested permission AND whose scope covers the requested scope. Fail-closed.

Scope coverage and the (pure) predicate live in scope.py; the org/unit/site path
lookups live in repository.py. Token break-glass is handled one layer up (in the
dependency), not here.
"""

from __future__ import annotations

import datetime as _dt

from sqlalchemy.ext.asyncio import AsyncSession

from app.rbac import repository as repo
from app.rbac.models import AccountRole, Role
from app.rbac.scope import Scope, covers

_MAX_INHERITANCE_DEPTH = 20


class RBACError(Exception):
    pass


class RoleNotFound(RBACError):
    pass


class RoleExists(RBACError):
    pass


class SystemRoleProtected(RBACError):
    """is_system roles are owned by the profile seeds — not editable/deletable via API."""


class InvalidGrant(RBACError):
    """A grant references a permission code that is not in the catalog."""


def _now() -> _dt.datetime:
    return _dt.datetime.now(tz=_dt.timezone.utc)


def _aware(dt: _dt.datetime | None) -> _dt.datetime | None:
    # SQLite returns naive datetimes; treat stored times as UTC for comparison.
    if dt is not None and dt.tzinfo is None:
        return dt.replace(tzinfo=_dt.timezone.utc)
    return dt


def match_permission(perm: str, granted: set[str]) -> bool:
    """A grant set authorizes `perm` if it holds the exact code, the global `*`,
    or the resource wildcard `resource.*`."""
    if "*" in granted or perm in granted:
        return True
    resource = perm.split(".", 1)[0]
    return f"{resource}.*" in granted


async def _ancestor_ids(session: AsyncSession, role: Role) -> list[str]:
    """Role id + its parent chain (cycle-guarded)."""
    ids: list[str] = [role.id]
    seen = {role.id}
    current = role
    for _ in range(_MAX_INHERITANCE_DEPTH):
        if not current.parent_id or current.parent_id in seen:
            break
        parent = await repo.get_role(session, current.parent_id)
        if parent is None:
            break
        ids.append(parent.id)
        seen.add(parent.id)
        current = parent
    return ids


def _expired(assignment: AccountRole) -> bool:
    exp = _aware(assignment.expires_at)
    return exp is not None and exp <= _now()


async def has_permission(session: AsyncSession, account_id: str, perm: str,
                         request: Scope) -> bool:
    assignments = await repo.active_account_roles(session, account_id)
    for ar in assignments:
        if _expired(ar):
            continue
        role = await repo.get_role(session, ar.role_id)
        if role is None or not role.is_active:
            continue
        codes = await repo.role_codes(session, await _ancestor_ids(session, role))
        if not match_permission(perm, codes):
            continue
        assign_scope = Scope(
            organization_id=ar.organization_id, org_unit_id=ar.org_unit_id,
            unit_path=await repo.unit_path(session, ar.org_unit_id),
            site_id=ar.site_id)
        if covers(assign_scope, request):
            return True
    return False


async def effective_permissions(session: AsyncSession, account_id: str) -> set[str]:
    """Union of permission codes granted to an account across its active,
    non-expired role assignments (scope-agnostic). For UI reflection only — the
    backend still enforces scope per request. May include wildcards (`*`,
    `<resource>.*`); the client matches them like the server does."""
    codes: set[str] = set()
    for ar in await repo.active_account_roles(session, account_id):
        if _expired(ar):
            continue
        role = await repo.get_role(session, ar.role_id)
        if role is None or not role.is_active:
            continue
        codes |= await repo.role_codes(session, await _ancestor_ids(session, role))
    return codes


async def visible_org_ids(session: AsyncSession, account_id: str,
                          perm: str) -> set[str] | None:
    """Org ids the account can exercise `perm` on, for scope-filtered listings.

    Returns None when a global grant applies (sees everything). A unit/site-scoped
    grant makes its parent organization visible (org-level granularity — finer
    unit/site list filtering is a later refinement)."""
    orgs: set[str] = set()
    for ar in await repo.active_account_roles(session, account_id):
        if _expired(ar):
            continue
        role = await repo.get_role(session, ar.role_id)
        if role is None or not role.is_active:
            continue
        codes = await repo.role_codes(session, await _ancestor_ids(session, role))
        if not match_permission(perm, codes):
            continue
        if ar.organization_id is None:
            return None  # global grant -> sees all
        orgs.add(ar.organization_id)
    return orgs


# --- Management ----------------------------------------------------------

async def validate_grants(session: AsyncSession, codes: list[str]) -> None:
    """Reject grants referencing unknown permission codes. Wildcards (`*`,
    `<resource>.*`) are always allowed (they are not catalog rows)."""
    known = await repo.permission_codes(session)
    unknown = [c for c in codes
               if c != "*" and not c.endswith(".*") and c not in known]
    if unknown:
        raise InvalidGrant(f"unknown permission code(s): {sorted(set(unknown))}")

async def create_role(session: AsyncSession, *, code: str, name: str,
                      description: str | None = None,
                      organization_id: str | None = None, is_system: bool = False,
                      parent_id: str | None = None,
                      grants: list[str] | None = None,
                      created_by: str | None = None) -> Role:
    if await repo.get_role_by_code(session, code, organization_id) is not None:
        raise RoleExists(f"role '{code}' already exists in this scope")
    if grants:
        await validate_grants(session, grants)
    role = Role(code=code, name=name, description=description,
                organization_id=organization_id, is_system=is_system,
                parent_id=parent_id, created_by=created_by, updated_by=created_by)
    session.add(role)
    await session.flush()
    if grants:
        await repo.set_role_codes(session, role.id, grants)
    return role


async def set_grants(session: AsyncSession, role_id: str, codes: list[str]) -> Role:
    role = await repo.get_role(session, role_id)
    if role is None:
        raise RoleNotFound(f"role '{role_id}' not found")
    if role.is_system:
        raise SystemRoleProtected(
            f"role '{role.code}' is a system role (managed by profile seeds)")
    await validate_grants(session, codes)
    await repo.set_role_codes(session, role_id, codes)
    return role


async def delete_role(session: AsyncSession, role_id: str) -> bool:
    role = await repo.get_role(session, role_id)
    if role is None:
        return False
    if role.is_system:
        raise SystemRoleProtected(
            f"role '{role.code}' is a system role (managed by profile seeds)")
    return await repo.delete_role(session, role_id)


async def assign_role(session: AsyncSession, *, account_id: str, role_id: str,
                      organization_id: str | None = None,
                      org_unit_id: str | None = None, site_id: str | None = None,
                      expires_at: _dt.datetime | None = None,
                      created_by: str | None = None) -> AccountRole:
    if await repo.get_role(session, role_id) is None:
        raise RoleNotFound(f"role '{role_id}' not found")
    assignment = AccountRole(
        account_id=account_id, role_id=role_id, organization_id=organization_id,
        org_unit_id=org_unit_id, site_id=site_id, expires_at=expires_at,
        created_by=created_by, updated_by=created_by)
    session.add(assignment)
    await session.flush()
    return assignment
