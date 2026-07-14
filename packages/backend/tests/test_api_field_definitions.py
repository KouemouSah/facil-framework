"""Caps, guards, allowlist and archive semantics on the definition API.

The definition CRUD endpoint (`/api/v1/admin/field-definitions`) needs a real
HTTP client wired to modules gated by MODULES_ENABLED (`organization`,
`location`) PLUS a real JWT auth chain (register/login) for the no-permission
and cross-tenant tests. The shared `client` fixture in `conftest.py` imports
the SINGLETON `app.main.app`, whose module-level `load_modules(...)` already
ran (with an empty MODULES_ENABLED) the first time ANY test file imported it
this session — `/api/v1/modules/location/...` 404s there (confirmed by the
Task 8 report: "app.main.app...has an empty MODULES_ENABLED in this test
session"). So this file builds its OWN standalone app, exactly like
`test_organization_api.py`'s `org_client` / `test_rbac_enforcement_e2e.py`'s
`e2e` fixtures — not a parallel harness invented from scratch, the same
established pattern for this exact problem.
"""

from __future__ import annotations

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

AUTH = {"X-Admin-Token": "test-token"}


def _body(key="convention_no", **kw):
    return {"target": "site.custom_fields", "key": key, "type": "string",
            "label": {"en": key, "fr": key, "es": key}, **kw}


@pytest_asyncio.fixture
async def _env(tmp_path, monkeypatch):
    monkeypatch.setenv("ADMIN_TOKEN", "test-token")
    monkeypatch.setenv("JWT_SECRET", "test-jwt-secret-0123456789abcdef0123456789")
    import app.config as cfg
    cfg._settings = None

    from app.api import admin_field_definitions
    from app.api import auth as auth_api
    from app.api import schema as schema_api
    from app.config_store.resolver import ConfigResolver
    from app.core.module_registry import import_module_models, load_modules
    from app.core.providers.registry import default_registry
    from app.core.schema.registry import default_schema_registry
    from app.db.base import Base
    from app.db.engine import Database
    from app.identity import models as _a  # noqa: F401 (register Account)
    from app.auth import models as _c  # noqa: F401 (register Credential)
    from app.rbac import models as _r  # noqa: F401 (register RBAC tables)
    from app.modules.party.api import router as party_router

    import_module_models()
    db = Database(f"sqlite+aiosqlite:///{tmp_path/'fd.db'}")
    async with db.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    application = FastAPI()
    application.state.db = db
    application.state.resolver = ConfigResolver(
        defaults={"branding.app_name": "Facil",
                  "auth.self_registration_enabled": True}, env={})
    application.state.registry = default_registry()
    application.state.schema_registry = default_schema_registry()
    application.state.auth = application.state.registry.build(
        "auth", "native", {"issuer": "facil"})
    application.include_router(auth_api.router)
    application.include_router(schema_api.router)
    application.include_router(admin_field_definitions.router)
    application.include_router(party_router)
    load_modules(application, enabled=["organization", "location"])

    yield db, application
    await db.dispose()
    cfg._settings = None


@pytest_asyncio.fixture
async def client(_env):
    _, application = _env
    transport = ASGITransport(app=application)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture
async def session(_env):
    db, _ = _env
    async with db.session_factory() as s:
        yield s


@pytest_asyncio.fixture
async def org_a(session):
    from app.modules.organization.models import Organization
    org = Organization(code="fd-org-a", legal_name="FD Organisation A")
    session.add(org)
    await session.commit()  # visible to the HTTP client's OWN session/connection
    return org


@pytest_asyncio.fixture
async def org_b(session):
    from app.modules.organization.models import Organization
    org = Organization(code="fd-org-b", legal_name="FD Organisation B")
    session.add(org)
    await session.commit()
    return org


@pytest_asyncio.fixture
async def site_a(session, org_a):
    from app.modules.location.models import Site
    site = Site(organization_id=org_a.id, code="site-a", name="Site A")
    session.add(site)
    await session.commit()
    return site


@pytest.fixture
def admin_headers():
    return AUTH


@pytest_asyncio.fixture
async def headers_no_perm(client):
    """A real, authenticated JWT principal with ZERO role assignments —
    distinct from `admin_headers` (break-glass, bypasses RBAC entirely)."""
    await client.post("/api/v1/auth/register",
                      json={"password": "Sup3rStr0ng!pw", "email": "noperm@x.com"})
    login = await client.post(
        "/api/v1/auth/login",
        json={"identifier": "noperm@x.com", "password": "Sup3rStr0ng!pw"})
    assert login.status_code == 200, login.text
    return {"Authorization": f"Bearer {login.json()['access']}"}


