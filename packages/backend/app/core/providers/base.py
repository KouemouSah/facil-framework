"""Provider ABCs — one interface per capability.

Concrete providers (env/openbao secrets, minio/s3 storage, ollama/openai LLM,
smtp/sendgrid email, …) implement these and register with the ProviderRegistry.
The business code depends ONLY on these interfaces, never on a vendor SDK.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping
from typing import Any

# Field types the admin config form understands — now the full FieldSpec
# contract (app.core.schema.types), not the 4-type subset this file used to
# carry. `cfg()` keeps its exact signature: the 13 built-in providers are
# untouched, and their declarations keep working verbatim.
from app.core.schema.spec import field as _field
from app.core.schema.types import LEGACY_TYPE_ALIASES  # noqa: F401  (re-export)

# Legacy provider type names → FieldSpec types.
_CFG_TYPE_MAP = {"text": "string", "boolean": "boolean",
                 "number": "number", "json": "json"}


def cfg(key: str, label: str, *, type: str = "text", required: bool = False,
        default: Any = None, hint: str = "") -> dict[str, Any]:
    """One declarative config field for a provider's admin form. NON-SECRET only —
    credentials travel via `secret_ref` / env and must never be declared here.

    Thin wrapper over `app.core.schema.spec.field()`: providers keep declaring
    `cfg("host", "Host")` and now get a full FieldSpec (widget, rules, i18n label)
    for free. The provider label is English-only today, so it is mirrored into the
    three locales — translating them is a follow-up, not a blocker.
    """
    ftype = _CFG_TYPE_MAP.get(type, type)
    kw: dict[str, Any] = {"required": required, "default": default}
    if ftype in ("select", "multiselect"):
        kw["options"] = []
    return _field(
        key,
        {"en": label, "fr": label, "es": label},
        type=ftype,
        hint={"en": hint, "fr": hint, "es": hint} if hint else {},
        **kw,
    )


class Provider(ABC):
    capability: str = ""
    code: str = ""

    def __init__(self, config: Mapping[str, Any] | None = None) -> None:
        self.config = dict(config or {})

    async def healthcheck(self) -> dict[str, Any]:
        """Lightweight connectivity probe. Override per provider."""
        return {"ok": True, "detail": "no check implemented"}

    @classmethod
    def config_schema(cls) -> list[dict[str, Any]]:
        """Declarative, **non-secret** config fields this provider reads from
        `config` — the single source of truth that drives the admin UI form (no
        client-side drift). Credentials are provided through `secret_ref` / env
        and MUST NOT appear here. Override per concrete provider; default: none."""
        return []


class SecretsProvider(Provider):
    capability = "secrets"

    @abstractmethod
    async def get_secret(self, name: str) -> str | None: ...


class StorageProvider(Provider):
    capability = "storage"

    @abstractmethod
    async def put(self, key: str, data: bytes, *, content_type: str = "") -> str: ...

    @abstractmethod
    async def get(self, key: str) -> bytes: ...

    @abstractmethod
    async def delete(self, key: str) -> None: ...


class LLMProvider(Provider):
    capability = "llm"

    @abstractmethod
    async def chat(self, messages: list[dict], **kw: Any) -> str: ...

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Return one embedding vector per input text. Override in providers
        that serve an embedding model (ollama, openai_compat). Chat-only
        providers (e.g. a managed chat API) may leave this unimplemented."""
        raise NotImplementedError(
            f"{type(self).__name__} does not implement embeddings")


class EmailProvider(Provider):
    capability = "email"

    @abstractmethod
    async def send(self, to: str, subject: str, body: str) -> bool: ...


class AuthProvider(Provider):
    capability = "auth"

    @abstractmethod
    async def issue(self, subject: str, claims: dict | None = None) -> dict:
        """Return {'access': <jwt>, 'refresh': <jwt>} for an authenticated subject."""

    @abstractmethod
    async def verify(self, token: str) -> dict | None:
        """Return the token claims if valid (access token), else None."""

    @abstractmethod
    async def refresh(self, refresh_token: str) -> dict | None:
        """Return a fresh token pair from a valid refresh token, else None."""
