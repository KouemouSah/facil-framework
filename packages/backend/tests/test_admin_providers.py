"""Admin providers API — CRUD, set-default, registered, token gate."""

from __future__ import annotations

import pytest

from tests.conftest import AUTH


@pytest.mark.asyncio
async def test_requires_token(client):
    ac, _ = client
    assert (await ac.get("/api/v1/admin/providers/")).status_code == 401


@pytest.mark.asyncio
async def test_registered_lists_builtin(client):
    ac, _ = client
    r = await ac.get("/api/v1/admin/providers/registered", headers=AUTH)
    assert r.status_code == 200
    pairs = {(e["capability"], e["provider_code"]) for e in r.json()}
    assert ("secrets", "env") in pairs
    assert ("storage", "minio") in pairs


# --- A0: config schema (backend = source of truth for the admin form) + etag ---

_SECRET_KEYS = {"access_key", "secret_key", "api_key", "password", "secret",
                "client_secret", "role_id", "secret_id"}


@pytest.mark.asyncio
async def test_registered_exposes_config_schema_without_secrets(client):
    ac, _ = client
    entries = (await ac.get("/api/v1/admin/providers/registered", headers=AUTH)).json()
    by = {(e["capability"], e["provider_code"]): e for e in entries}

    # Every registered type carries a (possibly empty) config_schema list.
    for e in entries:
        assert isinstance(e.get("config_schema"), list)

    # A known schema exposes the real, non-secret keys.
    minio = by[("storage", "minio")]["config_schema"]
    keys = {f["key"] for f in minio}
    assert keys == {"endpoint", "bucket"}
    assert all({"key", "label", "type"} <= set(f) for f in minio)

    # CRITICAL: no schema may declare a secret-bearing field (creds go via
    # secret_ref / env, never the config form).
    for e in entries:
        for f in e["config_schema"]:
            assert f["key"] not in _SECRET_KEYS, f"{e['provider_code']}.{f['key']} is a secret"


@pytest.mark.asyncio
async def test_get_and_list_return_etag(client):
    ac, _ = client
    await ac.put("/api/v1/admin/providers/llm/ollama", headers=AUTH,
                 json={"config": {"model": "gemma4:e4b"}})
    one = await ac.get("/api/v1/admin/providers/llm/ollama", headers=AUTH)
    assert one.json().get("etag")
    lst = await ac.get("/api/v1/admin/providers/?capability=llm", headers=AUTH)
    assert all(p.get("etag") for p in lst.json())


@pytest.mark.asyncio
async def test_put_if_match_optimistic_concurrency(client):
    ac, _ = client
    await ac.put("/api/v1/admin/providers/llm/ollama", headers=AUTH,
                 json={"config": {"model": "gemma4:e4b"}})
    etag = (await ac.get("/api/v1/admin/providers/llm/ollama", headers=AUTH)).json()["etag"]

    # Stale If-Match → 409.
    stale = await ac.put("/api/v1/admin/providers/llm/ollama",
                         headers={**AUTH, "If-Match": "deadbeef"},
                         json={"config": {"model": "gemma4:12b"}})
    assert stale.status_code == 409

    # Correct If-Match → 200, and the etag rotates.
    ok = await ac.put("/api/v1/admin/providers/llm/ollama",
                      headers={**AUTH, "If-Match": etag},
                      json={"config": {"model": "gemma4:12b"}})
    assert ok.status_code == 200
    assert ok.json()["etag"] != etag


@pytest.mark.asyncio
async def test_crud_and_default(client):
    ac, _ = client
    # upsert two storage providers
    await ac.put("/api/v1/admin/providers/storage/minio", headers=AUTH,
                 json={"config": {"endpoint": "http://minio:9000", "bucket": "facil-documents"},
                       "secret_ref": "minio_sa"})
    await ac.put("/api/v1/admin/providers/storage/s3", headers=AUTH,
                 json={"config": {"region": "eu-west-1"}})
    # list
    r = await ac.get("/api/v1/admin/providers/?capability=storage", headers=AUTH)
    assert {p["provider_code"] for p in r.json()} == {"minio", "s3"}
    # set default -> minio
    assert (await ac.post("/api/v1/admin/providers/storage/minio/default",
                          headers=AUTH)).status_code == 200
    r = await ac.get("/api/v1/admin/providers/storage/minio", headers=AUTH)
    assert r.json()["is_default"] is True
    # switching default to s3 unsets minio
    await ac.post("/api/v1/admin/providers/storage/s3/default", headers=AUTH)
    assert (await ac.get("/api/v1/admin/providers/storage/minio",
                         headers=AUTH)).json()["is_default"] is False
    # delete
    assert (await ac.delete("/api/v1/admin/providers/storage/s3",
                            headers=AUTH)).status_code == 200


@pytest.mark.asyncio
async def test_invalid_capability_rejected(client):
    ac, _ = client
    r = await ac.put("/api/v1/admin/providers/teleport/warp", headers=AUTH, json={})
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_set_default_missing_404(client):
    ac, _ = client
    assert (await ac.post("/api/v1/admin/providers/llm/ghost/default",
                          headers=AUTH)).status_code == 404


@pytest.mark.asyncio
async def test_check_builtin_provider(client):
    ac, _ = client
    r = await ac.post("/api/v1/admin/providers/secrets/env/check", headers=AUTH)
    assert r.status_code == 200 and r.json()["ok"] is True


@pytest.mark.asyncio
async def test_check_unregistered_404(client):
    ac, _ = client
    r = await ac.post("/api/v1/admin/providers/storage/ftp/check", headers=AUTH)
    assert r.status_code == 404


