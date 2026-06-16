"""SQLAlchemy model for accounts (identity core, D4.1).

An Account is the identity record. `account_number` (NIU) is UNIQUE and usable as
a login identifier alongside the optional unique `email`. It is **nullable**: under
the `on_verified_document` issuance policy the NIU is minted only after the
identity document is verified (status pending_identity -> active); under
`immediate` it is minted at registration. `subject_type` (national / foreigner /
entity …) is the authoritative, mutable category (the NIU prefix reflects it at
issuance and is immutable). Credentials (password, TOTP) land with D4.2.
"""

from __future__ import annotations

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import UUIDAuditBase

ACCOUNT_STATUSES = ("pending_identity", "active", "suspended", "deactivated")


class Account(UUIDAuditBase):
    __tablename__ = "account"

    # NIU — UNIQUE at the data layer; NULL until issued (gated policy).
    account_number: Mapped[str | None] = mapped_column(
        String(40), unique=True, index=True, nullable=True)
    # Optional secondary login identifier; UNIQUE allows multiple NULLs.
    email: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)
    organization_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("organization.id", ondelete="SET NULL"),
        nullable=True, index=True)
    display_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Authoritative category (national/foreigner/entity); configurable values.
    subject_type: Mapped[str | None] = mapped_column(String(20), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="pending_identity")

    def as_dict(self) -> dict:
        return {
            "id": self.id, "account_number": self.account_number,
            "email": self.email, "organization_id": self.organization_id,
            "display_name": self.display_name, "subject_type": self.subject_type,
            "status": self.status, "is_active": self.is_active,
        }
