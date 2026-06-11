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
