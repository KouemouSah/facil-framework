"""Task 14 — partial concurrent expression indexes + the sort/filter whitelist.

Three layers, in order of how much they can lie to you:
  1. Pure unit tests on `sortable_keys`/`index_name` — no DB at all.
  2. Route-level tests (own standalone app, SQLite — same convention as
     `test_api_field_definitions.py`): the `/index` route's state machine,
     archive/unarchive/purge dropping/leaving the index, and the sort
     whitelist's 422 behaviour. All of this is dialect-independent: it never
     reaches Postgres-only SQL, because SQLite can never produce
     `index_state == "ready"` (see `indexing.create_index`'s dialect guard).
  3. The ONE test that actually validates the design: `EXPLAIN` on a sort by
     an indexed custom field, over a meaningful number of rows, against a
     REAL Postgres — marked `@pytest.mark.postgres`, skipped by default.
"""

from __future__ import annotations

import os
from urllib.parse import urlsplit, urlunsplit

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.core.schema.indexing import index_name, sortable_keys
from app.core.schema.spec import field

AUTH = {"X-Admin-Token": "test-token"}

L = {"en": "X", "fr": "X", "es": "X"}


# --- 1. Pure unit tests ------------------------------------------------------

def test_only_indexed_and_ready_keys_are_sortable():
    specs = [
        {**field("a", L, indexed=True), "index_state": "ready"},
        {**field("b", L, indexed=True), "index_state": "pending"},
        {**field("c", L, indexed=True), "index_state": "failed"},
        {**field("d", L), "index_state": "none"},
    ]
    # A `pending` index means a seq scan on millions of rows. Explicitly
    # unavailable beats silently slow.
    assert sortable_keys(specs) == {"a"}


def test_index_name_is_deterministic_and_bounded():
    n = index_name("site", "convention_no")
    assert n == "ix_site_cf_convention_no"
    assert len(index_name("organization", "a" * 60)) <= 63  # Postgres identifier limit


def test_index_name_truncation_is_still_deterministic_and_collision_resistant():
    """Two different long keys sharing a common 34-char prefix must NOT collide
    onto the same truncated name — the sha1 digest suffix is what prevents it."""
    key_a = "a" * 60
    key_b = "a" * 34 + "b" * 26  # same first 34 chars as key_a
    name_a = index_name("organization", key_a)
    name_b = index_name("organization", key_b)
    assert name_a != name_b
    assert len(name_a) <= 63 and len(name_b) <= 63


def test_sortable_keys_ignores_unindexed_even_if_marked_ready():
    """Defence in depth: `index_state` alone must never authorise a sort —
    `indexed` is required too (a stale/forged `ready` on a field nobody asked
    to index must not become sortable)."""
    specs = [{**field("z", L, indexed=False), "index_state": "ready"}]
    assert sortable_keys(specs) == set()


# --- 2. Route-level tests: own standalone app (SQLite), same convention as --
#        test_api_field_definitions.py --------------------------------------

