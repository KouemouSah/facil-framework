"""OpenBaoSecretsProvider — reads app secrets from OpenBao via AppRole.

Sovereign secrets provider. Connection + AppRole creds come from the env the
deploy layer renders (OPENBAO_ADDR / OPENBAO_ROLE_ID / OPENBAO_SECRET_ID, from
.bootstrap-state.json). It logs in with the AppRole, reads the configured kv-v2
paths (default facil/boot + facil/runtime) and serves secrets by name.
"""

from __future__ import annotations

import os

import httpx

from app.core.providers.base import SecretsProvider, cfg


class OpenBaoSecretsProvider(SecretsProvider):
    code = "openbao"

    @classmethod
    def config_schema(cls):
        # role_id / secret_id (AppRole creds) come from env, never from config.
        return [
            cfg("addr", "Address", hint="http://openbao:8200"),
            cfg("kv_path", "KV mount path", default="facil"),
            cfg("paths", "Secret paths", type="json", default=["boot", "runtime"],
                hint='e.g. ["boot", "runtime"]'),
        ]

    def __init__(self, config=None) -> None:
        super().__init__(config)
        self._addr = (self.config.get("addr")
                      or os.environ.get("OPENBAO_ADDR", "http://openbao:8200"))
        self._role_id = os.environ.get("OPENBAO_ROLE_ID", "")
        self._secret_id = os.environ.get("OPENBAO_SECRET_ID", "")
        self._kv = self.config.get("kv_path", "facil")
        # Always read the infra path (DATABASE_URL/MinIO SA) on top of whatever is
        # configured, so a row seeded before S1 (paths=[boot,runtime]) still picks
        # up the backend infra creds. De-duplicated, order-preserving.
        configured = self.config.get("paths") or ["boot", "runtime"]
        self._paths = list(dict.fromkeys([*configured, "infra"]))
        self._cache: dict[str, str] | None = None

    async def _login(self, client: httpx.AsyncClient) -> str:
        r = await client.post(
            f"{self._addr}/v1/auth/approle/login",
            json={"role_id": self._role_id, "secret_id": self._secret_id})
        r.raise_for_status()
        return r.json()["auth"]["client_token"]

    async def _load(self) -> dict[str, str]:
        merged: dict[str, str] = {}
        async with httpx.AsyncClient(timeout=10) as client:
            headers = {"X-Vault-Token": await self._login(client)}
            for path in self._paths:
                r = await client.get(f"{self._addr}/v1/{self._kv}/data/{path}",
                                     headers=headers)
                if r.status_code == 200:
                    merged.update(r.json().get("data", {}).get("data", {}))
                elif r.status_code == 403:
                    # Policy gap — surface it (fail-fast) instead of silently
                    # returning a partial set that would mask a misconfiguration.
                    r.raise_for_status()
                # 404 (path not written yet) is tolerated: paths are optional.
        return merged

    async def load_all(self) -> dict[str, str]:
        """All readable secrets (merged across paths), cached after first load."""
        if self._cache is None:
            self._cache = await self._load()
        return dict(self._cache)

    async def get_secret(self, name: str) -> str | None:
        return (await self.load_all()).get(name)

    async def refresh(self) -> None:
        self._cache = None

    async def healthcheck(self) -> dict:
        try:
            data = await self._load()
            return {"ok": True, "detail": f"AppRole login OK, {len(data)} secrets readable"}
        except Exception as e:  # noqa: BLE001
            # Redact: never echo the raw exception (may carry the vault URL/body).
            return {"ok": False, "detail": type(e).__name__}
