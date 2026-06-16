"""Credential model — password + TOTP + lockout, 1:1 with Account (D4.2).

Separate from Account so identity (who you are) and credentials (how you prove
it) stay decoupled — a future provider (keycloak/OIDC) may own credentials
externally with no row here.
"""

from __future__ import annotations

import datetime as _dt

from sqlalchemy import (Boolean, DateTime, ForeignKey, Integer, String, Text,
                        UniqueConstraint)
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


class FederatedIdentity(UUIDAuditBase):
    """Links a local account to an external IdP subject (D4.7). The canonical,
    immutable key is (provider, subject) — e.g. ('keycloak', <kc-user-uuid>).
    Keycloak federates LDAP/AD and brokers SAML upstream, so a single OIDC link
    covers all of them. Email is NEVER the link key (takeover risk)."""

    __tablename__ = "federated_identity"
    __table_args__ = (
        UniqueConstraint("provider", "subject", name="uq_federated_provider_subject"),
    )

    account_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("account.id", ondelete="CASCADE"), index=True)
    provider: Mapped[str] = mapped_column(String(40), index=True)
    subject: Mapped[str] = mapped_column(String(255), index=True)


class AuthToken(UUIDAuditBase):
    """Single-use, hashed, expiring token for password reset / email verification
    (D4.5/B3). Only the SHA-256 of the token is stored; the raw token is mailed to
    the user. `used_at` enforces single use; `expires_at` enforces the TTL."""

    __tablename__ = "auth_token"

    account_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("account.id", ondelete="CASCADE"), index=True)
    purpose: Mapped[str] = mapped_column(String(40), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), index=True)
    expires_at: Mapped[_dt.datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[_dt.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True)


class AuthAudit(UUIDAuditBase):
    """Append-only audit of auth events (D4.5/B4): login (success/failure),
    logout, password reset, email verification, 2FA changes. `account_id` is
    nullable (a failed login by unknown identifier has none — anti-enumeration)."""

    __tablename__ = "auth_audit"

    account_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    action: Mapped[str] = mapped_column(String(60), index=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)
    detail: Mapped[dict] = mapped_column(JSONType, default=dict)


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