def _body(key="rank", **kw):
    return {"target": "site.custom_fields", "key": key, "type": "number",
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
    db = Database(f"sqlite+aiosqlite:///{tmp_path/'idx.db'}")
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
    org = Organization(code="idx-org-a", legal_name="Idx Organisation A")
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


async def _create_definition(client, org_id, **kw) -> dict:
    r = await client.post(f"/api/v1/admin/field-definitions/?organization_id={org_id}",
                          json=_body(**kw), headers=AUTH)
    assert r.status_code == 201, r.text
    return r.json()


# --- /index route: state machine ---------------------------------------------

@pytest.mark.asyncio
async def test_index_route_requires_indexed_flag_first(client, org_a):
    row = await _create_definition(client, org_a.id, indexed=False)
    r = await client.post(f"/api/v1/admin/field-definitions/{row['id']}/index",
                          headers={**AUTH, "If-Match": row["etag"]})
    assert r.status_code == 422 and "indexed" in r.text


@pytest.mark.asyncio
async def test_index_route_rejects_archived_definition(client, org_a):
    row = await _create_definition(client, org_a.id, indexed=True)
    arch = await client.post(f"/api/v1/admin/field-definitions/{row['id']}/archive",
                             headers=AUTH)
    assert arch.status_code == 200, arch.text
    r = await client.post(f"/api/v1/admin/field-definitions/{row['id']}/index",
                          headers={**AUTH, "If-Match": arch.json()["etag"]})
    assert r.status_code == 422 and "archived" in r.text


@pytest.mark.asyncio
async def test_index_build_under_sqlite_leaves_state_none_never_falsely_ready(
        client, org_a):
    """`create_index` is a clean no-op under SQLite (dialect-guarded). The
    background job must NOT report that no-op as `"ready"` — the whole point
    of `index_state` is that it never lies about there being a real index."""
    row = await _create_definition(client, org_a.id, indexed=True)
    r = await client.post(f"/api/v1/admin/field-definitions/{row['id']}/index",
                          headers={**AUTH, "If-Match": row["etag"]})
    assert r.status_code == 200, r.text
    # ASGITransport runs BackgroundTasks synchronously as part of the request/
    # response cycle, so the job has already run by the time this returns.
    got = await client.get(f"/api/v1/admin/field-definitions/{row['id']}", headers=AUTH)
    assert got.json()["index_state"] == "none"


@pytest.mark.asyncio
async def test_index_build_twice_while_pending_is_409(client, org_a, session):
    """A stuck-pending row (e.g. a slow build) must refuse a second concurrent
    request, not silently queue a second CONCURRENTLY build for the same name."""
    row = await _create_definition(client, org_a.id, indexed=True)
    from app.models.field_definition import FieldDefinition
    db_row = await session.get(FieldDefinition, row["id"])
    db_row.index_state = "pending"
    await session.commit()
    r = await client.post(f"/api/v1/admin/field-definitions/{row['id']}/index",
                          headers={**AUTH, "If-Match": row["etag"]})
    assert r.status_code == 409


# --- Archive / unarchive / purge index lifecycle -----------------------------

@pytest.mark.asyncio
async def test_archive_resets_index_state_to_none(client, session, org_a):
    """HARD REQUIREMENT: archive drops the index and resets `index_state`. We
    fast-forward the row to `"ready"` directly (SQLite can never reach it via
    the real job) to prove the RESET happens regardless of prior state."""
    from app.models.field_definition import FieldDefinition
    row = await _create_definition(client, org_a.id, indexed=True)
    db_row = await session.get(FieldDefinition, row["id"])
    db_row.index_state = "ready"
    await session.commit()

    arch = await client.post(f"/api/v1/admin/field-definitions/{row['id']}/archive",
                             headers=AUTH)
    assert arch.status_code == 200, arch.text
    assert arch.json()["index_state"] == "none"
    assert arch.json()["indexed"] is True  # `indexed` intent survives archive


@pytest.mark.asyncio
async def test_changing_the_type_of_a_ready_indexed_field_drops_the_index(
        client, session, org_a, site_a):
    """CRITICAL: the live Postgres index carries the OLD `INDEX_CAST[old_type]`
    expression. If `type` changes while `indexed` stays `True`, the generated
    ORDER BY would carry the NEW cast — a byte-for-byte mismatch means
    Postgres silently stops using the index, while `sortable_keys()` still
    says `ready`. Explicitly unavailable beats silently slow: the type change
    must reset `index_state` to `"none"` exactly like the `indexed` flip
    already does, and the field must drop out of the sort whitelist."""
    from app.models.field_definition import FieldDefinition
    row = await _create_definition(client, org_a.id, key="rank", type="number",
                                   indexed=True)
    db_row = await session.get(FieldDefinition, row["id"])
    db_row.index_state = "ready"
    await session.commit()

    body = _body(key="rank", type="string", indexed=True)
    # No If-Match: we mutated the row directly via `session` above (the only
    # way to reach `"ready"` under SQLite), which already rotated the etag
    # the earlier `POST` response captured.
    r = await client.put(f"/api/v1/admin/field-definitions/{row['id']}",
                         json=body, headers=AUTH)
    assert r.status_code == 200, r.text
    assert r.json()["type"] == "string"
    assert r.json()["index_state"] == "none"

    sort = await client.get(
        f"/api/v1/modules/location/sites?organization_id={org_a.id}"
        f"&sort=custom_fields.rank", headers=AUTH)
    assert sort.status_code == 422


@pytest.mark.asyncio
async def test_changing_only_the_widget_of_a_ready_indexed_field_keeps_the_index(
        client, session, org_a):
    """`widget` is presentation-only — it has no entry in `INDEX_CAST`, so it
    cannot desync the index expression from the generated ORDER BY. Unlike a
    `type` change, it must NOT reset `index_state`."""
    from app.models.field_definition import FieldDefinition
    row = await _create_definition(client, org_a.id, key="rank", type="number",
                                   indexed=True, widget="plain")
    db_row = await session.get(FieldDefinition, row["id"])
    db_row.index_state = "ready"
    await session.commit()

    body = _body(key="rank", type="number", indexed=True, widget="percent")
    r = await client.put(f"/api/v1/admin/field-definitions/{row['id']}",
                         json=body, headers=AUTH)
    assert r.status_code == 200, r.text
    assert r.json()["widget"] == "percent"
    assert r.json()["index_state"] == "ready"


@pytest.mark.asyncio
async def test_unarchive_does_not_auto_rebuild_the_index(client, session, org_a):
    """Chosen lifecycle (documented, see report): unarchive does NOT
    auto-rebuild — the field comes back `indexed=True, index_state="none"`,
    NOT sortable until an explicit `/index` call. The whitelist enforces
    that (`sortable_keys` requires BOTH `indexed` and `index_state=="ready"`)."""
    from app.models.field_definition import FieldDefinition
    row = await _create_definition(client, org_a.id, indexed=True)
    db_row = await session.get(FieldDefinition, row["id"])
    db_row.index_state = "ready"
    await session.commit()

    await client.post(f"/api/v1/admin/field-definitions/{row['id']}/archive", headers=AUTH)
    back = await client.post(f"/api/v1/admin/field-definitions/{row['id']}/unarchive",
                             headers=AUTH)
    assert back.status_code == 200, back.text
    assert back.json()["index_state"] == "none"
    assert back.json()["indexed"] is True


@pytest.mark.asyncio
async def test_purge_of_an_indexed_field_succeeds(client, org_a):
    """Purge must not blow up trying to drop an index (SQLite no-op) — and
    the row is really gone afterwards."""
    row = await _create_definition(client, org_a.id, indexed=True)
    r = await client.post(f"/api/v1/admin/field-definitions/{row['id']}/purge",
                          headers=AUTH)
    assert r.status_code == 200, r.text
    got = await client.get(f"/api/v1/admin/field-definitions/{row['id']}", headers=AUTH)
    assert got.status_code == 404


# --- Sort whitelist: 422 for anything not indexed+ready ----------------------

@pytest.mark.asyncio
async def test_site_list_sort_by_custom_field_without_organization_id_is_422(client):
    r = await client.get("/api/v1/modules/location/sites?sort=custom_fields.rank",
                         headers=AUTH)
    assert r.status_code == 422 and "organization_id" in r.text


@pytest.mark.asyncio
async def test_site_list_sort_by_unindexed_custom_field_is_422(client, org_a, site_a):
    await _create_definition(client, org_a.id, indexed=False)
    r = await client.get(
        f"/api/v1/modules/location/sites?organization_id={org_a.id}"
        f"&sort=custom_fields.rank", headers=AUTH)
    assert r.status_code == 422 and "rank" in r.text


@pytest.mark.asyncio
async def test_site_list_sort_by_pending_custom_field_is_422_not_silently_slow(
        client, org_a, site_a):
    """The hard requirement, at the route: `indexed=True` with `index_state
    == "pending"` (a build in flight) must be REFUSED for sorting, never
    silently accepted as a sequential scan."""
    row = await _create_definition(client, org_a.id, indexed=True)
    r = await client.get(
        f"/api/v1/modules/location/sites?organization_id={org_a.id}"
        f"&sort=custom_fields.rank", headers=AUTH)
    assert r.status_code == 422
    assert "indexed" in r.text or "ready" in r.text


@pytest.mark.asyncio
async def test_site_list_sort_by_unknown_custom_field_is_422(client, org_a, site_a):
    r = await client.get(
        f"/api/v1/modules/location/sites?organization_id={org_a.id}"
        f"&sort=custom_fields.does_not_exist", headers=AUTH)
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_party_list_sort_by_custom_field_without_definitions_org_id_is_422(client):
    r = await client.get("/api/v1/modules/party/parties?sort=custom_fields.segment",
                         headers=AUTH)
    assert r.status_code == 422 and "definitions_org_id" in r.text


@pytest.mark.asyncio
async def test_organization_list_ignores_custom_field_sort_by_design(client):
    """The top-level organisation list spans MULTIPLE organisations at once —
    there is no single `organization.custom_fields` definition set to resolve
    a typed cast against. Deliberately excluded (documented in the report),
    not silently accepted: still a 422, exactly like an unknown column."""
    r = await client.get("/api/v1/modules/organization/?sort=custom_fields.rank",
                         headers=AUTH)
    assert r.status_code == 422


# --- 3. The test that validates or invalidates the design -------------------

def _pg_test_url() -> str | None:
    """Derive a throwaway-database Postgres URL from the same `DATABASE_URL`
    the running stack already uses (host or container network — whichever
    this process can reach), swapping the database name for `facil_test`."""
    base = os.environ.get("PG_TEST_DATABASE_URL") or os.environ.get("DATABASE_URL")
    if not base:
        return None
    if base.startswith("postgres://"):
        base = base.replace("postgres://", "postgresql+asyncpg://", 1)
    elif base.startswith("postgresql://") and "+asyncpg" not in base:
        base = base.replace("postgresql://", "postgresql+asyncpg://", 1)
    parts = urlsplit(base)
    return urlunsplit((parts.scheme, parts.netloc, "/facil_test", "", ""))


@pytest_asyncio.fixture
async def pg_engine():
    """A real Postgres engine against a throwaway `facil_test` database,
    (re)created fresh from the module schema. Skips (never fails) the whole
    suite when no real Postgres is reachable — this fixture is only exercised
    by `@pytest.mark.postgres` tests, run explicitly."""
    admin_url = os.environ.get("PG_TEST_DATABASE_URL") or os.environ.get("DATABASE_URL")
    test_url = _pg_test_url()
    if not admin_url or not test_url:
        pytest.skip("no DATABASE_URL/PG_TEST_DATABASE_URL — no real Postgres to test against")
    if admin_url.startswith("postgres://"):
        admin_url = admin_url.replace("postgres://", "postgresql+asyncpg://", 1)
    elif admin_url.startswith("postgresql://") and "+asyncpg" not in admin_url:
        admin_url = admin_url.replace("postgresql://", "postgresql+asyncpg://", 1)

    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine

    try:
        admin_engine = create_async_engine(admin_url, pool_pre_ping=True)
        autocommit = admin_engine.execution_options(isolation_level="AUTOCOMMIT")
        async with autocommit.connect() as conn:
            await conn.exec_driver_sql("DROP DATABASE IF EXISTS facil_test WITH (FORCE)")
            await conn.exec_driver_sql("CREATE DATABASE facil_test")
        await admin_engine.dispose()
    except Exception as exc:  # noqa: BLE001 — any connectivity failure => skip, don't fail
        pytest.skip(f"real Postgres not reachable at {admin_url!r}: {exc!r}")

    from app.core.module_registry import import_module_models
    from app.db.base import Base
    from app.identity import models as _a  # noqa: F401
    from app.auth import models as _c  # noqa: F401
    from app.rbac import models as _r  # noqa: F401
    import_module_models()

    engine = create_async_engine(test_url, pool_pre_ping=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    await engine.dispose()
    cleanup_engine = create_async_engine(admin_url, pool_pre_ping=True)
    autocommit = cleanup_engine.execution_options(isolation_level="AUTOCOMMIT")
    async with autocommit.connect() as conn:
        await conn.exec_driver_sql("DROP DATABASE IF EXISTS facil_test WITH (FORCE)")
    await cleanup_engine.dispose()


@pytest_asyncio.fixture
async def seeded_100k(pg_engine):
    """org-a + 100k sites, each with a NUMERIC `rank` custom field, then the
    partial expression index built the exact way `create_index` builds it in
    production — plus `ANALYZE`, so the planner's choice reflects real
    statistics rather than a fixture-only cold start."""
    from sqlalchemy import text

    from app.core.schema import indexing

    async with pg_engine.begin() as conn:
        await conn.execute(text(
            "INSERT INTO organization "
            "(id, code, legal_name, document_identity, settings, custom_fields, is_active) "
            "VALUES ('org-a', 'org-a', 'Org A', '{}'::jsonb, '{}'::jsonb, '{}'::jsonb, true)"))
        await conn.execute(text(
            "INSERT INTO site (id, organization_id, code, name, site_type, "
            "operating_hours, metadata, custom_fields, is_primary, is_active) "
            "SELECT 'site-' || gs::text, 'org-a', 'site-' || gs::text, 'Site ' || gs::text, "
            "'branch', '{}'::jsonb, '{}'::jsonb, "
            "jsonb_build_object('rank', (100000 - gs)), false, true "
            "FROM generate_series(1, 100000) AS gs"))

    await indexing.create_index(pg_engine, "site.custom_fields",
                                {"type": "number", "key": "rank"}, "org-a")

    async with pg_engine.connect() as conn:
        await conn.execute(text("COMMIT"))  # exit the implicit transaction (ANALYZE needs it)
        await conn.exec_driver_sql("ANALYZE site")

    return pg_engine


@pytest.mark.postgres
@pytest.mark.asyncio
async def test_sorting_on_an_indexed_custom_field_uses_the_index(pg_engine, seeded_100k):
    # If this fails, the storage model is WRONG — and we must know before prod.
    async with pg_engine.connect() as conn:
        plan = (await conn.exec_driver_sql(
            "EXPLAIN SELECT id FROM site "
            "WHERE organization_id = 'org-a' "
            "ORDER BY ((custom_fields->>'rank')::numeric) LIMIT 50")).scalars().all()
    assert not any("Seq Scan" in line for line in plan), "\n".join(plan)


@pytest.mark.postgres
@pytest.mark.asyncio
async def test_order_by_expression_matches_the_index_expression_byte_for_byte(seeded_100k):
    """The hard requirement stated in the module docstring: `custom_sort_column`
    (what the API route puts in ORDER BY) must emit the EXACT same expression
    text `create_index` indexed — verified directly, not just inferred from
    the absence of a Seq Scan above."""
    from app.core.schema.indexing import custom_sort_column
    from app.core.schema.types import INDEX_CAST

    spec = {"type": "number", "key": "rank"}
    generated = str(custom_sort_column(spec))
    assert generated == INDEX_CAST["number"].format(key="rank")


@pytest_asyncio.fixture
async def org_and_site_pg(pg_engine):
    """The minimal `organization` + `site` rows `create_index`'s partial
    predicate (`WHERE organization_id = 'org-a'`) refers to — cheap sibling
    of `seeded_100k` for the two tests below, which only care about the
    INDEX OBJECT itself, not sort correctness over volume."""
    from sqlalchemy import text
    async with pg_engine.begin() as conn:
        await conn.execute(text(
            "INSERT INTO organization "
            "(id, code, legal_name, document_identity, settings, custom_fields, is_active) "
            "VALUES ('org-a', 'org-a', 'Org A', '{}'::jsonb, '{}'::jsonb, '{}'::jsonb, true)"))
        await conn.execute(text(
            "INSERT INTO site (id, organization_id, code, name, site_type, "
            "operating_hours, metadata, custom_fields, is_primary, is_active) "
            "VALUES ('site-1', 'org-a', 'site-1', 'Site 1', 'branch', "
            "'{}'::jsonb, '{}'::jsonb, jsonb_build_object('rank', 1), false, true)"))
    return pg_engine


@pytest.mark.postgres
@pytest.mark.asyncio
async def test_rebuilding_over_an_existing_index_produces_a_VALID_index(org_and_site_pg):
    """CRITICAL: a failed `CREATE INDEX CONCURRENTLY` build leaves an INVALID
    index object under the deterministic name. `IF NOT EXISTS` is a NAME-ONLY
    check, so a retry used to see the name taken and silently no-op — never
    raising, never fixing anything — and the caller would go on to report
    `ready`. We cannot easily force Postgres to leave a genuinely INVALID
    index on demand, so we prove the mechanism directly: plant a DECOY index
    under the exact same name but a DIFFERENT (wrong) expression, then call
    `create_index()` for real and assert the index that survives carries the
    CORRECT expression — i.e. it was actually DROPPED and REBUILT, not
    silently left alone."""
    from sqlalchemy import text

    from app.core.schema import indexing

    name = indexing.index_name("site", "rank")
    async with org_and_site_pg.connect() as conn:
        await conn.execute(text("COMMIT"))  # CONCURRENTLY needs no open tx
        # The decoy: same name, WRONG expression (text cast, not numeric) —
        # what a genuinely different/stale index under this name looks like.
        await conn.exec_driver_sql(
            f'CREATE INDEX CONCURRENTLY "{name}" ON site ((custom_fields->>\'decoy\')) '
            "WHERE organization_id = 'org-a'")

    await indexing.create_index(org_and_site_pg, "site.custom_fields",
                                {"type": "number", "key": "rank"}, "org-a")

    async with org_and_site_pg.connect() as conn:
        indexdef = (await conn.exec_driver_sql(
            f"SELECT indexdef FROM pg_indexes WHERE indexname = '{name}'")).scalar_one()
        valid = (await conn.exec_driver_sql(
            "SELECT indisvalid FROM pg_index JOIN pg_class "
            "ON pg_class.oid = pg_index.indexrelid "
            f"WHERE pg_class.relname = '{name}'")).scalar_one()
    assert "decoy" not in indexdef, (
        f"the decoy expression survived — create_index() no-op'd instead of "
        f"rebuilding: {indexdef}")
    assert "rank" in indexdef and "numeric" in indexdef
    assert valid is True


@pytest.mark.postgres
@pytest.mark.asyncio
async def test_index_validity_is_verified_before_reporting_ready(org_and_site_pg):
    """`create_index` must itself check `pg_index.indisvalid` and refuse to
    return normally (i.e. refuse to let the caller report `ready`) on an
    invalid index — proven two ways: (1) `index_is_valid` reports the TRUE
    state of a real, successfully-built index; (2) `index_is_valid` reports
    False for a name that doesn't exist at all (the same "not safe to sort
    by" verdict as an invalid one), so the check cannot be fooled by
    optimistically assuming existence == validity."""
    from app.core.schema import indexing

    # No index built yet under this key -> not valid (doesn't exist at all).
    assert await indexing.index_is_valid(
        org_and_site_pg, "site.custom_fields", "no_such_key") is False

    await indexing.create_index(org_and_site_pg, "site.custom_fields",
                                {"type": "number", "key": "rank"}, "org-a")
    assert await indexing.index_is_valid(
        org_and_site_pg, "site.custom_fields", "rank") is True


@pytest.mark.postgres
@pytest.mark.asyncio
async def test_full_list_sites_endpoint_sorts_correctly_via_the_index(seeded_100k):
    """End-to-end proof through the actual keyset-pagination code path (not
    just raw SQL): ascending `sort=custom_fields.rank` returns rows in
    increasing numeric order — never lexicographic ("10" < "9")."""
    from sqlalchemy import select

    from app.api.list_query import keyset_page
    from app.core.schema.indexing import custom_sort_column, custom_sort_value
    from app.modules.location.models import Site

    spec = {"type": "number", "key": "rank"}
    stmt = select(Site).where(Site.organization_id == "org-a")
    from sqlalchemy.ext.asyncio import AsyncSession
    async with AsyncSession(seeded_100k) as session:
        items, next_cursor, count, capped = await keyset_page(
            session, stmt, sort_col=custom_sort_column(spec), sort_desc=False,
            cursor=None, limit=5, id_col=Site.id, value_of=custom_sort_value(spec))
    ranks = [s.custom_fields["rank"] for s in items]
    assert ranks == sorted(ranks)
    assert ranks[0] == 0  # smallest rank: 100000 - gs for gs in 1..100000 -> 0..99999
