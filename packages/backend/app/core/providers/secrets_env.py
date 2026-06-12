"""EnvSecretsProvider — reads secrets from the process environment.

A fully-real provider (the sovereign default for dev / env_file deployments).
OpenBao / cloud secret-manager providers implement the same SecretsProvider ABC
and consume the AppRole / managed creds; they land as their backing is wired.
"""

from __future__ import annotations

import os

from app.core.providers.base import SecretsProvider


class EnvSecretsProvider(SecretsProvider):
    code = "env"

    async def get_secret(self, name: str) -> str | None:
        return os.environ.get(name) or None
