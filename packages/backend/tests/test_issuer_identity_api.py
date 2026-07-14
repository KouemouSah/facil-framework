"""GET .../issuer-identity — SP1 debt D1, endpoint layer.

End-to-end through real JWT principals (mirrors `test_rbac_enforcement_e2e.py`):
the resolver itself is unit-tested in `test_issuer_identity.py`; this file
covers the HTTP contract — scope-filtered (`visible_orgs`), 404 (not 403)
outside the caller's perimeter, and the resolved+origin response shape.
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
    from app.core.schema.registry import default_schema_registry
    from app.db.base import Base
    from app.db.engine import Database
    from app.identity import models as _a  # noqa: F401
    from app.auth import models as _c  # noqa: F401
    from app.rbac import models as _r  # noqa: F401

    import_module_models()
    db = Database(f"sqlite+aiosqlite:///{tmp_path/'issuer_e2e.db'}")
    async with db.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    application = FastAPI()
    application.state.db = db
    application.state.resolver = ConfigResolver(
        defaults={"branding.app_name": "Facil", "profile": "empty",
                  "auth.self_registration_enabled": True}, env={})
    application.state.registry = default_registry()
    application.state.auth = application.state.registry.build(
        "auth", "native", {"issuer": "facil"})
    application.state.schema_registry = default_schema_registry()
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


async def _mk_org(ac, code, **extra):
    r = await ac.post(f"{ORG}/", headers=ADMIN,
                      json={"code": code, "legal_name": f"{code} legal name", **extra})
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def _mk_unit(ac, org_id, code):
    r = await ac.post(f"{ORG}/{org_id}/units", headers=ADMIN, json={"code": code, "name": code})
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def _mk_site(ac, org_id, code):
    r = await ac.post(f"{LOC}/sites", headers=ADMIN,
                      json={"organization_id": org_id, "code": code, "name": code})
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


# --- Organization ----------------------------------------------------------

@pytest.mark.asyncio
async def test_organization_issuer_identity_resolves_with_origin(seeded):
    ac, org_a, _ = seeded
    r = await ac.get(f"{ORG}/{org_a}/issuer-identity", headers=ADMIN)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["legal_name"] == {"value": "org-a legal name", "from": "organization"}
    assert body["tax_id"] == {"value": None, "from": None}


@pytest.mark.asyncio
async def test_unknown_organization_is_404(seeded):
    ac, _, _ = seeded
    r = await ac.get(f"{ORG}/does-not-exist/issuer-identity", headers=ADMIN)
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_org_b_scoped_principal_cannot_resolve_org_a_issuer_identity(seeded):
    """A principal scoped to org B resolving org A's issuer identity is 404,
    never 403 — the endpoint must not leak that org A exists to a caller with
    no visibility into it (established pattern, mirrors GET /api/v1/schema)."""
    ac, org_a, org_b = seeded
    member = await _role_id(ac, "member")
    hdr, acc_id = await _bearer(ac, "alice@x.com")
    await ac.post(f"/api/v1/rbac/accounts/{acc_id}/roles", headers=ADMIN,
                 json={"role_id": member, "organization_id": org_b})

    assert (await ac.get(f"{ORG}/{org_b}/issuer-identity", headers=hdr)).status_code == 200
    r = await ac.get(f"{ORG}/{org_a}/issuer-identity", headers=hdr)
    assert r.status_code == 404, r.text


# --- OrgUnit -----------------------------------------------------------------

@pytest.mark.asyncio
async def test_unit_issuer_identity_resolves(seeded):
    ac, org_a, _ = seeded
    unit_id = await _mk_unit(ac, org_a, "dept-1")
    r = await ac.get(f"{ORG}/units/{unit_id}/issuer-identity", headers=ADMIN)
    assert r.status_code == 200, r.text
    assert r.json()["legal_name"] == {"value": "org-a legal name", "from": "organization"}


@pytest.mark.asyncio
async def test_unknown_unit_is_404(seeded):
    ac, _, _ = seeded
    r = await ac.get(f"{ORG}/units/does-not-exist/issuer-identity", headers=ADMIN)
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_org_b_scoped_principal_cannot_resolve_org_a_unit_issuer_identity(seeded):
    ac, org_a, org_b = seeded
    unit_id = await _mk_unit(ac, org_a, "dept-1")
    member = await _role_id(ac, "member")
    hdr, acc_id = await _bearer(ac, "bob@x.com")
    await ac.post(f"/api/v1/rbac/accounts/{acc_id}/roles", headers=ADMIN,
                 json={"role_id": member, "organization_id": org_b})

    r = await ac.get(f"{ORG}/units/{unit_id}/issuer-identity", headers=hdr)
    assert r.status_code == 404, r.text


# --- Site --------------------------------------------------------------------

@pytest.mark.asyncio
async def test_site_issuer_identity_resolves(seeded):
    ac, org_a, _ = seeded
    site_id = await _mk_site(ac, org_a, "branch-1")
    r = await ac.get(f"{LOC}/sites/{site_id}/issuer-identity", headers=ADMIN)
    assert r.status_code == 200, r.text
    assert r.json()["legal_name"] == {"value": "org-a legal name", "from": "organization"}


@pytest.mark.asyncio
async def test_unknown_site_is_404(seeded):
    ac, _, _ = seeded
    r = await ac.get(f"{LOC}/sites/does-not-exist/issuer-identity", headers=ADMIN)
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_org_b_scoped_principal_cannot_resolve_org_a_site_issuer_identity(seeded):
    ac, org_a, org_b = seeded
    site_id = await _mk_site(ac, org_a, "branch-1")
    member = await _role_id(ac, "member")
    hdr, acc_id = await _bearer(ac, "carol@x.com")
    await ac.post(f"/api/v1/rbac/accounts/{acc_id}/roles", headers=ADMIN,
                 json={"role_id": member, "organization_id": org_b})

    r = await ac.get(f"{LOC}/sites/{site_id}/issuer-identity", headers=hdr)
    assert r.status_code == 404, r.text


@pytest.mark.asyncio
async def test_requires_authentication(seeded):
    ac, org_a, _ = seeded
    r = await ac.get(f"{ORG}/{org_a}/issuer-identity")
    assert r.status_code == 401
