"""System / first-run install-status API (D5.3)."""

from __future__ import annotations

import pytest

from tests.conftest import AUTH


@pytest.mark.asyncio
async def test_install_status_flips_when_superadmin_exists(client):
    ac, _ = client
    # fresh system -> not installed (no super-admin)
    r = await ac.get("/api/v1/system/install-status")
    assert r.status_code == 200 and r.json()["installed"] is False
    assert "app_name" in r.json()

    # seed roles + create an account + assign the admin role (grants '*') at
    # global scope -> the installer's end state
    await ac.post("/api/v1/rbac/admin/reseed?profile=empty", headers=AUTH)
    roles = (await ac.get("/api/v1/rbac/roles", headers=AUTH)).json()["items"]
    admin_id = next(x["id"] for x in roles if x["code"] == "admin")
    acc = (await ac.post("/api/v1/auth/register",
                         json={"password": "Sup3rStr0ng!pw", "email": "root@x.io"})).json()
    await ac.post(f"/api/v1/rbac/accounts/{acc['id']}/roles", headers=AUTH,
                  json={"role_id": admin_id})  # global scope

    again = await ac.get("/api/v1/system/install-status")
    assert again.json()["installed"] is True


# --- Self-registration feature flag (P7, audit 15) --------------------------

from app.branding import self_registration_enabled  # noqa: E402


class _StubResolver:
    def __init__(self, value):
        self._value = value

    def resolve(self, key, default=None):
        if key == "auth.self_registration_enabled":
            return self._value
        return default


@pytest.mark.parametrize("value,expected", [
    (True, True), (False, False), (None, False),
    ("true", True), ("false", False), ("1", True), ("0", False),
    ("yes", True), ("on", True), ("", False),
])
def test_self_registration_flag_coercion(value, expected):
    # Env overrides arrive as strings; "false" must NOT be truthy.
    assert self_registration_enabled(_StubResolver(value)) is expected


@pytest.mark.asyncio
async def test_branding_exposes_self_registration_flag(client):
    ac, _ = client
    body = (await ac.get("/api/v1/system/branding")).json()
    assert "self_registration_enabled" in body
    # conftest opts the harness in.
    assert body["self_registration_enabled"] is True


@pytest.mark.asyncio
async def test_register_gated_by_flag(client):
    ac, _ = client
    from app.config_store.resolver import ConfigResolver
    from app.main import app

    saved = app.state.resolver
    try:
        # Flip to the production default (flag absent -> False).
        app.state.resolver = ConfigResolver(defaults={"branding.app_name": "Facil"}, env={})
        assert (await ac.get("/api/v1/system/branding")).json()["self_registration_enabled"] is False
        blocked = await ac.post("/api/v1/auth/register",
                                json={"password": "Sup3rStr0ng!pw", "email": "no@x.io"})
        assert blocked.status_code == 403, blocked.text
    finally:
        app.state.resolver = saved
    # Restored (opted-in) -> registration works again.
    ok = await ac.post("/api/v1/auth/register",
                       json={"password": "Sup3rStr0ng!pw", "email": "yes@x.io"})
    assert ok.status_code == 201, ok.text
