"""SQLAlchemy model for accounts (identity core, D4.1).

An Account is the identity record. `account_number` (NIU) is UNIQUE and usable as
a login identifier alongside the optional unique `email`. Credentials (password,
TOTP) live separately and land with the auth provider (D4.2). Multi-tenant:
`organization_id` scopes the account (nullable for system/global accounts).
"""

from __future__ import annotations

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import UUIDAuditBase

ACCOUNT_STATUSES = ("active", "pending", "suspended", "deactivated")


class Account(UUIDAuditBase):
    __tablename__ = "account"

    # NIU — UNIQUE at the data layer (integrity guarantee, not app-enforced).
    account_number: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    # Optional secondary login identifier; UNIQUE allows multiple NULLs.
    email: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)
    organization_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("organization.id", ondelete="SET NULL"),
        nullable=True, index=True)
    display_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="active")

    def as_dict(self) -> dict:
        return {
            "id": self.id, "account_number": self.account_number,
            "email": self.email, "organization_id": self.organization_id,
            "display_name": self.display_name, "status": self.status,
            "is_active": self.is_active,
        }
