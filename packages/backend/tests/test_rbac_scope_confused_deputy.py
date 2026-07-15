"""RED tests: cross-tenant write via caller-supplied org scope (confused deputy).

SECURITY INCIDENT. `rbac.repository.resolve_scope` derives the request's
organisation from the target row (site -> organization_id, unit ->
organization_id) but does `org = org or site.organization_id` — an `or`, not an
authoritative override. `org` is seeded from `rbac.scope.raw_scope_ids`, which
falls back to the QUERY STRING when the path carries no org (true for every
id-addressed route: `PUT /sites/{site_id}`, `PUT /units/{unit_id}`,
`PUT /parties/{pid}`, ...). A caller can therefore append
`?organization_id=<their own org>` (or the `?org_id=` alias) and have
`resolve_scope` report THEIR org instead of the target row's real owner —
`covers()` then authorizes the write against a row the caller does not own.

These tests assert the CORRECT behaviour (403/404, row unchanged) and are
expected to FAIL on the vulnerable code (200, row mutated). Harness copied from
`test_rbac_enforcement_e2e.py` (real JWT principals via /auth/register+login,
scoped role assignment via the RBAC API) — no parallel harness invented; only
the party router is added since party is a core (always-mounted) router, not
gated by `load_modules`.
"""

from __future__ import annotations

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

ADMIN = {"X-Admin-Token": "test-token"}
ORG = "/api/v1/modules/organization"
LOC = "/api/v1/modules/location"
PARTY = "/api/v1/modules/party"


@pytest_asyncio.fixture
async def cd(tmp_path, monkeypatch):
    monkeypatch.setenv("ADMIN_TOKEN", "test-token")
    monkeypatch.setenv("JWT_SECRET", "test-jwt-secret-0123456789abcdef0123456789")
    import app.config as cfg
    cfg._settings = None

    from app.api import auth as auth_api
    from app.api import rbac as rbac_api
    from app.config_store.resolver import ConfigResolver
    from app.core.module_registry import import_module_models, load_modules
    from app.core.providers.registry import default_registry
    from app.db.base import Base
    from app.db.engine import Database
    from app.identity import models as _a  # noqa: F401 (register Account)
    from app.auth import models as _c  # noqa: F401 (register Credential)
    from app.modules.party.api import router as party_router
    from app.rbac import models as _r  # noqa: F401 (register RBAC tables)

    import_module_models()
    db = Database(f"sqlite+aiosqlite:///{tmp_path/'cd.db'}")
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
    application.include_router(auth_api.router)
    application.include_router(rbac_api.router)
    application.include_router(party_router)  # core router (see app/main.py)
    load_modules(application, enabled=["organization", "location"])

    transport = ASGITransport(app=application)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac, db
    await db.dispose()
    cfg._settings = None


