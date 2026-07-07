"""SendgridProvider — transactional email via the SendGrid v3 HTTP API.

httpx-only (no SDK). The API key NEVER lives in provider_settings.config: a
caller resolves `api_key_secret` via the SecretsProvider and injects the value
as config['api_key']; SENDGRID_API_KEY env is the dev fallback. Same injection
contract as the openai_compat LLM provider.
"""

from __future__ import annotations

import os

import httpx

from app.core.providers.base import EmailProvider, cfg

_BASE = "https://api.sendgrid.com/v3"


class SendgridProvider(EmailProvider):
    code = "sendgrid"

    @classmethod
    def config_schema(cls):
        # api_key travels via secret_ref/env (SENDGRID_API_KEY), never in config.
        return [
            cfg("from_email", "From address", hint="no-reply@example.com"),
            cfg("from_name", "From name", default="Facil"),
            cfg("timeout_seconds", "Timeout (s)", type="number", default=15),
        ]

    def __init__(self, config=None) -> None:
        super().__init__(config)
        self._api_key = (self.config.get("api_key")
                         or os.environ.get("SENDGRID_API_KEY", ""))
        self._from = (self.config.get("from_email")
                      or os.environ.get("SENDGRID_FROM_EMAIL", ""))
        self._from_name = self.config.get("from_name") or "Facil"
        self._timeout = float(self.config.get("timeout_seconds") or 15)
        self._transport = self.config.get("transport")  # test seam only

    def _client(self) -> httpx.AsyncClient:
        headers = {"Authorization": f"Bearer {self._api_key}",
                   "Content-Type": "application/json"}
        return httpx.AsyncClient(timeout=self._timeout, transport=self._transport,
                                 headers=headers)

    async def send(self, to: str, subject: str, body: str) -> bool:
        payload = {
            "personalizations": [{"to": [{"email": to}]}],
            "from": {"email": self._from, "name": self._from_name},
            "subject": subject,
            "content": [{"type": "text/plain", "value": body}],
        }
        async with self._client() as client:
            r = await client.post(f"{_BASE}/mail/send", json=payload)
            r.raise_for_status()
            return r.status_code in (200, 202)

    async def healthcheck(self) -> dict:
        try:
            async with self._client() as client:
                r = await client.get(f"{_BASE}/scopes")
                r.raise_for_status()
                scopes = r.json().get("scopes", [])
            return {"ok": True, "detail": f"API key valid, {len(scopes)} scope(s)"}
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "detail": f"{type(e).__name__}: {e}"}
