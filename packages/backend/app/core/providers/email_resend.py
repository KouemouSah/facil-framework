"""ResendProvider — transactional email via the Resend HTTP API.

httpx-only (no SDK). The API key NEVER lives in provider_settings.config: a
caller resolves `api_key_secret` via the SecretsProvider and injects the value as
config['api_key']; RESEND_API_KEY env is the dev fallback. Same injection
contract as the SendGrid / openai_compat providers.

Sending requires either a verified domain or the sandbox sender
`onboarding@resend.dev` (which only delivers to the account owner) — set via
`from_email` / RESEND_FROM_EMAIL.
"""

from __future__ import annotations

import os

import httpx

from app.core.providers.base import EmailProvider

_BASE = "https://api.resend.com"


class ResendProvider(EmailProvider):
    code = "resend"

    def __init__(self, config=None) -> None:
        super().__init__(config)
        self._api_key = (self.config.get("api_key")
                         or os.environ.get("RESEND_API_KEY", ""))
        self._from = (self.config.get("from_email")
                      or os.environ.get("RESEND_FROM_EMAIL", "onboarding@resend.dev"))
        self._from_name = self.config.get("from_name") or "Facil"
        self._timeout = float(self.config.get("timeout_seconds") or 15)
        self._transport = self.config.get("transport")  # test seam only

    def _client(self) -> httpx.AsyncClient:
        headers = {"Authorization": f"Bearer {self._api_key}",
                   "Content-Type": "application/json"}
        return httpx.AsyncClient(timeout=self._timeout, transport=self._transport,
                                 headers=headers)

    def _from_header(self) -> str:
        return f"{self._from_name} <{self._from}>" if self._from_name else self._from

    async def send(self, to: str, subject: str, body: str) -> bool:
        payload = {"from": self._from_header(), "to": [to],
                   "subject": subject, "text": body}
        async with self._client() as client:
            r = await client.post(f"{_BASE}/emails", json=payload)
            r.raise_for_status()
            return r.status_code in (200, 201)

    async def healthcheck(self) -> dict:
        try:
            async with self._client() as client:
                r = await client.get(f"{_BASE}/domains")
            # 200 = key valid (full access); 403 = key valid but scoped (sending
            # only) — both mean the key authenticates. 401 = bad key.
            if r.status_code in (200, 403):
                return {"ok": True, "detail": f"API key authenticates (HTTP {r.status_code})"}
            return {"ok": False, "detail": f"unexpected HTTP {r.status_code}"}
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "detail": f"{type(e).__name__}: {e}"}
