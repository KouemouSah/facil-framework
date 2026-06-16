"""require_auth — accept a Bearer JWT (native or a federated OIDC IdP) OR the
bootstrap admin token (break-glass). Returns the principal claims.

For a token validated by a NON-native verifier (e.g. keycloak_oidc), the external
identity is resolved to a LOCAL account (link / JIT-provision + IdP role sync, see
app.auth.federation) and `sub` is rewritten to the local account id — so RBAC scope
applies unchanged. The admin-token path is the migration bridge until RBAC fully
replaces it.
"""

from __future__ import annotations

import json

from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_session
from app.security.admin_token import break_glass_allowed


def _role_map(resolver) -> dict:
    raw = resolver.resolve("auth.oidc.role_map", {})
    if isinstance(raw, str):
        try:
            return json.loads(raw or "{}")
        except ValueError:
            return {}
    return raw or {}


async def require_auth(request: Request,
                       authorization: str | None = Header(default=None),
                       x_admin_token: str | None = Header(default=None),
                       session: AsyncSession = Depends(get_session)) -> dict:
    ip = request.client.host if request.client else None
    if x_admin_token and break_glass_allowed(x_admin_token, ip):
        return {"sub": "bootstrap-admin", "break_glass": True}
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization.split(" ", 1)[1]
        verifiers = getattr(request.app.state, "auth_verifiers", None) \
            or [request.app.state.auth]
        for verifier in verifiers:
            claims = await verifier.verify(token)
            if claims is None:
                continue
            code = getattr(verifier, "code", "native")
            if code == "native":
                return claims
            # Federated (OIDC) token: honour IdP-initiated revocation
            # (back-channel logout) — deny if the token's session id was revoked.
            # Backed by the shared cache (global across replicas at scale).
            from app.auth import federation
            cache = getattr(request.app.state, "cache", None)
            if cache is not None:
                marker = claims.get("sid") or claims.get("jti")
                if marker and await cache.exists(f"oidc_revoked:{marker}"):
                    await cache.delete("fed:" + federation._cache_key(
                        code, claims, token))
                    continue  # revoked -> 401
            # Resolve to a local account + sync roles, reusing a per-token cached
            # resolution (TTL) to avoid a DB write on every request (D4.8 #3).
            resolver = request.app.state.resolver
            principal, wrote = await federation.resolve_cached(
                cache, session, code, claims, token, role_map=_role_map(resolver),
                introspect=getattr(verifier, "introspect", None),
                claim_groups=resolver.resolve("auth.oidc.claim_groups", "groups"),
                claim_org=resolver.resolve("auth.oidc.claim_org", "org"),
                claim_unit=resolver.resolve("auth.oidc.claim_unit", "unit"))
            if principal is None:
                continue  # disabled/unresolvable account -> try next / 401
            if wrote:
                await session.commit()
            return principal
    raise HTTPException(status.HTTP_401_UNAUTHORIZED, "authentication required")