@pytest_asyncio.fixture
async def seed_50_fields(session, org_a):
    from app.models.field_definition import FieldDefinition
    for i in range(50):
        session.add(FieldDefinition(
            organization_id=org_a.id, target="site.custom_fields", key=f"f{i}",
            type="string", widget="plain", label_en=f"f{i}", label_fr=f"f{i}",
            label_es=f"f{i}"))
    await session.commit()


@pytest_asyncio.fixture
async def seed_10_indexed_fields(session, org_a):
    from app.models.field_definition import FieldDefinition
    for i in range(10):
        session.add(FieldDefinition(
            organization_id=org_a.id, target="site.custom_fields", key=f"idx{i}",
            type="string", widget="plain", label_en=f"idx{i}", label_fr=f"idx{i}",
            label_es=f"idx{i}", indexed=True))
    await session.commit()


# --- Permission / guards ---------------------------------------------------

@pytest.mark.asyncio
async def test_creating_a_definition_requires_fields_manage(client, org_a, headers_no_perm):
    r = await client.post(f"/api/v1/admin/field-definitions/?organization_id={org_a.id}",
                          json=_body(), headers=headers_no_perm)
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_reserved_key_is_refused(client, org_a, admin_headers):
    r = await client.post(f"/api/v1/admin/field-definitions/?organization_id={org_a.id}",
                          json=_body(key="organization_id"), headers=admin_headers)
    assert r.status_code == 422 and "reserved" in r.text


@pytest.mark.asyncio
async def test_secret_looking_key_is_refused(client, org_a, admin_headers):
    r = await client.post(f"/api/v1/admin/field-definitions/?organization_id={org_a.id}",
                          json=_body(key="api_key"), headers=admin_headers)
    assert r.status_code == 422 and "secret" in r.text


@pytest.mark.asyncio
async def test_relation_field_with_disallowed_resource_is_refused(client, org_a, admin_headers):
    # RELATION_RESOURCES is a fixed allowlist (countries/currencies/regions) —
    # a free-form resource string would be interpolated into a client request
    # path by the picker. "products" is not on it.
    r = await client.post(
        f"/api/v1/admin/field-definitions/?organization_id={org_a.id}",
        json=_body(key="linked_thing", type="relation", widget="combobox",
                  relation_resource="products"),
        headers=admin_headers)
    assert r.status_code == 422 and "not allowed" in r.text


@pytest.mark.asyncio
async def test_relation_field_with_an_allowed_resource_succeeds(client, org_a, admin_headers):
    r = await client.post(
        f"/api/v1/admin/field-definitions/?organization_id={org_a.id}",
        json=_body(key="hq_country", type="relation", widget="combobox",
                  relation_resource="countries"),
        headers=admin_headers)
    assert r.status_code == 201, r.text


@pytest.mark.asyncio
async def test_the_51st_field_is_refused(client, org_a, admin_headers, seed_50_fields):
    r = await client.post(f"/api/v1/admin/field-definitions/?organization_id={org_a.id}",
                          json=_body(key="one_too_many"), headers=admin_headers)
    assert r.status_code == 422 and "50" in r.text


@pytest.mark.asyncio
async def test_the_11th_indexed_field_is_refused(client, org_a, admin_headers,
                                                 seed_10_indexed_fields):
    r = await client.post(f"/api/v1/admin/field-definitions/?organization_id={org_a.id}",
                          json=_body(key="idx_11", indexed=True), headers=admin_headers)
    assert r.status_code == 422 and "10" in r.text


@pytest.mark.asyncio
async def test_indexed_is_refused_on_a_non_indexable_type(client, org_a, admin_headers):
    r = await client.post(f"/api/v1/admin/field-definitions/?organization_id={org_a.id}",
                          json=_body(key="blob", type="json", widget="raw", indexed=True),
                          headers=admin_headers)
    assert r.status_code == 422


# --- Archive vs purge -------------------------------------------------------

@pytest.mark.asyncio
async def test_archive_hides_the_field_but_keeps_the_values(client, session, org_a,
                                                            admin_headers, site_a):
    r = await client.post(f"/api/v1/admin/field-definitions/?organization_id={org_a.id}",
                          json=_body(), headers=admin_headers)
    assert r.status_code == 201, r.text
    fid = r.json()["id"]
    put = await client.put(f"/api/v1/modules/location/sites/{site_a.id}",
                           json={"custom_fields": {"convention_no": "C-1"}},
                           headers=admin_headers)
    assert put.status_code == 200, put.text
    arch = await client.post(f"/api/v1/admin/field-definitions/{fid}/archive",
                             headers=admin_headers)
    assert arch.status_code == 200, arch.text
    assert arch.json()["archived"] is True

    schema = await client.get(
        f"/api/v1/schema/site.custom_fields?organization_id={org_a.id}", headers=admin_headers)
    assert schema.json()["fields"] == []            # gone from the form
    await session.refresh(site_a)
    assert site_a.custom_fields == {"convention_no": "C-1"}   # value SURVIVES


