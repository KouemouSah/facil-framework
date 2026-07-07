"""Admin settings API — CRUD, token gate, resolver invalidation, /health."""

from __future__ import annotations

import pytest

from tests.conftest import AUTH


@pytest.mark.asyncio
async def test_health_ok(client):
    ac, _ = client
    r = await ac.get("/health")
    assert r.status_code == 200
    assert r.json()["database"] is True


@pytest.mark.asyncio
async def test_admin_requires_token(client):
    ac, _ = client
    assert (await ac.get("/api/v1/admin/settings/")).status_code == 401
    assert (await ac.get("/api/v1/admin/settings/",
                         headers={"X-Admin-Token": "wrong"})).status_code == 401


@pytest.mark.asyncio
async def test_crud_roundtrip(client):
    ac, _ = client
    # empty list
    r = await ac.get("/api/v1/admin/settings/", headers=AUTH)
    assert r.status_code == 200 and r.json() == []
    # upsert
    body = {"value": "sendgrid", "value_type": "string", "scope": "email"}
    r = await ac.put("/api/v1/admin/settings/email.provider", headers=AUTH, json=body)
    assert r.status_code == 200 and r.json()["value"] == "sendgrid"
    # get
    r = await ac.get("/api/v1/admin/settings/email.provider", headers=AUTH)
    assert r.status_code == 200 and r.json()["scope"] == "email"
    # update (same key)
    r = await ac.put("/api/v1/admin/settings/email.provider", headers=AUTH,
                     json={"value": "ses"})
    assert r.json()["value"] == "ses"
    # list has it
    r = await ac.get("/api/v1/admin/settings/", headers=AUTH)
    assert any(s["key"] == "email.provider" for s in r.json())
    # delete
    assert (await ac.delete("/api/v1/admin/settings/email.provider",
                            headers=AUTH)).status_code == 200
    assert (await ac.get("/api/v1/admin/settings/email.provider",
                         headers=AUTH)).status_code == 404


@pytest.mark.asyncio
async def test_json_value_and_types(client):
    ac, _ = client
    body = {"value": {"public_chat": "ollama_pub"}, "value_type": "json", "scope": "ai"}
    r = await ac.put("/api/v1/admin/settings/ai.routing", headers=AUTH, json=body)
    assert r.status_code == 200 and r.json()["value"] == {"public_chat": "ollama_pub"}


@pytest.mark.asyncio
async def test_invalid_value_type_rejected(client):
    ac, _ = client
    r = await ac.put("/api/v1/admin/settings/x", headers=AUTH,
                     json={"value": "y", "value_type": "blob"})
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_put_refreshes_resolver(client):
    ac, db = client
    from app.main import app
    await ac.put("/api/v1/admin/settings/branding.app_name", headers=AUTH,
                 json={"value": "MyApp", "scope": "branding"})
    # the DB layer of the live resolver now reflects the change
    assert app.state.resolver.resolve("branding.app_name") == "MyApp"
    assert app.state.resolver.source("branding.app_name") == "db"


@pytest.mark.asyncio
async def test_delete_missing_404(client):
    ac, _ = client
    assert (await ac.delete("/api/v1/admin/settings/ghost",
                            headers=AUTH)).status_code == 404


@pytest.mark.asyncio
async def test_setting_if_match_optimistic_concurrency(client):
    """A0: routing edits (ai.routing / ai.providers) are concurrency-safe."""
    ac, _ = client
    await ac.put("/api/v1/admin/settings/ai.routing", headers=AUTH,
                 json={"value": {"public_chat": "ollama_public"}, "value_type": "json"})
    etag = (await ac.get("/api/v1/admin/settings/ai.routing", headers=AUTH)).json()["etag"]
    assert etag

    stale = await ac.put("/api/v1/admin/settings/ai.routing",
                         headers={**AUTH, "If-Match": "stale123"},
                         json={"value": {"public_chat": "cloud_x"}, "value_type": "json"})
    assert stale.status_code == 409

    ok = await ac.put("/api/v1/admin/settings/ai.routing",
                      headers={**AUTH, "If-Match": etag},
                      json={"value": {"public_chat": "cloud_x"}, "value_type": "json"})
    assert ok.status_code == 200 and ok.json()["etag"] != etag


# --- SEC-001 (sub-project A verification): ai.providers secrets discipline ---

from app.models.provider import provider_map_secret_keys, public_provider_map  # noqa: E402


def test_provider_map_helpers_unit():
    m = {"openai": {"kind": "openai_compat", "model": "m",
                    "api_key": "sk-REAL", "api_key_secret": "ref/openai"}}
    # A raw credential is a secret; the *reference* (api_key_secret) is not.
    assert provider_map_secret_keys(m) == {"api_key"}
    stripped = public_provider_map(m)
    assert "api_key" not in stripped["openai"]
    assert stripped["openai"]["api_key_secret"] == "ref/openai"  # reference kept
    assert public_provider_map(None) is None  # non-dict passes through


@pytest.mark.asyncio
async def test_ai_providers_rejects_plaintext_secret(client):
    ac, _ = client
    ref = {"openai": {"kind": "openai_compat", "endpoint": "https://x/v1",
                      "model": "m", "api_key_secret": "ref/openai"}}
    ok = await ac.put("/api/v1/admin/settings/ai.providers", headers=AUTH,
                      json={"value": ref, "value_type": "json"})
    assert ok.status_code == 200, ok.text
    bad = await ac.put("/api/v1/admin/settings/ai.providers", headers=AUTH,
                       json={"value": {"openai": {"api_key": "sk-REAL"}},
                             "value_type": "json"})
    assert bad.status_code == 422 and "secret" in bad.text.lower()


@pytest.mark.asyncio
async def test_ai_providers_stripped_on_read(client):
    ac, db = client
    # Seed a LEGACY row directly (bypass the API guard) carrying a raw secret.
    from app.config_store import repository as repo
    async with db.session_factory() as s:
        await repo.upsert_setting(s, "ai.providers",
            {"openai": {"kind": "openai_compat", "model": "m", "api_key": "sk-LEGACY"}},
            value_type="json")
        await s.commit()
    got = (await ac.get("/api/v1/admin/settings/ai.providers", headers=AUTH)).json()
    assert "api_key" not in got["value"]["openai"]  # stripped on read
    assert any(s["key"] == "ai.providers" and "api_key" not in s["value"]["openai"]
               for s in (await ac.get("/api/v1/admin/settings/", headers=AUTH)).json())


@pytest.mark.asyncio
async def test_setting_mutation_audited(client):
    ac, db = client
    await ac.put("/api/v1/admin/settings/email.provider", headers=AUTH,
                 json={"value": "smtp", "value_type": "string"})
    from sqlalchemy import select
    from app.auth.models import AuthAudit
    async with db.session_factory() as s:
        actions = {r.action for r in (await s.scalars(select(AuthAudit))).all()}
    assert "setting_changed" in actions
