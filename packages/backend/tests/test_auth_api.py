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
async def test_me_whoami(client):
    ac, _ = client
    # no auth -> 401
    assert (await ac.get(f"{A}/me")).status_code == 401
    # break-glass admin token -> flagged
    from tests.conftest import AUTH
    bg = await ac.get(f"{A}/me", headers=AUTH)
    assert bg.status_code == 200 and bg.json()["break_glass"] is True
    # JWT principal -> account echoed
    await _register(ac, email="me@x.io")
    t = (await ac.post(f"{A}/login", json={"identifier": "me@x.io", "password": PW})).json()
    me = await ac.get(f"{A}/me", headers={"Authorization": f"Bearer {t['access']}"})
    assert me.status_code == 200
    assert me.json()["account"]["email"] == "me@x.io" and me.json()["break_glass"] is False


@pytest.mark.asyncio
async def test_idle_timeout_disconnects(client):
    import datetime as dt
    from sqlalchemy import select
    from app.auth.models import Session
    ac, db = client
    await _register(ac, email="idle@x.io")
    t = (await ac.post(f"{A}/login", json={"identifier": "idle@x.io", "password": PW})).json()
    # backdate last activity beyond the 1 h user idle window
    async with db.session_factory() as s:
        sess = (await s.scalars(select(Session))).first()
        sess.last_used_at = dt.datetime.now(tz=dt.timezone.utc) - dt.timedelta(hours=2)
        await s.commit()
    r = await ac.post(f"{A}/refresh", json={"refresh_token": t["refresh"]})
    assert r.status_code == 401  # idle-expired -> client re-authenticates


@pytest.mark.asyncio
async def test_agent_is_single_session(client):
    from sqlalchemy import select
    from app.identity.models import Account
    ac, db = client
    acc = (await _register(ac, email="agent@x.io")).json()
    # mark the account as an agent -> single-session enforced
    async with db.session_factory() as s:
        a = await s.get(Account, acc["id"])
        a.subject_type = "agent"
        await s.commit()
    t1 = (await ac.post(f"{A}/login", json={"identifier": "agent@x.io", "password": PW})).json()
    t2 = (await ac.post(f"{A}/login", json={"identifier": "agent@x.io", "password": PW})).json()
    # the second login revoked the first device's session
    assert (await ac.post(f"{A}/refresh", json={"refresh_token": t1["refresh"]})).status_code == 401
    assert (await ac.post(f"{A}/refresh", json={"refresh_token": t2["refresh"]})).status_code == 200


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
async def test_password_reset_flow(client):
    ac, db = client
    await _register(ac, email="pr@x.io")
    # mint a real reset token at the service layer (the raw token is mailed IRL)
    from app.auth import service as auth_service
    async with db.session_factory() as s:
        raw = await auth_service.request_password_reset(s, "pr@x.io")
        await s.commit()
    new_pw = "N3wStr0ng!pass"
    done = await ac.post(f"{A}/password-reset/confirm",
                         json={"token": raw, "new_password": new_pw})
    assert done.status_code == 200
    # new password works, old one does not
    assert (await ac.post(f"{A}/login",
                          json={"identifier": "pr@x.io", "password": new_pw})).status_code == 200
    assert (await ac.post(f"{A}/login",
                          json={"identifier": "pr@x.io", "password": PW})).status_code == 401
    # the reset token is single-use
    assert (await ac.post(f"{A}/password-reset/confirm",
                          json={"token": raw, "new_password": new_pw})).status_code == 400


@pytest.mark.asyncio
async def test_password_reset_is_anti_enumeration(client):
    ac, _ = client
    # unknown email -> still 200 (no oracle); bad token -> 400
    assert (await ac.post(f"{A}/password-reset/request",
                          json={"email": "nobody@x.io"})).status_code == 200
    assert (await ac.post(f"{A}/password-reset/confirm",
                          json={"token": "bogus", "new_password": "N3wStr0ng!pass"})
            ).status_code == 400


@pytest.mark.asyncio
async def test_email_verification_flow(client):
    ac, db = client
    acc = (await _register(ac, email="ev@x.io")).json()
    from app.auth import service as auth_service
    async with db.session_factory() as s:
        raw = await auth_service.request_email_verification(s, acc["id"])
        await s.commit()
    r = await ac.post(f"{A}/email-verification/confirm", json={"token": raw})
    assert r.status_code == 200 and r.json()["email_verified"] is True
    # account now flagged verified
    from app.identity import repository as identity_repo
    async with db.session_factory() as s:
        a = await identity_repo.get_account(s, acc["id"])
        assert a.email_verified is True


@pytest.mark.asyncio
async def test_oversized_payload_rejected(client):
    ac, _ = client
    big = "x" * (1024 * 1024 + 64)  # > 1 MB
    r = await ac.post(f"{A}/register",
                      json={"email": "big@x.io", "password": PW, "display_name": big})
    assert r.status_code == 413


@pytest.mark.asyncio
async def test_register_is_rate_limited(client):
    ac, _ = client
    # register limit = 10/min per IP; the 11th in the window -> 429
    codes = []
    for i in range(12):
        r = await ac.post(f"{A}/register",
                          json={"email": f"rl{i}@x.io", "password": PW})
        codes.append(r.status_code)
    assert 429 in codes
    assert codes[:10] == [201] * 10  # first 10 allowed


@pytest.mark.asyncio
async def test_login_writes_audit(client):
    ac, db = client
    await _register(ac, email="au@x.io")
    await ac.post(f"{A}/login", json={"identifier": "au@x.io", "password": PW})
    await ac.post(f"{A}/login", json={"identifier": "au@x.io", "password": "wrong"})
    from sqlalchemy import select
    from app.auth.models import AuthAudit
    async with db.session_factory() as s:
        rows = (await s.scalars(select(AuthAudit))).all()
    actions = {r.action for r in rows}
    assert "login" in actions and "login_failed" in actions


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
async def test_2fa_backup_code_login_is_single_use(client):
    ac, _ = client
    await _register(ac, email="bk@x.io")
    tokens = (await ac.post(f"{A}/login", json={"identifier": "bk@x.io", "password": PW})).json()
    hdr = {"Authorization": f"Bearer {tokens['access']}"}
    secret = (await ac.post(f"{A}/2fa/setup", headers=hdr)).json()["secret"]
    enabled = await ac.post(f"{A}/2fa/enable", headers=hdr,
                            json={"code": pyotp.TOTP(secret).now()})
    backup = enabled.json()["backup_codes"]
    assert len(backup) == 10
    # log in with a backup code (as the 2fa code)
    ok = await ac.post(f"{A}/login", json={"identifier": "bk@x.io", "password": PW,
                                           "totp_code": backup[0]})
    assert ok.status_code == 200
    # the same backup code cannot be reused
    again = await ac.post(f"{A}/login", json={"identifier": "bk@x.io", "password": PW,
                                              "totp_code": backup[0]})
    assert again.status_code == 401


@pytest.mark.asyncio
async def test_2fa_requires_auth(client):
    ac, _ = client
    assert (await ac.post(f"{A}/2fa/setup")).status_code == 401  # no token
    # break-glass admin token authenticates but has no credential -> 400
    from tests.conftest import AUTH
    assert (await ac.post(f"{A}/2fa/setup", headers=AUTH)).status_code == 400