@pytest.mark.asyncio
async def test_purge_deletes_the_definition_but_keeps_the_values(client, session, org_a,
                                                                  admin_headers, site_a):
    r = await client.post(f"/api/v1/admin/field-definitions/?organization_id={org_a.id}",
                          json=_body(key="purge_me"), headers=admin_headers)
    fid = r.json()["id"]
    await client.put(f"/api/v1/modules/location/sites/{site_a.id}",
                     json={"custom_fields": {"purge_me": "still-here"}},
                     headers=admin_headers)
    purged = await client.post(f"/api/v1/admin/field-definitions/{fid}/purge",
                               headers=admin_headers)
    assert purged.status_code == 200, purged.text

    # Purge, unlike archive, actually removes the ROW.
    from app.models.field_definition import FieldDefinition
    assert await session.get(FieldDefinition, fid) is None

    await session.refresh(site_a)
    assert site_a.custom_fields == {"purge_me": "still-here"}   # value SURVIVES


# --- entity-write allowlist: BOTH create and update -------------------------

@pytest.mark.asyncio
async def test_writing_an_undeclared_custom_field_on_update_is_422_not_ignored(
        client, org_a, admin_headers, site_a):
    r = await client.put(f"/api/v1/modules/location/sites/{site_a.id}",
                         json={"custom_fields": {"never_declared": "x"}},
                         headers=admin_headers)
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_writing_an_undeclared_custom_field_on_create_is_422_not_ignored(
        client, org_a, admin_headers):
    r = await client.post(
        "/api/v1/modules/location/sites",
        json={"organization_id": org_a.id, "code": "site-x", "name": "Site X",
              "custom_fields": {"never_declared": "x"}},
        headers=admin_headers)
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_a_declared_custom_field_is_accepted_on_create(client, org_a, admin_headers):
    await client.post(f"/api/v1/admin/field-definitions/?organization_id={org_a.id}",
                      json=_body(key="convention_no"), headers=admin_headers)
    r = await client.post(
        "/api/v1/modules/location/sites",
        json={"organization_id": org_a.id, "code": "site-y", "name": "Site Y",
              "custom_fields": {"convention_no": "C-99"}},
        headers=admin_headers)
    assert r.status_code == 201, r.text
    assert r.json()["custom_fields"] == {"convention_no": "C-99"}


@pytest.mark.asyncio
async def test_an_empty_custom_fields_on_create_is_not_configured_not_rejected(
        client, org_a, admin_headers):
    # No field definitions exist for org_a at all — an empty dict must not 422.
    r = await client.post(
        "/api/v1/modules/location/sites",
        json={"organization_id": org_a.id, "code": "site-z", "name": "Site Z"},
        headers=admin_headers)
    assert r.status_code == 201, r.text
    assert r.json()["custom_fields"] == {}


@pytest.mark.asyncio
async def test_richtext_value_is_sanitized_on_write(client, org_a, admin_headers, site_a):
    """Guard #4: `clean_richtext` is applied on WRITE, not just at render time —
    the row in the DB must already be clean (defence in depth)."""
    await client.post(
        f"/api/v1/admin/field-definitions/?organization_id={org_a.id}",
        json=_body(key="notes_html", type="richtext", widget="editor"),
        headers=admin_headers)
    dirty = '<p>hello</p><script>alert(1)</script><img src="http://evil/x">'
    r = await client.put(
        f"/api/v1/modules/location/sites/{site_a.id}",
        json={"custom_fields": {"notes_html": dirty}}, headers=admin_headers)
    assert r.status_code == 200, r.text
    stored = r.json()["custom_fields"]["notes_html"]
    assert "<script>" not in stored
    assert "<img" not in stored
    assert "<p>hello</p>" in stored


# --- organization's OWN custom_fields (self-scoped; no existing row on create) ---

