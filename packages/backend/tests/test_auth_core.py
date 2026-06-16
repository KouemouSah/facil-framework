"""D4.2 auth core — password (bcrypt), TOTP, NativeAuthProvider (JWT)."""

from __future__ import annotations

import pyotp
import pytest

from app.auth import password, totp
from app.core.providers.auth_native import NativeAuthProvider
from app.core.providers.registry import default_registry


# --- password ------------------------------------------------------------

def test_password_hash_and_verify():
    h = password.hash_password("Str0ngPass")
    assert h != "Str0ngPass"
    assert password.verify_password("Str0ngPass", h) is True
    assert password.verify_password("wrong", h) is False


def test_password_over_72_bytes_consistent():
    long = "A1" + "x" * 100
    h = password.hash_password(long)
    assert password.verify_password(long, h) is True  # truncation is consistent


def test_password_strength():
    assert password.check_strength("Abcdef12")[0] is True
    assert password.check_strength("short1A")[0] is False     # < 8
    assert password.check_strength("alllower123")[0] is False  # no upper
    assert password.check_strength("ALLUPPER123")[0] is False  # no lower
    assert password.check_strength("NoDigitsHere")[0] is False


# --- TOTP ----------------------------------------------------------------

def test_totp_verify():
    secret = totp.generate_secret()
    code = pyotp.TOTP(secret).now()
    assert totp.verify_code(secret, code) is True
    assert totp.verify_code(secret, "000000") is False
    assert totp.verify_code(secret, "") is False


def test_totp_provisioning_uri_uses_issuer():
    uri = totp.provisioning_uri(totp.generate_secret(), "user@x.io", issuer="MyGov")
    assert uri.startswith("otpauth://totp/") and "MyGov" in uri


# --- NativeAuthProvider (JWT) --------------------------------------------

_SECRET = "test-secret-0123456789abcdef0123456789abcdef"  # >= 32 bytes


def _provider(**cfg):
    base = {"secret": _SECRET, "issuer": "facil"}
    base.update(cfg)
    return NativeAuthProvider(base)


@pytest.mark.asyncio
async def test_issue_and_verify():
    p = _provider()
    tokens = await p.issue("acc-1", {"role": "admin"})
    claims = await p.verify(tokens["access"])
    assert claims is not None and claims["sub"] == "acc-1" and claims["role"] == "admin"
    assert claims["type"] == "access"


@pytest.mark.asyncio
async def test_access_token_not_accepted_as_refresh():
    p = _provider()
    tokens = await p.issue("acc-1")
    assert await p.verify(tokens["access"], expect="refresh") is None
    assert await p.verify(tokens["refresh"], expect="refresh") is not None


@pytest.mark.asyncio
async def test_tampered_and_wrong_secret_rejected():
    p = _provider()
    tokens = await p.issue("acc-1")
    assert await p.verify(tokens["access"] + "x") is None       # tampered
    other = _provider(secret="different-secret-0123456789abcdef0123456789")
    assert await other.verify(tokens["access"]) is None  # wrong key


@pytest.mark.asyncio
async def test_expired_token_rejected():
    p = _provider(access_ttl_seconds=-1)  # already expired
    tokens = await p.issue("acc-1")
    assert await p.verify(tokens["access"]) is None


@pytest.mark.asyncio
async def test_refresh_rotation():
    p = _provider()
    tokens = await p.issue("acc-1")
    rotated = await p.refresh(tokens["refresh"])
    assert rotated is not None
    assert (await p.verify(rotated["access"]))["sub"] == "acc-1"
    assert await p.refresh(tokens["access"]) is None  # access can't refresh


@pytest.mark.asyncio
async def test_healthcheck_and_registered():
    assert (await _provider().healthcheck())["ok"] is True
    assert (await NativeAuthProvider({}).healthcheck())["ok"] is False  # no secret
    assert default_registry().is_registered("auth", "native")
