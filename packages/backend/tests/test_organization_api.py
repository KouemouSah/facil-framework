"""organization module API — CRUD, hierarchy, reparent + cycle guard (token-gated)."""

from __future__ import annotations

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

AUTH = {"X-Admin-Token": "test-token"}
BASE = "/api/v1/modules/organization"


@pytest_asyncio.fixture
async def org_client(tmp_path, monkeypatch):
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
    load_modules(application, enabled=["organization"])
    transport = ASGITransport(app=application)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    await db.dispose()
    cfg._settings = None


async def _mk_org(ac, code="acme"):
    r = await ac.post(f"{BASE}/", headers=AUTH,
                      json={"code": code, "legal_name": "Acme Corp"})
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def _mk_unit(ac, org_id, code, parent_id=None):
    r = await ac.post(f"{BASE}/{org_id}/units", headers=AUTH,
                      json={"code": code, "name": code, "parent_id": parent_id})
    assert r.status_code == 201, r.text
    return r.json()


@pytest.mark.asyncio
async def test_requires_token(org_client):
    assert (await org_client.get(f"{BASE}/")).status_code == 401


@pytest.mark.asyncio
async def test_create_get_list_org(org_client):
    org_id = await _mk_org(org_client)
    got = await org_client.get(f"{BASE}/{org_id}", headers=AUTH)
    assert got.json()["code"] == "acme" and got.json()["legal_name"] == "Acme Corp"
    lst = await org_client.get(f"{BASE}/", headers=AUTH)
    assert org_id in [o["id"] for o in lst.json()]


@pytest.mark.asyncio
async def test_list_pagination(org_client):
    for i in range(3):
        await _mk_org(org_client, f"pg{i}")
    page1 = await org_client.get(f"{BASE}/?limit=2&offset=0", headers=AUTH)
    assert page1.status_code == 200 and len(page1.json()) == 2
    page2 = await org_client.get(f"{BASE}/?limit=2&offset=2", headers=AUTH)
    assert len(page2.json()) >= 1
    # limit is clamped (max 200) — a huge limit doesn't error
    assert (await org_client.get(f"{BASE}/?limit=9999", headers=AUTH)).status_code == 200


@pytest.mark.asyncio
async def test_duplicate_org_code_409(org_client):
    await _mk_org(org_client, "dup")
    r = await org_client.post(f"{BASE}/", headers=AUTH,
                              json={"code": "dup", "legal_name": "Other"})
    assert r.status_code == 409


@pytest.mark.asyncio
async def test_update_org(org_client):
    org_id = await _mk_org(org_client)
    r = await org_client.put(f"{BASE}/{org_id}", headers=AUTH,
                             json={"display_name": "Acme!", "country_code": "GQ"})
    assert r.status_code == 200 and r.json()["display_name"] == "Acme!"


@pytest.mark.asyncio
async def test_unit_hierarchy_paths(org_client):
    org_id = await _mk_org(org_client)
    root = await _mk_unit(org_client, org_id, "ROOT")
    child = await _mk_unit(org_client, org_id, "CH", parent_id=root["id"])
    assert root["path"] == f"/{root['id']}/" and root["depth"] == 0
    assert child["path"] == f"/{root['id']}/{child['id']}/" and child["depth"] == 1
    units = (await org_client.get(f"{BASE}/{org_id}/units", headers=AUTH)).json()
    assert {u["code"] for u in units} == {"ROOT", "CH"}


@pytest.mark.asyncio
async def test_unit_duplicate_code_409(org_client):
    org_id = await _mk_org(org_client)
    await _mk_unit(org_client, org_id, "DEPT")
    r = await org_client.post(f"{BASE}/{org_id}/units", headers=AUTH,
                              json={"code": "DEPT", "name": "x"})
    assert r.status_code == 409


@pytest.mark.asyncio
async def test_invalid_parent_422(org_client):
    org_a = await _mk_org(org_client, "a")
    org_b = await _mk_org(org_client, "b")
    unit_b = await _mk_unit(org_client, org_b, "UB")
    r = await org_client.post(f"{BASE}/{org_a}/units", headers=AUTH,
                              json={"code": "X", "name": "x", "parent_id": unit_b["id"]})
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_reparent_rewrites_subtree(org_client):
    org_id = await _mk_org(org_client)
    root = await _mk_unit(org_client, org_id, "ROOT")
    child = await _mk_unit(org_client, org_id, "CH", parent_id=root["id"])
    gc = await _mk_unit(org_client, org_id, "GC", parent_id=child["id"])
    # move CH (and its subtree GC) to be a root
    r = await org_client.put(f"{BASE}/units/{child['id']}", headers=AUTH,
                             json={"parent_id": None})
    assert r.status_code == 200 and r.json()["depth"] == 0
    gc_now = (await org_client.get(f"{BASE}/units/{gc['id']}", headers=AUTH)).json()
    assert gc_now["path"] == f"/{child['id']}/{gc['id']}/" and gc_now["depth"] == 1


@pytest.mark.asyncio
async def test_reparent_cycle_guard_422(org_client):
    org_id = await _mk_org(org_client)
    root = await _mk_unit(org_client, org_id, "ROOT")
    child = await _mk_unit(org_client, org_id, "CH", parent_id=root["id"])
    # moving ROOT under its own descendant CH must fail
    r = await org_client.put(f"{BASE}/units/{root['id']}", headers=AUTH,
                             json={"parent_id": child["id"]})
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_delete_unit_and_org(org_client):
    org_id = await _mk_org(org_client)
    unit = await _mk_unit(org_client, org_id, "U")
    assert (await org_client.delete(f"{BASE}/units/{unit['id']}",
                                    headers=AUTH)).status_code == 200
    assert (await org_client.delete(f"{BASE}/{org_id}",
                                    headers=AUTH)).status_code == 200
    assert (await org_client.get(f"{BASE}/{org_id}", headers=AUTH)).status_code == 404
