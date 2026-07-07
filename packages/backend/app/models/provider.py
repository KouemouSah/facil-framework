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

# Credential-bearing keys that must NEVER live in `config`. The DURABLE control
# (SEC-F2) is an ALLOWLIST: a registered provider's config is restricted to the
# keys it declares in `config_schema()` (enforced in admin_providers on write, and
# used to strip on read) — this closes the case/variant/nested denylist gaps
# structurally. This denylist remains only as the FALLBACK for an UNREGISTERED
# `(capability, code)` where no schema exists to allowlist against.
SECRET_CONFIG_KEYS = frozenset({
    "access_key", "secret_key", "api_key", "password", "secret", "client_secret",
    "role_id", "secret_id", "token", "private_key", "passwd", "pwd",
})

# The `ai.providers` map has a fixed entry shape (no per-entry schema), so it gets
# its own allowlist. `api_key_secret` is a REFERENCE (a secret name), allowed.
AI_PROVIDER_ALLOWED = frozenset({"kind", "endpoint", "model", "api_key_secret"})


def public_config(config: dict | None) -> dict:
    """A config dict with any secret-bearing key removed (defence in depth for
    legacy/env-injected rows) — used for every API response."""
    return {k: v for k, v in (config or {}).items() if k not in SECRET_CONFIG_KEYS}


def secret_keys_in(config: dict | None) -> set[str]:
    """Secret-bearing keys present in a config dict (empty = clean)."""
    return SECRET_CONFIG_KEYS & set(config or {})


def public_provider_map(value):
    """The `ai.providers` map with each entry ALLOWLISTED to `AI_PROVIDER_ALLOWED`
    (kind/endpoint/model/api_key_secret) — any other key (a raw credential or a
    denylist-bypassing variant) is dropped on read. `/llm/routing` is only
    `provider.read`-gated, so it must never echo a plaintext credential a legacy
    row might carry. Non-dict values pass through unchanged."""
    if not isinstance(value, dict):
        return value
    return {name: ({k: v for k, v in entry.items() if k in AI_PROVIDER_ALLOWED}
                   if isinstance(entry, dict) else entry)
            for name, entry in value.items()}


def provider_map_unknown_keys(value) -> set[str]:
    """Entry keys NOT in `AI_PROVIDER_ALLOWED` — used to reject an `ai.providers`
    write carrying a raw credential (e.g. `api_key`) or any unexpected key at the
    authority. Allowlist, so it closes case/variant gaps that a denylist misses."""
    if not isinstance(value, dict):
        return set()
    bad: set[str] = set()
    for entry in value.values():
        if isinstance(entry, dict):
            bad |= (set(entry) - AI_PROVIDER_ALLOWED)
    return bad


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

    def as_dict_raw(self) -> dict:
        """Full row INCLUDING raw `config` (may contain secrets). Internal use only
        (never returned by an endpoint directly — the API strips via the registry
        schema allowlist / `public_config`)."""
        return {
            "capability": self.capability, "provider_code": self.provider_code,
            "config": self.config or {}, "secret_ref": self.secret_ref,
            "is_default": self.is_default, "is_active": self.is_active,
            "rate_limit_per_minute": self.rate_limit_per_minute,
            "retry_attempts": self.retry_attempts, "timeout_seconds": self.timeout_seconds,
            "updated_by": self.updated_by,
        }

    def as_dict(self) -> dict:
        # SEC-F4: strip secret-bearing config keys by default (denylist baseline),
        # so any future caller that returns as_dict() directly can't reopen SEC-001.
        # The providers API strips more strictly (schema allowlist) in _public().
        return {**self.as_dict_raw(), "config": public_config(self.config)}
