"""API tests for branding — public theme endpoint + RBAC-gated admin editor (D5.4)."""

from __future__ import annotations

import pytest

from tests.conftest import AUTH


@pytest.mark.asyncio
async def test_public_branding_defaults(client):
    ac, _ = client
    r = await ac.get("/api/v1/system/branding")  # public, no auth
    assert r.status_code == 200
    body = r.json()
    assert body["app_name"] == "Facil"
    assert body["primary_color"] == "#2563eb"
    assert body["supported_locales"] == ["en", "fr", "es"]


@pytest.mark.asyncio
async def test_admin_branding_requires_auth(client):
    ac, _ = client
    assert (await ac.get("/api/v1/admin/branding")).status_code == 401
    assert (await ac.put("/api/v1/admin/branding", json={"app_name": "X"})
            ).status_code == 401


@pytest.mark.asyncio
async def test_update_reflects_in_admin_and_public(client):
    ac, _ = client
    upd = await ac.put("/api/v1/admin/branding", headers=AUTH,
                       json={"app_name": "Acme Portal", "primary_color": "#ff0000"})
    assert upd.status_code == 200
    assert upd.json()["app_name"] == "Acme Portal"

    # Admin GET reflects the new values (live resolver refresh).
    g = (await ac.get("/api/v1/admin/branding", headers=AUTH)).json()
    assert g["app_name"] == "Acme Portal"
    assert g["primary_color"] == "#ff0000"

    # The public theme endpoint reflects them too.
    pub = (await ac.get("/api/v1/system/branding")).json()
    assert pub["app_name"] == "Acme Portal"
    assert pub["primary_color"] == "#ff0000"


@pytest.mark.asyncio
async def test_invalid_theme_mode_422(client):
    ac, _ = client
    r = await ac.put("/api/v1/admin/branding", headers=AUTH,
                     json={"theme_mode": "neon"})
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_partial_update_leaves_others(client):
    ac, _ = client
    await ac.put("/api/v1/admin/branding", headers=AUTH, json={"tagline": "Only this"})
    g = (await ac.get("/api/v1/admin/branding", headers=AUTH)).json()
    assert g["tagline"] == "Only this"
    assert g["app_name"] == "Facil"  # untouched -> still the default
