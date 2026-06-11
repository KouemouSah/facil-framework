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

    # Bootstrap admin token gating /admin/* (D1). Replaced by real auth in D4.
    admin_token: str = ""

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
