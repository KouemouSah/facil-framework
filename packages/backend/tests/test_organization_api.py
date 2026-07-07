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

    # Register the non-module core tables (account/credential/rbac) so the FK
    # from account_role -> account resolves during create_all, even when this
    # file runs in isolation (import_module_models only covers app.modules.*).
    from app.identity import models as _account_models  # noqa: F401
    from app.auth import models as _cred_models  # noqa: F401
    from app.rbac import models as _rbac_models  # noqa: F401
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
    assert org_id in [o["id"] for o in lst.json()["items"]]


@pytest.mark.asyncio
async def test_list_pagination(org_client):
    for i in range(3):
        await _mk_org(org_client, f"pg{i}")
    page1 = await org_client.get(f"{BASE}/?sort=code&limit=2", headers=AUTH)
    assert page1.status_code == 200
    b1 = page1.json()
    assert len(b1["items"]) == 2 and b1["count"] >= 3 and b1["next_cursor"]
    page2 = await org_client.get(
        f"{BASE}/?sort=code&limit=2&cursor={b1['next_cursor']}", headers=AUTH)
    assert len(page2.json()["items"]) >= 1
    # limit is clamped (max 200) — a huge limit doesn't error
    assert (await org_client.get(f"{BASE}/?limit=9999", headers=AUTH)).status_code == 200
    # unknown sort field -> 422 (whitelist)
    assert (await org_client.get(f"{BASE}/?sort=evil", headers=AUTH)).status_code == 422


@pytest.mark.asyncio
async def test_org_export_csv(org_client):
    await _mk_org(org_client, "expco")
    r = await org_client.get(f"{BASE}/export", headers=AUTH)
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/csv")
    lines = r.text.strip().splitlines()
    assert lines[0].startswith("id,code,legal_name")
    assert any("expco" in ln for ln in lines[1:])


@pytest.mark.asyncio
async def test_org_optimistic_concurrency(org_client):
    org_id = await _mk_org(org_client, "concur")
    g = (await org_client.get(f"{BASE}/{org_id}", headers=AUTH)).json()
    etag = g["etag"]
    assert etag
    ok = await org_client.put(f"{BASE}/{org_id}", headers={**AUTH, "If-Match": etag},
                              json={"legal_name": "Renamed"})
    assert ok.status_code == 200
    # etag rotates (refetch to read it).
    new_etag = (await org_client.get(f"{BASE}/{org_id}", headers=AUTH)).json()["etag"]
    assert new_etag != etag
    # stale etag -> 409
    assert (await org_client.put(f"{BASE}/{org_id}", headers={**AUTH, "If-Match": etag},
                                 json={"legal_name": "Race"})).status_code == 409


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


# --- Company links (F.3): parent / party / hq_address / currency ----------
# A second client mounts organization + reference + party so the linked master
# data is created through the real APIs and the FK validation is exercised
# end-to-end (not just stubbed).

RBASE = "/api/v1/modules/reference"
PBASE = "/api/v1/modules/party"


@pytest_asyncio.fixture
async def links_client(tmp_path, monkeypatch):
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
    db = Database(f"sqlite+aiosqlite:///{tmp_path/'links.db'}")
    async with db.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    application = FastAPI()
    application.state.db = db
    load_modules(application, enabled=["organization", "reference", "party"])
    transport = ASGITransport(app=application)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    await db.dispose()
    cfg._settings = None


async def _mk_currency(ac, code="USD"):
    r = await ac.post(f"{RBASE}/currencies", headers=AUTH, json={"code": code, "name": code})
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def _mk_party(ac, name="Acme Legal Identity"):
    r = await ac.post(f"{PBASE}/parties", headers=AUTH, json={"name": name})
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def _mk_address(ac, city="Malabo"):
    r = await ac.post(f"{PBASE}/addresses", headers=AUTH, json={"city": city})
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def _etag(ac, org_id):
    return (await ac.get(f"{BASE}/{org_id}", headers=AUTH)).json()["etag"]


@pytest.mark.asyncio
async def test_company_links_roundtrip(links_client):
    ac = links_client
    cur = await _mk_currency(ac, "EUR")
    party = await _mk_party(ac)
    addr = await _mk_address(ac)
    parent = await _mk_org(ac, "group")
    r = await ac.post(f"{BASE}/", headers=AUTH, json={
        "code": "subco", "legal_name": "Sub Co", "parent_id": parent,
        "party_id": party, "hq_address_id": addr, "currency_id": cur})
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["parent_id"] == parent and body["party_id"] == party
    assert body["hq_address_id"] == addr and body["currency_id"] == cur
    got = (await ac.get(f"{BASE}/{body['id']}", headers=AUTH)).json()
    assert got["currency_id"] == cur and got["hq_address_id"] == addr


