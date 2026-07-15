"""D2 — the resolved-schema cache (spec §7 promised it; no SP1 task delivered
it). Three layers:

  1. Pure unit tests on `core.schema.cache` — no DB, no HTTP.
  2. `GET /api/v1/schema/{target}` actually USES the cache: repeated reads
     for the same (organization_id, target) do not re-resolve from the DB.
  3. THE test that must have teeth: cache ISOLATION — an entry populated by
     org A must never answer for org B. Also: a break-glass/global principal
     reading the SAME org+target as a scope-limited one must get the SAME
     (correctly-scoped) entry, never a principal-poisoned one.
  4. Every definition write path (create/update/archive/unarchive/purge/
     both index-state transitions) invalidates its own cache entry.
"""

from __future__ import annotations

import pytest

from tests.conftest import AUTH

L = {"en": "X", "fr": "X", "es": "X"}


def _body(key: str = "rank", **kw) -> dict:
    return {"target": "site.custom_fields", "key": key, "type": "string",
           "label": L, **kw}


async def _make_org(db, code: str) -> str:
    from app.modules.organization.models import Organization
    async with db.session_factory() as s:
        org = Organization(code=code, legal_name=code)
        s.add(org)
        await s.commit()
        return org.id


# --- 1. Pure unit tests on core.schema.cache ---------------------------------

@pytest.mark.asyncio
async def test_get_is_none_on_a_miss_and_with_no_cache_configured():
    from app.core.cache import MemoryCache
    from app.core.schema import cache as schema_cache
    assert await schema_cache.get(None, "org-a", "site.custom_fields") is None
    assert await schema_cache.get(MemoryCache(), "org-a", "site.custom_fields") is None


@pytest.mark.asyncio
async def test_set_then_get_round_trips_the_specs():
    from app.core.cache import MemoryCache
    from app.core.schema import cache as schema_cache
    cache = MemoryCache()
    specs = [{"key": "rank", "type": "number"}]
    await schema_cache.set(cache, "org-a", "site.custom_fields", specs)
    assert await schema_cache.get(cache, "org-a", "site.custom_fields") == specs


@pytest.mark.asyncio
async def test_key_is_a_pure_function_of_org_and_target_only():
    """THE guard, at the unit level: two DIFFERENT orgs (same target) must
    never collide on the same cache entry, and the same org with two
    DIFFERENT targets must not collide either."""
    from app.core.cache import MemoryCache
    from app.core.schema import cache as schema_cache
    cache = MemoryCache()
    await schema_cache.set(cache, "org-a", "site.custom_fields", [{"key": "a"}])
    await schema_cache.set(cache, "org-b", "site.custom_fields", [{"key": "b"}])
    await schema_cache.set(cache, "org-a", "org_unit.custom_fields", [{"key": "c"}])
    assert await schema_cache.get(cache, "org-a", "site.custom_fields") == [{"key": "a"}]
    assert await schema_cache.get(cache, "org-b", "site.custom_fields") == [{"key": "b"}]
    assert await schema_cache.get(cache, "org-a", "org_unit.custom_fields") == [{"key": "c"}]


@pytest.mark.asyncio
async def test_invalidate_evicts_only_the_named_entry():
    from app.core.cache import MemoryCache
    from app.core.schema import cache as schema_cache
    cache = MemoryCache()
    await schema_cache.set(cache, "org-a", "site.custom_fields", [{"key": "a"}])
    await schema_cache.set(cache, "org-b", "site.custom_fields", [{"key": "b"}])
    await schema_cache.invalidate(cache, "org-a", "site.custom_fields")
    assert await schema_cache.get(cache, "org-a", "site.custom_fields") is None
    assert await schema_cache.get(cache, "org-b", "site.custom_fields") == [{"key": "b"}]


@pytest.mark.asyncio
async def test_invalidate_and_set_are_no_ops_with_no_cache_configured():
    from app.core.schema import cache as schema_cache
    await schema_cache.invalidate(None, "org-a", "site.custom_fields")  # must not raise
    await schema_cache.set(None, "org-a", "site.custom_fields", [{"key": "a"}])  # must not raise


# --- 2. GET /api/v1/schema/{target} actually uses the cache ------------------

