"""API tests for the admin accounts endpoints (D5.2 support).

The bootstrap admin token (break-glass) authorizes management before any grant
exists — that is the intended bootstrap path.
"""

from __future__ import annotations

import pytest

from tests.conftest import AUTH


@pytest.mark.asyncio
async def test_accounts_require_auth(client):
    ac, _ = client
    assert (await ac.get("/api/v1/admin/accounts")).status_code == 401
    assert (await ac.post("/api/v1/admin/accounts",
                          json={"email": "x@e.com", "password": "Secret123"})
            ).status_code == 401


@pytest.mark.asyncio
async def test_create_then_list_and_search(client):
    ac, _ = client
    created = await ac.post("/api/v1/admin/accounts", headers=AUTH,
                            json={"email": "agent@corp.com", "password": "Secret123",
                                  "display_name": "Agent One"})
    assert created.status_code == 201
    acc = created.json()
    assert acc["email"] == "agent@corp.com"
    assert acc["is_active"] is True

    rows = (await ac.get("/api/v1/admin/accounts", headers=AUTH)).json()
    assert any(r["id"] == acc["id"] for r in rows)

    # Substring search hits display_name / email.
    hit = (await ac.get("/api/v1/admin/accounts?q=agent", headers=AUTH)).json()
    assert [r["id"] for r in hit] == [acc["id"]]
    miss = (await ac.get("/api/v1/admin/accounts?q=zzzznope", headers=AUTH)).json()
    assert miss == []


@pytest.mark.asyncio
async def test_duplicate_email_409(client):
    ac, _ = client
    body = {"email": "dup@corp.com", "password": "Secret123"}
    assert (await ac.post("/api/v1/admin/accounts", headers=AUTH, json=body)
            ).status_code == 201
    assert (await ac.post("/api/v1/admin/accounts", headers=AUTH, json=body)
            ).status_code == 409


@pytest.mark.asyncio
async def test_weak_password_422(client):
    ac, _ = client
    r = await ac.post("/api/v1/admin/accounts", headers=AUTH,
                      json={"email": "weak@corp.com", "password": "short"})
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_set_status_transitions(client):
    ac, _ = client
    acc = (await ac.post("/api/v1/admin/accounts", headers=AUTH,
                         json={"email": "susp@corp.com", "password": "Secret123"})).json()
    aid = acc["id"]

    # Suspend -> is_active flips off.
    sus = await ac.patch(f"/api/v1/admin/accounts/{aid}/status", headers=AUTH,
                         json={"status": "suspended"})
    assert sus.status_code == 200
    assert sus.json()["status"] == "suspended"
    assert sus.json()["is_active"] is False

    # Reactivate.
    act = await ac.patch(f"/api/v1/admin/accounts/{aid}/status", headers=AUTH,
                         json={"status": "active"})
    assert act.json()["is_active"] is True

    # Invalid status -> 422; unknown account -> 404.
    assert (await ac.patch(f"/api/v1/admin/accounts/{aid}/status", headers=AUTH,
                           json={"status": "bogus"})).status_code == 422
    assert (await ac.patch("/api/v1/admin/accounts/nope/status", headers=AUTH,
                           json={"status": "active"})).status_code == 404


@pytest.mark.asyncio
async def test_invalid_email_422(client):
    ac, _ = client
    r = await ac.post("/api/v1/admin/accounts", headers=AUTH,
                      json={"email": "not-an-email", "password": "Secret123"})
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_suspended_account_cannot_login(client):
    """S1/S2: native login enforces status, and suspension kills sessions."""
    ac, _ = client
    await ac.post("/api/v1/admin/accounts", headers=AUTH,
                  json={"email": "agent2@corp.com", "password": "Secret123"})
    # Fresh account logs in fine.
    ok = await ac.post("/api/v1/auth/login",
                       json={"identifier": "agent2@corp.com", "password": "Secret123"})
    assert ok.status_code == 200
    aid = ok.json()["account"]["id"]
    # Suspend -> native login is now rejected (uniform 401, no status oracle).
    sus = await ac.patch(f"/api/v1/admin/accounts/{aid}/status", headers=AUTH,
                         json={"status": "suspended"})
    assert sus.status_code == 200
    again = await ac.post("/api/v1/auth/login",
                          json={"identifier": "agent2@corp.com", "password": "Secret123"})
    assert again.status_code == 401
    # Reactivate -> login works again.
    await ac.patch(f"/api/v1/admin/accounts/{aid}/status", headers=AUTH,
                   json={"status": "active"})
    assert (await ac.post("/api/v1/auth/login",
                          json={"identifier": "agent2@corp.com", "password": "Secret123"})
            ).status_code == 200


@pytest.mark.asyncio
async def test_bulk_status(client):
    ac, _ = client
    a1 = (await ac.post("/api/v1/admin/accounts", headers=AUTH,
                        json={"email": "blk1@corp.com", "password": "Secret123"})).json()
    a2 = (await ac.post("/api/v1/admin/accounts", headers=AUTH,
                        json={"email": "blk2@corp.com", "password": "Secret123"})).json()

    r = await ac.post("/api/v1/admin/accounts/bulk-status", headers=AUTH,
                      json={"account_ids": [a1["id"], a2["id"], "ghost"],
                            "status": "suspended"})
    assert r.status_code == 200
    body = r.json()
    assert set(body["updated"]) == {a1["id"], a2["id"]}
    assert body["errors"] == [{"account_id": "ghost", "detail": "not found"}]

    # Both suspended -> native login blocked.
    assert (await ac.post("/api/v1/auth/login",
                          json={"identifier": "blk1@corp.com", "password": "Secret123"})
            ).status_code == 401

    # Invalid status / empty -> 422.
    assert (await ac.post("/api/v1/admin/accounts/bulk-status", headers=AUTH,
                          json={"account_ids": [a1["id"]], "status": "nope"})
            ).status_code == 422
    assert (await ac.post("/api/v1/admin/accounts/bulk-status", headers=AUTH,
                          json={"account_ids": [], "status": "active"})
            ).status_code == 422


@pytest.mark.asyncio
async def test_statuses_catalog(client):
    ac, _ = client
    r = await ac.get("/api/v1/admin/accounts/statuses", headers=AUTH)
    assert r.status_code == 200
    assert set(r.json()["statuses"]) == {
        "pending_identity", "active", "suspended", "deactivated"}
