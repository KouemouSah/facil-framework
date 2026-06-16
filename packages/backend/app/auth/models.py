"""Credential model — password + TOTP + lockout, 1:1 with Account (D4.2).

Separate from Account so identity (who you are) and credentials (how you prove
it) stay decoupled — a future provider (keycloak/OIDC) may own credentials
externally with no row here.
"""

from __future__ import annotations

import datetime as _dt

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import JSONType, UUIDAuditBase


class Session(UUIDAuditBase):
    """A refresh-token session. The row id IS the refresh token's `jti` claim;
    we store the SHA-256 of the refresh token (never the raw token). Rotation:
    each refresh revokes the current row and mints a new one; presenting an
    already-revoked refresh token (reuse) triggers revocation of the whole
    account's sessions (theft response). Logout = revoke."""

    __tablename__ = "session"

    account_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("account.id", ondelete="CASCADE"), index=True)
    refresh_token_hash: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)
    expires_at: Mapped[_dt.datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[_dt.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True)
    last_used_at: Mapped[_dt.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)

    def as_dict(self) -> dict:
        return {
            "id": self.id, "account_id": self.account_id, "status": self.status,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "revoked_at": self.revoked_at.isoformat() if self.revoked_at else None,
            "last_used_at": self.last_used_at.isoformat() if self.last_used_at else None,
            "ip_address": self.ip_address, "user_agent": self.user_agent,
        }


class Credential(UUIDAuditBase):
    __tablename__ = "credential"

    account_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("account.id", ondelete="CASCADE"),
        unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    # NOTE: TOTP secret should be encrypted at rest (D4.1b brings the AES-GCM
    # helper / verified_identifiers pattern); stored as-is for now.
    # Encrypted at rest (AES-256-GCM, app.security.crypto) — base64, so wider.
    totp_secret: Mapped[str | None] = mapped_column(String(255), nullable=True)
    totp_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # One-time backup codes, stored as SHA-256 hashes (consumed on use).
    totp_backup_codes: Mapped[list] = mapped_column(JSONType, default=list)
    failed_attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    locked_until: Mapped[_dt.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True)