@pytest.mark.asyncio
async def test_repeated_schema_reads_resolve_from_the_db_exactly_once(client, monkeypatch):
    ac, db = client
    from app.core.schema import repository as schema_repo
    org_id = await _make_org(db, "cache-repeat")

    calls = {"n": 0}
    orig = schema_repo.definitions_for

    async def _counting(*a, **kw):
        calls["n"] += 1
        return await orig(*a, **kw)

    monkeypatch.setattr(schema_repo, "definitions_for", _counting)

    for _ in range(5):
        r = await ac.get(
            f"/api/v1/schema/site.custom_fields?organization_id={org_id}", headers=AUTH)
        assert r.status_code == 200

    assert calls["n"] == 1, (
        f"expected exactly 1 DB resolution across 5 reads, measured {calls['n']} — "
        "the cache is not being hit on repeat reads")


@pytest.mark.asyncio
async def test_a_different_target_for_the_same_org_is_its_own_cache_entry(client, monkeypatch):
    ac, db = client
    from app.core.schema import repository as schema_repo
    org_id = await _make_org(db, "cache-two-targets")

    calls = {"n": 0}
    orig = schema_repo.definitions_for

    async def _counting(*a, **kw):
        calls["n"] += 1
        return await orig(*a, **kw)

    monkeypatch.setattr(schema_repo, "definitions_for", _counting)

    await ac.get(f"/api/v1/schema/site.custom_fields?organization_id={org_id}", headers=AUTH)
    await ac.get(f"/api/v1/schema/org_unit.custom_fields?organization_id={org_id}", headers=AUTH)
    assert calls["n"] == 2


# --- 3. THE test that must have teeth: cache isolation -----------------------

@pytest.mark.asyncio
async def test_cache_never_serves_org_As_definitions_to_org_B(client):
    """MANDATORY isolation test. Org A defines a field and resolves its
    schema (populating the cache entry for (org_a, site.custom_fields)). Org
    B then resolves the SAME target and must get its OWN (empty) schema —
    never org A's field.

    THE EXACT CHANGE THAT WOULD BREAK THIS: dropping `organization_id` from
    `core.schema.cache._key()` (e.g. keying by `target` alone, or by any
    value not equal to the exact org being resolved) — verified manually by
    reverting `_key` to `f"schema:resolved:v1:{target}"` and re-running this
    test, which then fails with org B seeing `only_a` in its fields."""
    ac, db = client
    org_a_id = await _make_org(db, "iso-org-a")
    org_b_id = await _make_org(db, "iso-org-b")

    created = await ac.post(
        f"/api/v1/admin/field-definitions/?organization_id={org_a_id}",
        json=_body(key="only_a"), headers=AUTH)
    assert created.status_code == 201, created.text

    ra = await ac.get(
        f"/api/v1/schema/site.custom_fields?organization_id={org_a_id}", headers=AUTH)
    assert ra.status_code == 200
    assert {f["key"] for f in ra.json()["fields"]} == {"only_a"}

    rb = await ac.get(
        f"/api/v1/schema/site.custom_fields?organization_id={org_b_id}", headers=AUTH)
    assert rb.status_code == 200
    assert rb.json()["fields"] == [], (
        "LEAK: org B's resolved-schema cache entry served org A's field — "
        "the cache key is no longer a pure function of organization_id")


@pytest.mark.asyncio
async def test_break_glass_principal_does_not_poison_the_cache_for_a_scoped_one(client):
    """A break-glass/global principal (ADMIN_TOKEN, unrestricted `visible_orgs`)
    and a principal SCOPE-LIMITED to org A must see the IDENTICAL resolved
    schema for org A — proving the cache entry is keyed by the org being
    resolved, never by who is asking. If the key ever folded in the calling
    principal, this would degrade to a cache that simply never hits across
    principals (a correctness smell, not just a perf one) or, worse, could
    let a global principal's broader view leak under a scoped principal's
    read of the SAME org — this test exercises exactly that shared path."""
    from app.rbac.models import AccountRole, Role, RolePermission

    ac, db = client
    org_a_id = await _make_org(db, "iso-org-scoped")

    created = await ac.post(
        f"/api/v1/admin/field-definitions/?organization_id={org_a_id}",
        json=_body(key="shared_field"), headers=AUTH)
    assert created.status_code == 201, created.text

    # Global/break-glass principal resolves first — populates the cache.
    r_global = await ac.get(
        f"/api/v1/schema/site.custom_fields?organization_id={org_a_id}", headers=AUTH)
    assert r_global.status_code == 200
    assert {f["key"] for f in r_global.json()["fields"]} == {"shared_field"}

    # A principal scope-limited to org A ONLY (organization.read grant).
    await ac.post("/api/v1/auth/register",
                  json={"password": "Sup3rStr0ng!pw", "email": "scoped@x.com"})
    login = await ac.post("/api/v1/auth/login",
                          json={"identifier": "scoped@x.com", "password": "Sup3rStr0ng!pw"})
    assert login.status_code == 200, login.text
    acc_id = login.json()["account"]["id"]
    hdr = {"Authorization": f"Bearer {login.json()['access']}"}

    async with db.session_factory() as s:
        role = Role(code="scoped-reader", name="scoped-reader", is_system=False)
        s.add(role)
        await s.flush()
        s.add(RolePermission(role_id=role.id, permission_code="organization.read"))
        s.add(AccountRole(account_id=acc_id, role_id=role.id, organization_id=org_a_id))
        await s.commit()

    r_scoped = await ac.get(
        f"/api/v1/schema/site.custom_fields?organization_id={org_a_id}", headers=hdr)
    assert r_scoped.status_code == 200
    assert {f["key"] for f in r_scoped.json()["fields"]} == {"shared_field"}, (
        "the scope-limited principal did not see the same cached entry the "
        "break-glass principal populated — the cache is not shared correctly "
        "across principals for the SAME organisation")


