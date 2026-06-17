"""Per-user saved list views (backlog ERP item 4).

A saved view is a named preset of a table's query state (q / filters / sort) that
a user can re-apply. Scoped to the owning principal via `account_id` (the JWT
`sub`, or a break-glass sentinel) — stored as a plain string (no FK) so the
bootstrap admin can also save views and account deletion never cascades here.
"""

from __future__ import annotations

from sqlalchemy import String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import JSONType, UUIDAuditBase


class SavedView(UUIDAuditBase):
    __tablename__ = "saved_view"
    __table_args__ = (
        UniqueConstraint("account_id", "resource", "name", name="uq_saved_view"),
    )

    account_id: Mapped[str] = mapped_column(String(64), index=True)
    resource: Mapped[str] = mapped_column(String(60), index=True)
    name: Mapped[str] = mapped_column(String(120))
    config: Mapped[dict] = mapped_column(JSONType, default=dict)

    def as_dict(self) -> dict:
        return {"id": self.id, "resource": self.resource, "name": self.name,
                "config": self.config or {}}
