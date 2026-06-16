"""KeycloakOIDCProvider — JWKS RS256 verification (D4.6) + verifier chain.

Uses a real RSA keypair and a MockTransport-served JWKS (no live Keycloak).
"""

from __future__ import annotations

import datetime as _dt
import json
import types

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from app.core.providers.auth_keycloak_oidc import KeycloakOIDCProvider

ISS = "https://kc.example/realms/facil"
AUD = "facil-backend"
JWKS_URI = f"{ISS}/protocol/openid-connect/certs"
KID = "test-kid-1"

_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)


def _jwks() -> dict:
    jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(_KEY.public_key()))
    jwk.update({"kid": KID, "alg": "RS256", "use": "sig"})
    return {"keys": [jwk]}


def _token(*, iss=ISS, aud=AUD, sub="user-1", exp_delta=3600, kid=KID) -> str:
    now = _dt.datetime.now(tz=_dt.timezone.utc)
    payload = {"sub": sub, "iss": iss, "aud": aud, "iat": now,
               "exp": now + _dt.timedelta(seconds=exp_delta)}
    return jwt.encode(payload, _KEY, algorithm="RS256", headers={"kid": kid})


def _provider(jwks: dict | None = None) -> KeycloakOIDCProvider:
    served = jwks if jwks is not None else _jwks()
    transport = httpx.MockTransport(lambda req: httpx.Response(200, json=served))
    return KeycloakOIDCProvider({"issuer": ISS, "jwks_uri": JWKS_URI,
                                 "audience": AUD, "transport": transport})


@pytest.mark.asyncio
async def test_valid_token_verifies():
    claims = await _provider().verify(_token())
    assert claims is not None and claims["sub"] == "user-1"


@pytest.mark.asyncio
async def test_wrong_audience_rejected():
    p = _provider()
    assert await p.verify(_token(aud="some-other-client")) is None


@pytest.mark.asyncio
async def test_wrong_issuer_rejected():
    p = _provider()
    assert await p.verify(_token(iss="https://evil/realms/x")) is None


@pytest.mark.asyncio
async def test_expired_token_rejected():
    p = _provider()
    assert await p.verify(_token(exp_delta=-10)) is None


@pytest.mark.asyncio
async def test_unknown_kid_rejected():
    p = _provider()
    assert await p.verify(_token(kid="not-in-jwks")) is None


@pytest.mark.asyncio
async def test_token_signed_by_other_key_rejected():
    other = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    now = _dt.datetime.now(tz=_dt.timezone.utc)
    forged = jwt.encode({"sub": "x", "iss": ISS, "aud": AUD, "iat": now,
                         "exp": now + _dt.timedelta(hours=1)},
                        other, algorithm="RS256", headers={"kid": KID})
    assert await _provider().verify(forged) is None


@pytest.mark.asyncio
async def test_issue_and_refresh_not_implemented():
    p = _provider()
    with pytest.raises(NotImplementedError):
        await p.issue("user-1")
    with pytest.raises(NotImplementedError):
        await p.refresh("whatever")


@pytest.mark.asyncio
async def test_require_auth_tries_each_verifier(monkeypatch):
    # native verifier rejects (None), OIDC verifier accepts -> chain returns it.
    from app.security import auth_dep

    class _V:
        def __init__(self, result):
            self._r = result
        async def verify(self, token):
            return self._r

    app = types.SimpleNamespace(state=types.SimpleNamespace(
        auth=_V(None), auth_verifiers=[_V(None), _V({"sub": "kc-user"})]))
    request = types.SimpleNamespace(app=app)
    monkeypatch.setattr(auth_dep, "get_settings",
                        lambda: types.SimpleNamespace(admin_token="x"))
    claims = await auth_dep.require_auth(request, authorization="Bearer abc",
                                         x_admin_token=None)
    assert claims == {"sub": "kc-user"}
