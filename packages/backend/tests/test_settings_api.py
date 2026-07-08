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

from app.models.provider import provider_map_unknown_keys, public_provider_map  # noqa: E402


def test_provider_map_helpers_unit():
    m = {"openai": {"kind": "openai_compat", "model": "m",
                    "api_key": "sk-REAL", "api_key_secret": "ref/openai"}}
    # SEC-F2 allowlist: `api_key` isn't an allowed entry key; the *reference*
    # (api_key_secret) is. Variants/raw creds are caught structurally.
    assert provider_map_unknown_keys(m) == {"api_key"}
    assert provider_map_unknown_keys({"a": {"kind": "ollama", "API_KEY": "x"}}) == {"API_KEY"}
    stripped = public_provider_map(m)
    assert "api_key" not in stripped["openai"]
    assert stripped["openai"]["api_key_secret"] == "ref/openai"  # reference kept
    # SEC-002: a malformed (non-dict) shape is collapsed, never echoed raw.
    assert public_provider_map(None) == {}
    assert public_provider_map({"a": "sk-RAW"}) == {"a": {}}
    assert public_provider_map([{"api_key": "sk"}]) == {}


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
    assert bad.status_code == 422, bad.text
    assert "api_key" in bad.text


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


@pytest.mark.asyncio
async def test_ai_providers_rejects_malformed_shape(client):
    """SEC-002: a non-dict top-level value or entry must be rejected on write
    (else it would bypass the entry-key allowlist and leak a raw secret on read)."""
    ac, _ = client
    for bad_value in ([{"api_key": "sk"}], "sk-RAW", {"openai": "sk-RAW"}):
        r = await ac.put("/api/v1/admin/settings/ai.providers", headers=AUTH,
                         json={"value": bad_value, "value_type": "json"})
        assert r.status_code == 422, (bad_value, r.text)


# --- SEC-F5 / SEC-F6: config-store secret discipline + protected keys + typing ---

def test_settings_guards_unit():
    from app.api.admin_settings import _is_protected_key, _is_secret_scalar_key, _type_ok
    assert all(_is_protected_key(k) for k in
               ("auth.oidc.issuer", "rbac", "rbac.foo", "security.x"))
    assert not any(_is_protected_key(k) for k in ("email.provider", "branding.app_name"))
    assert _is_secret_scalar_key("smtp.password") and _is_secret_scalar_key("auth.oidc.client_secret")
    # exact last-segment: a knob whose NAME contains a secret word is not flagged.
    assert not _is_secret_scalar_key("auth.password_policy")
    assert not _is_secret_scalar_key("email.provider")
    assert _type_ok("x", "string") and not _type_ok({}, "string")
    assert _type_ok(5, "number") and not _type_ok(True, "number")
    assert _type_ok({"a": 1}, "json") and not _type_ok("x", "json")


@pytest.mark.asyncio
async def test_setting_rejects_plaintext_secret(client):
    ac, _ = client
    # A dict value carrying a secret key (SEC-F5).
    assert (await ac.put("/api/v1/admin/settings/some.integration", headers=AUTH,
            json={"value": {"api_key": "sk"}, "value_type": "json"})).status_code == 422
    # A scalar under a credential-named key.
    assert (await ac.put("/api/v1/admin/settings/smtp.password", headers=AUTH,
            json={"value": "leak", "value_type": "string"})).status_code == 422
    # A knob merely containing a secret word (exact-segment) is allowed.
    assert (await ac.put("/api/v1/admin/settings/auth.password_policy", headers=AUTH,
            json={"value": "strong", "value_type": "string"})).status_code == 200


@pytest.mark.asyncio
async def test_setting_read_masks_and_strips_legacy(client):
    ac, db = client
    from app.config_store import repository as srepo
    async with db.session_factory() as s:
        await srepo.upsert_setting(s, "legacy.password", "leaked", value_type="string")
        await srepo.upsert_setting(s, "legacy.blob", {"api_key": "x", "url": "u"}, value_type="json")
        await s.commit()
    scalar = (await ac.get("/api/v1/admin/settings/legacy.password", headers=AUTH)).json()
    assert scalar["value"] != "leaked"  # masked
    blob = (await ac.get("/api/v1/admin/settings/legacy.blob", headers=AUTH)).json()
    assert "api_key" not in blob["value"] and blob["value"] == {"url": "u"}  # nested stripped


@pytest.mark.asyncio
async def test_setting_rejects_type_mismatch(client):
    ac, _ = client
    assert (await ac.put("/api/v1/admin/settings/x.scalar", headers=AUTH,
            json={"value": {"a": 1}, "value_type": "string"})).status_code == 422
    assert (await ac.put("/api/v1/admin/settings/x.num", headers=AUTH,
            json={"value": "nope", "value_type": "number"})).status_code == 422
    assert (await ac.put("/api/v1/admin/settings/x.ok", headers=AUTH,
            json={"value": 5, "value_type": "number"})).status_code == 200


async def _narrow_bearer(ac, email, grants):
    """A JWT for an account holding exactly `grants` at global scope."""
    await ac.post("/api/v1/rbac/admin/reseed?profile=empty", headers=AUTH)  # seed catalog
    code = "role_" + email.split("@")[0]
    await ac.post("/api/v1/rbac/roles", headers=AUTH,
                  json={"code": code, "name": code, "grants": grants})
    role_id = next(r["id"] for r in (await ac.get("/api/v1/rbac/roles", headers=AUTH)).json()["items"]
                   if r["code"] == code)
    acc = (await ac.post("/api/v1/auth/register",
                         json={"email": email, "password": "Sup3rStr0ng!pw"})).json()
    await ac.post(f"/api/v1/rbac/accounts/{acc['id']}/roles", headers=AUTH,
                  json={"role_id": role_id})  # global scope
    tok = (await ac.post("/api/v1/auth/login",
                         json={"identifier": email, "password": "Sup3rStr0ng!pw"})).json()
    return {"Authorization": f"Bearer {tok['access']}"}


@pytest.mark.asyncio
async def test_protected_settings_need_elevated_permission(client):
    ac, _ = client
    hdr = await _narrow_bearer(ac, "ops@x.io", ["settings.read", "settings.manage"])
    # Non-protected key: settings.manage suffices.
    assert (await ac.put("/api/v1/admin/settings/email.provider", headers=hdr,
            json={"value": "smtp"})).status_code == 200
    # Protected namespace (auth.*): needs settings.manage_protected → 403.
    assert (await ac.put("/api/v1/admin/settings/auth.oidc.issuer", headers=hdr,
            json={"value": "https://idp"})).status_code == 403
    assert (await ac.delete("/api/v1/admin/settings/rbac", headers=hdr)).status_code == 403
