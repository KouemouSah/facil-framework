"""Bootstrap admin-token gate for /admin/* (D1).

Minimal protection until full auth lands in D4. The token comes from the deploy
secrets (OpenBao / .env.secrets -> ADMIN_TOKEN env). If unset, the admin API is
LOCKED (503) rather than open — fail closed.
"""

from __future__ import annotations

from fastapi import Header, HTTPException, status

from app.config import get_settings


async def require_admin_token(x_admin_token: str | None = Header(default=None)) -> None:
    token = get_settings().admin_token
    if not token:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "admin API locked: ADMIN_TOKEN is not configured",
        )
    if not x_admin_token or x_admin_token != token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid admin token")
