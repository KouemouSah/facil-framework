"""Auth API — register / login (email & NIU) / lockout / refresh / 2FA (D4.2)."""

from __future__ import annotations

import pyotp
import pytest

A = "/api/v1/auth"
PW = "Str0ngPass"


async def _register(ac, email="u@x.io", password=PW):
    return await ac.post(f"{A}/register", json={"email": email, "password": password})


@pytest.mark.asyncio
async def test_register_creates_account_with_niu(client):
    ac, _ = client
    r = await _register(ac)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["email"] == "u@x.io" and body["account_number"] and body["status"] == "active"


@pytest.mark.asyncio
async def test_register_weak_password_and_dup_email(client):
    ac, _ = client
    assert (await _register(ac, email="w@x.io", password="weak")).status_code == 422
    await _register(ac, email="dup@x.io")
    assert (await _register(ac, email="dup@x.io")).status_code == 409


@pytest.mark.asyncio
async def test_login_by_email_and_niu(client):
    ac, _ = client
    niu = (await _register(ac, email="log@x.io")).json()["account_number"]
    by_email = await ac.post(f"{A}/login", json={"identifier": "log@x.io", "password": PW})
    assert by_email.status_code == 200 and by_email.json()["access"]
    by_niu = await ac.post(f"{A}/login", json={"identifier": niu, "password": PW})
    assert by_niu.status_code == 200 and by_niu.json()["account"]["account_number"] == niu


@pytest.mark.asyncio
async def test_login_invalid_is_uniform_401(client):
    ac, _ = client
    await _register(ac, email="real@x.io")
    assert (await ac.post(f"{A}/login", json={"identifier": "real@x.io",
                                              "password": "WrongPass1"})).status_code == 401
    assert (await ac.post(f"{A}/login", json={"identifier": "ghost@x.io",
                                              "password": PW})).status_code == 401


@pytest.mark.asyncio
async def test_lockout_after_repeated_failures(client):
    ac, _ = client
    await _register(ac, email="lock@x.io")
    for _ in range(5):
        r = await ac.post(f"{A}/login", json={"identifier": "lock@x.io", "password": "Bad1pass"})
        assert r.status_code == 401
    locked = await ac.post(f"{A}/login", json={"identifier": "lock@x.io", "password": PW})
    assert locked.status_code == 423  # correct password now, but locked


@pytest.mark.asyncio
async def test_refresh_rotation(client):
    ac, _ = client
    await _register(ac, email="rf@x.io")
    tokens = (await ac.post(f"{A}/login", json={"identifier": "rf@x.io", "password": PW})).json()
    r = await ac.post(f"{A}/refresh", json={"refresh_token": tokens["refresh"]})
    assert r.status_code == 200 and r.json()["access"]
    # an access token cannot be used to refresh
    assert (await ac.post(f"{A}/refresh",
                          json={"refresh_token": tokens["access"]})).status_code == 401


@pytest.mark.asyncio
async def test_refresh_token_reuse_is_detected(client):
    ac, _ = client
    await _register(ac, email="reuse@x.io")
    t0 = (await ac.post(f"{A}/login", json={"identifier": "reuse@x.io", "password": PW})).json()
    # First rotation succeeds and revokes t0's refresh token.
    t1 = (await ac.post(f"{A}/refresh", json={"refresh_token": t0["refresh"]})).json()
    assert t1["access"]
    # Re-using the OLD (already rotated) refresh token is rejected as theft...
    assert (await ac.post(f"{A}/refresh",
                          json={"refresh_token": t0["refresh"]})).status_code == 401
    # ...and that revokes the whole chain, so the rotated token is dead too.
    assert (await ac.post(f"{A}/refresh",
                          json={"refresh_token": t1["refresh"]})).status_code == 401


@pytest.mark.asyncio
async def test_logout_revokes_refresh(client):
    ac, _ = client
    await _register(ac, email="lo@x.io")
    t = (await ac.post(f"{A}/login", json={"identifier": "lo@x.io", "password": PW})).json()
    bearer = {"Authorization": f"Bearer {t['access']}"}
    out = await ac.post(f"{A}/logout", headers=bearer,
                        json={"refresh_token": t["refresh"]})
    assert out.status_code == 200
    # the refresh token no longer works after logout
    assert (await ac.post(f"{A}/refresh",
                          json={"refresh_token": t["refresh"]})).status_code == 401


@pytest.mark.asyncio
async def test_2fa_setup_enable_and_login(client):
    ac, _ = client
    await _register(ac, email="2fa@x.io")
    tokens = (await ac.post(f"{A}/login", json={"identifier": "2fa@x.io", "password": PW})).json()
    hdr = {"Authorization": f"Bearer {tokens['access']}"}
    setup = await ac.post(f"{A}/2fa/setup", headers=hdr)
    assert setup.status_code == 200
    secret = setup.json()["secret"]
    code = pyotp.TOTP(secret).now()
    assert (await ac.post(f"{A}/2fa/enable", headers=hdr, json={"code": code})).status_code == 200
    # now login requires the code
    assert (await ac.post(f"{A}/login", json={"identifier": "2fa@x.io",
                                              "password": PW})).status_code == 401  # totp_required
    ok = await ac.post(f"{A}/login", json={"identifier": "2fa@x.io", "password": PW,
                                           "totp_code": pyotp.TOTP(secret).now()})
    assert ok.status_code == 200


@pytest.mark.asyncio
async def test_2fa_requires_auth(client):
    ac, _ = client
    assert (await ac.post(f"{A}/2fa/setup")).status_code == 401  # no token
    # break-glass admin token authenticates but has no credential -> 400
    from tests.conftest import AUTH
    assert (await ac.post(f"{A}/2fa/setup", headers=AUTH)).status_code == 400