@pytest.mark.asyncio
async def test_organization_self_custom_field_create_and_update(client, admin_headers):
    # An organisation must exist to own a definition BEFORE it can be targeted —
    # but "organization.custom_fields" describes THAT SAME org's own row. Create
    # the org first (no custom fields defined yet -> empty is accepted), define
    # a field scoped to it, then prove both the create and the update path of a
    # DIFFERENT org enforce the allowlist against it.
    org = await client.post("/api/v1/modules/organization/",
                            json={"code": "self-scope-org", "legal_name": "Self Scope"},
                            headers=admin_headers)
    assert org.status_code == 201, org.text
    org_id = org.json()["id"]
    await client.post(
        f"/api/v1/admin/field-definitions/?organization_id={org_id}",
        json=_body(key="ministry_code", target="organization.custom_fields"),
        headers=admin_headers)

    # create path: a NEW org with the SAME field NOT declared for it is 422.
    other = await client.post(
        "/api/v1/modules/organization/",
        json={"code": "other-org", "legal_name": "Other",
              "custom_fields": {"ministry_code": "M-1"}},
        headers=admin_headers)
    assert other.status_code == 422, other.text

    # update path on the OWNING org: declared key is accepted.
    upd = await client.put(f"/api/v1/modules/organization/{org_id}",
                           json={"custom_fields": {"ministry_code": "M-42"}},
                           headers=admin_headers)
    assert upd.status_code == 200, upd.text
    assert upd.json()["custom_fields"] == {"ministry_code": "M-42"}

    # update path: an undeclared key is still 422 on that same org.
    bad = await client.put(f"/api/v1/modules/organization/{org_id}",
                           json={"custom_fields": {"nope": "x"}},
                           headers=admin_headers)
    assert bad.status_code == 422


# --- party is NOT an extensible target (Fix wave 1 — design correction) ----
#
# `Party` is a GLOBAL directory row with no `organization_id` of its own, but
# a `FieldDefinition` is ALWAYS org-owned (`organization_id` NOT NULL — SP1's
# formal statement of tenant isolation: "there is no such thing as a global
# custom field"). "Which organisation's schema governs a global party row?"
# has no answer, so `party.custom_fields` was removed from
# `EXTENSIBLE_TARGETS` (see its docstring). These two tests replace the old
# `test_party_custom_field_requires_the_definitions_org` /
# `test_party_custom_field_is_allowlisted_when_organization_id_given` /
# `test_party_empty_custom_fields_clear_requires_the_org`, which all assumed
# the now-removed `definitions_org_id` allowlist flow.

@pytest.mark.asyncio
async def test_party_target_is_refused_by_the_definitions_allowlist(
        client, org_a, admin_headers):
    r = await client.post(
        f"/api/v1/admin/field-definitions/?organization_id={org_a.id}",
        json=_body(key="segment", target="party.custom_fields"),
        headers=admin_headers)
    assert r.status_code == 422 and "not extensible" in r.text


@pytest.mark.asyncio
async def test_party_custom_fields_write_is_always_rejected_on_create(
        client, admin_headers):
    r = await client.post(
        "/api/v1/modules/party/parties",
        json={"name": "Acme SARL", "custom_fields": {"anything": "x"}},
        headers=admin_headers)
    assert r.status_code == 422
    assert "not an extensible target" in r.text


@pytest.mark.asyncio
async def test_party_custom_fields_write_is_always_rejected_on_update(
        client, admin_headers):
    made = await client.post(
        "/api/v1/modules/party/parties", json={"name": "Acme SARL"}, headers=admin_headers)
    assert made.status_code == 201, made.text
    pid = made.json()["id"]

    # Even an EMPTY dict (a "clear" under the old semantics) is refused — no
    # organisation could ever validate it, so there is nothing to clear.
    r = await client.put(f"/api/v1/modules/party/parties/{pid}",
                         json={"custom_fields": {}}, headers=admin_headers)
    assert r.status_code == 422
    assert "not an extensible target" in r.text


# --- If-Match concurrency ---------------------------------------------------

@pytest.mark.asyncio
async def test_update_requires_if_match(client, org_a, admin_headers):
    r = await client.post(f"/api/v1/admin/field-definitions/?organization_id={org_a.id}",
                          json=_body(), headers=admin_headers)
    assert r.status_code == 201, r.text
    fid, etag = r.json()["id"], r.json()["etag"]
    stale = await client.put(f"/api/v1/admin/field-definitions/{fid}",
                             json=_body(key="convention_no", required=True),
                             headers={**admin_headers, "If-Match": "stale"})
    assert stale.status_code == 409
    ok = await client.put(f"/api/v1/admin/field-definitions/{fid}",
                          json=_body(key="convention_no", required=True),
                          headers={**admin_headers, "If-Match": etag})
    assert ok.status_code == 200, ok.text
    assert ok.json()["required"] is True


@pytest.mark.asyncio
async def test_target_and_key_are_immutable_on_update(client, org_a, admin_headers):
    r = await client.post(f"/api/v1/admin/field-definitions/?organization_id={org_a.id}",
                          json=_body(), headers=admin_headers)
    fid, etag = r.json()["id"], r.json()["etag"]
    r2 = await client.put(f"/api/v1/admin/field-definitions/{fid}",
                          json=_body(key="renamed"),
                          headers={**admin_headers, "If-Match": etag})
    assert r2.status_code == 422


