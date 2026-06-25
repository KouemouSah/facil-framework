"""D4.2 auth core — password (bcrypt), TOTP, NativeAuthProvider (JWT)."""

from __future__ import annotations

import pyotp
import pytest

from app.auth import password, totp
from app.core.providers.auth_native import NativeAuthProvider
from app.core.providers.registry import default_registry
from app.security import crypto


# --- password ------------------------------------------------------------

def test_break_glass_policy(monkeypatch):
    import app.config as cfg
    from app.security import admin_token as at
    monkeypatch.setenv("ADMIN_TOKEN", "tok")
    # wrong token never allowed
    cfg._settings = None
    assert at.break_glass_allowed("wrong", "1.2.3.4") is False
    # expired -> denied
    monkeypatch.setenv("ADMIN_TOKEN_EXPIRES_AT", "2000-01-01T00:00:00+00:00")
    cfg._settings = None
    assert at.break_glass_allowed("tok", "1.2.3.4") is False
    monkeypatch.delenv("ADMIN_TOKEN_EXPIRES_AT")
    # IP allowlist enforced
    monkeypatch.setenv("ADMIN_TOKEN_ALLOWED_IPS", "10.0.0.1, 10.0.0.2")
    cfg._settings = None
    assert at.break_glass_allowed("tok", "1.2.3.4") is False
    assert at.break_glass_allowed("tok", "10.0.0.2") is True
    # no policy -> allowed
    monkeypatch.delenv("ADMIN_TOKEN_ALLOWED_IPS")
    cfg._settings = None
    assert at.break_glass_allowed("tok", "anything") is True
    cfg._settings = None


def test_crypto_roundtrip_and_tamper(monkeypatch):
    monkeypatch.setenv("TOTP_ENCRYPTION_KEY", "unit-test-key-0123456789abcdef")
    from app.security import crypto
    token = crypto.encrypt("JBSWY3DPEHPK3PXP")
    assert token != "JBSWY3DPEHPK3PXP"               # not plaintext
    assert crypto.decrypt(token) == "JBSWY3DPEHPK3PXP"
    with pytest.raises(crypto.DecryptionError):
        crypto.decrypt(token[:-4] + "AAAA")          # tampered ciphertext


def test_backup_codes_generate_and_consume():
    from app.auth import backup_codes as bc
    plain, hashes = bc.generate()
    assert len(plain) == len(hashes) == 10
    assert all(h not in plain for h in hashes)        # stored as hashes, not raw
    ok, remaining = bc.verify_and_consume(hashes, plain[0])
    assert ok and len(remaining) == 9
    again, _ = bc.verify_and_consume(remaining, plain[0])
    assert not again                                  # single-use


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
    assert password.check_strength("Tr0ub4dourXl")[0] is True    # 12, mixed, uncommon
    assert password.check_strength("Abcdef12")[0] is False      # < 12 (SEC-009)
    assert password.check_strength("short1A")[0] is False       # < 12
    assert password.check_strength("alllowercase1")[0] is False  # no upper (13)
    assert password.check_strength("ALLUPPERCASE1")[0] is False  # no lower (13)
    assert password.check_strength("NoDigitsHere!")[0] is False  # no digit (13)
    assert password.check_strength("Password1234")[0] is False   # too common (core 'password')


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


# --- crypto (TOTP secret at rest, AES-GCM) — key separation (SEC-008) ----

def test_crypto_roundtrip_with_distinct_key(monkeypatch):
    monkeypatch.setenv("TOTP_ENCRYPTION_KEY", "a-distinct-totp-key")
    token = crypto.encrypt("shared-secret")
    assert crypto.decrypt(token) == "shared-secret"


def test_crypto_jwt_fallback_allowed_in_dev(monkeypatch):
    monkeypatch.delenv("TOTP_ENCRYPTION_KEY", raising=False)
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("JWT_SECRET_KEY", "jwt-signing-secret")
    assert crypto.decrypt(crypto.encrypt("x")) == "x"  # dev tolerates key reuse


def test_crypto_requires_distinct_key_in_prod(monkeypatch):
    # Reusing the JWT signing secret to encrypt 2FA secrets at rest = no domain
    # separation; refused in production.
    monkeypatch.delenv("TOTP_ENCRYPTION_KEY", raising=False)
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("JWT_SECRET_KEY", "jwt-signing-secret")
    with pytest.raises(RuntimeError, match="TOTP_ENCRYPTION_KEY"):
        crypto.encrypt("x")


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
async def test_secret_falls_back_to_jwt_secret_key(monkeypatch):
    # No injected secret, no JWT_SECRET -> must fall back to JWT_SECRET_KEY
    # (the canonical framework / .env.secrets name) and NOT boot with "".
    monkeypatch.delenv("JWT_SECRET", raising=False)
    monkeypatch.setenv("JWT_SECRET_KEY", _SECRET)
    p = NativeAuthProvider({"issuer": "facil"})
    tokens = await p.issue("acc-1")          # would raise if HMAC key were empty
    assert (await p.verify(tokens["access"]))["sub"] == "acc-1"


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
