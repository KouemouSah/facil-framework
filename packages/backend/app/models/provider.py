"""`provider_settings` — the runtime provider registry table.

Generalises the legacy `communication_provider_settings` (encrypted creds,
config jsonb, is_default/is_active, rate-limit/retry/timeout) from the single
"communication" scope to ANY capability: storage / llm / email / secrets / auth /
payment. The admin selects + configures providers here at runtime; the
ProviderRegistry instantiates them.
"""

from __future__ import annotations

import datetime as _dt

from sqlalchemy import (
    Boolean, DateTime, Integer, String, UniqueConstraint, func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, JSONType

CAPABILITIES = ("storage", "llm", "email", "secrets", "auth", "payment")


class ProviderSetting(Base):
    __tablename__ = "provider_settings"
    __table_args__ = (
        UniqueConstraint("capability", "provider_code", name="uq_provider_cap_code"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    capability: Mapped[str] = mapped_column(String(20), index=True)
    provider_code: Mapped[str] = mapped_column(String(50))
    # Non-secret provider config (endpoint, model, bucket, region, …).
    config: Mapped[dict] = mapped_column(JSONType, default=dict)
    # Reference to the secret store for credentials (NOT the secret itself).
    secret_ref: Mapped[str] = mapped_column(String(200), default="")

    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    rate_limit_per_minute: Mapped[int] = mapped_column(Integer, default=0)
    retry_attempts: Mapped[int] = mapped_column(Integer, default=3)
    timeout_seconds: Mapped[int] = mapped_column(Integer, default=30)

    updated_by: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[_dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[_dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    def as_dict(self) -> dict:
        return {
            "capability": self.capability, "provider_code": self.provider_code,
            "config": self.config or {}, "secret_ref": self.secret_ref,
            "is_default": self.is_default, "is_active": self.is_active,
            "rate_limit_per_minute": self.rate_limit_per_minute,
            "retry_attempts": self.retry_attempts, "timeout_seconds": self.timeout_seconds,
            "updated_by": self.updated_by,
        }
