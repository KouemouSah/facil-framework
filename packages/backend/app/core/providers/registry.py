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

    def register(self, capability: str, code: str, factory: Factory) -> None:
        self._factories[(capability, code)] = factory

    def is_registered(self, capability: str, code: str) -> bool:
        return (capability, code) in self._factories

    @property
    def registered(self) -> list[tuple[str, str]]:
        return sorted(self._factories)

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
    from app.core.providers.secrets_env import EnvSecretsProvider
    from app.core.providers.secrets_openbao import OpenBaoSecretsProvider
    from app.core.providers.storage_minio import MinIOStorageProvider

    r = ProviderRegistry()
    r.register("secrets", "env", lambda config: EnvSecretsProvider(config))
    r.register("secrets", "openbao", lambda config: OpenBaoSecretsProvider(config))
    r.register("storage", "minio", lambda config: MinIOStorageProvider(config))
    r.register("llm", "ollama", lambda config: OllamaLLMProvider(config))
    r.register("llm", "openai_compat", lambda config: OpenAICompatLLMProvider(config))
    r.register("email", "smtp", lambda config: SMTPEmailProvider(config))
    r.register("email", "sendgrid", lambda config: SendgridProvider(config))
    r.register("email", "resend", lambda config: ResendProvider(config))
    r.register("auth", "native", lambda config: NativeAuthProvider(config))
    r.register("auth", "keycloak_oidc", lambda config: KeycloakOIDCProvider(config))
    return r
