"""location module API — Site CRUD, refs, branches, single-primary, cycle guard."""

from __future__ import annotations

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

AUTH = {"X-Admin-Token": "test-token"}
ORG = "/api/v1/modules/organization"
LOC = "/api/v1/modules/location"


@pytest_asyncio.fixture
async def loc_client(tmp_path, monkeypatch):
    monkeypatch.setenv("ADMIN_TOKEN", "test-token")
    import app.config as cfg
    cfg._settings = None
    from app.core.module_registry import import_module_models, load_modules
    from app.db.base import Base
    from app.db.engine import Database

    import_module_models()
    db = Database(f"sqlite+aiosqlite:///{tmp_path/'t.db'}")
    async with db.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    application = FastAPI()
    application.state.db = db
    load_modules(application, enabled=["organization", "location"])
    transport = ASGITransport(app=application)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    await db.dispose()
    cfg._settings = None


async def _org(ac, code="acme"):
    r = await ac.post(f"{ORG}/", headers=AUTH, json={"code": code, "legal_name": code})
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def _site(ac, org_id, code, **kw):
    body = {"organization_id": org_id, "code": code, "name": code, **kw}
    return await ac.post(f"{LOC}/sites", headers=AUTH, json=body)


@pytest.mark.asyncio
async def test_site_export_csv(loc_client):
    org_id = await _org(loc_client)
    await _site(loc_client, org_id, "EXP")
    r = await loc_client.get(f"{LOC}/sites/export?organization_id={org_id}", headers=AUTH)
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/csv")
    lines = r.text.strip().splitlines()
    assert lines[0].startswith("id,code,name,site_type")
    assert any("EXP" in ln for ln in lines[1:])


@pytest.mark.asyncio
async def test_site_optimistic_concurrency(loc_client):
    org_id = await _org(loc_client)
    site_id = (await _site(loc_client, org_id, "CONC")).json()["id"]
    g = (await loc_client.get(f"{LOC}/sites/{site_id}", headers=AUTH)).json()
    etag = g["etag"]
    assert etag
    ok = await loc_client.put(f"{LOC}/sites/{site_id}", headers={**AUTH, "If-Match": etag},
                              json={"name": "Renamed"})
    assert ok.status_code == 200
    new_etag = (await loc_client.get(f"{LOC}/sites/{site_id}", headers=AUTH)).json()["etag"]
    assert new_etag != etag
    assert (await loc_client.put(f"{LOC}/sites/{site_id}", headers={**AUTH, "If-Match": etag},
                                 json={"name": "Race"})).status_code == 409


@pytest.mark.asyncio
async def test_requires_token(loc_client):
    assert (await loc_client.get(f"{LOC}/sites")).status_code == 401


@pytest.mark.asyncio
async def test_create_get_site(loc_client):
    org_id = await _org(loc_client)
    r = await _site(loc_client, org_id, "HQ", site_type="headquarters", city="Malabo",
                    country_code="gq", is_primary=True)
    assert r.status_code == 201, r.text
    site = r.json()
    assert site["country_code"] == "GQ" and site["is_primary"] is True
    got = await loc_client.get(f"{LOC}/sites/{site['id']}", headers=AUTH)
    assert got.json()["code"] == "HQ"


@pytest.mark.asyncio
async def test_org_not_found_404(loc_client):
    r = await _site(loc_client, "ghost-org", "X")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_duplicate_code_409(loc_client):
    org_id = await _org(loc_client)
    await _site(loc_client, org_id, "DUP")
    assert (await _site(loc_client, org_id, "DUP")).status_code == 409


@pytest.mark.asyncio
async def test_invalid_unit_ref_422(loc_client):
    org_a = await _org(loc_client, "a")
    org_b = await _org(loc_client, "b")
    # unit belongs to org_b
    u = await loc_client.post(f"{ORG}/{org_b}/units", headers=AUTH,
                              json={"code": "U", "name": "U"})
    r = await _site(loc_client, org_a, "S", org_unit_id=u.json()["id"])
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_branch_hierarchy_and_filter(loc_client):
    org_id = await _org(loc_client)
    main = (await _site(loc_client, org_id, "MAIN")).json()
    br = await _site(loc_client, org_id, "BR", parent_site_id=main["id"])
    assert br.status_code == 201
    branches = (await loc_client.get(f"{LOC}/sites/{main['id']}/branches",
                                     headers=AUTH)).json()
    assert {b["code"] for b in branches} == {"BR"}
    filtered = (await loc_client.get(
        f"{LOC}/sites?parent_site_id={main['id']}", headers=AUTH)).json()
    assert {b["code"] for b in filtered["items"]} == {"BR"} and filtered["total"] == 1


@pytest.mark.asyncio
async def test_single_primary_per_org(loc_client):
    org_id = await _org(loc_client)
    a = (await _site(loc_client, org_id, "A", is_primary=True)).json()
    await _site(loc_client, org_id, "B", is_primary=True)
    a_now = (await loc_client.get(f"{LOC}/sites/{a['id']}", headers=AUTH)).json()
    assert a_now["is_primary"] is False  # B became primary, A cleared


@pytest.mark.asyncio
async def test_branch_cycle_guard_422(loc_client):
    org_id = await _org(loc_client)
    main = (await _site(loc_client, org_id, "MAIN")).json()
    br = (await _site(loc_client, org_id, "BR", parent_site_id=main["id"])).json()
    # making MAIN a child of its own branch BR must fail
    r = await loc_client.put(f"{LOC}/sites/{main['id']}", headers=AUTH,
                             json={"parent_site_id": br["id"]})
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_update_and_delete_site(loc_client):
    org_id = await _org(loc_client)
    site = (await _site(loc_client, org_id, "S")).json()
    upd = await loc_client.put(f"{LOC}/sites/{site['id']}", headers=AUTH,
                               json={"name": "Renamed", "phone": "+240 222"})
    assert upd.status_code == 200 and upd.json()["name"] == "Renamed"
    assert (await loc_client.delete(f"{LOC}/sites/{site['id']}",
                                    headers=AUTH)).status_code == 200
    assert (await loc_client.get(f"{LOC}/sites/{site['id']}",
                                 headers=AUTH)).status_code == 404
