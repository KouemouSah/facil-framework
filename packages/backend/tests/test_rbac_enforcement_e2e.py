"""End-to-end RBAC enforcement (D4.3) — real JWT principals, no break-glass.

Bootstrap admin (token) seeds roles, creates orgs, registers users and assigns
scoped roles. Then each user authenticates with a real JWT and we assert the
scope boundary: a member of org A reads A but not B; a scoped admin writes only
in their org; a read-only member cannot write or perform a global action.
"""

from __future__ import annotations

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

ADMIN = {"X-Admin-Token": "test-token"}
ORG = "/api/v1/modules/organization"
LOC = "/api/v1/modules/location"


@pytest_asyncio.fixture
async def e2e(tmp_path, monkeypatch):
    monkeypatch.setenv("ADMIN_TOKEN", "test-token")
    monkeypatch.setenv("JWT_SECRET", "test-jwt-secret-0123456789abcdef0123456789")
    import app.config as cfg
    cfg._settings = None

    from app.api import admin_accounts as accounts_api
    from app.api import admin_settings as settings_api
    from app.api import auth as auth_api
    from app.api import rbac as rbac_api
    from app.models import setting as _set  # noqa: F401 (register settings table)
    from app.config_store.resolver import ConfigResolver
    from app.core.module_registry import import_module_models, load_modules
    from app.core.providers.registry import default_registry
    from app.db.base import Base
    from app.db.engine import Database
    from app.identity import models as _a  # noqa: F401
    from app.auth import models as _c  # noqa: F401
    from app.rbac import models as _r  # noqa: F401

    import_module_models()
    db = Database(f"sqlite+aiosqlite:///{tmp_path/'e2e.db'}")
    async with db.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    application = FastAPI()
    application.state.db = db
    application.state.resolver = ConfigResolver(
        defaults={"branding.app_name": "Facil", "profile": "empty"}, env={})
    application.state.registry = default_registry()
    application.state.auth = application.state.registry.build(
        "auth", "native", {"issuer": "facil"})
    application.include_router(auth_api.router)
    application.include_router(rbac_api.router)
    application.include_router(accounts_api.router)
    application.include_router(settings_api.router)
    load_modules(application, enabled=["organization", "location"])

    transport = ASGITransport(app=application)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac, db
    await db.dispose()
    cfg._settings = None


async def _bearer(ac, email, password="Sup3rStr0ng!pw"):
    await ac.post("/api/v1/auth/register", json={"password": password, "email": email})
    r = await ac.post("/api/v1/auth/login", json={"identifier": email, "password": password})
    assert r.status_code == 200, r.text
    acc = r.json()["account"]
    return {"Authorization": f"Bearer {r.json()['access']}"}, acc["id"]


async def _role_id(ac, code):
    roles = (await ac.get("/api/v1/rbac/roles", headers=ADMIN)).json()["items"]
    return next(r["id"] for r in roles if r["code"] == code)


async def _mk_org(ac, code):
    r = await ac.post(f"{ORG}/", headers=ADMIN, json={"code": code, "legal_name": code})
    assert r.status_code == 201, r.text
    return r.json()["id"]


@pytest_asyncio.fixture
async def seeded(e2e):
    ac, db = e2e
    assert (await ac.post("/api/v1/rbac/admin/reseed?profile=empty",
                          headers=ADMIN)).status_code == 200
    org_a = await _mk_org(ac, "org-a")
    org_b = await _mk_org(ac, "org-b")
    return ac, org_a, org_b


@pytest.mark.asyncio
async def test_member_is_tenant_isolated(seeded):
    ac, org_a, org_b = seeded
    member = await _role_id(ac, "member")
    hdr, acc_id = await _bearer(ac, "alice@x.com")
    await ac.post(f"/api/v1/rbac/accounts/{acc_id}/roles", headers=ADMIN,
                  json={"role_id": member, "organization_id": org_a})

    assert (await ac.get(f"{ORG}/{org_a}", headers=hdr)).status_code == 200
    assert (await ac.get(f"{ORG}/{org_b}", headers=hdr)).status_code == 403


