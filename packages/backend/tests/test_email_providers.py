"""Email providers — SMTP (fake smtplib) + SendGrid (httpx MockTransport)."""

from __future__ import annotations

import smtplib

import httpx
import pytest

from app.core.providers.email_sendgrid import SendgridProvider
from app.core.providers.email_smtp import SMTPEmailProvider
from app.core.providers.registry import default_registry


class FakeSMTP:
    """Records the SMTP conversation; one instance per _connect()."""
    instances: list["FakeSMTP"] = []

    def __init__(self, host, port, timeout=None):
        self.host, self.port = host, port
        self.calls: list = []
        self.sent: list = []
        self.fail_on_connect = host == "unreachable.invalid"
        if self.fail_on_connect:
            raise OSError("connection refused")
        FakeSMTP.instances.append(self)

    def ehlo(self): self.calls.append("ehlo")
    def starttls(self): self.calls.append("starttls")
    def login(self, u, p): self.calls.append(("login", u, p))
    def send_message(self, msg): self.sent.append(msg)
    def noop(self): self.calls.append("noop")
    def quit(self): self.calls.append("quit")


@pytest.fixture
def fake_smtp(monkeypatch):
    FakeSMTP.instances = []
    monkeypatch.setattr(smtplib, "SMTP", FakeSMTP)
    return FakeSMTP


@pytest.mark.asyncio
async def test_smtp_send_starttls_and_login(fake_smtp):
    p = SMTPEmailProvider({"host": "smtp.local", "port": 587, "use_tls": True,
                           "username": "u", "password": "pw",
                           "from_email": "no-reply@facil.local"})
    assert await p.send("dest@example.com", "Hi", "Body") is True
    inst = fake_smtp.instances[-1]
    assert "starttls" in inst.calls
    assert ("login", "u", "pw") in inst.calls
    assert inst.sent[0]["To"] == "dest@example.com"
    assert inst.sent[0]["Subject"] == "Hi"


@pytest.mark.asyncio
async def test_smtp_no_tls_no_login(fake_smtp):
    p = SMTPEmailProvider({"host": "smtp4dev", "port": 25, "use_tls": False})
    await p.send("a@b.c", "s", "b")
    inst = fake_smtp.instances[-1]
    assert "starttls" not in inst.calls
    assert not any(isinstance(c, tuple) and c[0] == "login" for c in inst.calls)


@pytest.mark.asyncio
async def test_smtp_healthcheck_ok(fake_smtp):
    p = SMTPEmailProvider({"host": "smtp4dev", "port": 25, "use_tls": False})
    res = await p.healthcheck()
    assert res["ok"] is True and "reachable" in res["detail"]


@pytest.mark.asyncio
async def test_smtp_healthcheck_unreachable(fake_smtp):
    p = SMTPEmailProvider({"host": "unreachable.invalid", "port": 25})
    res = await p.healthcheck()
    assert res["ok"] is False


# --- SendGrid ------------------------------------------------------------

def _sg_handler(captured: dict):
    def handler(request: httpx.Request) -> httpx.Response:
        captured["auth"] = request.headers.get("authorization")
        if request.url.path == "/v3/mail/send":
            import json
            captured["payload"] = json.loads(request.content)
            return httpx.Response(202)
        if request.url.path == "/v3/scopes":
            return httpx.Response(200, json={"scopes": ["mail.send"]})
        return httpx.Response(404)
    return handler


def _sg(captured, **cfg) -> SendgridProvider:
    base = {"api_key": "SG.test", "from_email": "no-reply@facil.io",
            "transport": httpx.MockTransport(_sg_handler(captured))}
    base.update(cfg)
    return SendgridProvider(base)


@pytest.mark.asyncio
async def test_sendgrid_send():
    cap: dict = {}
    assert await _sg(cap).send("dest@example.com", "Subj", "Hello") is True
    assert cap["auth"] == "Bearer SG.test"
    assert cap["payload"]["personalizations"][0]["to"][0]["email"] == "dest@example.com"
    assert cap["payload"]["subject"] == "Subj"


@pytest.mark.asyncio
async def test_sendgrid_healthcheck():
    cap: dict = {}
    res = await _sg(cap).healthcheck()
    assert res["ok"] is True and "scope" in res["detail"]


@pytest.mark.asyncio
async def test_sendgrid_healthcheck_bad_key():
    def handler(request):
        return httpx.Response(401)
    p = SendgridProvider({"api_key": "bad", "transport": httpx.MockTransport(handler)})
    res = await p.healthcheck()
    assert res["ok"] is False


def test_email_providers_registered():
    reg = default_registry()
    assert reg.is_registered("email", "smtp")
    assert reg.is_registered("email", "sendgrid")
