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

# Credential-bearing keys that must NEVER live in `config` (plaintext jsonb,
# echoed to `provider.read`). Credentials travel via `secret_ref` / env only.
# Enforced server-side on write (422) and stripped from read responses — the
# secrets discipline is guaranteed at the authority, not just the UI.
# NOTE (SEC-F2, docs/SECURITY_FOLLOWUPS.md): matching below is exact + case-
# sensitive + top-level, so variants (API_KEY, smtp_password, nested) bypass it.
# Durable fix = allowlist config keys to each provider's config_schema(). Deferred.
SECRET_CONFIG_KEYS = frozenset({
    "access_key", "secret_key", "api_key", "password", "secret", "client_secret",
    "role_id", "secret_id", "token", "private_key", "passwd", "pwd",
})


def public_config(config: dict | None) -> dict:
    """A config dict with any secret-bearing key removed (defence in depth for
    legacy/env-injected rows) — used for every API response."""
    return {k: v for k, v in (config or {}).items() if k not in SECRET_CONFIG_KEYS}


def secret_keys_in(config: dict | None) -> set[str]:
    """Secret-bearing keys present in a config dict (empty = clean)."""
    return SECRET_CONFIG_KEYS & set(config or {})


def public_provider_map(value):
    """Strip secret-bearing keys from each entry of a provider map — the
    `ai.providers` settings value (`name -> {kind, endpoint, model,
    api_key_secret, …}`). Same secrets discipline as `public_config`, applied on
    read to the LLM-routing map (defence in depth for legacy/env-seeded rows).
    Credential references like `api_key_secret` are NOT secrets (exact-match
    denylist) and are preserved. Non-dict values pass through unchanged."""
    if not isinstance(value, dict):
        return value
    return {name: (public_config(entry) if isinstance(entry, dict) else entry)
            for name, entry in value.items()}


def provider_map_secret_keys(value) -> set[str]:
    """Secret-bearing keys present in any entry of a provider map (empty = clean).
    Used to reject a plaintext credential in an `ai.providers` write at the
    authority (mirrors `secret_keys_in` for provider rows)."""
    if not isinstance(value, dict):
        return set()
    found: set[str] = set()
    for entry in value.values():
        if isinstance(entry, dict):
            found |= secret_keys_in(entry)
    return found


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
        # NOTE (SEC-F4, docs/SECURITY_FOLLOWUPS.md): returns RAW config. The API
        # must wrap this in _public() (admin_providers.py) to strip secrets; the
        # only caller does today. Deferred: make as_dict() strip + add as_dict_raw().
        return {
            "capability": self.capability, "provider_code": self.provider_code,
            "config": self.config or {}, "secret_ref": self.secret_ref,
            "is_default": self.is_default, "is_active": self.is_active,
            "rate_limit_per_minute": self.rate_limit_per_minute,
            "retry_attempts": self.retry_attempts, "timeout_seconds": self.timeout_seconds,
            "updated_by": self.updated_by,
        }
