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
    roles = (await ac.get("/api/v1/rbac/roles", headers=AUTH)).json()
    admin_id = next(x["id"] for x in roles if x["code"] == "admin")
    acc = (await ac.post("/api/v1/auth/register",
                         json={"password": "Sup3rStr0ng!pw", "email": "root@x.io"})).json()
    await ac.post(f"/api/v1/rbac/accounts/{acc['id']}/roles", headers=AUTH,
                  json={"role_id": admin_id})  # global scope

    again = await ac.get("/api/v1/system/install-status")
    assert again.json()["installed"] is True