# --- 4. Every write path invalidates its own entry ---------------------------

@pytest.mark.asyncio
async def test_create_invalidates_the_cache(client):
    ac, db = client
    org_id = await _make_org(db, "cache-create")
    r0 = await ac.get(
        f"/api/v1/schema/site.custom_fields?organization_id={org_id}", headers=AUTH)
    assert r0.json()["fields"] == []  # populates the (now stale-to-be) cache entry

    created = await ac.post(
        f"/api/v1/admin/field-definitions/?organization_id={org_id}",
        json=_body(key="new_field"), headers=AUTH)
    assert created.status_code == 201, created.text

    r1 = await ac.get(
        f"/api/v1/schema/site.custom_fields?organization_id={org_id}", headers=AUTH)
    assert {f["key"] for f in r1.json()["fields"]} == {"new_field"}, (
        "stale cache: the schema read did not reflect the field just created")


@pytest.mark.asyncio
async def test_update_invalidates_the_cache(client):
    ac, db = client
    org_id = await _make_org(db, "cache-update")
    created = await ac.post(
        f"/api/v1/admin/field-definitions/?organization_id={org_id}",
        json=_body(key="convention_no"), headers=AUTH)
    assert created.status_code == 201, created.text
    fid, etag = created.json()["id"], created.json()["etag"]

    r0 = await ac.get(
        f"/api/v1/schema/site.custom_fields?organization_id={org_id}", headers=AUTH)
    assert r0.json()["fields"][0]["required"] is False  # populates the cache

    upd = await ac.put(f"/api/v1/admin/field-definitions/{fid}",
                       json=_body(key="convention_no", required=True),
                       headers={**AUTH, "If-Match": etag})
    assert upd.status_code == 200, upd.text

    r1 = await ac.get(
        f"/api/v1/schema/site.custom_fields?organization_id={org_id}", headers=AUTH)
    assert r1.json()["fields"][0]["required"] is True, (
        "stale cache: the schema read did not reflect the update")


@pytest.mark.asyncio
async def test_archive_invalidates_the_cache(client):
    ac, db = client
    org_id = await _make_org(db, "cache-archive")
    created = await ac.post(
        f"/api/v1/admin/field-definitions/?organization_id={org_id}",
        json=_body(key="archivable"), headers=AUTH)
    assert created.status_code == 201, created.text
    fid = created.json()["id"]

    r0 = await ac.get(
        f"/api/v1/schema/site.custom_fields?organization_id={org_id}", headers=AUTH)
    assert {f["key"] for f in r0.json()["fields"]} == {"archivable"}  # populates the cache

    arch = await ac.post(f"/api/v1/admin/field-definitions/{fid}/archive", headers=AUTH)
    assert arch.status_code == 200, arch.text

    r1 = await ac.get(
        f"/api/v1/schema/site.custom_fields?organization_id={org_id}", headers=AUTH)
    assert r1.json()["fields"] == [], (
        "stale cache: an archived field is still showing up on the resolved schema")


@pytest.mark.asyncio
async def test_unarchive_invalidates_the_cache(client):
    ac, db = client
    org_id = await _make_org(db, "cache-unarchive")
    created = await ac.post(
        f"/api/v1/admin/field-definitions/?organization_id={org_id}",
        json=_body(key="restorable"), headers=AUTH)
    assert created.status_code == 201, created.text
    fid = created.json()["id"]
    await ac.post(f"/api/v1/admin/field-definitions/{fid}/archive", headers=AUTH)

    r0 = await ac.get(
        f"/api/v1/schema/site.custom_fields?organization_id={org_id}", headers=AUTH)
    assert r0.json()["fields"] == []  # populates the cache with the archived state

    back = await ac.post(f"/api/v1/admin/field-definitions/{fid}/unarchive", headers=AUTH)
    assert back.status_code == 200, back.text

    r1 = await ac.get(
        f"/api/v1/schema/site.custom_fields?organization_id={org_id}", headers=AUTH)
    assert {f["key"] for f in r1.json()["fields"]} == {"restorable"}, (
        "stale cache: an unarchived field is not showing back up on the resolved schema")


