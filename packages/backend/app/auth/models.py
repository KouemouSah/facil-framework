"""Credential model — password + TOTP + lockout, 1:1 with Account (D4.2).

Separate from Account so identity (who you are) and credentials (how you prove
it) stay decoupled — a future provider (keycloak/OIDC) may own credentials
externally with no row here.
"""

from __future__ import annotations

import datetime as _dt

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import UUIDAuditBase


class Credential(UUIDAuditBase):
    __tablename__ = "credential"

    account_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("account.id", ondelete="CASCADE"),
        unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    # NOTE: TOTP secret should be encrypted at rest (D4.1b brings the AES-GCM
    # helper / verified_identifiers pattern); stored as-is for now.
    totp_secret: Mapped[str | None] = mapped_column(String(64), nullable=True)
    totp_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    failed_attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    locked_until: Mapped[_dt.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True)
