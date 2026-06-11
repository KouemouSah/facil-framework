"""The `settings` config-store table — the DB layer of runtime config.

Generalises the legacy TaxasGE `system_rules` table (typed JSON value, i18n
names, effective dates, audit) WITHOUT its domain-specific `rule_category`
constraint. This is the single table D1 owns.
"""

from __future__ import annotations

import datetime as _dt

from sqlalchemy import Boolean, Date, DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, JSONType

VALUE_TYPES = ("string", "number", "boolean", "json")


class Setting(Base):
    __tablename__ = "settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # Dotted key, e.g. "email.provider", "ai.routing.public_chat".
    key: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    value: Mapped[dict | list | str | int | float | bool | None] = mapped_column(JSONType)
    value_type: Mapped[str] = mapped_column(String(20), default="string")
    # Logical grouping (e.g. "ai", "email", "branding") — not a hard constraint.
    scope: Mapped[str] = mapped_column(String(50), default="global", index=True)
    # If the value is a reference to a secret store entry rather than the value.
    secret_ref: Mapped[str] = mapped_column(String(200), default="")

    name_es: Mapped[str | None] = mapped_column(Text, nullable=True)
    name_fr: Mapped[str | None] = mapped_column(Text, nullable=True)
    name_en: Mapped[str | None] = mapped_column(Text, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    effective_from: Mapped[_dt.date | None] = mapped_column(Date, nullable=True)
    effective_until: Mapped[_dt.date | None] = mapped_column(Date, nullable=True)

    updated_by: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[_dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[_dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    def as_dict(self) -> dict:
        return {
            "key": self.key, "value": self.value, "value_type": self.value_type,
            "scope": self.scope, "secret_ref": self.secret_ref,
            "is_active": self.is_active,
            "name": {"es": self.name_es, "fr": self.name_fr, "en": self.name_en},
            "description": self.description, "updated_by": self.updated_by,
        }