# --- HARD REQUIREMENT 2: write-path tenant isolation ------------------------

async def _grant(db, account_id: str, permission: str, *, code: str,
                 organization_id: str | None = None,
                 org_unit_id: str | None = None,
                 site_id: str | None = None) -> None:
    """Grant `permission` to `account_id` at the given scope — built directly on
    the RBAC tables (bypassing the HTTP role-assignment API and
    `service.create_role`'s catalog validation, which is orthogonal to what
    `has_permission` actually reads at enforcement time: `role`,
    `role_permission`, `account_role`)."""
    from app.rbac.models import AccountRole, Role, RolePermission
    async with db.session_factory() as s:
        role = Role(code=code, name=code, is_system=False)
        s.add(role)
        await s.flush()
        s.add(RolePermission(role_id=role.id, permission_code=permission))
        s.add(AccountRole(account_id=account_id, role_id=role.id,
                          organization_id=organization_id, org_unit_id=org_unit_id,
                          site_id=site_id))
        await s.commit()


async def _grant_fields_manage(db, account_id: str, organization_id: str) -> None:
    await _grant(db, account_id, "fields.manage", code="fd-manager",
                 organization_id=organization_id)


async def _login(client, email: str) -> tuple[dict, str]:
    await client.post("/api/v1/auth/register",
                      json={"password": "Sup3rStr0ng!pw", "email": email})
    r = await client.post("/api/v1/auth/login",
                          json={"identifier": email, "password": "Sup3rStr0ng!pw"})
    assert r.status_code == 200, r.text
    return ({"Authorization": f"Bearer {r.json()['access']}"},
            r.json()["account"]["id"])


@pytest.mark.asyncio
async def test_org_b_scoped_principal_cannot_touch_org_a_definition(client, _env, org_a, org_b):
    """THE central write-side guarantee: a principal whose `fields.manage`
    grant is scoped to org B must get 404 (never 403 — that would confirm the
    id belongs to a real organisation it cannot see) on create/update/archive/
    purge of a definition that belongs to org A. This fails the moment
    `_authorize_target` is replaced with a caller-scoped check (e.g. `enforce`
    against the CALLER's own claimed org instead of the ROW's), or if 404 were
    swapped for 403 — either regression is exactly what this test pins."""
    db, _ = _env
    r = await client.post(f"/api/v1/admin/field-definitions/?organization_id={org_a.id}",
                          json=_body(key="internal_field"), headers=AUTH)
    assert r.status_code == 201, r.text
    fid, etag = r.json()["id"], r.json()["etag"]

    await client.post("/api/v1/auth/register",
                      json={"password": "Sup3rStr0ng!pw", "email": "iso@x.com"})
    login = await client.post(
        "/api/v1/auth/login",
        json={"identifier": "iso@x.com", "password": "Sup3rStr0ng!pw"})
    assert login.status_code == 200, login.text
    acc_id = login.json()["account"]["id"]
    hdr = {"Authorization": f"Bearer {login.json()['access']}"}
    await _grant_fields_manage(db, acc_id, org_b.id)

    # This principal DOES have fields.manage — just not on org A. Prove the
    # grant itself works (create ON org B succeeds) before asserting isolation.
    own_org = await client.post(
        f"/api/v1/admin/field-definitions/?organization_id={org_b.id}",
        json=_body(key="own_field"), headers=hdr)
    assert own_org.status_code == 201, own_org.text

    upd = await client.put(f"/api/v1/admin/field-definitions/{fid}",
                           json=_body(key="internal_field", required=True),
                           headers={**hdr, "If-Match": etag})
    assert upd.status_code == 404, upd.text

    arch = await client.post(f"/api/v1/admin/field-definitions/{fid}/archive", headers=hdr)
    assert arch.status_code == 404, arch.text

    purge = await client.post(f"/api/v1/admin/field-definitions/{fid}/purge", headers=hdr)
    assert purge.status_code == 404, purge.text

    # ... and creating a definition ON org A (naming it explicitly) is a plain
    # 403 — the org is not hidden there (the caller named it), so no leak.
    create_on_a = await client.post(
        f"/api/v1/admin/field-definitions/?organization_id={org_a.id}",
        json=_body(key="cross_tenant"), headers=hdr)
    assert create_on_a.status_code == 403, create_on_a.text


# --- Review-gate regressions (findings raised by the quality gate, all fixed) ---

