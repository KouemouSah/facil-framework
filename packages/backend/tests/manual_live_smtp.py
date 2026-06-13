"""Manual LIVE check — SMTPEmailProvider against a real smtp4dev sink.

Not part of pytest (needs a running smtp4dev). Run after:
  docker compose --profile mail up -d smtp4dev   (or a standalone container)

  cd packages/backend
  PYTHONPATH=. python tests/manual_live_smtp.py

Validated live 2026-06-13 against rnwood/smtp4dev:v3 (host localhost:2525):
healthcheck ok, send True, message captured by the sink.
"""

from __future__ import annotations

import asyncio

from app.core.providers.email_smtp import SMTPEmailProvider


async def main() -> None:
    p = SMTPEmailProvider({"host": "localhost", "port": 2525, "use_tls": False,
                           "from_email": "no-reply@facil.local"})
    print("healthcheck:", await p.healthcheck())
    ok = await p.send("citizen@example.com", "Facil live test",
                      "Hello from SMTPEmailProvider.")
    print("send:", ok)


if __name__ == "__main__":
    asyncio.run(main())