@pytest.mark.asyncio
async def test_purge_invalidates_the_cache(client):
    ac, db = client
    org_id = await _make_org(db, "cache-purge")
    created = await ac.post(
        f"/api/v1/admin/field-definitions/?organization_id={org_id}",
        json=_body(key="purgeable"), headers=AUTH)
    assert created.status_code == 201, created.text
    fid = created.json()["id"]

    r0 = await ac.get(
        f"/api/v1/schema/site.custom_fields?organization_id={org_id}", headers=AUTH)
    assert {f["key"] for f in r0.json()["fields"]} == {"purgeable"}  # populates the cache

    purged = await ac.post(f"/api/v1/admin/field-definitions/{fid}/purge", headers=AUTH)
    assert purged.status_code == 200, purged.text

    r1 = await ac.get(
        f"/api/v1/schema/site.custom_fields?organization_id={org_id}", headers=AUTH)
    assert r1.json()["fields"] == [], (
        "stale cache: a purged field is still showing up on the resolved schema")


@pytest.mark.asyncio
async def test_index_pending_transition_invalidates_the_cache(client, monkeypatch):
    """The `/index` request itself flips `index_state` to `"pending"` and
    commits BEFORE the background job runs. Isolate that transition from the
    background job's own (separately tested below) invalidation by
    neutralising `_run_index_build` — otherwise, under SQLite,
    `ASGITransport` runs the background task synchronously and the terminal
    "none" would mask whether the PENDING transition itself invalidated
    anything."""
    ac, db = client
    from app.api import admin_field_definitions as afd

    async def _noop(*_a, **_kw) -> None:
        return None

    monkeypatch.setattr(afd, "_run_index_build", _noop)

    org_id = await _make_org(db, "cache-index-pending")
    created = await ac.post(
        f"/api/v1/admin/field-definitions/?organization_id={org_id}",
        json=_body(key="rank", type="number", indexed=True), headers=AUTH)
    assert created.status_code == 201, created.text
    fid, etag = created.json()["id"], created.json()["etag"]

    r0 = await ac.get(
        f"/api/v1/schema/site.custom_fields?organization_id={org_id}", headers=AUTH)
    assert r0.json()["fields"][0]["index_state"] == "none"  # populates the cache

    idx = await ac.post(f"/api/v1/admin/field-definitions/{fid}/index",
                        headers={**AUTH, "If-Match": etag})
    assert idx.status_code == 200, idx.text

    r1 = await ac.get(
        f"/api/v1/schema/site.custom_fields?organization_id={org_id}", headers=AUTH)
    assert r1.json()["fields"][0]["index_state"] == "pending", (
        "stale cache: the resolved schema still reports the pre-build index_state")


@pytest.mark.asyncio
async def test_run_index_build_terminal_transition_invalidates_the_cache(client):
    """The background job's OWN invalidation, tested directly (bypassing
    `ASGITransport`'s synchronous background-task execution, which would
    otherwise make the pending-vs-terminal states indistinguishable under
    SQLite — see the test above)."""
    ac, db = client
    from app.api.admin_field_definitions import _run_index_build
    from app.core.cache import MemoryCache
    from app.core.schema import cache as schema_cache
    from app.models.field_definition import FieldDefinition

    org_id = await _make_org(db, "cache-index-bg")
    created = await ac.post(
        f"/api/v1/admin/field-definitions/?organization_id={org_id}",
        json=_body(key="rank", type="number", indexed=True), headers=AUTH)
    assert created.status_code == 201, created.text
    definition_id = created.json()["id"]

    async with db.session_factory() as s:
        row = await s.get(FieldDefinition, definition_id)
        row.index_state = "pending"
        await s.commit()

    cache = MemoryCache()
    await schema_cache.set(cache, org_id, "site.custom_fields",
                           [{"key": "rank", "index_state": "pending"}])
    assert await schema_cache.get(cache, org_id, "site.custom_fields") is not None

    await _run_index_build(db, definition_id, "site.custom_fields",
                           {"type": "number", "key": "rank"}, org_id, None, cache)

    assert await schema_cache.get(cache, org_id, "site.custom_fields") is None, (
        "the background job's terminal index_state transition did not "
        "invalidate the resolved-schema cache entry")
