"""SMTPEmailProvider — transactional email over plain SMTP / STARTTLS.

Uses the stdlib `smtplib` wrapped in `asyncio.to_thread` (same pattern as the
MinIO storage provider) so the async API is non-blocking and we add ZERO new
runtime dependency (aiosmtplib avoided on purpose).

Credentials NEVER live in provider_settings.config: a caller (the future email
service) resolves `smtp_password_secret` via the SecretsProvider and injects the
value as config['password']; the SMTP_PASSWORD env is the dev fallback. Host/port
/from come from the DB config (ai-style W6 EmailConfig) or the rendered env.
"""

from __future__ import annotations

import asyncio
import os
import smtplib
from email.message import EmailMessage

from app.core.providers.base import EmailProvider, cfg


class SMTPEmailProvider(EmailProvider):
    code = "smtp"

    @classmethod
    def config_schema(cls):
        # password travels via secret_ref/env (SMTP_PASSWORD), never in config.
        return [
            cfg("host", "SMTP host", required=True, hint="smtp.example.com"),
            cfg("port", "Port", type="number", default=587),
            cfg("username", "Username"),
            cfg("use_tls", "Use STARTTLS", type="boolean", default=True),
            cfg("from_email", "From address", hint="no-reply@example.com"),
            cfg("from_name", "From name", default="Facil"),
            cfg("timeout_seconds", "Timeout (s)", type="number", default=15),
        ]

    def __init__(self, config=None) -> None:
        super().__init__(config)
        self._host = self.config.get("host") or os.environ.get("SMTP_HOST", "")
        self._port = int(self.config.get("port") or os.environ.get("SMTP_PORT", 587))
        self._username = self.config.get("username") or os.environ.get("SMTP_USERNAME", "")
        # Resolved value injected by the caller; env is the dev fallback only.
        self._password = self.config.get("password") or os.environ.get("SMTP_PASSWORD", "")
        self._use_tls = bool(self.config.get("use_tls", True))  # STARTTLS
        self._from = (self.config.get("from_email")
                      or os.environ.get("SMTP_FROM_EMAIL", "no-reply@facil.local"))
        self._from_name = self.config.get("from_name") or "Facil"
        self._timeout = float(self.config.get("timeout_seconds") or 15)

    def _connect(self) -> smtplib.SMTP:
        client = smtplib.SMTP(self._host, self._port, timeout=self._timeout)
        client.ehlo()
        if self._use_tls:
            client.starttls()
            client.ehlo()
        if self._username:
            client.login(self._username, self._password)
        return client

    async def send(self, to: str, subject: str, body: str) -> bool:
        def _send() -> bool:
            msg = EmailMessage()
            msg["From"] = f"{self._from_name} <{self._from}>"
            msg["To"] = to
            msg["Subject"] = subject
            msg.set_content(body)
            client = self._connect()
            try:
                client.send_message(msg)
            finally:
                client.quit()
            return True
        return await asyncio.to_thread(_send)

    async def healthcheck(self) -> dict:
        def _check() -> dict:
            try:
                client = self._connect()
                try:
                    client.noop()
                finally:
                    client.quit()
                tls = "STARTTLS" if self._use_tls else "plain"
                return {"ok": True,
                        "detail": f"SMTP {self._host}:{self._port} reachable ({tls})"}
            except Exception as e:  # noqa: BLE001
                return {"ok": False, "detail": f"{type(e).__name__}: {e}"}
        return await asyncio.to_thread(_check)
