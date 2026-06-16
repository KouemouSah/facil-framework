"""SCIM 2.0 provisioning API (D4.13) — create / filter / get / deprovision."""

from __future__ import annotations

import pytest

USER = "urn:ietf:params:scim:schemas:core:2.0:User"
PATCHOP = "urn:ietf:params:scim:api:messages:2.0:PatchOp"


def _scim_on(monkeypatch):
    monkeypatch.setenv("SCIM_TOKEN", "scim-secret")
    import app.config as cfg
    cfg._settings = None
    return {"Authorization": "Bearer scim-secret"}


@pytest.mark.asyncio
async def test_scim_locked_or_unauthorized(client):
    ac, _ = client
    # no SCIM_TOKEN configured -> locked (503)
    assert (await ac.get("/scim/v2/Users")).status_code == 503


@pytest.mark.asyncio
async def test_scim_user_lifecycle_and_deprovision(client, monkeypatch):
    ac, db = client
    H = _scim_on(monkeypatch)
    # bearer required
    assert (await ac.get("/scim/v2/Users")).status_code == 401
    # create (pre-provision) with externalId -> links a federated identity
    created = await ac.post("/scim/v2/Users", headers=H, json={
        "schemas": [USER], "userName": "agent@x.io",
        "name": {"givenName": "Agent", "familyName": "One"},
        "active": True, "externalId": "kc-123"})
    assert created.status_code == 201
    uid = created.json()["id"]
    assert created.json()["active"] is True
    # duplicate -> 409
    assert (await ac.post("/scim/v2/Users", headers=H, json={
        "schemas": [USER], "userName": "agent@x.io"})).status_code == 409
    # filter + get
    lst = await ac.get('/scim/v2/Users?filter=userName eq "agent@x.io"', headers=H)
    assert lst.status_code == 200 and lst.json()["totalResults"] == 1
    assert (await ac.get(f"/scim/v2/Users/{uid}", headers=H)).status_code == 200
    # DEPROVISION: PATCH active=false -> account deactivated + sessions revoked
    patched = await ac.patch(f"/scim/v2/Users/{uid}", headers=H, json={
        "schemas": [PATCHOP],
        "Operations": [{"op": "replace", "path": "active", "value": False}]})
    assert patched.status_code == 200 and patched.json()["active"] is False
    # verify in DB: account deactivated + the federated link exists
    from sqlalchemy import select
    from app.auth.models import FederatedIdentity
    from app.identity.models import Account
    async with db.session_factory() as s:
        acc = await s.get(Account, uid)
        assert acc.status == "deactivated"
        links = list(await s.scalars(
            select(FederatedIdentity).where(FederatedIdentity.subject == "kc-123")))
        assert len(links) == 1 and links[0].account_id == uid
