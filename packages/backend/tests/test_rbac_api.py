"""API tests for the RBAC management endpoints (D4.3).

The bootstrap admin token (break-glass) authorizes management before any grant
exists — that is the intended bootstrap path.
"""

from __future__ import annotations

import pytest

from tests.conftest import AUTH


@pytest.mark.asyncio
async def test_management_requires_auth(client):
    ac, _ = client
    assert (await ac.get("/api/v1/rbac/roles")).status_code == 401
    assert (await ac.post("/api/v1/rbac/roles", json={"code": "x", "name": "x"})
            ).status_code == 401


@pytest.mark.asyncio
async def test_reseed_then_list(client):
    ac, _ = client
    r = await ac.post("/api/v1/rbac/admin/reseed?profile=empty", headers=AUTH)
    assert r.status_code == 200
    assert "admin" in r.json()["roles"]
    roles = (await ac.get("/api/v1/rbac/roles", headers=AUTH)).json()
    assert {x["code"] for x in roles} >= {"admin", "member"}
    perms = (await ac.get("/api/v1/rbac/permissions", headers=AUTH)).json()
    assert any(p["code"] == "organization.read" for p in perms)


@pytest.mark.asyncio
async def test_create_set_grants_delete_role(client):
    ac, _ = client
    await ac.post("/api/v1/rbac/admin/reseed?profile=empty", headers=AUTH)  # catalog
    created = await ac.post("/api/v1/rbac/roles", headers=AUTH,
                            json={"code": "auditor", "name": "Auditor",
                                  "grants": ["organization.read"]})
    assert created.status_code == 201
    assert created.json()["is_system"] is False  # API never mints system roles
    role_id = created.json()["id"]
    # duplicate code in same (global) scope -> 409
    dup = await ac.post("/api/v1/rbac/roles", headers=AUTH,
                        json={"code": "auditor", "name": "Auditor"})
    assert dup.status_code == 409
    upd = await ac.put(f"/api/v1/rbac/roles/{role_id}/permissions", headers=AUTH,
                       json={"codes": ["organization.read", "location.read"]})
    assert upd.status_code == 200
    assert (await ac.delete(f"/api/v1/rbac/roles/{role_id}", headers=AUTH)
            ).status_code == 200


@pytest.mark.asyncio
async def test_get_role_permissions_roundtrip(client):
    ac, _ = client
    await ac.post("/api/v1/rbac/admin/reseed?profile=empty", headers=AUTH)  # catalog
    created = await ac.post("/api/v1/rbac/roles", headers=AUTH,
                            json={"code": "viewer", "name": "Viewer"})
    role_id = created.json()["id"]
    # No grants yet.
    g0 = await ac.get(f"/api/v1/rbac/roles/{role_id}/permissions", headers=AUTH)
    assert g0.status_code == 200
    assert g0.json() == {"role_id": role_id, "codes": []}
    # Set then read back (sorted).
    await ac.put(f"/api/v1/rbac/roles/{role_id}/permissions", headers=AUTH,
                 json={"codes": ["location.read", "organization.read"]})
    g1 = (await ac.get(f"/api/v1/rbac/roles/{role_id}/permissions", headers=AUTH)).json()
    assert g1["codes"] == ["location.read", "organization.read"]
    # Unknown role -> 404.
    assert (await ac.get("/api/v1/rbac/roles/does-not-exist/permissions", headers=AUTH)
            ).status_code == 404


@pytest.mark.asyncio
async def test_unknown_grant_rejected(client):
    ac, _ = client
    await ac.post("/api/v1/rbac/admin/reseed?profile=empty", headers=AUTH)
    r = await ac.post("/api/v1/rbac/roles", headers=AUTH,
                      json={"code": "typo", "name": "Typo",
                            "grants": ["organisation.raed"]})  # typo'd code
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_system_role_is_protected(client):
    ac, _ = client
    await ac.post("/api/v1/rbac/admin/reseed?profile=empty", headers=AUTH)
    roles = (await ac.get("/api/v1/rbac/roles", headers=AUTH)).json()
    admin_id = next(r["id"] for r in roles if r["code"] == "admin")
    # cannot delete or re-grant a seeded system role
    assert (await ac.delete(f"/api/v1/rbac/roles/{admin_id}", headers=AUTH)
            ).status_code == 409
    assert (await ac.put(f"/api/v1/rbac/roles/{admin_id}/permissions", headers=AUTH,
                         json={"codes": ["organization.read"]})).status_code == 409


@pytest.mark.asyncio
async def test_assignment_records_who_assigned(client):
    ac, db = client
    await ac.post("/api/v1/rbac/admin/reseed?profile=empty", headers=AUTH)
    roles = (await ac.get("/api/v1/rbac/roles", headers=AUTH)).json()
    member = next(r["id"] for r in roles if r["code"] == "member")
    acc = (await ac.post("/api/v1/auth/register",
                         json={"password": "Sup3rStr0ng!pw", "email": "w@x.com"})).json()
    assigned = (await ac.post(f"/api/v1/rbac/accounts/{acc['id']}/roles", headers=AUTH,
                              json={"role_id": member, "organization_id": "org-1"})).json()
    # created_by is audited (break-glass principal = bootstrap-admin)
    from app.rbac.models import AccountRole
    async with db.session_factory() as s:
        row = await s.get(AccountRole, assigned["id"])
        assert row.created_by == "bootstrap-admin"


@pytest.mark.asyncio
async def test_assign_and_revoke(client):
    ac, _ = client
    await ac.post("/api/v1/rbac/admin/reseed?profile=empty", headers=AUTH)
    roles = (await ac.get("/api/v1/rbac/roles", headers=AUTH)).json()
    admin_id = next(r["id"] for r in roles if r["code"] == "admin")
    acc = (await ac.post("/api/v1/auth/register",
                         json={"password": "Sup3rStr0ng!pw", "email": "u@x.com"})).json()
    assigned = await ac.post(f"/api/v1/rbac/accounts/{acc['id']}/roles", headers=AUTH,
                             json={"role_id": admin_id, "organization_id": "org-1"})
    assert assigned.status_code == 201
    assignment_id = assigned.json()["id"]
    listed = (await ac.get(f"/api/v1/rbac/accounts/{acc['id']}/roles",
                           headers=AUTH)).json()
    assert len(listed) == 1 and listed[0]["organization_id"] == "org-1"
    assert (await ac.delete(
        f"/api/v1/rbac/accounts/{acc['id']}/roles/{assignment_id}", headers=AUTH)
    ).status_code == 200


@pytest.mark.asyncio
async def test_assign_unknown_role_404(client):
    ac, _ = client
    acc = (await ac.post("/api/v1/auth/register",
                         json={"password": "Sup3rStr0ng!pw", "email": "v@x.com"})).json()
    r = await ac.post(f"/api/v1/rbac/accounts/{acc['id']}/roles", headers=AUTH,
                      json={"role_id": "does-not-exist"})
    assert r.status_code == 404