@pytest.mark.asyncio
async def test_member_cannot_write_or_act_globally(seeded):
    ac, org_a, org_b = seeded
    member = await _role_id(ac, "member")
    hdr, acc_id = await _bearer(ac, "bob@x.com")
    await ac.post(f"/api/v1/rbac/accounts/{acc_id}/roles", headers=ADMIN,
                  json={"role_id": member, "organization_id": org_a})

    # read-only -> cannot update its own org
    assert (await ac.put(f"{ORG}/{org_a}", headers=hdr,
                         json={"legal_name": "x"})).status_code == 403
    # org-scoped -> the global list is SCOPE-FILTERED (sees only org A, not B)
    listed = await ac.get(f"{ORG}/", headers=hdr)
    assert listed.status_code == 200
    ids = {o["id"] for o in listed.json()["items"]}
    assert org_a in ids and org_b not in ids
    # org-scoped -> cannot create an org (global write)
    assert (await ac.post(f"{ORG}/", headers=hdr,
                          json={"code": "z", "legal_name": "z"})).status_code == 403


@pytest.mark.asyncio
async def test_scoped_admin_writes_only_in_its_org(seeded):
    ac, org_a, org_b = seeded
    admin = await _role_id(ac, "admin")
    hdr, acc_id = await _bearer(ac, "carol@x.com")
    await ac.post(f"/api/v1/rbac/accounts/{acc_id}/roles", headers=ADMIN,
                  json={"role_id": admin, "organization_id": org_b})

    # admin scoped to org B can update B...
    assert (await ac.put(f"{ORG}/{org_b}", headers=hdr,
                         json={"legal_name": "B2"})).status_code == 200
    # ...but not A
    assert (await ac.put(f"{ORG}/{org_a}", headers=hdr,
                         json={"legal_name": "A2"})).status_code == 403


@pytest.mark.asyncio
async def test_unauthenticated_is_401(seeded):
    ac, org_a, _ = seeded
    assert (await ac.get(f"{ORG}/{org_a}")).status_code == 401


@pytest.mark.asyncio
async def test_site_create_is_body_scoped(seeded):
    ac, org_a, org_b = seeded
    admin = await _role_id(ac, "admin")
    hdr, acc_id = await _bearer(ac, "dave@x.com")
    await ac.post(f"/api/v1/rbac/accounts/{acc_id}/roles", headers=ADMIN,
                  json={"role_id": admin, "organization_id": org_a})

    # can create a site in org A (body-scoped enforcement)
    ok = await ac.post(f"{LOC}/sites", headers=hdr,
                       json={"organization_id": org_a, "code": "s1", "name": "Site 1"})
    assert ok.status_code == 201, ok.text
    # cannot create a site in org B
    ko = await ac.post(f"{LOC}/sites", headers=hdr,
                       json={"organization_id": org_b, "code": "s2", "name": "Site 2"})
    assert ko.status_code == 403, ko.text


@pytest.mark.asyncio
async def test_site_list_is_scope_filtered(seeded):
    ac, org_a, org_b = seeded
    admin = await _role_id(ac, "admin")
    # seed a site in each org via break-glass
    await ac.post(f"{LOC}/sites", headers=ADMIN,
                  json={"organization_id": org_a, "code": "sa", "name": "SA"})
    await ac.post(f"{LOC}/sites", headers=ADMIN,
                  json={"organization_id": org_b, "code": "sb", "name": "SB"})
    # a user scoped admin on org A sees only org A's sites in the global list
    hdr, acc_id = await _bearer(ac, "erin@x.com")
    await ac.post(f"/api/v1/rbac/accounts/{acc_id}/roles", headers=ADMIN,
                  json={"role_id": admin, "organization_id": org_a})
    listed = await ac.get(f"{LOC}/sites", headers=hdr)
    assert listed.status_code == 200
    orgs = {s["organization_id"] for s in listed.json()["items"]}
    assert orgs == {org_a}


