"""NativeAuthProvider — JWT (HS256) access + refresh tokens.

The sovereign default auth provider (registered as auth/native). Stateless JWT:
short-lived access token + longer refresh token (rotated). The signing secret
comes from the rendered env (JWT_SECRET) or injected config — never hard-coded.
Keycloak / OIDC providers implement the same AuthProvider ABC and land later.

Password hashing (bcrypt) and TOTP live in app/auth/{password,totp}.py; this
provider only mints/verifies tokens (the auth surface that varies by mechanism).
"""

from __future__ import annotations

import datetime as _dt
import os

import jwt

from app.core.providers.base import AuthProvider, cfg


class NativeAuthProvider(AuthProvider):
    code = "native"

    @classmethod
    def config_schema(cls):
        # JWT signing secret travels via secret_ref/env (JWT_SECRET), never here.
        return [
            cfg("issuer", "Issuer", default="facil"),
            cfg("access_ttl_seconds", "Access token TTL (s)", type="number", default=3600),
            cfg("refresh_ttl_seconds", "Refresh token TTL (s)", type="number", default=604800),
        ]

    def __init__(self, config=None) -> None:
        super().__init__(config)
        # Injected config wins; else env JWT_SECRET, with a fallback to the
        # canonical framework secret name JWT_SECRET_KEY (init.py/manifest/
        # .env.secrets use that name, while ensure_secrets/compose use JWT_SECRET
        # — accept either so a deployment never boots with an empty HMAC key).
        self._secret = (self.config.get("secret")
                        or os.environ.get("JWT_SECRET")
                        or os.environ.get("JWT_SECRET_KEY", ""))
        self._alg = "HS256"
        self._issuer = self.config.get("issuer", "facil")
        self._access_ttl = int(self.config.get("access_ttl_seconds", 3600))
        self._refresh_ttl = int(self.config.get("refresh_ttl_seconds", 7 * 24 * 3600))

    def _encode(self, subject: str, ttl: int, token_type: str,
                claims: dict | None) -> str:
        now = _dt.datetime.now(tz=_dt.timezone.utc)
        payload = {"sub": subject, "type": token_type, "iss": self._issuer,
                   "iat": now, "exp": now + _dt.timedelta(seconds=ttl)}
        if claims:
            payload.update(claims)
        return jwt.encode(payload, self._secret, algorithm=self._alg)

    async def issue(self, subject: str, claims: dict | None = None,
                    *, jti: str | None = None) -> dict:
        # `jti` (the session id) goes on BOTH tokens so the service can tie a
        # refresh token to its revocable session row (rotation + reuse detection).
        access_claims = dict(claims or {})
        refresh_claims: dict = {}
        if jti is not None:
            access_claims["jti"] = jti
            refresh_claims["jti"] = jti
        return {
            "access": self._encode(subject, self._access_ttl, "access", access_claims),
            "refresh": self._encode(subject, self._refresh_ttl, "refresh",
                                    refresh_claims or None),
        }

    async def verify(self, token: str, *, expect: str = "access") -> dict | None:
        try:
            payload = jwt.decode(token, self._secret, algorithms=[self._alg],
                                 issuer=self._issuer)
        except jwt.PyJWTError:
            return None
        if expect and payload.get("type") != expect:
            return None
        return payload

    async def refresh(self, refresh_token: str) -> dict | None:
        payload = await self.verify(refresh_token, expect="refresh")
        if payload is None:
            return None
        return await self.issue(payload["sub"])

    async def healthcheck(self) -> dict:
        ok = bool(self._secret)
        return {"ok": ok,
                "detail": "JWT secret configured" if ok else "JWT_SECRET not set"}
