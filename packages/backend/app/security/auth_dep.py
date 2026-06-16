"""require_auth — accept a Bearer JWT (NativeAuthProvider) OR the bootstrap admin
token (break-glass). Returns the token claims (principal). The admin-token path
is the migration bridge until RBAC wholesale-replaces it (D4.4).
"""

from __future__ import annotations

from fastapi import Header, HTTPException, Request, status

from app.config import get_settings


async def require_auth(request: Request,
                       authorization: str | None = Header(default=None),
                       x_admin_token: str | None = Header(default=None)) -> dict:
    admin = get_settings().admin_token
    if x_admin_token and admin and x_admin_token == admin:
        return {"sub": "bootstrap-admin", "break_glass": True}
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization.split(" ", 1)[1]
        # Try each configured verifier (native, and optionally keycloak_oidc /
        # other OIDC IdPs) — the first to validate the token wins. Falls back to
        # the single native provider when no verifier list is configured.
        verifiers = getattr(request.app.state, "auth_verifiers", None) \
            or [request.app.state.auth]
        for verifier in verifiers:
            claims = await verifier.verify(token)
            if claims is not None:
                return claims
    raise HTTPException(status.HTTP_401_UNAUTHORIZED, "authentication required")
