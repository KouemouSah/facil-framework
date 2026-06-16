"""Data access for RBAC (D4.3).

Also resolves request/assignment scope against the org -> unit -> site tables.
This couples RBAC to the organization/location module *models* — acceptable
because org/unit/site IS the scope hierarchy the framework enforces against, and
the tables always exist (module tables are unconditional; only routers gate).
"""

from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.location.models import Site
from app.modules.organization.models import OrgUnit
from app.rbac.models import AccountRole, Permission, Role, RolePermission
from app.rbac.scope import Scope


# --- Scope resolution ----------------------------------------------------

async def unit_path(session: AsyncSession, unit_id: str | None) -> str | None:
    if not unit_id:
        return None
    unit = await session.get(OrgUnit, unit_id)
    return unit.path if unit else None


async def resolve_scope(session: AsyncSession, raw: dict) -> Scope:
    """Turn raw scope ids (from the request) into a full Scope: derive the org
    from a unit/site and load the unit's materialized path for subtree checks."""
    org = raw.get("organization_id")
    unit = raw.get("org_unit_id")
    site_id = raw.get("site_id")
    path = None
    if site_id:
        site = await session.get(Site, site_id)
        if site is not None:
            org = org or site.organization_id
            unit = unit or site.org_unit_id
    if unit:
        u = await session.get(OrgUnit, unit)
        if u is not None:
            org = org or u.organization_id
            path = u.path
    return Scope(organization_id=org, org_unit_id=unit, unit_path=path, site_id=site_id)


# --- Roles ---------------------------------------------------------------

async def get_role(session: AsyncSession, role_id: str) -> Role | None:
    return await session.get(Role, role_id)


async def get_role_by_code(session: AsyncSession, code: str,
                           organization_id: str | None) -> Role | None:
    stmt = select(Role).where(Role.code == code)
    stmt = stmt.where(Role.organization_id.is_(None) if organization_id is None
                      else Role.organization_id == organization_id)
    return await session.scalar(stmt)


async def list_roles(session: AsyncSession,
                     organization_id: str | None = None) -> list[Role]:
    stmt = select(Role).order_by(Role.organization_id, Role.code)
    if organization_id is not None:
        stmt = stmt.where(Role.organization_id == organization_id)
    return list((await session.scalars(stmt)).all())


async def delete_role(session: AsyncSession, role_id: str) -> bool:
    res = await session.execute(delete(Role).where(Role.id == role_id))
    return res.rowcount > 0


# --- Role permissions ----------------------------------------------------

async def role_codes(session: AsyncSession, role_ids: list[str]) -> set[str]:
    """Granted permission codes across a set of roles (used with inheritance)."""
    if not role_ids:
        return set()
    rows = await session.scalars(
        select(RolePermission.permission_code).where(
            RolePermission.role_id.in_(role_ids)))
    return set(rows.all())


async def set_role_codes(session: AsyncSession, role_id: str,
                         codes: list[str]) -> None:
    """Replace a role's grants with `codes` (idempotent)."""
    await session.execute(
        delete(RolePermission).where(RolePermission.role_id == role_id))
    for code in dict.fromkeys(codes):  # de-dupe, keep order
        session.add(RolePermission(role_id=role_id, permission_code=code))
    await session.flush()


# --- Permission catalog --------------------------------------------------

async def upsert_permission(session: AsyncSession, code: str, module: str,
                            description: str | None) -> None:
    existing = await session.scalar(select(Permission).where(Permission.code == code))
    if existing is None:
        session.add(Permission(code=code, module=module, description=description))
    else:
        existing.module = module
        existing.description = description
    await session.flush()


async def list_permissions(session: AsyncSession) -> list[Permission]:
    return list((await session.scalars(
        select(Permission).order_by(Permission.module, Permission.code))).all())


async def permission_codes(session: AsyncSession) -> set[str]:
    return set((await session.scalars(select(Permission.code))).all())


# --- Account roles (assignments) -----------------------------------------

async def active_account_roles(session: AsyncSession,
                               account_id: str) -> list[AccountRole]:
    """All active assignments for an account (expiry filtered by the service)."""
    stmt = select(AccountRole).where(AccountRole.account_id == account_id,
                                     AccountRole.is_active.is_(True))
    return list((await session.scalars(stmt)).all())


async def list_account_roles(session: AsyncSession,
                             account_id: str) -> list[AccountRole]:
    return list((await session.scalars(
        select(AccountRole).where(AccountRole.account_id == account_id)
        .order_by(AccountRole.created_at))).all())


async def get_account_role(session: AsyncSession, assignment_id: str) -> AccountRole | None:
    return await session.get(AccountRole, assignment_id)


async def delete_account_role(session: AsyncSession, assignment_id: str) -> bool:
    res = await session.execute(
        delete(AccountRole).where(AccountRole.id == assignment_id))
    return res.rowcount > 0
