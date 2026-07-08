"""ProviderRegistry — factory mapping (capability, code) -> provider instance.

Providers register a factory; the registry builds an instance from a config dict,
or resolves the DB-configured default for a capability (provider_settings). The
business layer asks the registry for `get_default('storage', session)` and never
touches a vendor SDK directly.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Callable

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.providers import repository as repo
from app.core.providers.base import Provider

Factory = Callable[[Mapping[str, Any]], Provider]


class ProviderRegistry:
    def __init__(self) -> None:
        self._factories: dict[tuple[str, str], Factory] = {}
        self._schemas: dict[tuple[str, str], list[dict[str, Any]]] = {}

    def register(self, capability: str, code: str, factory: Factory,
                 schema: list[dict[str, Any]] | None = None) -> None:
        self._factories[(capability, code)] = factory
        self._schemas[(capability, code)] = schema or []

    def is_registered(self, capability: str, code: str) -> bool:
        return (capability, code) in self._factories

    @property
    def registered(self) -> list[tuple[str, str]]:
        return sorted(self._factories)

    def schema_keys(self, capability: str, code: str) -> set[str] | None:
        """Declared config keys for a registered type (SEC-F2 allowlist source);
        None if `(capability, code)` isn't registered (no schema to allowlist)."""
        if (capability, code) not in self._factories:
            return None
        return {f["key"] for f in self._schemas.get((capability, code), [])}

    @property
    def registered_detailed(self) -> list[dict[str, Any]]:
        """Instantiable types + their declarative config schema (drives the admin
        UI form; the backend is the single source of truth, no client drift)."""
        return [{"capability": c, "provider_code": k,
                 "config_schema": self._schemas.get((c, k), [])}
                for c, k in self.registered]

    def build(self, capability: str, code: str,
              config: Mapping[str, Any] | None = None) -> Provider:
        factory = self._factories.get((capability, code))
        if factory is None:
            raise KeyError(f"no provider '{code}' registered for capability '{capability}'")
        return factory(config or {})

    async def get_default(self, capability: str, session: AsyncSession) -> Provider:
        row = await repo.get_default(session, capability)
        if row is None:
            raise LookupError(f"no active default provider for capability '{capability}'")
        return self.build(row.capability, row.provider_code, row.config or {})


def default_registry() -> ProviderRegistry:
    """Registry pre-loaded with the built-in providers (factories are lazy —
    nothing connects until a provider is built + used)."""
    from app.core.providers.auth_keycloak_oidc import KeycloakOIDCProvider
    from app.core.providers.auth_native import NativeAuthProvider
    from app.core.providers.email_resend import ResendProvider
    from app.core.providers.email_sendgrid import SendgridProvider
    from app.core.providers.email_smtp import SMTPEmailProvider
    from app.core.providers.llm_ollama import OllamaLLMProvider
    from app.core.providers.llm_openai_compat import OpenAICompatLLMProvider
    from app.core.providers.secrets_aws import AwsSecretsManagerProvider
    from app.core.providers.secrets_env import EnvSecretsProvider
    from app.core.providers.secrets_openbao import OpenBaoSecretsProvider
    from app.core.providers.storage_memory import MemoryStorageProvider
    from app.core.providers.storage_minio import MinIOStorageProvider
    from app.core.providers.storage_s3 import S3StorageProvider

    r = ProviderRegistry()
    r.register("secrets", "env", lambda config: EnvSecretsProvider(config),
               EnvSecretsProvider.config_schema())
    r.register("secrets", "openbao", lambda config: OpenBaoSecretsProvider(config),
               OpenBaoSecretsProvider.config_schema())
    r.register("secrets", "aws_secretsmanager", lambda config: AwsSecretsManagerProvider(config),
               AwsSecretsManagerProvider.config_schema())
    r.register("storage", "minio", lambda config: MinIOStorageProvider(config),
               MinIOStorageProvider.config_schema())
    r.register("storage", "memory", lambda config: MemoryStorageProvider(config),
               MemoryStorageProvider.config_schema())
    r.register("storage", "s3", lambda config: S3StorageProvider(config),
               S3StorageProvider.config_schema())
    r.register("llm", "ollama", lambda config: OllamaLLMProvider(config),
               OllamaLLMProvider.config_schema())
    r.register("llm", "openai_compat", lambda config: OpenAICompatLLMProvider(config),
               OpenAICompatLLMProvider.config_schema())
    r.register("email", "smtp", lambda config: SMTPEmailProvider(config),
               SMTPEmailProvider.config_schema())
    r.register("email", "sendgrid", lambda config: SendgridProvider(config),
               SendgridProvider.config_schema())
    r.register("email", "resend", lambda config: ResendProvider(config),
               ResendProvider.config_schema())
    r.register("auth", "native", lambda config: NativeAuthProvider(config),
               NativeAuthProvider.config_schema())
    r.register("auth", "keycloak_oidc", lambda config: KeycloakOIDCProvider(config),
               KeycloakOIDCProvider.config_schema())
    return r
