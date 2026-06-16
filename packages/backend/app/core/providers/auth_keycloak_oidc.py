"""KeycloakOIDCProvider — verify OIDC (Keycloak) access tokens (D4.6).

In the OIDC model the IdP (Keycloak) issues tokens via the browser
authorization-code flow; the backend's job is to VERIFY them. This provider
implements `verify()` against the realm's JWKS (RS256): it fetches the signing
keys, checks the signature + issuer + audience, and returns the claims.

`issue()`/`refresh()` are NOT implemented here — token issuance belongs to the
IdP (the auth-code flow at the edge/frontend), not the resource server. Native
self-service issuance stays with NativeAuthProvider.

Config: {issuer, jwks_uri, audience?, algorithms?=["RS256"]}. `transport` may be
injected (httpx MockTransport) for tests. Keys are cached and re-fetched on a
`kid` miss (handles key rotation).
"""

from __future__ import annotations

import json

import httpx
import jwt

from app.core.providers.base import AuthProvider


class KeycloakOIDCProvider(AuthProvider):
    code = "keycloak_oidc"

    def __init__(self, config=None) -> None:
        super().__init__(config)
        self._issuer = self.config.get("issuer", "")
        # Explicit jwks_uri (override) OR discovered from the issuer's
        # .well-known/openid-configuration (the professional, standards path —
        # works with any OIDC IdP: Keycloak/Okta/Azure/Auth0).
        self._jwks_uri = self.config.get("jwks_uri", "")
        self._discovery_url = self.config.get("discovery_url") or (
            f"{self._issuer.rstrip('/')}/.well-known/openid-configuration"
            if self._issuer else "")
        self._audience = self.config.get("audience") or None
        self._algs = list(self.config.get("algorithms", ["RS256"]))
        self._transport = self.config.get("transport")  # httpx transport (tests)
        self._jwks: dict | None = None
        self._meta: dict | None = None  # cached discovery document

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(transport=self._transport, timeout=5)

    async def _discover(self) -> dict:
        """Fetch + cache the OIDC discovery document; derive jwks_uri/issuer."""
        if self._meta is not None:
            return self._meta
        async with self._client() as c:
            resp = await c.get(self._discovery_url)
            resp.raise_for_status()
            self._meta = resp.json()
        if not self._jwks_uri:
            self._jwks_uri = self._meta.get("jwks_uri", "")
        if not self._issuer:
            self._issuer = self._meta.get("issuer", "")
        return self._meta

    async def _ensure_jwks_uri(self) -> None:
        if not self._jwks_uri and self._discovery_url:
            await self._discover()

    async def _fetch_jwks(self, *, force: bool = False) -> dict:
        if self._jwks is not None and not force:
            return self._jwks
        await self._ensure_jwks_uri()
        async with self._client() as c:
            resp = await c.get(self._jwks_uri)
            resp.raise_for_status()
            self._jwks = resp.json()
        return self._jwks

    @staticmethod
    def _find_key(jwks: dict, kid: str | None) -> dict | None:
        for key in jwks.get("keys", []):
            if kid is None or key.get("kid") == kid:
                return key
        return None

    async def verify(self, token: str, *, expect: str = "access") -> dict | None:
        if not self._jwks_uri and not self._discovery_url:
            return None
        try:
            kid = jwt.get_unverified_header(token).get("kid")
        except jwt.PyJWTError:
            return None
        jwks = await self._fetch_jwks()
        jwk = self._find_key(jwks, kid)
        if jwk is None:  # unknown kid -> maybe rotated; refetch once
            jwks = await self._fetch_jwks(force=True)
            jwk = self._find_key(jwks, kid)
        if jwk is None:
            return None
        try:
            public_key = jwt.algorithms.RSAAlgorithm.from_jwk(json.dumps(jwk))
            return jwt.decode(
                token, public_key, algorithms=self._algs,
                audience=self._audience, issuer=self._issuer or None,
                options={"verify_aud": bool(self._audience)})
        except jwt.PyJWTError:
            return None

    async def issue(self, subject: str, claims: dict | None = None) -> dict:
        raise NotImplementedError(
            "OIDC tokens are issued by the IdP (Keycloak) via the auth-code flow, "
            "not by the resource server. Use NativeAuthProvider for self-service.")

    async def refresh(self, refresh_token: str) -> dict | None:
        raise NotImplementedError(
            "OIDC refresh is performed against the IdP token endpoint, not here.")

    async def healthcheck(self) -> dict:
        try:
            jwks = await self._fetch_jwks(force=True)
            n = len(jwks.get("keys", []))
            return {"ok": n > 0, "detail": f"{n} JWKS key(s)"}
        except Exception as e:  # noqa: BLE001 — health probe
            return {"ok": False, "detail": f"JWKS fetch failed: {e}"}