@pytest.mark.asyncio
async def test_update_links(links_client):
    ac = links_client
    cur = await _mk_currency(ac, "GBP")
    org = await _mk_org(ac, "updlink")
    r = await ac.put(f"{BASE}/{org}", headers={**AUTH, "If-Match": await _etag(ac, org)},
                     json={"currency_id": cur})
    assert r.status_code == 200 and r.json()["currency_id"] == cur


@pytest.mark.asyncio
async def test_self_parent_422(links_client):
    ac = links_client
    org = await _mk_org(ac, "selfp")
    r = await ac.put(f"{BASE}/{org}", headers={**AUTH, "If-Match": await _etag(ac, org)},
                     json={"parent_id": org})
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_parent_cycle_422(links_client):
    ac = links_client
    a = await _mk_org(ac, "ca")
    b = await _mk_org(ac, "cb")
    # a's parent = b (ok)
    ok = await ac.put(f"{BASE}/{a}", headers={**AUTH, "If-Match": await _etag(ac, a)},
                      json={"parent_id": b})
    assert ok.status_code == 200, ok.text
    # b's parent = a would close the loop -> 422
    r = await ac.put(f"{BASE}/{b}", headers={**AUTH, "If-Match": await _etag(ac, b)},
                     json={"parent_id": a})
    assert r.status_code == 422


@pytest.mark.asyncio
@pytest.mark.parametrize("field", ["party_id", "hq_address_id", "currency_id", "parent_id"])
async def test_bad_reference_422(links_client, field):
    missing = "00000000-0000-0000-0000-000000000000"
    r = await links_client.post(f"{BASE}/", headers=AUTH, json={
        "code": f"bad.{field}", "legal_name": "Bad Ref", field: missing})
    assert r.status_code == 422, r.text


@pytest.mark.asyncio
async def test_blank_fk_clears_link(links_client):
    """A cleared picker sends "" — it must detach (NULL), not 422 on a "" FK."""
    ac = links_client
    cur = await _mk_currency(ac, "JPY")
    org = await _mk_org(ac, "clearlink")
    set_r = await ac.put(f"{BASE}/{org}", headers={**AUTH, "If-Match": await _etag(ac, org)},
                         json={"currency_id": cur})
    assert set_r.status_code == 200 and set_r.json()["currency_id"] == cur
    clr = await ac.put(f"{BASE}/{org}", headers={**AUTH, "If-Match": await _etag(ac, org)},
                       json={"currency_id": ""})
    assert clr.status_code == 200, clr.text
    assert clr.json()["currency_id"] is None


@pytest.mark.asyncio
async def test_labels_batch_resolves_many_in_one_call(org_client):
    a = await _mk_org(org_client, code="alpha")
    b = await _mk_org(org_client, code="beta")
    r = await org_client.get(f"{BASE}/labels?ids={a},{b}", headers=AUTH)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body == {a: "Acme Corp", b: "Acme Corp"}


@pytest.mark.asyncio
async def test_labels_empty_and_unknown(org_client):
    a = await _mk_org(org_client, code="gamma")
    # No ids → empty map.
    assert (await org_client.get(f"{BASE}/labels", headers=AUTH)).json() == {}
    assert (await org_client.get(f"{BASE}/labels?ids=", headers=AUTH)).json() == {}
    # Unknown ids are simply absent (graceful degradation, no 404).
    r = await org_client.get(f"{BASE}/labels?ids={a},does-not-exist", headers=AUTH)
    assert r.status_code == 200
    assert r.json() == {a: "Acme Corp"}


@pytest.mark.asyncio
async def test_labels_requires_auth(org_client):
    assert (await org_client.get(f"{BASE}/labels?ids=x")).status_code == 401


@pytest.mark.asyncio
async def test_labels_over_cap_truncates_observably(org_client, monkeypatch, caplog):
    # Over-cap requests still degrade gracefully (partial map, id fallback) but the
    # truncation is LOGGED — not silent (CLAUDE.md: no silent cap). Patch the cap
    # low instead of seeding 500 orgs.
    import app.modules.organization.api as org_api
    monkeypatch.setattr(org_api, "_LABELS_CAP", 1)
    a = await _mk_org(org_client, code="delta")
    b = await _mk_org(org_client, code="epsilon")
    with caplog.at_level("WARNING"):
        r = await org_client.get(f"{BASE}/labels?ids={a},{b}", headers=AUTH)
    assert r.status_code == 200
    assert len(r.json()) == 1  # 2 requested, capped to 1 (deterministic, sorted)
    assert any("truncated to cap" in rec.message for rec in caplog.records)