async def _bearer(ac, email, password="Sup3rStr0ng!pw"):
    await ac.post("/api/v1/auth/register", json={"password": password, "email": email})
    r = await ac.post("/api/v1/auth/login",
                      json={"identifier": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access']}"}, r.json()["account"]["id"]


async def _role(ac, code, grants):
    r = await ac.post("/api/v1/rbac/roles", headers=ADMIN,
                      json={"code": code, "name": code, "grants": grants})
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def _mk_org(ac, code):
    r = await ac.post(f"{ORG}/", headers=ADMIN, json={"code": code, "legal_name": code})
    assert r.status_code == 201, r.text
    return r.json()["id"]


@pytest_asyncio.fixture
async def scenario(cd):
    ac, db = cd
    assert (await ac.post("/api/v1/rbac/admin/reseed?profile=empty", headers=ADMIN)
            ).status_code == 200
    org_a = await _mk_org(ac, "org-a")
    org_b = await _mk_org(ac, "org-b")
    return ac, db, org_a, org_b


# --- Site (location.update) -----------------------------------------------

@pytest.mark.asyncio
async def test_cross_tenant_site_update_via_organization_id_query_spoof(scenario):
    """A principal holding `location.update` ONLY in org A must not be able to
    rewrite a site that belongs to org B by appending ?organization_id=<org A>."""
    ac, db, org_a, org_b = scenario
    role_id = await _role(ac, "site_updater", ["location.update"])
    hdr, acc_id = await _bearer(ac, "mallory@x.com")
    await ac.post(f"/api/v1/rbac/accounts/{acc_id}/roles", headers=ADMIN,
                  json={"role_id": role_id, "organization_id": org_a})

    victim = (await ac.post(f"{LOC}/sites", headers=ADMIN,
                            json={"organization_id": org_b, "code": "VICTIM",
                                  "name": "Victim Site"})).json()

    # THE EXPLOIT: caller's grant is scoped to org A; the target row (site_id)
    # belongs to org B. ?organization_id=<A> must NOT let this pass.
    resp = await ac.put(f"{LOC}/sites/{victim['id']}?organization_id={org_a}",
                        headers=hdr, json={"name": "PWNED"})

    after = (await ac.get(f"{LOC}/sites/{victim['id']}", headers=ADMIN)).json()
    assert resp.status_code in (403, 404), (
        f"cross-tenant site write via ?organization_id= succeeded: "
        f"status={resp.status_code} body={resp.text!r} "
        f"victim.name BEFORE='Victim Site' AFTER={after.get('name')!r}")
    assert after["name"] == "Victim Site", (
        f"victim row was mutated despite a non-2xx response: {after!r}")


@pytest.mark.asyncio
async def test_cross_tenant_site_update_via_org_id_alias_query_spoof(scenario):
    """Same exploit via the `org_id` alias that `_pick` also accepts (not just
    `organization_id`)."""
    ac, db, org_a, org_b = scenario
    role_id = await _role(ac, "site_updater2", ["location.update"])
    hdr, acc_id = await _bearer(ac, "mallory2@x.com")
    await ac.post(f"/api/v1/rbac/accounts/{acc_id}/roles", headers=ADMIN,
                  json={"role_id": role_id, "organization_id": org_a})

    victim = (await ac.post(f"{LOC}/sites", headers=ADMIN,
                            json={"organization_id": org_b, "code": "VICTIM2",
                                  "name": "Victim Site 2"})).json()

    resp = await ac.put(f"{LOC}/sites/{victim['id']}?org_id={org_a}",
                        headers=hdr, json={"name": "PWNED-ALIAS"})

    after = (await ac.get(f"{LOC}/sites/{victim['id']}", headers=ADMIN)).json()
    assert resp.status_code in (403, 404), (
        f"cross-tenant site write via ?org_id= alias succeeded: "
        f"status={resp.status_code} body={resp.text!r} "
        f"victim.name AFTER={after.get('name')!r}")
    assert after["name"] == "Victim Site 2"


# --- OrgUnit (organization.update) -----------------------------------------

@pytest.mark.asyncio
async def test_cross_tenant_unit_update_via_query_org_spoof(scenario):
    """Same confused deputy on the OrgUnit route (`organization.update`)."""
    ac, db, org_a, org_b = scenario
    role_id = await _role(ac, "unit_updater", ["organization.update"])
    hdr, acc_id = await _bearer(ac, "eve@x.com")
    await ac.post(f"/api/v1/rbac/accounts/{acc_id}/roles", headers=ADMIN,
                  json={"role_id": role_id, "organization_id": org_a})

    victim = (await ac.post(f"{ORG}/{org_b}/units", headers=ADMIN,
                            json={"code": "VU", "name": "Victim Unit"})).json()

    resp = await ac.put(f"{ORG}/units/{victim['id']}?organization_id={org_a}",
                        headers=hdr, json={"name": "PWNED-UNIT"})

    after = (await ac.get(f"{ORG}/units/{victim['id']}", headers=ADMIN)).json()
    assert resp.status_code in (403, 404), (
        f"cross-tenant unit write via ?organization_id= succeeded: "
        f"status={resp.status_code} body={resp.text!r} "
        f"victim.name AFTER={after.get('name')!r}")
    assert after["name"] == "Victim Unit"


# --- Party (party.update — global-only resource) ---------------------------

@pytest.mark.asyncio
async def test_party_update_org_scoped_grant_is_refused(scenario):
    """party is explicitly NOT tenant-scoped (global admin master data, see
    app/modules/party/api/__init__.py docstring) — an org-scoped `party.update`
    grant must never authorize a party write, even when the caller echoes their
    own org via `?org_id=`. Today, with no site/unit row for resolve_scope to
    consult, the query string is taken at face value and the org-scoped grant
    is (wrongly) treated as if it covered this request."""
    ac, db, org_a, org_b = scenario
    role_id = await _role(ac, "party_updater", ["party.update"])
    hdr, acc_id = await _bearer(ac, "trudy@x.com")
    await ac.post(f"/api/v1/rbac/accounts/{acc_id}/roles", headers=ADMIN,
                  json={"role_id": role_id, "organization_id": org_a})

    victim = (await ac.post(f"{PARTY}/parties", headers=ADMIN,
                            json={"name": "Victim Party"})).json()

    resp = await ac.put(f"{PARTY}/parties/{victim['id']}?org_id={org_a}",
                        headers=hdr, json={"name": "PWNED-PARTY"})

    after = (await ac.get(f"{PARTY}/parties/{victim['id']}", headers=ADMIN)).json()
    assert resp.status_code == 403, (
        f"org-scoped party.update grant authorized a party write via ?org_id=: "
        f"status={resp.status_code} body={resp.text!r} "
        f"victim.name AFTER={after.get('name')!r}")
    assert after["name"] == "Victim Party"
