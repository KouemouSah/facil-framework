"""Phase 1 — organization/location models: insert, constraints, path subtree."""

from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.modules.location.models import Site
from app.modules.organization.models import OrgUnit, Organization


async def _org(db, code="acme", **kw):
    async with db.session_factory() as s:
        org = Organization(code=code, legal_name=kw.pop("legal_name", "Acme Corp"), **kw)
        s.add(org)
        await s.commit()
        return org.id


@pytest.mark.asyncio
async def test_create_org_unit_site_roundtrip(client):
    _, db = client
    org_id = await _org(db)
    async with db.session_factory() as s:
        unit = OrgUnit(organization_id=org_id, code="HQ", name="Headquarters",
                       unit_type="division", path=f"/{org_id}/", depth=1)
        s.add(unit)
        await s.flush()
        site = Site(organization_id=org_id, org_unit_id=unit.id, code="HQ-1",
                    name="HQ Main Office", site_type="headquarters", city="Malabo",
                    country_code="GQ", is_primary=True,
                    operating_hours={"monday": {"open": "08:00", "close": "16:00"}},
                    meta={"floor": 3})
        s.add(site)
        await s.commit()
        site_id = site.id

    async with db.session_factory() as s:
        got = (await s.scalars(select(Site).where(Site.id == site_id))).one()
        d = got.as_dict()
        assert d["organization_id"] == org_id and d["org_unit_id"] is not None
        assert d["is_primary"] is True and d["country_code"] == "GQ"
        assert d["operating_hours"]["monday"]["open"] == "08:00"
        assert d["metadata"] == {"floor": 3}


@pytest.mark.asyncio
async def test_organization_code_unique(client):
    _, db = client
    await _org(db, code="dup")
    with pytest.raises(IntegrityError):
        await _org(db, code="dup")


@pytest.mark.asyncio
async def test_org_unit_code_unique_per_org(client):
    _, db = client
    org_a = await _org(db, code="a")
    org_b = await _org(db, code="b")
    async with db.session_factory() as s:
        s.add(OrgUnit(organization_id=org_a, code="DEPT", name="Dept A"))
        s.add(OrgUnit(organization_id=org_b, code="DEPT", name="Dept B"))  # same code, other org
        await s.commit()  # OK: unique is per (organization_id, code)
    async with db.session_factory() as s:
        s.add(OrgUnit(organization_id=org_a, code="DEPT", name="Dup"))
        with pytest.raises(IntegrityError):
            await s.commit()


@pytest.mark.asyncio
async def test_subtree_query_via_path(client):
    _, db = client
    org_id = await _org(db, code="tree")
    async with db.session_factory() as s:
        root = OrgUnit(organization_id=org_id, code="ROOT", name="Root", path="", depth=0)
        s.add(root)
        await s.flush()
        root.path = f"/{root.id}/"
        child = OrgUnit(organization_id=org_id, code="CH", name="Child",
                        parent_id=root.id, path=f"/{root.id}/", depth=1)
        s.add(child)
        await s.flush()
        child.path = f"/{root.id}/{child.id}/"
        s.add(OrgUnit(organization_id=org_id, code="GC", name="Grandchild",
                      parent_id=child.id, path=f"/{root.id}/{child.id}/", depth=2))
        await s.commit()
        prefix = f"/{root.id}/"

    async with db.session_factory() as s:
        subtree = (await s.scalars(
            select(OrgUnit).where(OrgUnit.path.like(f"{prefix}%")))).all()
        assert {u.code for u in subtree} == {"ROOT", "CH", "GC"}


@pytest.mark.asyncio
async def test_site_branch_hierarchy(client):
    _, db = client
    org_id = await _org(db, code="branches")
    async with db.session_factory() as s:
        main = Site(organization_id=org_id, code="MAIN", name="Main", is_primary=True)
        s.add(main)
        await s.flush()
        s.add(Site(organization_id=org_id, code="BR1", name="Branch 1",
                   parent_site_id=main.id))
        s.add(Site(organization_id=org_id, code="BR2", name="Branch 2",
                   parent_site_id=main.id))
        await s.commit()
        main_id = main.id

    async with db.session_factory() as s:
        branches = (await s.scalars(
            select(Site).where(Site.parent_site_id == main_id))).all()
        assert {b.code for b in branches} == {"BR1", "BR2"}
