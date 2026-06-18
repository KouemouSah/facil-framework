"""location module — site ↔ reusable address link (ERP-grade F.3c).

Self-contained fixture mounting organization + location + party + reference so
the site/address link is exercised end-to-end through the real APIs (the shared
`client` fixture does not mount the MODULES_ENABLED-gated org/location routers).
The bootstrap admin token authorizes management.
"""

from __future__ import annotations

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

AUTH = {"X-Admin-Token": "test-token"}
ORG = "/api/v1/modules/organization"
LOC = "/api/v1/modules/location"
PARTY = "/api/v1/modules/party"


@pytest_asyncio.fixture
async def loc_client(tmp_path, monkeypatch):
    monkeypatch.setenv("ADMIN_TOKEN", "test-token")
    import app.config as cfg
    cfg._settings = None
    from app.core.module_registry import import_module_models, load_modules
    from app.db.base import Base
    from app.db.engine import Database

    from app.identity import models as _account_models  # noqa: F401
    from app.auth import models as _cred_models  # noqa: F401
    from app.rbac import models as _rbac_models  # noqa: F401
    import_module_models()
    db = Database(f"sqlite+aiosqlite:///{tmp_path/'loc.db'}")
    async with db.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    application = FastAPI()
    application.state.db = db
    load_modules(application, enabled=["organization", "location", "party", "reference"])
    transport = ASGITransport(app=application)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    await db.dispose()
    cfg._settings = None


async def _org(ac, code="acme"):
    r = await ac.post(f"{ORG}/", headers=AUTH, json={"code": code, "legal_name": "Acme"})
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def _address(ac, city="Malabo"):
    r = await ac.post(f"{PARTY}/addresses", headers=AUTH, json={"city": city})
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def _site_etag(ac, site_id):
    return (await ac.get(f"{LOC}/sites/{site_id}", headers=AUTH)).json()["etag"]


@pytest.mark.asyncio
async def test_site_address_roundtrip(loc_client):
    ac = loc_client
    org = await _org(ac, "rt")
    addr = await _address(ac)
    r = await ac.post(f"{LOC}/sites", headers=AUTH, json={
        "organization_id": org, "code": "hq", "name": "HQ", "address_id": addr})
    assert r.status_code == 201, r.text
    assert r.json()["address_id"] == addr
    got = (await ac.get(f"{LOC}/sites/{r.json()['id']}", headers=AUTH)).json()
    assert got["address_id"] == addr


@pytest.mark.asyncio
async def test_site_bad_address_422(loc_client):
    ac = loc_client
    org = await _org(ac, "bad")
    r = await ac.post(f"{LOC}/sites", headers=AUTH, json={
        "organization_id": org, "code": "hq", "name": "HQ",
        "address_id": "00000000-0000-0000-0000-000000000000"})
    assert r.status_code == 422, r.text


@pytest.mark.asyncio
async def test_site_update_and_clear_address(loc_client):
    ac = loc_client
    org = await _org(ac, "upd")
    addr = await _address(ac)
    site = (await ac.post(f"{LOC}/sites", headers=AUTH, json={
        "organization_id": org, "code": "hq", "name": "HQ"})).json()
    set_r = await ac.put(f"{LOC}/sites/{site['id']}",
                         headers={**AUTH, "If-Match": await _site_etag(ac, site["id"])},
                         json={"address_id": addr})
    assert set_r.status_code == 200 and set_r.json()["address_id"] == addr
    # A cleared picker ("") detaches to NULL (not a 422 on an empty FK).
    clr = await ac.put(f"{LOC}/sites/{site['id']}",
                       headers={**AUTH, "If-Match": await _site_etag(ac, site["id"])},
                       json={"address_id": ""})
    assert clr.status_code == 200, clr.text
    assert clr.json()["address_id"] is None