@pytest.mark.asyncio
async def test_org_id_alias_cannot_be_used_to_write_into_another_org(client, _env,
                                                                    org_a, org_b):
    """SEC-001 (confused deputy). `rbac.scope.raw_scope_ids` resolves the request
    scope with `_pick(request, "org_id", "organization_id")` — the `org_id` ALIAS
    WINS over the canonical name, in the query string too. So a router-level
    `require_permission` dependency and a handler that separately binds its own
    `organization_id` query param can be played off against each other:

        ?organization_id=<VICTIM>&org_id=<MY OWN ORG>

    RBAC authorises against `org_id` (mine); the handler writes the row against
    `organization_id` (the victim's). FastAPI silently ignores the undeclared
    extra param, so nothing catches it.

    The fix: authorization is enforced IN-HANDLER (`_authorize_org`), bound to the
    exact variable the row is built from. This test goes 201 (with a definition
    planted in org A) the moment anyone "simplifies" that back into a router-level
    `dependencies=[Depends(require_permission("fields.manage"))]`.
    """
    from sqlalchemy import select

    from app.models.field_definition import FieldDefinition

    db, _ = _env
    hdr, acc_id = await _login(client, "deputy@x.com")
    await _grant_fields_manage(db, acc_id, org_b.id)   # ONLY on org B

    r = await client.post(
        f"/api/v1/admin/field-definitions/?organization_id={org_a.id}&org_id={org_b.id}",
        json=_body(key="planted"), headers=hdr)
    assert r.status_code == 403, r.text

    async with db.session_factory() as s:
        rows = (await s.execute(select(FieldDefinition).where(
            FieldDefinition.organization_id == org_a.id))).scalars().all()
    assert rows == [], "LEAK: a definition was planted in another tenant's organisation"


@pytest.mark.asyncio
async def test_site_scoped_grant_cannot_purge_an_org_wide_definition(client, _env,
                                                                     org_a, site_a):
    """`visible_orgs` is deliberately COARSE (its own docstring: "a unit/site-scoped
    grant makes its parent organization visible — org-level granularity"). It is a
    LISTING filter. Using it alone as the WRITE decision would let a `fields.manage`
    grant scoped to ONE SITE inside org A rewrite and purge org A's org-wide
    definitions. `_authorize_target` therefore ALSO runs the real `enforce`
    (`covers()`: org -> unit subtree -> site), so PUT/archive/purge are exactly as
    strong as POST. Remove that `enforce` and these go 200."""
    db, _ = _env
    r = await client.post(f"/api/v1/admin/field-definitions/?organization_id={org_a.id}",
                          json=_body(key="org_wide"), headers=AUTH)
    fid, etag = r.json()["id"], r.json()["etag"]

    hdr, acc_id = await _login(client, "sitescoped@x.com")
    await _grant(db, acc_id, "fields.manage", code="site-fd",
                 organization_id=org_a.id, site_id=site_a.id)

    upd = await client.put(f"/api/v1/admin/field-definitions/{fid}",
                           json=_body(key="org_wide", required=True),
                           headers={**hdr, "If-Match": etag})
    assert upd.status_code == 403, upd.text
    purge = await client.post(f"/api/v1/admin/field-definitions/{fid}/purge",
                              headers={**hdr, "If-Match": etag})
    assert purge.status_code == 403, purge.text


@pytest.mark.asyncio
async def test_duplicate_key_is_409_not_500(client, org_a, admin_headers):
    """`audit.record` flushes AND swallows every exception by design ("audit must
    never break the auth flow"). If the new row's FIRST flush happened inside it, a
    duplicate-key IntegrityError would be absorbed there as a mere warning, leaving
    the transaction poisoned, and the commit would then raise PendingRollbackError
    as an unhandled 500. We flush BEFORE the audit so it surfaces as a clean 409.
    Redefining an existing key is the likeliest admin mistake there is."""
    first = await client.post(f"/api/v1/admin/field-definitions/?organization_id={org_a.id}",
                              json=_body(key="dup_key"), headers=admin_headers)
    assert first.status_code == 201, first.text
    second = await client.post(f"/api/v1/admin/field-definitions/?organization_id={org_a.id}",
                               json=_body(key="dup_key"), headers=admin_headers)
    assert second.status_code == 409, second.text


@pytest.mark.asyncio
async def test_creating_against_a_nonexistent_org_is_404_not_an_orphan_row(
        client, admin_headers):
    r = await client.post(
        "/api/v1/admin/field-definitions/?organization_id=does-not-exist",
        json=_body(key="orphan"), headers=admin_headers)
    assert r.status_code == 404, r.text


