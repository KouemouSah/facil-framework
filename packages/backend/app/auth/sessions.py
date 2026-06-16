"""Refresh-token sessions — rotation, revocation, reuse detection (D4.5/B1).

The auth *service* owns sessions (it has the DB); the AuthProvider stays a
stateless token mint/verify and only carries a `jti` claim (= the session id).

Security model (refresh-token rotation with reuse detection):
- login -> create a Session (store SHA-256 of the refresh token), embed its id as
  the token `jti`.
- refresh -> verify the refresh JWT, look up its session; if active + matching
  hash + not expired, REVOKE it and mint a fresh session (rotation).
- presenting an already-revoked refresh token (reuse) -> revoke ALL of the
  account's sessions (theft response) and deny.
- logout -> revoke the presented session; logout-all -> revoke every session.
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import inspect

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import Session as SessionModel
from app.db.base import uuid_str


def _now() -> _dt.datetime:
    return _dt.datetime.now(tz=_dt.timezone.utc)


def _aware(dt: _dt.datetime | None) -> _dt.datetime | None:
    if dt is not None and dt.tzinfo is None:
        return dt.replace(tzinfo=_dt.timezone.utc)
    return dt


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


async def open_session(db: AsyncSession, account_id: str, *, auth_provider,
                       claims: dict | None = None, ip: str | None = None,
                       ua: str | None = None, single_session: bool = False) -> dict:
    """Mint access+refresh for a NEW session and persist it. Returns tokens.
    With `single_session`, all other active sessions for the account are revoked
    first (one device at a time — kicks out other logins)."""
    if single_session:
        await revoke_all(db, account_id)
    sid = uuid_str()
    tokens = await auth_provider.issue(account_id, claims, jti=sid)
    ttl = getattr(auth_provider, "_refresh_ttl", 7 * 24 * 3600)
    db.add(SessionModel(
        id=sid, account_id=account_id,
        refresh_token_hash=hash_token(tokens["refresh"]),
        status="active", expires_at=_now() + _dt.timedelta(seconds=int(ttl)),
        last_used_at=_now(), ip_address=ip, user_agent=ua))
    await db.flush()
    return tokens


async def rotate(db: AsyncSession, refresh_token: str, *, auth_provider,
                 claims_for=None, idle_seconds: int | None = None,
                 single_session: bool = False) -> dict | None:
    """Validate + rotate a refresh token. Returns new tokens, or None if invalid.

    Enforces both the ABSOLUTE deadline (session.expires_at) and the optional
    sliding IDLE timeout (`idle_seconds` since last_used_at). `claims_for` rebuilds
    the access-token claims for the new token."""
    payload = await auth_provider.verify(refresh_token, expect="refresh")
    if payload is None:
        return None
    sid = payload.get("jti")
    account_id = payload.get("sub")
    if not sid or not account_id:
        return None
    sess = await db.get(SessionModel, sid)
    if sess is None:
        return None
    if sess.status != "active":
        # Reuse of a ROTATED token is a theft signal -> kill the whole chain.
        # A 'revoked'/'expired' token (logout, single-session kick, idle) is just
        # denied — it must NOT nuke the legitimately-active session.
        if sess.status == "rotated":
            await revoke_all(db, account_id)
        return None
    if hash_token(refresh_token) != sess.refresh_token_hash:
        return None
    if _aware(sess.expires_at) and _aware(sess.expires_at) <= _now():
        sess.status = "expired"
        await db.flush()
        return None
    # Sliding idle timeout: no refresh within the idle window -> session dies.
    if idle_seconds:
        last = _aware(sess.last_used_at) or _aware(sess.created_at)
        if last and (_now() - last).total_seconds() > idle_seconds:
            sess.status = "expired"
            await db.flush()
            return None
    # Rotate: supersede the current session ('rotated' so a later reuse of THIS
    # token is detected as theft), open a fresh one.
    sess.status = "rotated"
    sess.revoked_at = _now()
    sess.last_used_at = _now()
    await db.flush()
    claims = None
    if claims_for is not None:
        claims = claims_for(account_id)
        if inspect.isawaitable(claims):
            claims = await claims
    return await open_session(db, account_id, auth_provider=auth_provider,
                              claims=claims, ip=sess.ip_address, ua=sess.user_agent,
                              single_session=single_session)


async def revoke(db: AsyncSession, refresh_token: str, *, auth_provider) -> bool:
    """Revoke the session behind a refresh token (logout). True if one was revoked."""
    payload = await auth_provider.verify(refresh_token, expect="refresh")
    if payload is None or not payload.get("jti"):
        return False
    sess = await db.get(SessionModel, payload["jti"])
    if sess is None or sess.status != "active":
        return False
    sess.status = "revoked"
    sess.revoked_at = _now()
    await db.flush()
    return True


async def revoke_all(db: AsyncSession, account_id: str) -> int:
    """Revoke every active session for an account (logout-all / theft response)."""
    res = await db.execute(
        update(SessionModel)
        .where(SessionModel.account_id == account_id,
               SessionModel.status == "active")
        .values(status="revoked", revoked_at=_now()))
    await db.flush()
    return res.rowcount or 0


async def active_sessions(db: AsyncSession, account_id: str) -> list[SessionModel]:
    return list((await db.scalars(
        select(SessionModel).where(SessionModel.account_id == account_id,
                                   SessionModel.status == "active")
        .order_by(SessionModel.created_at))).all())
