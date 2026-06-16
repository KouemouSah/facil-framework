"""Backend settings (Pydantic) — the FILE/ENV layer of the config resolver.

This is the *bootstrap* configuration the app needs to start (DB URL, admin
token). Runtime application config lives in the DB `settings` table and is read
through the resolver (defaults -> config.yaml -> DB -> env). Kept intentionally
small for D1.
"""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    environment: str = "development"

    # SQLAlchemy async URL. The deploy layer emits DATABASE_URL as
    # postgresql://… (libpq form); we normalise it to the asyncpg driver.
    database_url: str = (
        "postgresql+asyncpg://facil_app:changeme@localhost:5432/facil"
    )

    # Bootstrap admin token gating /admin/* (D1). Break-glass — bypasses RBAC.
    # Hardened (D4.9): optional expiry (ISO8601, empty = none) + IP allowlist
    # (CSV, empty = any). Use is always audited. Disable by leaving admin_token
    # empty once real RBAC admins exist.
    admin_token: str = ""
    admin_token_expires_at: str = ""
    admin_token_allowed_ips: str = ""

    # Session policy (D4.11). Sliding idle timeout (no refresh within the window
    # => the session is disconnected; the client gets a 401 and re-authenticates).
    # Agents are stricter (30 min) than ordinary users (1 h); 0 disables.
    session_idle_seconds: int = 3600          # ordinary users — 1 h
    session_idle_seconds_agent: int = 1800    # agents — 30 min
    # One active device per account (new login revokes the rest). Agents are
    # ALWAYS single-session; this flag also forces it for everyone else.
    auth_single_session: bool = False

    def idle_seconds_for(self, subject_type: str | None) -> int:
        return self.session_idle_seconds_agent if subject_type == "agent" \
            else self.session_idle_seconds

    def single_session_for(self, subject_type: str | None) -> bool:
        return self.auth_single_session or subject_type == "agent"

    @property
    def async_database_url(self) -> str:
        url = self.database_url
        if url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        elif url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql+asyncpg://", 1)
        return url


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