@pytest.mark.asyncio
async def test_flipping_indexed_at_the_50_field_cap_is_allowed(
        client, org_a, admin_headers, seed_50_fields):
    """The 50-field cap must NOT block an operation that adds no field. An org
    legitimately sitting AT its limit must still be able to flip an existing field
    to `indexed` — the old code refused it, and with a misleading "you already have
    50 fields" message on what was an INDEX request."""
    listed = await client.get(
        f"/api/v1/admin/field-definitions/?organization_id={org_a.id}",
        headers=admin_headers)
    assert listed.status_code == 200, listed.text
    row = listed.json()["items"][0]
    r = await client.put(
        f"/api/v1/admin/field-definitions/{row['id']}",
        json=_body(key=row["key"], indexed=True),
        headers={**admin_headers, "If-Match": row["etag"]})
    assert r.status_code == 200, r.text
    assert r.json()["indexed"] is True


@pytest.mark.asyncio
async def test_archive_is_reversible_and_the_value_was_never_lost(
        client, org_a, admin_headers, site_a):
    """Archive must be REVERSIBLE (the spec's word). Since `GET /schema` filters
    archived rows out, without `/unarchive` the field would be a one-way trapdoor.
    The values never left the JSONB, so restoring the definition restores the
    field intact."""
    r = await client.post(f"/api/v1/admin/field-definitions/?organization_id={org_a.id}",
                          json=_body(), headers=admin_headers)
    fid = r.json()["id"]
    await client.put(f"/api/v1/modules/location/sites/{site_a.id}",
                     json={"custom_fields": {"convention_no": "C-7"}},
                     headers=admin_headers)
    await client.post(f"/api/v1/admin/field-definitions/{fid}/archive",
                      headers=admin_headers)
    gone = await client.get(
        f"/api/v1/schema/site.custom_fields?organization_id={org_a.id}",
        headers=admin_headers)
    assert gone.json()["fields"] == []

    back = await client.post(f"/api/v1/admin/field-definitions/{fid}/unarchive",
                             headers=admin_headers)
    assert back.status_code == 200, back.text
    assert back.json()["archived"] is False
    restored = await client.get(
        f"/api/v1/schema/site.custom_fields?organization_id={org_a.id}",
        headers=admin_headers)
    assert [f["key"] for f in restored.json()["fields"]] == ["convention_no"]
    site = await client.get(f"/api/v1/modules/location/sites/{site_a.id}",
                            headers=admin_headers)
    assert site.json()["custom_fields"] == {"convention_no": "C-7"}


@pytest.mark.asyncio
async def test_archived_definition_stays_reachable_via_the_list(client, org_a,
                                                                admin_headers):
    """`GET /schema` returns `as_spec()`, which carries NO id, and filters archived
    rows out — so without this list route an archived definition would be
    permanently unaddressable (never purgeable, never restorable)."""
    r = await client.post(f"/api/v1/admin/field-definitions/?organization_id={org_a.id}",
                          json=_body(key="hidden_one"), headers=admin_headers)
    fid = r.json()["id"]
    await client.post(f"/api/v1/admin/field-definitions/{fid}/archive",
                      headers=admin_headers)

    default = await client.get(
        f"/api/v1/admin/field-definitions/?organization_id={org_a.id}",
        headers=admin_headers)
    assert [i["key"] for i in default.json()["items"]] == []

    with_archived = await client.get(
        f"/api/v1/admin/field-definitions/?organization_id={org_a.id}"
        f"&include_archived=true", headers=admin_headers)
    assert [i["key"] for i in with_archived.json()["items"]] == ["hidden_one"]
    assert with_archived.json()["items"][0]["id"] == fid


@pytest.mark.asyncio
async def test_richtext_is_sanitized_in_document_identity_too(client, admin_headers):
    """SEC-002: `DOCUMENT_IDENTITY` declares `legal_mentions` as a real `richtext`
    field, in a CODE-declared, always-active product schema, and `_coerce` treats
    richtext as a plain string. Sanitising only the DB-defined custom fields would
    have left the one richtext field the product itself ships wide open."""
    r = await client.post(
        "/api/v1/modules/organization/",
        json={"code": "rt-org", "legal_name": "RT",
              "document_identity": {
                  "legal_name": "RT SARL",
                  "legal_mentions": "<p>ok</p><script>alert(1)</script>"}},
        headers=admin_headers)
    assert r.status_code == 201, r.text
    stored = r.json()["document_identity"]["legal_mentions"]
    assert "<script>" not in stored
    assert "<p>ok</p>" in stored


# --- Cap bypass via archive/unarchive (Fix wave 1 review finding) ----------

@pytest.mark.asyncio
async def test_archive_then_create_cannot_bypass_the_field_cap(
        client, session, org_a, admin_headers, seed_50_fields):
    """The caps exist so ONE org cannot saturate the DB for every other
    tenant. Archived rows still occupy storage and still hold the
    (org, target, key) unique constraint — so they must count against the
    total cap. Purge is the deliberate escape valve, not archive."""
    from sqlalchemy import update

    from app.models.field_definition import FieldDefinition

    await session.execute(
        update(FieldDefinition)
        .where(FieldDefinition.organization_id == org_a.id)
        .values(archived=True))
    await session.commit()

    r = await client.post(
        f"/api/v1/admin/field-definitions/?organization_id={org_a.id}",
        json=_body(key="one_more_after_archiving_all"), headers=admin_headers)
    assert r.status_code == 422 and "50" in r.text, r.text