# --- Secrets discipline enforced at the backend (SEC-001) --------------------

from app.models.provider import public_config, secret_keys_in  # noqa: E402


def test_public_config_strips_secret_keys():
    cfg = {"endpoint": "http://x", "access_key": "AKIA", "secret_key": "s", "bucket": "b"}
    assert public_config(cfg) == {"endpoint": "http://x", "bucket": "b"}
    assert secret_keys_in(cfg) == {"access_key", "secret_key"}
    assert secret_keys_in({"endpoint": "x"}) == set()
    assert public_config(None) == {}


@pytest.mark.asyncio
async def test_put_rejects_secret_keys_in_config(client):
    ac, _ = client
    r = await ac.put("/api/v1/admin/providers/storage/minio", headers=AUTH,
                     json={"config": {"endpoint": "http://minio:9000", "secret_key": "leak"},
                           "secret_ref": "minio_sa"})
    assert r.status_code == 422, r.text
    assert "secret" in r.text.lower()


@pytest.mark.asyncio
async def test_get_strips_secret_from_legacy_config(client):
    ac, _ = client
    # Simulate a legacy/env-injected row that already carries a secret in config
    # (bypassing the API guard) — the READ response must not echo it.
    from app.core.providers import repository as repo
    from app.db.engine import Database  # noqa: F401
    _, db = client
    async with db.session_factory() as s:
        await repo.upsert_provider(s, "storage", "minio",
                                   config={"endpoint": "http://x", "access_key": "AKIA"},
                                   secret_ref="minio_sa")
        await s.commit()
    got = await ac.get("/api/v1/admin/providers/storage/minio", headers=AUTH)
    assert "access_key" not in got.json()["config"]
    assert got.json()["config"] == {"endpoint": "http://x"}


@pytest.mark.asyncio
async def test_put_provider_is_audited(client):
    ac, db = client
    r = await ac.put("/api/v1/admin/providers/llm/ollama", headers=AUTH,
                     json={"config": {"endpoint": "http://ollama:11434", "model": "m"},
                           "is_active": True})
    assert r.status_code == 200, r.text
    from sqlalchemy import select
    from app.auth.models import AuthAudit
    async with db.session_factory() as s:
        actions = {x.action for x in (await s.scalars(select(AuthAudit))).all()}
    assert "provider_changed" in actions


# --- SEC-F2 (allowlist by config_schema) + SEC-F4 (as_dict strips) ------------

from app.models.provider import AI_PROVIDER_ALLOWED, ProviderSetting  # noqa: E402


@pytest.mark.asyncio
async def test_put_allowlists_config_by_schema(client):
    ac, _ = client
    # minio schema = {endpoint, bucket}. Anything else is rejected (case/variant/
    # nested/non-secret-but-undeclared) — allowlist, not denylist.
    for bad_cfg in ({"endpoint": "x", "region": "eu"},          # undeclared key
                    {"endpoint": "x", "API_KEY": "v"},          # case variant
                    {"endpoint": "x", "extra": {"api_key": 1}}):  # nested blob
        r = await ac.put("/api/v1/admin/providers/storage/minio", headers=AUTH,
                         json={"config": bad_cfg})
        assert r.status_code == 422, (bad_cfg, r.text)
    # Declared keys only → OK.
    ok = await ac.put("/api/v1/admin/providers/storage/minio", headers=AUTH,
                      json={"config": {"endpoint": "http://minio:9000", "bucket": "b"}})
    assert ok.status_code == 200, ok.text


@pytest.mark.asyncio
async def test_unregistered_code_falls_back_to_denylist(client):
    ac, _ = client
    # s3 is not registered → no schema to allowlist → denylist fallback.
    ok = await ac.put("/api/v1/admin/providers/storage/s3", headers=AUTH,
                      json={"config": {"region": "eu-west-1"}})  # non-secret → allowed
    assert ok.status_code == 200, ok.text
    bad = await ac.put("/api/v1/admin/providers/storage/s3", headers=AUTH,
                       json={"config": {"secret_key": "leak"}})
    assert bad.status_code == 422, bad.text


def test_registry_schema_keys():
    from app.core.providers.registry import default_registry
    r = default_registry()
    assert r.schema_keys("storage", "minio") == {"endpoint", "bucket"}
    assert r.schema_keys("storage", "memory") == set()   # registered, empty schema
    assert r.schema_keys("storage", "s3") is None        # not registered


def test_as_dict_strips_config_but_raw_keeps_it():
    row = ProviderSetting(capability="storage", provider_code="minio",
                          config={"endpoint": "x", "access_key": "AKIA"}, secret_ref="ref")
    assert "access_key" not in row.as_dict()["config"]     # SEC-F4: stripped
    assert row.as_dict()["config"] == {"endpoint": "x"}
    assert row.as_dict_raw()["config"]["access_key"] == "AKIA"  # internal raw kept


def test_ai_provider_allowlist_constant():
    assert AI_PROVIDER_ALLOWED == {"kind", "endpoint", "model", "api_key_secret"}


def test_no_registered_schema_declares_a_secret_key():
    """SEC-005 invariant: the allowlist trusts config_schema, so no registered
    provider may ever declare a secret-bearing key (that would reopen SEC-001)."""
    from app.core.providers.registry import default_registry
    from app.models.provider import SECRET_CONFIG_KEYS
    r = default_registry()
    for cap, code in r.registered:
        keys = r.schema_keys(cap, code) or set()
        assert keys & SECRET_CONFIG_KEYS == set(), f"{cap}/{code} declares a secret key"
