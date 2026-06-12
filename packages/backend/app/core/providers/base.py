"""Provider ABCs — one interface per capability.

Concrete providers (env/openbao secrets, minio/s3 storage, ollama/openai LLM,
smtp/sendgrid email, …) implement these and register with the ProviderRegistry.
The business code depends ONLY on these interfaces, never on a vendor SDK.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping
from typing import Any


class Provider(ABC):
    capability: str = ""
    code: str = ""

    def __init__(self, config: Mapping[str, Any] | None = None) -> None:
        self.config = dict(config or {})

    async def healthcheck(self) -> dict[str, Any]:
        """Lightweight connectivity probe. Override per provider."""
        return {"ok": True, "detail": "no check implemented"}


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


class EmailProvider(Provider):
    capability = "email"

    @abstractmethod
    async def send(self, to: str, subject: str, body: str) -> bool: ...