@pytest.mark.asyncio
async def test_unarchiving_beyond_the_active_cap_is_refused(
        client, org_a, admin_headers, seed_10_indexed_fields):
    """Un-archiving pushes a field back into the ACTIVE set. Under the chosen
    fix (archived rows do NOT count against the INDEXED cap — an archived
    field is not sortable, so it should not hold a live index), the indexed
    cap can be quietly exceeded via archive/refill/unarchive unless
    `_set_archived` re-checks it: fill the 10-indexed cap, archive one
    indexed field (frees a slot), create a new indexed field to refill to 10,
    then unarchive the first one — that pushes ACTIVE indexed count to 11 and
    must be refused, not silently allowed."""
    listed = await client.get(
        f"/api/v1/admin/field-definitions/?organization_id={org_a.id}",
        headers=admin_headers)
    victim = listed.json()["items"][0]

    arch = await client.post(
        f"/api/v1/admin/field-definitions/{victim['id']}/archive",
        headers=admin_headers)
    assert arch.status_code == 200, arch.text

    refill = await client.post(
        f"/api/v1/admin/field-definitions/?organization_id={org_a.id}",
        json=_body(key="refill_indexed", indexed=True), headers=admin_headers)
    assert refill.status_code == 201, refill.text

    unarch = await client.post(
        f"/api/v1/admin/field-definitions/{victim['id']}/unarchive",
        headers=admin_headers)
    assert unarch.status_code == 422 and "10" in unarch.text, unarch.text


@pytest.mark.asyncio
async def test_purging_frees_capacity(client, org_a, admin_headers, seed_50_fields):
    """Purge is the explicit, audited "I really mean it" operation — the
    escape valve archive deliberately is not."""
    listed = await client.get(
        f"/api/v1/admin/field-definitions/?organization_id={org_a.id}",
        headers=admin_headers)
    victim = listed.json()["items"][0]

    purge = await client.post(
        f"/api/v1/admin/field-definitions/{victim['id']}/purge",
        headers=admin_headers)
    assert purge.status_code == 200, purge.text

    r = await client.post(
        f"/api/v1/admin/field-definitions/?organization_id={org_a.id}",
        json=_body(key="after_purge"), headers=admin_headers)
    assert r.status_code == 201, r.text


@pytest.mark.asyncio
async def test_party_write_still_requires_a_global_grant(client, _env, org_a):
    """Party writes must stay GLOBALLY gated, never narrowable by a query param.

    A `Party` is GLOBAL directory data (no `organization_id` column). Its writes
    are gated by `require_permission("party.update")`, whose scope comes from
    `raw_scope_ids` — which harvests any query param called `org_id`/
    `organization_id`. With no such param present the request scope is GLOBAL,
    and `covers()` correctly rejects an org-scoped grant (only a global
    `party.*` grant may touch the shared directory).

    Historically (Task 13/15) `update_party` also accepted a `definitions_org_id`
    query param for the now-removed `party.custom_fields` allowlist flow —
    deliberately NOT named `organization_id` for exactly this reason. Fix wave 1
    removed `party.custom_fields` as an extensible target entirely (see
    `EXTENSIBLE_TARGETS`'s docstring), so `update_party` no longer declares that
    param at all; FastAPI silently drops an undeclared query param, so passing it
    here is now a no-op. This test still pins the load-bearing guarantee: no
    query param, past or hypothetical, may narrow a party write's scope from
    GLOBAL to org-scoped.
    """
    db, _ = _env
    from app.modules.party.models import Party
    async with db.session_factory() as s:
        party = Party(name="Global Directory Row")
        s.add(party)
        await s.commit()
        pid = party.id

    hdr, acc_id = await _login(client, "tenantadmin@x.com")
    await _grant(db, acc_id, "party.update", code="party-org-scoped",
                 organization_id=org_a.id)   # org-scoped, NOT global

    plain = await client.put(f"/api/v1/modules/party/parties/{pid}",
                             json={"name": "hijacked"}, headers=hdr)
    assert plain.status_code == 403, plain.text

    # The escalation attempt: name my own org via the (now-inert) legacy param,
    # hoping it narrows the scope.
    escalate = await client.put(
        f"/api/v1/modules/party/parties/{pid}?definitions_org_id={org_a.id}",
        json={"name": "hijacked"}, headers=hdr)
    assert escalate.status_code == 403, escalate.text