ACC = "/api/v1/admin/accounts"


@pytest.mark.asyncio
async def test_admin_accounts_tenant_isolation(seeded):
    ac, org_a, org_b = seeded
    admin = await _role_id(ac, "admin")
    # Seed an account in each org via break-glass.
    a = (await ac.post(ACC, headers=ADMIN, json={
        "email": "a@org-a.com", "password": "Sup3rStr0ng!pw",
        "organization_id": org_a})).json()
    b = (await ac.post(ACC, headers=ADMIN, json={
        "email": "b@org-b.com", "password": "Sup3rStr0ng!pw",
        "organization_id": org_b})).json()

    # A user with admin scoped to org A.
    hdr, acc_id = await _bearer(ac, "frank@x.com")
    await ac.post(f"/api/v1/rbac/accounts/{acc_id}/roles", headers=ADMIN,
                  json={"role_id": admin, "organization_id": org_a})

    # List is scope-filtered: sees org A's account, not org B's. {items,total}.
    body = (await ac.get(ACC, headers=hdr)).json()
    emails = {r["email"] for r in body["items"]}
    assert "a@org-a.com" in emails
    assert "b@org-b.com" not in emails

    # Status change is scope-enforced: allowed in org A, 403 in org B.
    assert (await ac.patch(f"{ACC}/{a['id']}/status", headers=hdr,
                           json={"status": "suspended"})).status_code == 200
    assert (await ac.patch(f"{ACC}/{b['id']}/status", headers=hdr,
                           json={"status": "suspended"})).status_code == 403


SET = "/api/v1/admin/settings"


@pytest.mark.asyncio
async def test_admin_settings_now_rbac_gated(seeded):
    """A2: settings moved from token-only to RBAC. A logged-in user without
    settings.manage is forbidden; break-glass still works."""
    ac, org_a, _ = seeded
    member = await _role_id(ac, "member")  # member lacks settings.*
    hdr, acc_id = await _bearer(ac, "grace@x.com")
    await ac.post(f"/api/v1/rbac/accounts/{acc_id}/roles", headers=ADMIN,
                  json={"role_id": member, "organization_id": org_a})

    # No settings grant -> read 403 and write 403.
    assert (await ac.get(f"{SET}/", headers=hdr)).status_code == 403
    assert (await ac.put(f"{SET}/branding.app_name", headers=hdr,
                         json={"value": "Hacked"})).status_code == 403
    # Break-glass still works (write + read).
    assert (await ac.put(f"{SET}/branding.app_name", headers=ADMIN,
                         json={"value": "Ok"})).status_code == 200


@pytest.mark.asyncio
async def test_me_permissions_reflects_grants(seeded):
    """A1: /me/permissions returns the union of granted codes (UI nav gating)."""
    ac, org_a, _ = seeded
    member = await _role_id(ac, "member")
    hdr, acc_id = await _bearer(ac, "heidi@x.com")
    # No roles yet -> empty.
    r0 = (await ac.get("/api/v1/auth/me/permissions", headers=hdr)).json()
    assert r0 == {"break_glass": False, "permissions": []}
    # Assign member (organization.read + location.read).
    await ac.post(f"/api/v1/rbac/accounts/{acc_id}/roles", headers=ADMIN,
                  json={"role_id": member, "organization_id": org_a})
    r1 = (await ac.get("/api/v1/auth/me/permissions", headers=hdr)).json()
    assert set(r1["permissions"]) == {"organization.read", "location.read"}
    # Break-glass holds everything.
    bg = (await ac.get("/api/v1/auth/me/permissions", headers=ADMIN)).json()
    assert bg == {"break_glass": True, "permissions": ["*"]}
