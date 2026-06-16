"""DB-backed tests for the RBAC seeder + authorization service (D4.3)."""

from __future__ import annotations

import datetime as _dt

import pytest

from app.identity.models import Account
from app.modules.organization.models import OrgUnit, Organization
from app.rbac import repository as repo
from app.rbac import seed, service
from app.rbac.scope import Scope


async def _account(s, email: str) -> Account:
    a = Account(email=email, status="active")
    s.add(a)
    await s.flush()
    return a


async def _org(s, code: str) -> Organization:
    o = Organization(code=code, legal_name=code)
    s.add(o)
    await s.flush()
    return o


@pytest.mark.asyncio
async def test_seed_is_idempotent(client):
    _, db = client
    async with db.session_factory() as s:
        await seed.seed_roles(s, "empty")
        await s.commit()
        await seed.seed_roles(s, "empty")
        await s.commit()
        codes = [r.code for r in await repo.list_roles(s)]
        assert codes.count("admin") == 1
        assert codes.count("member") == 1
        perms = {p.code for p in await repo.list_permissions(s)}
        assert {"organization.read", "location.read", "rbac.manage"} <= perms


@pytest.mark.asyncio
async def test_global_admin_covers_everything(client):
    _, db = client
    async with db.session_factory() as s:
        await seed.seed_roles(s, "empty")
        admin = await repo.get_role_by_code(s, "admin", None)
        acc = await _account(s, "admin@x.com")
        await service.assign_role(s, account_id=acc.id, role_id=admin.id)  # global
        await s.commit()
        assert await service.has_permission(
            s, acc.id, "organization.delete", Scope(organization_id="any"))
        assert await service.has_permission(s, acc.id, "location.write", Scope())


@pytest.mark.asyncio
async def test_org_scoped_member_is_tenant_isolated(client):
    _, db = client
    async with db.session_factory() as s:
        await seed.seed_roles(s, "empty")
        member = await repo.get_role_by_code(s, "member", None)
        org_a, org_b = await _org(s, "A"), await _org(s, "B")
        acc = await _account(s, "m@x.com")
        await service.assign_role(s, account_id=acc.id, role_id=member.id,
                                  organization_id=org_a.id)
        await s.commit()
        # reads own org, not the other tenant
        assert await service.has_permission(
            s, acc.id, "organization.read", Scope(organization_id=org_a.id))
        assert not await service.has_permission(
            s, acc.id, "organization.read", Scope(organization_id=org_b.id))
        # member is read-only
        assert not await service.has_permission(
            s, acc.id, "organization.write", Scope(organization_id=org_a.id))


@pytest.mark.asyncio
async def test_no_assignment_is_denied(client):
    _, db = client
    async with db.session_factory() as s:
        await seed.seed_roles(s, "empty")
        acc = await _account(s, "nobody@x.com")
        await s.commit()
        assert not await service.has_permission(
            s, acc.id, "organization.read", Scope(organization_id="A"))


@pytest.mark.asyncio
async def test_unit_grant_covers_subtree_only(client):
    _, db = client
    async with db.session_factory() as s:
        org = await _org(s, "ORG")
        root = OrgUnit(organization_id=org.id, code="root", name="root", path="/r/")
        s.add(root)
        await s.flush()
        root.path = f"/{root.id}/"
        child = OrgUnit(organization_id=org.id, code="child", name="child",
                        parent_id=root.id, path=f"/{root.id}/c/")
        s.add(child)
        await s.flush()
        child.path = f"/{root.id}/{child.id}/"
        sibling = OrgUnit(organization_id=org.id, code="sib", name="sib")
        s.add(sibling)
        await s.flush()
        sibling.path = f"/{sibling.id}/"
        role = await service.create_role(s, code="unit_mgr", name="Unit Mgr",
                                          grants=["organization.*"])
        acc = await _account(s, "u@x.com")
        await service.assign_role(s, account_id=acc.id, role_id=role.id,
                                  organization_id=org.id, org_unit_id=root.id)
        await s.commit()

        # request scopes (unit_path as the resolver would compute)
        in_child = Scope(organization_id=org.id, org_unit_id=child.id,
                         unit_path=child.path)
        in_sib = Scope(organization_id=org.id, org_unit_id=sibling.id,
                       unit_path=sibling.path)
        assert await service.has_permission(s, acc.id, "organization.write", in_child)
        assert not await service.has_permission(s, acc.id, "organization.write", in_sib)
        # org-level request is broader than a unit grant -> denied
        assert not await service.has_permission(
            s, acc.id, "organization.write", Scope(organization_id=org.id))


@pytest.mark.asyncio
async def test_role_inheritance(client):
    _, db = client
    async with db.session_factory() as s:
        parent = await service.create_role(s, code="base", name="Base",
                                            grants=["location.read"])
        childr = await service.create_role(s, code="ext", name="Ext",
                                            parent_id=parent.id,
                                            grants=["organization.read"])
        acc = await _account(s, "h@x.com")
        await service.assign_role(s, account_id=acc.id, role_id=childr.id)
        await s.commit()
        # inherits parent's location.read AND has its own organization.read
        assert await service.has_permission(s, acc.id, "location.read", Scope())
        assert await service.has_permission(s, acc.id, "organization.read", Scope())


@pytest.mark.asyncio
async def test_expired_assignment_is_ignored(client):
    _, db = client
    async with db.session_factory() as s:
        await seed.seed_roles(s, "empty")
        admin = await repo.get_role_by_code(s, "admin", None)
        acc = await _account(s, "exp@x.com")
        past = _dt.datetime.now(tz=_dt.timezone.utc) - _dt.timedelta(hours=1)
        await service.assign_role(s, account_id=acc.id, role_id=admin.id,
                                  expires_at=past)
        await s.commit()
        assert not await service.has_permission(
            s, acc.id, "organization.read", Scope())
