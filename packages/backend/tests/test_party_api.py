"""API tests for the party module (Party / PartyRole / Address / PartyAddress).

Party is a CORE router (foundational directory pillar), so the shared `client`
fixture mounts it. The bootstrap admin token authorizes management.
"""

from __future__ import annotations

import pytest

from tests.conftest import AUTH

P = "/api/v1/modules/party"


@pytest.mark.asyncio
async def test_party_requires_auth(client):
    ac, _ = client
    assert (await ac.get(f"{P}/parties")).status_code == 401


@pytest.mark.asyncio
async def test_party_crud_roles_and_addresses(client):
    ac, _ = client
    # Create party + keyset contract.
    p = (await ac.post(f"{P}/parties", headers=AUTH, json={
        "party_type": "organization", "name": "Acme SA", "tax_id": "T-1"})).json()
    assert p["party_type"] == "organization"
    body = (await ac.get(f"{P}/parties?sort=name", headers=AUTH)).json()
    assert body["count"] >= 1 and "next_cursor" in body
    # Invalid party_type -> 422.
    assert (await ac.post(f"{P}/parties", headers=AUTH,
                          json={"party_type": "alien", "name": "x"})).status_code == 422

    # ETag update.
    g = (await ac.get(f"{P}/parties/{p['id']}", headers=AUTH)).json()
    ok = await ac.put(f"{P}/parties/{p['id']}", headers={**AUTH, "If-Match": g["etag"]},
                      json={"website": "https://acme.example"})
    assert ok.status_code == 200 and ok.json()["website"] == "https://acme.example"

    # Roles (nested): add, list, remove.
    role = (await ac.post(f"{P}/parties/{p['id']}/roles", headers=AUTH,
                          json={"role": "customer"})).json()
    roles = (await ac.get(f"{P}/parties/{p['id']}/roles", headers=AUTH)).json()
    assert [r["role"] for r in roles] == ["customer"]
    assert (await ac.delete(f"{P}/parties/{p['id']}/roles/{role['id']}", headers=AUTH)
            ).status_code == 200

    # Address + link to the party.
    addr = (await ac.post(f"{P}/addresses", headers=AUTH,
                          json={"line1": "1 Main", "city": "Malabo"})).json()
    link = (await ac.post(f"{P}/parties/{p['id']}/addresses", headers=AUTH,
                          json={"address_id": addr["id"], "address_type": "billing",
                                "is_primary": True})).json()
    linked = (await ac.get(f"{P}/parties/{p['id']}/addresses", headers=AUTH)).json()
    assert [a["address_id"] for a in linked] == [addr["id"]]
    # Link to a missing address -> 422.
    assert (await ac.post(f"{P}/parties/{p['id']}/addresses", headers=AUTH,
                          json={"address_id": "ghost"})).status_code == 422
    assert (await ac.delete(f"{P}/parties/{p['id']}/addresses/{link['id']}", headers=AUTH)
            ).status_code == 200

    # Delete the party.
    assert (await ac.delete(f"{P}/parties/{p['id']}", headers=AUTH)).status_code == 200
    assert (await ac.get(f"{P}/parties/{p['id']}", headers=AUTH)).status_code == 404
