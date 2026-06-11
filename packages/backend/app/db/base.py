"""SQLAlchemy declarative base + a portable JSON column type.

JSONB on Postgres (production), JSON on SQLite (fast unit tests) — the same
models run against both.
"""

from __future__ import annotations

from sqlalchemy import JSON
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


# Use JSONB on Postgres, fall back to generic JSON elsewhere (SQLite tests).
JSONType = JSONB().with_variant(JSON(), "sqlite")
