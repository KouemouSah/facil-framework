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

from app.core.providers.base import AuthProvider


class NativeAuthProvider(AuthProvider):
    code = "native"

    def __init__(self, config=None) -> None:
        super().__init__(config)
        self._secret = self.config.get("secret") or os.environ.get("JWT_SECRET", "")
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

    async def issue(self, subject: str, claims: dict | None = None) -> dict:
        return {"access": self._encode(subject, self._access_ttl, "access", claims),
                "refresh": self._encode(subject, self._refresh_ttl, "refresh", None)}

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
