"""API tests for the reference module (currency / country / region master data).

Reference is a CORE router (foundational master data), so the shared `client`
fixture mounts it. The bootstrap admin token (break-glass) authorizes management.
"""

from __future__ import annotations

import pytest

from tests.conftest import AUTH


@pytest.mark.asyncio
async def test_reference_requires_auth(client):
    ac, _ = client
    assert (await ac.get("/api/v1/modules/reference/currencies")).status_code == 401
    assert (await ac.post("/api/v1/modules/reference/currencies",
                          json={"code": "USD", "name": "Dollar"})).status_code == 401


@pytest.mark.asyncio
async def test_currency_crud_and_keyset(client):
    ac, _ = client
    B = "/api/v1/modules/reference/currencies"
    # Create (code upper-cased by schema).
    c = (await ac.post(B, headers=AUTH,
                       json={"code": "usd", "name": "US Dollar", "symbol": "$"})).json()
    assert c["code"] == "USD" and c["decimal_places"] == 2

    # Keyset list contract.
    body = (await ac.get(f"{B}?sort=code&limit=50", headers=AUTH)).json()
    assert body["count"] >= 1 and body["capped"] is False and "next_cursor" in body
    assert any(r["code"] == "USD" for r in body["items"])

    # Duplicate code -> 409.
    assert (await ac.post(B, headers=AUTH, json={"code": "USD", "name": "x"})
            ).status_code == 409
    # Unknown sort -> 422.
    assert (await ac.get(f"{B}?sort=evil", headers=AUTH)).status_code == 422

    # Get (etag) + optimistic update.
    g = (await ac.get(f"{B}/{c['id']}", headers=AUTH)).json()
    etag = g["etag"]
    ok = await ac.put(f"{B}/{c['id']}", headers={**AUTH, "If-Match": etag},
                      json={"symbol": "US$"})
    assert ok.status_code == 200 and ok.json()["symbol"] == "US$"
    # Stale etag -> 412/409.
    assert (await ac.put(f"{B}/{c['id']}", headers={**AUTH, "If-Match": etag},
                         json={"symbol": "X"})).status_code in (409, 412)


@pytest.mark.asyncio
async def test_country_and_region_relationship(client):
    ac, _ = client
    CUR = "/api/v1/modules/reference/currencies"
    CO = "/api/v1/modules/reference/countries"
    RE = "/api/v1/modules/reference/regions"

    cur = (await ac.post(CUR, headers=AUTH, json={"code": "XAF", "name": "CFA", "decimal_places": 0})).json()
    co = (await ac.post(CO, headers=AUTH, json={
        "code": "gq", "alpha3": "GNQ", "name": "Equatorial Guinea",
        "default_currency_id": cur["id"]})).json()
    assert co["code"] == "GQ" and co["default_currency_id"] == cur["id"]

    # Region needs a valid country.
    assert (await ac.post(RE, headers=AUTH, json={
        "country_id": "ghost", "code": "X", "name": "X"})).status_code == 422
    r = (await ac.post(RE, headers=AUTH, json={
        "country_id": co["id"], "code": "GQ-LI", "name": "Litoral",
        "region_type": "province"})).json()
    assert r["country_id"] == co["id"]

    # Regions filtered by country (keyset).
    listed = (await ac.get(f"{RE}?country_id={co['id']}&sort=name", headers=AUTH)).json()
    assert listed["count"] == 1 and listed["items"][0]["code"] == "GQ-LI"
    # Other country -> empty.
    assert (await ac.get(f"{RE}?country_id=other", headers=AUTH)).json()["count"] == 0
