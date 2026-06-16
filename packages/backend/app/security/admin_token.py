"""Bootstrap admin-token gate for /admin/* (D1).

Minimal protection until full auth lands in D4. The token comes from the deploy
secrets (OpenBao / .env.secrets -> ADMIN_TOKEN env). If unset, the admin API is
LOCKED (503) rather than open — fail closed.
"""

from __future__ import annotations

import datetime as _dt
import logging

from fastapi import Header, HTTPException, status

from app.config import get_settings

logger = logging.getLogger(__name__)


def _parse_iso(s: str) -> _dt.datetime | None:
    try:
        d = _dt.datetime.fromisoformat(s)
        return d if d.tzinfo else d.replace(tzinfo=_dt.timezone.utc)
    except ValueError:
        return None


def break_glass_allowed(x_admin_token: str | None, ip: str | None) -> bool:
    """PAM-hardened break-glass check (D4.9): the static admin token bypasses
    RBAC ONLY if it matches AND is not past its optional expiry AND the caller IP
    is in the optional allowlist. Disable entirely by leaving admin_token empty.
    Every successful use is logged (break-glass must be traceable)."""
    s = get_settings()
    if not s.admin_token or x_admin_token != s.admin_token:
        return False
    if s.admin_token_expires_at:
        exp = _parse_iso(s.admin_token_expires_at)
        if exp is not None and _dt.datetime.now(tz=_dt.timezone.utc) >= exp:
            logger.warning("break-glass token presented but EXPIRED (ip=%s)", ip)
            return False
    allow = [x.strip() for x in s.admin_token_allowed_ips.split(",") if x.strip()]
    if allow and (ip or "") not in allow:
        logger.warning("break-glass token from non-allowlisted ip=%s", ip)
        return False
    logger.warning("BREAK-GLASS admin-token used (ip=%s) — bypasses RBAC", ip)
    return True


async def require_admin_token(x_admin_token: str | None = Header(default=None)) -> None:
    token = get_settings().admin_token
    if not token:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "admin API locked: ADMIN_TOKEN is not configured",
        )
    if not x_admin_token or x_admin_token != token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid admin token")
