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
from app.config import get_settings


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
    admin = get_settings().admin_token
    if x_admin_token and admin and x_admin_token == admin:
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
            # Federated (OIDC) token: resolve to a local account + sync roles,
            # reusing a per-token cached resolution (TTL) to avoid a DB write on
            # every request (D4.8 #3). Commit only when a real write happened.
            from app.auth import federation
            resolver = request.app.state.resolver
            cache = getattr(request.app.state, "federation_cache", None)
            principal, wrote = await federation.resolve_cached(
                cache, session, code, claims, token, role_map=_role_map(resolver),
                claim_groups=resolver.resolve("auth.oidc.claim_groups", "groups"),
                claim_org=resolver.resolve("auth.oidc.claim_org", "org"),
                claim_unit=resolver.resolve("auth.oidc.claim_unit", "unit"))
            if principal is None:
                continue  # disabled/unresolvable account -> try next / 401
            if wrote:
                await session.commit()
            return principal
    raise HTTPException(status.HTTP_401_UNAUTHORIZED, "authentication required")
