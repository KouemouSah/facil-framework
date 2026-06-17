"""Auth audit recording (D4.5/B4).

`record()` appends an AuthAudit row in the caller's session (committed by the
caller). It NEVER raises — an audit failure must not break the auth flow.
Standard actions are defined as constants for consistency.
"""

from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import AuthAudit

logger = logging.getLogger(__name__)

LOGIN = "login"
LOGIN_FAILED = "login_failed"
LOGOUT = "logout"
PASSWORD_RESET = "password_reset"
EMAIL_VERIFIED = "email_verified"
TWO_FACTOR_ENABLED = "two_factor_enabled"
# Admin mutations (D5.2/D5.4) — sensitive actions must be traceable.
ACCOUNT_CREATED = "account_created"
ACCOUNT_STATUS_CHANGED = "account_status_changed"
ROLE_ASSIGNED = "role_assigned"
ROLE_REVOKED = "role_revoked"
BRANDING_CHANGED = "branding_changed"


async def record(db: AsyncSession, action: str, *, account_id: str | None = None,
                 ip: str | None = None, ua: str | None = None,
                 detail: dict | None = None) -> None:
    try:
        db.add(AuthAudit(account_id=account_id, action=action, ip_address=ip,
                         user_agent=ua, detail=detail or {}))
        await db.flush()
    except Exception:  # audit must never break the auth flow
        logger.warning("auth audit failed for action=%s", action, exc_info=True)
