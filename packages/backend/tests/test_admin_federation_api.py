"""API tests for the admin federation/SCIM read view (D5.2).

Read-only, RBAC-gated (break-glass authorizes). Does not touch the SCIM_TOKEN
surface — it reports state without exposing the token.
"""

from __future__ import annotations

import pytest

from tests.conftest import AUTH


@pytest.mark.asyncio
async def test_federation_requires_auth(client):
    ac, _ = client
    assert (await ac.get("/api/v1/admin/federation/status")).status_code == 401
    assert (await ac.get("/api/v1/admin/federation/identities")).status_code == 401


@pytest.mark.asyncio
async def test_status_defaults(client):
    ac, _ = client
    r = await ac.get("/api/v1/admin/federation/status", headers=AUTH)
    assert r.status_code == 200
    body = r.json()
    # No SCIM_TOKEN in the test env -> disabled; token value never surfaced.
    assert body["scim"]["enabled"] is False
    assert "provider" in body["scim"]
    assert body["federation"] == {"linked_identities": 0, "providers": []}


@pytest.mark.asyncio
async def test_identities_listing_and_search(client):
    ac, db = client
    # Create an account, then link a federated identity directly in the DB.
    acc = (await ac.post("/api/v1/admin/accounts", headers=AUTH,
                         json={"email": "fed@corp.com", "password": "Secret123",
                               "display_name": "Fed User"})).json()
    from app.auth.models import FederatedIdentity
    async with db.session_factory() as s:
        s.add(FederatedIdentity(account_id=acc["id"], provider="keycloak",
                                subject="kc-uuid-123"))
        await s.commit()

    body = (await ac.get("/api/v1/admin/federation/identities", headers=AUTH)).json()
    assert body["total"] == 1
    rows = body["items"]
    assert rows[0]["provider"] == "keycloak"
    assert rows[0]["subject"] == "kc-uuid-123"
    assert rows[0]["email"] == "fed@corp.com"

    # Status now reflects the link.
    st = (await ac.get("/api/v1/admin/federation/status", headers=AUTH)).json()
    assert st["federation"]["linked_identities"] == 1
    assert st["federation"]["providers"] == ["keycloak"]

    # Search by subject / provider / email.
    assert (await ac.get("/api/v1/admin/federation/identities?q=kc-uuid",
                         headers=AUTH)).json()["total"] == 1
    assert (await ac.get("/api/v1/admin/federation/identities?q=nomatch",
                         headers=AUTH)).json()["items"] == []
