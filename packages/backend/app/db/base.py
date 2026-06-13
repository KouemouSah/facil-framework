"""SQLAlchemy declarative base + a portable JSON column type.

JSONB on Postgres (production), JSON on SQLite (fast unit tests) — the same
models run against both.
"""

from __future__ import annotations

import datetime as _dt
import uuid

from sqlalchemy import JSON, Boolean, DateTime, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


# Use JSONB on Postgres, fall back to generic JSON elsewhere (SQLite tests).
JSONType = JSONB().with_variant(JSON(), "sqlite")


def uuid_str() -> str:
    return str(uuid.uuid4())


class UUIDAuditBase(Base):
    """Reusable base for module tables: UUID PK (portable as String(36)),
    is_active flag, and created/updated audit columns. Shared by the business
    modules so every table carries the same identity + audit shape."""

    __abstract__ = True

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[_dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[_dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(),
        nullable=False)
    created_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    updated_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
