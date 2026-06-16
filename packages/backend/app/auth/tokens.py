"""Single-use, hashed, expiring auth tokens — password reset / email verification.

Token model (D4.5/B3): a high-entropy opaque token is generated, its SHA-256 is
stored (never the raw token), and it is consumed once within a TTL. This is the
GitHub/Stripe-style flow — a DB leak cannot replay tokens, and single-use + TTL
bound the window.
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import secrets

from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import AuthToken

PASSWORD_RESET = "password_reset"
EMAIL_VERIFICATION = "email_verification"

# Default TTLs (seconds): reset short-lived, email verification longer.
TTL = {PASSWORD_RESET: 3600, EMAIL_VERIFICATION: 24 * 3600}


def _now() -> _dt.datetime:
    return _dt.datetime.now(tz=_dt.timezone.utc)


def _aware(dt: _dt.datetime | None) -> _dt.datetime | None:
    if dt is not None and dt.tzinfo is None:
        return dt.replace(tzinfo=_dt.timezone.utc)
    return dt


def _hash(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


async def issue(db: AsyncSession, account_id: str, purpose: str,
                *, ttl: int | None = None) -> str:
    """Mint a token for `purpose`, persist its hash, return the RAW token."""
    raw = secrets.token_urlsafe(32)
    ttl = ttl if ttl is not None else TTL.get(purpose, 3600)
    db.add(AuthToken(account_id=account_id, purpose=purpose, token_hash=_hash(raw),
                     expires_at=_now() + _dt.timedelta(seconds=ttl)))
    await db.flush()
    return raw


async def consume(db: AsyncSession, purpose: str, raw: str) -> str | None:
    """Validate + single-use-consume a token. Returns the account_id or None."""
    if not raw:
        return None
    from sqlalchemy import select
    row = await db.scalar(select(AuthToken).where(
        AuthToken.token_hash == _hash(raw), AuthToken.purpose == purpose))
    if row is None or row.used_at is not None:
        return None
    if _aware(row.expires_at) and _aware(row.expires_at) <= _now():
        return None
    row.used_at = _now()
    await db.flush()
    return row.account_id
