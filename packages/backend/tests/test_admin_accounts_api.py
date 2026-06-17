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

    # Keyset list contract: {items, next_cursor, count, capped}.
    body = (await ac.get("/api/v1/admin/accounts", headers=AUTH)).json()
    assert body["count"] >= 1 and body["capped"] is False
    assert body["next_cursor"] is None  # one account fits one page
    assert any(r["id"] == acc["id"] for r in body["items"])

    # Substring search hits display_name / email.
    hit = (await ac.get("/api/v1/admin/accounts?q=agent", headers=AUTH)).json()
    assert [r["id"] for r in hit["items"]] == [acc["id"]] and hit["count"] == 1
    miss = (await ac.get("/api/v1/admin/accounts?q=zzzznope", headers=AUTH)).json()
    assert miss["items"] == [] and miss["count"] == 0 and miss["next_cursor"] is None


@pytest.mark.asyncio
async def test_list_contract_sort_filter_keyset(client):
    ac, _ = client
    # Seed 3 accounts; suspend one.
    a = (await ac.post("/api/v1/admin/accounts", headers=AUTH,
                       json={"email": "aaa@corp.com", "password": "Secret123"})).json()
    await ac.post("/api/v1/admin/accounts", headers=AUTH,
                  json={"email": "bbb@corp.com", "password": "Secret123"})
    await ac.post("/api/v1/admin/accounts", headers=AUTH,
                  json={"email": "ccc@corp.com", "password": "Secret123"})
    await ac.patch(f"/api/v1/admin/accounts/{a['id']}/status", headers=AUTH,
                   json={"status": "suspended"})

    # Sort by email asc; capped count reflects the full set.
    asc = (await ac.get("/api/v1/admin/accounts?sort=email", headers=AUTH)).json()
    emails = [r["email"] for r in asc["items"]]
    assert emails == sorted(emails) and asc["count"] == 3 and asc["capped"] is False

    # Status filter (eq) + count reflects the filter.
    susp = (await ac.get("/api/v1/admin/accounts?status=suspended", headers=AUTH)).json()
    assert susp["count"] == 1 and susp["items"][0]["id"] == a["id"]

    # Unknown sort field -> 422 (whitelist).
    assert (await ac.get("/api/v1/admin/accounts?sort=password", headers=AUTH)
            ).status_code == 422

    # Keyset paging: limit caps the page; follow next_cursor to the last page.
    p1 = (await ac.get("/api/v1/admin/accounts?sort=email&limit=2", headers=AUTH)).json()
    assert len(p1["items"]) == 2 and p1["count"] == 3 and p1["next_cursor"]
    p2 = (await ac.get(
        f"/api/v1/admin/accounts?sort=email&limit=2&cursor={p1['next_cursor']}",
        headers=AUTH)).json()
    assert len(p2["items"]) == 1 and p2["next_cursor"] is None
    # No overlap / no skip across the two pages.
    ids = [r["id"] for r in p1["items"]] + [r["id"] for r in p2["items"]]
    assert len(set(ids)) == 3


@pytest.mark.asyncio
async def test_list_keyset_nullable_sort_no_skip(client):
    """End-to-end null-safety: sorting by a nullable column (display_name) and
    paging one row at a time must surface every account, NULLs included."""
    ac, _ = client
    seeded = []
    for email, dn in [("n1@corp.com", "Zed"), ("n2@corp.com", None),
                      ("n3@corp.com", "Amy"), ("n4@corp.com", None)]:
        body = {"email": email, "password": "Secret123"}
        if dn is not None:
            body["display_name"] = dn
        seeded.append((await ac.post("/api/v1/admin/accounts", headers=AUTH,
                                     json=body)).json()["id"])

    seen, cursor, guard = [], None, 0
    while guard < 20:
        guard += 1
        url = "/api/v1/admin/accounts?sort=display_name&limit=1"
        if cursor:
            url += f"&cursor={cursor}"
        page = (await ac.get(url, headers=AUTH)).json()
        seen.extend(r["id"] for r in page["items"])
        cursor = page["next_cursor"]
        if not cursor:
            break
    assert set(seeded).issubset(set(seen))      # no NULL-row dropped
    assert len(seen) == len(set(seen))          # no duplicates


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
async def test_get_and_update_account(client):
    ac, _ = client
    a = (await ac.post("/api/v1/admin/accounts", headers=AUTH,
                       json={"email": "edit@corp.com", "password": "Secret123"})).json()
    g = (await ac.get(f"/api/v1/admin/accounts/{a['id']}", headers=AUTH)).json()
    etag = g["etag"]
    assert etag and g["email"] == "edit@corp.com"

    # Update display_name (correct etag) -> 200; etag rotates (content changed).
    ok = await ac.put(f"/api/v1/admin/accounts/{a['id']}", headers={**AUTH, "If-Match": etag},
                      json={"display_name": "Edited"})
    assert ok.status_code == 200 and ok.json()["display_name"] == "Edited"
    new_etag = (await ac.get(f"/api/v1/admin/accounts/{a['id']}", headers=AUTH)).json()["etag"]
    assert new_etag != etag
    # Stale etag -> 409.
    assert (await ac.put(f"/api/v1/admin/accounts/{a['id']}", headers={**AUTH, "If-Match": etag},
                         json={"display_name": "Race"})).status_code == 409
    # Unknown account -> 404.
    assert (await ac.get("/api/v1/admin/accounts/ghost", headers=AUTH)).status_code == 404


@pytest.mark.asyncio
async def test_export_csv(client):
    ac, _ = client
    await ac.post("/api/v1/admin/accounts", headers=AUTH,
                  json={"email": "exp1@corp.com", "password": "Secret123"})
    await ac.post("/api/v1/admin/accounts", headers=AUTH,
                  json={"email": "exp2@corp.com", "password": "Secret123"})
    r = await ac.get("/api/v1/admin/accounts/export", headers=AUTH)
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/csv")
    lines = r.text.strip().splitlines()
    assert lines[0].startswith("id,account_number,email")
    assert any("exp1@corp.com" in ln for ln in lines[1:])
    # Filter carries into the export.
    one = await ac.get("/api/v1/admin/accounts/export?q=exp1", headers=AUTH)
    body = one.text.strip().splitlines()
    assert len(body) == 2  # header + 1 row


@pytest.mark.asyncio
async def test_statuses_catalog(client):
    ac, _ = client
    r = await ac.get("/api/v1/admin/accounts/statuses", headers=AUTH)
    assert r.status_code == 200
    assert set(r.json()["statuses"]) == {
        "pending_identity", "active", "suspended", "deactivated"}
